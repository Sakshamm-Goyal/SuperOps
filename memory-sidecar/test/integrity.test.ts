// CONTRACT + adverse-case tests: provider outage, corrupt state, unscoped engine records,
// embedding profile change/reindex, and hash_conformance labelling.

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { HMEM } from "../vendor/hmem/src/index.ts";
import {
  contractEnv,
  recallBody,
  rememberBody,
  snapshotFiles,
  startFakeEmbedder,
  startSidecar,
  tempDataDir,
} from "./helpers.ts";
import type { Sidecar } from "./helpers.ts";

test("CONTRACT: embedding provider down -> 503 MEMORY_EMBEDDING_UNAVAILABLE and nothing persisted", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  const sc = await startSidecar(contractEnv(dir, fake));
  try {
    assert.equal((await sc.req("POST", "/memory/remember", rememberBody())).status, 201);
    const before = snapshotFiles(dir);
    fake.setFailing(true);
    const body = rememberBody({ finding: "This finding must never be written while the provider is down" });
    const res = await sc.req("POST", "/memory/remember", body);
    assert.equal(res.status, 503);
    assert.equal(res.body.error.code, "MEMORY_EMBEDDING_UNAVAILABLE");
    const recall = await sc.req("POST", "/memory/recall", recallBody());
    assert.equal(recall.status, 503);
    assert.equal(recall.body.error.code, "MEMORY_EMBEDDING_UNAVAILABLE");
    assert.deepEqual(snapshotFiles(dir), before, "state.json, ledger.jsonl and index unchanged");
    assert.equal(JSON.stringify(snapshotFiles(dir)).includes("must never be written"), false);

    // Provider fully unreachable (connection refused), not just HTTP 503.
    await fake.close();
    const down = await sc.req("POST", "/memory/remember", body);
    assert.equal(down.status, 503);
    assert.equal(down.body.error.code, "MEMORY_EMBEDDING_UNAVAILABLE");
    assert.deepEqual(snapshotFiles(dir), before);
  } finally {
    await sc.stop();
    await fake.close().catch(() => undefined);
  }
});

test("CONTRACT: malformed provider responses are rejected (finite, length, order, norm, dimension)", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  const sc = await startSidecar(contractEnv(dir, fake));
  try {
    assert.equal((await sc.req("POST", "/memory/remember", rememberBody())).status, 201);
    const before = snapshotFiles(dir);
    for (const mode of ["nan", "short", "zero", "misorder", "dims", "notjson"] as const) {
      fake.setMode(mode);
      const r = await sc.req("POST", "/memory/remember", rememberBody());
      assert.equal(r.status, 503, mode);
      assert.equal(r.body.error.code, "MEMORY_EMBEDDING_UNAVAILABLE", mode);
    }
    assert.deepEqual(snapshotFiles(dir), before);
  } finally {
    await sc.stop();
    await fake.close();
  }
});

test("CONTRACT: corrupt state.json -> health unavailable MEMORY_STATE_CORRUPT, files untouched", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  let sc = await startSidecar(contractEnv(dir, fake));
  assert.equal((await sc.req("POST", "/memory/remember", rememberBody())).status, 201);
  assert.equal(await sc.stop(), 0);

  fs.writeFileSync(path.join(dir, "state.json"), '{"seq": 1, "records": [ {"id": "mem-1", "content"');
  const before = snapshotFiles(dir);
  sc = await startSidecar(contractEnv(dir, fake));
  try {
    const health = await sc.req("GET", "/health");
    assert.equal(health.status, 503);
    assert.equal(health.body.status, "unavailable");
    assert.deepEqual(health.body.reasons, ["MEMORY_STATE_CORRUPT"]);
    for (const [method, p, body] of [
      ["POST", "/memory/remember", rememberBody()],
      ["POST", "/memory/recall", recallBody()],
      ["POST", "/memory/reindex", {}],
    ] as const) {
      const r = await sc.req(method, p, body);
      assert.equal(r.status, 503, p);
      assert.equal(r.body.error.code, "MEMORY_STATE_CORRUPT");
    }
    const audit = await sc.req("GET", `/memory/audit/${rememberBody().application_receipt_id}?tenant_id=tenant-a&service_id=checkout`);
    assert.equal(audit.status, 503);
  } finally {
    await sc.stop();
    await fake.close();
  }
  assert.deepEqual(snapshotFiles(dir), before, "corrupt files never reset or overwritten");
});

