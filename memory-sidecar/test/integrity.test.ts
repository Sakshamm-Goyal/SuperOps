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