test("CONTRACT: corrupt ledger.jsonl and corrupt index are also detected without writes", async () => {
  const fake = await startFakeEmbedder(32);
  for (const victim of ["ledger.jsonl", "greenops-index.json"]) {
    const dir = tempDataDir();
    let sc = await startSidecar(contractEnv(dir, fake));
    assert.equal((await sc.req("POST", "/memory/remember", rememberBody())).status, 201);
    await sc.stop();
    fs.appendFileSync(path.join(dir, victim), "{truncated");
    const before = snapshotFiles(dir);
    sc = await startSidecar(contractEnv(dir, fake));
    const health = await sc.req("GET", "/health");
    assert.equal(health.body.status, "unavailable", victim);
    assert.deepEqual(health.body.reasons, ["MEMORY_STATE_CORRUPT"]);
    await sc.stop();
    assert.deepEqual(snapshotFiles(dir), before);
  }
  await fake.close();
});

test("CONTRACT: unscoped engine record is excluded before ranking and counted", async () => {
  const dir = tempDataDir();
  // Written directly through a separate engine instance, bypassing the wrapper's index.
  const direct = new HMEM({ persistDir: dir });
  const stray = direct.add({
    content: "Unscoped stray memory: rightsizing checkout-api to m5.large failed the latency trial",
    source: "manual-import",
    layer: "long_term",
  });
  const fake = await startFakeEmbedder(32);
  const sc = await startSidecar(contractEnv(dir, fake));
  try {
    const health = await sc.req("GET", "/health");
    assert.equal(health.body.status, "degraded");
    assert.deepEqual(health.body.reasons, ["INDEX_ENGINE_MISMATCH"]);
    assert.equal(health.body.store.unindexed_engine_records, 1);
    assert.equal(health.body.store.reconcilable_orphans, 0, "non-receipt source is not adoptable");

    const mine = rememberBody();
    assert.equal((await sc.req("POST", "/memory/remember", mine)).status, 201);
    const res = await sc.req("POST", "/memory/recall", recallBody({ threshold: 0, top_k: 10 }));
    assert.equal(res.status, 200);
    assert.equal(res.body.excluded_unscoped, 1);
    const ids = [...res.body.items, ...res.body.historical].map((i: any) => i.engine_memory_id);
    assert.ok(ids.includes((await sc.req("POST", "/memory/remember", mine)).body.engine_memory_id));
    assert.equal(ids.includes(stray.id), false);
    assert.equal(stray.id in res.body.trace.scores, false, "stray record never scored");
    assert.equal(JSON.stringify(res.body).includes("Unscoped stray"), false);
  } finally {
    await sc.stop();
    await fake.close();
  }
});

test("CONTRACT: crash orphan (engine written, index not) is adopted on retry; exactly one engine record", async () => {
  const dir = tempDataDir();
  const body = rememberBody({ finding: "Orphaned finding: cache node downsizing for checkout passed the soak test" });
  // Simulate a crash between the engine write and the index write: a separate engine
  // instance writes the record with the receipt source; no greenops-index.json exists.
  const direct = new HMEM({ persistDir: dir });
  const orphan = direct.add({
    content: body.finding,
    source: `greenops:receipt:${body.application_receipt_id}`,
    type: "factual",
    layer: "long_term",
    confidence: 0.9,
  });
  assert.equal(fs.existsSync(path.join(dir, "greenops-index.json")), false);

  const fake = await startFakeEmbedder(32);
  const sc = await startSidecar(contractEnv(dir, fake));
  try {
    const health = await sc.req("GET", "/health");
    assert.equal(health.body.status, "degraded");
    assert.deepEqual(health.body.reasons, ["INDEX_ENGINE_MISMATCH"]);
    assert.equal(health.body.store.reconcilable_orphans, 1);
    assert.match(sc.stdout(), /"event":"memory_reconcilable_orphans"/);

    const res = await sc.req("POST", "/memory/remember", body);
    assert.equal(res.status, 201);
    assert.equal(res.body.duplicate, true);
    assert.equal(res.body.reconciled, true);
    assert.equal(res.body.engine_memory_id, orphan.id);

    const state = JSON.parse(fs.readFileSync(path.join(dir, "state.json"), "utf-8"));
    const matching = state.records.filter((r: any) => r.source === `greenops:receipt:${body.application_receipt_id}`);
    assert.equal(matching.length, 1, "exactly one engine record for the receipt");
    assert.equal(state.records.length, 1);
    assert.equal(matching[0].embedding.length, 32, "adopted record re-embedded with the configured provider");
    const index = JSON.parse(fs.readFileSync(path.join(dir, "greenops-index.json"), "utf-8"));
    assert.equal(index.receipts[body.application_receipt_id].engine_memory_id, orphan.id);

    const after = await sc.req("GET", "/health");
    assert.equal(after.body.status, "ready");
    assert.equal(after.body.store.reconcilable_orphans, 0);

    const again = await sc.req("POST", "/memory/remember", body);
    assert.equal(again.status, 200);
    assert.equal(again.body.duplicate, true);
    assert.equal(again.body.engine_memory_id, orphan.id);
    assert.equal("reconciled" in again.body, false);

    const recall = await sc.req("POST", "/memory/recall", recallBody({ query: "cache node downsizing checkout soak" }));
    assert.equal(recall.body.items[0].engine_memory_id, orphan.id);
    assert.equal(recall.body.excluded_unscoped, 0);
  } finally {
    await sc.stop();
    await fake.close();
  }
});

test("CONTRACT: crash orphan with different content -> 409 ORPHAN_CONFLICT, nothing written", async () => {
  const dir = tempDataDir();
  const body = rememberBody();
  const direct = new HMEM({ persistDir: dir });
  direct.add({ content: "Different content than the retried finding", source: `greenops:receipt:${body.application_receipt_id}` });
  const fake = await startFakeEmbedder(32);
  const sc = await startSidecar(contractEnv(dir, fake));
  try {
    const before = snapshotFiles(dir);
    const res = await sc.req("POST", "/memory/remember", body);
    assert.equal(res.status, 409);
    assert.equal(res.body.error.code, "ORPHAN_CONFLICT");
    assert.deepEqual(snapshotFiles(dir), before);
    assert.equal((await sc.req("GET", "/health")).body.store.records, 1);
  } finally {
    await sc.stop();
    await fake.close();
  }
});

test("CONTRACT: embedding profile change -> degraded + MEMORY_NOT_READY until reindex", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  let sc = await startSidecar(contractEnv(dir, fake, "fake-model-a"));
  const body = rememberBody();
  const created = await sc.req("POST", "/memory/remember", body);
  assert.equal(created.status, 201);
  const oldHash = created.body.embedding_profile.profile_hash;
  await sc.stop();

  sc = await startSidecar(contractEnv(dir, fake, "fake-model-b"));
  try {
    const health = await sc.req("GET", "/health");
    assert.equal(health.status, 503);
    assert.equal(health.body.status, "degraded");
    assert.deepEqual(health.body.reasons, ["EMBEDDING_PROFILE_MISMATCH"]);
    assert.equal(health.body.stored_embedding_profile.model_id, "fake-model-a");
    for (const [p, b] of [["/memory/recall", recallBody()], ["/memory/remember", rememberBody()]] as const) {
      const r = await sc.req("POST", p, b);
      assert.equal(r.status, 503);
      assert.equal(r.body.error.code, "MEMORY_NOT_READY");
    }
    const audit = await sc.req("GET", `/memory/audit/${body.application_receipt_id}?tenant_id=tenant-a&service_id=checkout`);
    assert.equal(audit.status, 200, "audit stays available while degraded");

    const reindex = await sc.req("POST", "/memory/reindex", {});
    assert.equal(reindex.status, 200);
    assert.equal(reindex.body.reindexed, 1);
    assert.equal(reindex.body.embedding_profile.model_id, "fake-model-b");
    assert.notEqual(reindex.body.embedding_profile.profile_hash, oldHash);
    const ready = await sc.req("GET", "/health");
    assert.equal(ready.body.status, "ready");
    const recall = await sc.req("POST", "/memory/recall", recallBody());
    assert.equal(recall.status, 200);
    assert.equal(recall.body.items[0].engine_memory_id, created.body.engine_memory_id);
  } finally {
    await sc.stop();
  }
  // The new profile is durable across restart.
  sc = await startSidecar(contractEnv(dir, fake, "fake-model-b"));
  assert.equal((await sc.req("GET", "/health")).body.status, "ready");
  await sc.stop();
  await fake.close();
});

test("CONFORMANCE: hash_conformance mode works deterministically and is labelled semantic:false", async () => {
  const dir = tempDataDir();
  const sc = await startSidecar({ HMEM_DATA_DIR: dir, EMBEDDING_MODE: "hash_conformance" });
  try {
    const health = await sc.req("GET", "/health");
    assert.equal(health.body.embedding_profile.kind, "hash_conformance");
    assert.equal(health.body.embedding_profile.semantic, false);
    assert.equal(health.body.embedding_profile.dimensions, 64);
    const created = await sc.req("POST", "/memory/remember", rememberBody());
    assert.equal(created.status, 201);
    assert.equal(created.body.embedding_profile.semantic, false);
    const recall = await sc.req("POST", "/memory/recall", recallBody());
    assert.equal(recall.status, 200);
    assert.equal(recall.body.embedding_profile.semantic, false);
    assert.equal(recall.body.items[0].engine_memory_id, created.body.engine_memory_id);
  } finally {
    await sc.stop();
  }
});

test("CONFIG: missing auth token, data dir or embedding mode exits 1", async () => {
  const dir = tempDataDir();
  for (const env of [
    { MEMORY_AUTH_TOKEN: "", HMEM_DATA_DIR: dir, EMBEDDING_MODE: "hash_conformance" },
    { HMEM_DATA_DIR: "", EMBEDDING_MODE: "hash_conformance" },
    { HMEM_DATA_DIR: dir, EMBEDDING_MODE: "" },
    { HMEM_DATA_DIR: dir, EMBEDDING_MODE: "nvidia" },
  ]) {
    await assert.rejects(startSidecar(env), /sidecar exited 1/);
  }
});

// A11 (audit 2026-10-17): an index entry whose engine record was removed from state.json must
// never be acknowledged as persisted. A same-hash retry re-creates the record; a different
// hash is refused with nothing written.
function dropEngineRecords(dir: string, engineIds: string[]): void {
  const sf = path.join(dir, "state.json");
  const state = JSON.parse(fs.readFileSync(sf, "utf-8"));
  state.records = state.records.filter((r: any) => !engineIds.includes(r.id));
  fs.writeFileSync(sf, JSON.stringify(state));
}

function readState(dir: string): any {
  return JSON.parse(fs.readFileSync(path.join(dir, "state.json"), "utf-8"));
}

function readIndex(dir: string): any {
  return JSON.parse(fs.readFileSync(path.join(dir, "greenops-index.json"), "utf-8"));
}

test("CONTRACT A11: missing engine record behind an index entry is reconciled on same-hash retry, never falsely acknowledged", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  const body = rememberBody({ finding: "Missing-record finding: queue worker downsizing for checkout failed the backlog trial" });
  let sc: Sidecar | null = null;
  try {
    sc = await startSidecar(contractEnv(dir, fake));
    const first = await sc.req("POST", "/memory/remember", body);
    assert.equal(first.status, 201);
    await sc.stop();

    dropEngineRecords(dir, [first.body.engine_memory_id]);
    assert.equal(readIndex(dir).receipts[body.application_receipt_id].engine_memory_id, first.body.engine_memory_id);

    sc = await startSidecar(contractEnv(dir, fake));
    const health = await sc.req("GET", "/health");
    assert.equal(health.status, 503);
    assert.equal(health.body.status, "degraded");
    assert.deepEqual(health.body.reasons, ["INDEX_ENGINE_MISMATCH", "ENGINE_RECORD_MISSING"]);
    assert.equal(health.body.store.missing_engine_records, 1);
    assert.deepEqual(health.body.store.missing_engine_receipt_ids, [body.application_receipt_id]);
    assert.match(sc.stdout(), /"event":"memory_missing_engine_records"/);

    // Different hash for the same receipt: refused, nothing written.
    const before = snapshotFiles(dir);
    const conflicting = await sc.req("POST", "/memory/remember", { ...body, content_hash: `sha256:${"0".repeat(64)}` });
    assert.equal(conflicting.status, 409);
    assert.equal(conflicting.body.error.code, "IDEMPOTENCY_CONFLICT");
    assert.notEqual(conflicting.body.persisted, true);
    assert.deepEqual(snapshotFiles(dir), before, "conflicting retry writes nothing");

    // Same hash: the engine record is re-created and the index re-pointed.
    const retry = await sc.req("POST", "/memory/remember", body);
    assert.equal(retry.status, 201);
    assert.equal(retry.body.persisted, true);
    assert.equal(retry.body.duplicate, true);
    assert.equal(retry.body.reconciled, true);
    assert.notEqual(retry.body.engine_memory_id, first.body.engine_memory_id);
    assert.equal(retry.body.stored_at, first.body.stored_at, "original receipt time is kept");

    const state = readState(dir);
    const matching = state.records.filter((r: any) => r.source === `greenops:receipt:${body.application_receipt_id}`);
    assert.equal(matching.length, 1, "exactly one engine record on disk for the receipt");
    assert.equal(matching[0].id, retry.body.engine_memory_id);
    assert.equal(matching[0].content, body.finding);
    assert.equal(matching[0].embedding.length, 32);
    assert.equal(readIndex(dir).receipts[body.application_receipt_id].engine_memory_id, retry.body.engine_memory_id);

    const recall = await sc.req("POST", "/memory/recall", recallBody({ query: "queue worker downsizing checkout backlog" }));
    assert.equal(recall.status, 200);
    assert.deepEqual(recall.body.items.map((i: any) => i.engine_memory_id), [retry.body.engine_memory_id]);
    assert.equal(recall.body.excluded_unscoped, 0);

    const healed = await sc.req("GET", "/health");
    assert.equal(healed.body.status, "ready");
    assert.equal(healed.body.store.missing_engine_records, 0);
    assert.deepEqual(healed.body.store.missing_engine_receipt_ids, []);

    const again = await sc.req("POST", "/memory/remember", body);
    assert.equal(again.status, 200);
    assert.equal(again.body.engine_memory_id, retry.body.engine_memory_id);
    assert.equal("reconciled" in again.body, false);
    await sc.stop();

    // Durable across restart.
    sc = await startSidecar(contractEnv(dir, fake));
    assert.equal((await sc.req("GET", "/health")).body.status, "ready");
    const reload = await sc.req("POST", "/memory/recall", recallBody({ query: "queue worker downsizing checkout backlog" }));
    assert.deepEqual(reload.body.items.map((i: any) => i.engine_memory_id), [retry.body.engine_memory_id]);
  } finally {
    await sc?.stop();
    await fake.close();
  }
});

test("CONTRACT A11: reconciling missing records re-links supersession in both directions", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  const scope = { tenant_id: "tenant-a", service_id: "search", target_id: "db-1" };
  const old = rememberBody({ scope, finding: "Search database storage tier downgrade was validated at 40 percent IOPS headroom" });
  const fix = rememberBody({ scope, kind: "correction", supersedes_receipt_id: old.application_receipt_id, correction_review_id: "review-42",
    finding: "Correction: search database storage tier downgrade headroom was 4 percent, not 40 percent" });
  const assertLinked = (oldEngineId: string, newEngineId: string) => {
    const state = readState(dir);
    const oldRec = state.records.find((r: any) => r.id === oldEngineId);
    const newRec = state.records.find((r: any) => r.id === newEngineId);
    assert.equal(oldRec.supersededBy, newRec.id);
    assert.equal(newRec.supersedes, oldRec.id);
    const index = readIndex(dir);
    assert.equal(index.receipts[old.application_receipt_id].engine_memory_id, oldEngineId);
    assert.equal(index.receipts[fix.application_receipt_id].engine_memory_id, newEngineId);
    assert.equal(index.receipts[old.application_receipt_id].superseded_by_receipt_id, fix.application_receipt_id);
    assert.equal(index.receipts[fix.application_receipt_id].supersedes_receipt_id, old.application_receipt_id);
  };
  let sc: Sidecar | null = null;
  try {
    sc = await startSidecar(contractEnv(dir, fake));
    const oldRes = await sc.req("POST", "/memory/remember", old);
    const fixRes = await sc.req("POST", "/memory/remember", fix);
    assert.equal(oldRes.status, 201);
    assert.equal(fixRes.status, 201);
    await sc.stop();

    // Order 1: the superseded record first (its successor is still missing), then the correction.
    dropEngineRecords(dir, [oldRes.body.engine_memory_id, fixRes.body.engine_memory_id]);
    sc = await startSidecar(contractEnv(dir, fake));
    assert.equal((await sc.req("GET", "/health")).body.store.missing_engine_records, 2);
    const oldRetry = await sc.req("POST", "/memory/remember", old);
    assert.equal(oldRetry.status, 201);
    assert.equal(oldRetry.body.reconciled, true);
    const fixRetry = await sc.req("POST", "/memory/remember", fix);
    assert.equal(fixRetry.status, 201);
    assert.equal(fixRetry.body.reconciled, true);
    assertLinked(oldRetry.body.engine_memory_id, fixRetry.body.engine_memory_id);

    const rec = await sc.req("POST", "/memory/recall", recallBody({
      scope: { tenant_id: "tenant-a", service_id: "search" }, query: "search database storage tier downgrade headroom",
    }));
    assert.deepEqual(rec.body.items.map((i: any) => i.application_receipt_id), [fix.application_receipt_id]);
    assert.deepEqual(rec.body.historical.map((i: any) => i.application_receipt_id), [old.application_receipt_id]);
    assert.deepEqual(rec.body.historical[0].inapplicable_reasons, ["SUPERSEDED"]);
    assert.equal((await sc.req("GET", "/health")).body.status, "ready");
    await sc.stop();

    // Order 2: the correction first, then the record it supersedes.
    dropEngineRecords(dir, [oldRetry.body.engine_memory_id, fixRetry.body.engine_memory_id]);
    sc = await startSidecar(contractEnv(dir, fake));
    const fix2 = await sc.req("POST", "/memory/remember", fix);
    const old2 = await sc.req("POST", "/memory/remember", old);
    assert.equal(fix2.status, 201);
    assert.equal(old2.status, 201);
    assertLinked(old2.body.engine_memory_id, fix2.body.engine_memory_id);
    assert.equal((await sc.req("GET", "/health")).body.status, "ready");
  } finally {
    await sc?.stop();
    await fake.close();
  }
});

test("CONTRACT A11: crash during reconciliation leaves an orphan that the next retry adopts (no second record)", async () => {
  const fake = await startFakeEmbedder(32);
  const dir = tempDataDir();
  const body = rememberBody({ finding: "Reconcile-crash finding: batch window shift for checkout passed the throughput trial" });
  let sc: Sidecar | null = null;
  try {
    sc = await startSidecar(contractEnv(dir, fake));
    const first = await sc.req("POST", "/memory/remember", body);
    assert.equal(first.status, 201);
    await sc.stop();

    // Engine record lost, then a re-created record written without the index being re-pointed.
    dropEngineRecords(dir, [first.body.engine_memory_id]);
    const direct = new HMEM({ persistDir: dir });
    const recreated = direct.add({ content: body.finding, source: `greenops:receipt:${body.application_receipt_id}`, layer: "long_term" });
    const conflicting = rememberBody({ finding: "Other content" });
    direct.add({ content: "Different content for another receipt", source: `greenops:receipt:${conflicting.application_receipt_id}` });

    sc = await startSidecar(contractEnv(dir, fake));
    const health = await sc.req("GET", "/health");
    assert.deepEqual(health.body.reasons, ["INDEX_ENGINE_MISMATCH", "ENGINE_RECORD_MISSING"]);
    assert.deepEqual(health.body.store.missing_engine_receipt_ids, [body.application_receipt_id]);

    const retry = await sc.req("POST", "/memory/remember", body);
    assert.equal(retry.status, 201);
    assert.equal(retry.body.reconciled, true);
    assert.equal(retry.body.engine_memory_id, recreated.id, "orphan adopted, not duplicated");
    const matching = readState(dir).records.filter((r: any) => r.source === `greenops:receipt:${body.application_receipt_id}`);
    assert.equal(matching.length, 1);
    assert.equal(matching[0].embedding.length, 32, "adopted record re-embedded with the configured provider");
    assert.equal(readIndex(dir).receipts[body.application_receipt_id].engine_memory_id, recreated.id);

    // An orphan whose content differs from the retried finding is never adopted.
    const before = snapshotFiles(dir);
    const refused = await sc.req("POST", "/memory/remember", conflicting);
    assert.equal(refused.status, 409);
    assert.equal(refused.body.error.code, "ORPHAN_CONFLICT");
    assert.deepEqual(snapshotFiles(dir), before);
  } finally {
    await sc?.stop();
    await fake.close();
  }
});
