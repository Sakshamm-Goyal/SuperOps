// CONTRACT tests: real sidecar process + real vendored H-MEM persistence, with a local
// deterministic fake OpenAI-compatible embedding server. These prove wrapper behaviour
// (auth, scope, applicability, idempotency, lineage, durability), NOT semantic recall quality.

import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { after, before, describe, test } from "node:test";
import {
  APPLICABILITY,
  contractEnv,
  recallBody,
  rememberBody,
  startFakeEmbedder,
  startSidecar,
  tempDataDir,
} from "./helpers.ts";
import type { FakeEmbedder, Sidecar } from "./helpers.ts";

describe("CONTRACT (fake openai_compatible embedder): memory sidecar", () => {
  let fake: FakeEmbedder;
  let dataDir: string;
  let sc: Sidecar;

  before(async () => {
    fake = await startFakeEmbedder(32);
    dataDir = tempDataDir();
    sc = await startSidecar(contractEnv(dataDir, fake));
  });
  after(async () => {
    await sc?.stop();
    await fake?.close();
  });

  test("CONTRACT: every route requires the bearer token (401 AUTH_REQUIRED)", async () => {
    for (const [method, p] of [["GET", "/health"], ["POST", "/memory/recall"], ["POST", "/memory/remember"], ["GET", "/nope"]] as const) {
      const none = await sc.req(method, p, method === "POST" ? recallBody() : undefined, { token: null });
      assert.equal(none.status, 401, `${method} ${p}`);
      assert.deepEqual(none.body.error.code, "AUTH_REQUIRED");
      const wrong = await sc.req(method, p, method === "POST" ? recallBody() : undefined, { token: "wrong-token-but-long-enough" });
      assert.equal(wrong.status, 401);
    }
    const ok = await sc.req("GET", "/health");
    assert.equal(ok.status, 200);
    assert.equal(ok.body.status, "ready");
    assert.equal(ok.body.engine.package, "@meterless/hmem-reference");
    assert.equal(ok.body.engine.upstream_sha, "0aa7417ba5c826396d91e891328be78c45e6fbf6");
    assert.equal(ok.body.embedding_profile.semantic, true);
    assert.equal(ok.body.embedding_profile.kind, "openai_compatible");
  });

  test("CONTRACT: unknown fields, bad types and malformed bodies are rejected", async () => {
    const extra = await sc.req("POST", "/memory/remember", { ...rememberBody(), surprise: 1 });
    assert.equal(extra.status, 422);
    assert.equal(extra.body.error.code, "VALIDATION_ERROR");
    const nested = rememberBody();
    nested.scope.extra = "x";
    assert.equal((await sc.req("POST", "/memory/remember", nested)).status, 422);
    const recallExtra = await sc.req("POST", "/memory/recall", { ...recallBody(), applicability: { ...APPLICABILITY, foo: "bar" } });
    assert.equal(recallExtra.status, 422);
    assert.equal((await sc.req("POST", "/memory/remember", rememberBody({ kind: "approval" }))).status, 422);
    assert.equal((await sc.req("POST", "/memory/remember", rememberBody({ content_hash: "md5:abc" }))).status, 422);
    assert.equal((await sc.req("POST", "/memory/recall", recallBody({ top_k: 11 }))).status, 422);
    assert.equal((await sc.req("POST", "/memory/recall", recallBody({ threshold: 2 }))).status, 422);
    const malformed = await sc.req("POST", "/memory/recall", undefined, { raw: "{not json" });
    assert.equal(malformed.status, 400);
    assert.equal(malformed.body.error.code, "MALFORMED_JSON");
    const big = await sc.req("POST", "/memory/recall", undefined, { raw: JSON.stringify({ q: "x".repeat(70 * 1024) }) });
    assert.equal(big.status, 413);
    const unknownQuery = await sc.req("GET", `/memory/audit/${crypto.randomUUID()}?tenant_id=a&service_id=b&x=1`);
    assert.equal(unknownQuery.status, 422);
  });

  test("CONTRACT: remember sends documented openai_compatible request (no input_type/truncate)", async () => {
    const before = fake.requests.length;
    const res = await sc.req("POST", "/memory/remember", rememberBody());
    assert.equal(res.status, 201);
    const r = fake.requests[before];
    assert.equal(r.path, "/v1/embeddings");
    assert.equal(r.model, "fake-bow-32");
    assert.equal(r.encoding_format, "float");
    assert.equal(r.authorization, "Bearer fake-key");
    assert.equal("input_type" in r, false);
    assert.equal("truncate" in r, false);
    assert.equal(res.body.embedding_profile.dimensions, 32);
    assert.match(res.body.embedding_profile.profile_hash, /^sha256:[0-9a-f]{64}$/);
  });

  test("CONTRACT: duplicate receipt is idempotent; same id with different hash is 409", async () => {
    const body = rememberBody();
    const first = await sc.req("POST", "/memory/remember", body);
    assert.equal(first.status, 201);
    assert.equal(first.body.duplicate, false);
    assert.equal(first.body.persisted, true);
    const recordsBefore = (await sc.req("GET", "/health")).body.store.records;
    const dup = await sc.req("POST", "/memory/remember", body);
    assert.equal(dup.status, 200);
    assert.equal(dup.body.duplicate, true);
    assert.equal(dup.body.engine_memory_id, first.body.engine_memory_id);
    assert.equal((await sc.req("GET", "/health")).body.store.records, recordsBefore);
    const conflict = await sc.req("POST", "/memory/remember", { ...body, content_hash: `sha256:${"0".repeat(64)}` });
    assert.equal(conflict.status, 409);
    assert.equal(conflict.body.error.code, "IDEMPOTENCY_CONFLICT");
  });

  test("CONTRACT: foreign tenant/service records are never returned or auditable", async () => {
    const secret = "Foreign tenant secret: rightsizing checkout-api to m5.large failed the latency trial";
    const foreignTenant = rememberBody({ finding: secret, scope: { tenant_id: "tenant-b", service_id: "checkout", target_id: null } });
    const foreignService = rememberBody({ finding: secret, scope: { tenant_id: "tenant-a", service_id: "billing", target_id: null } });
    assert.equal((await sc.req("POST", "/memory/remember", foreignTenant)).status, 201);
    assert.equal((await sc.req("POST", "/memory/remember", foreignService)).status, 201);
    const res = await sc.req("POST", "/memory/recall", recallBody({ top_k: 10, threshold: 0 }));
    assert.equal(res.status, 200);
    const all = [...res.body.items, ...res.body.historical];
    assert.ok(all.length > 0, "in-scope memories are returned");
    for (const it of all) {
      assert.notEqual(it.finding, secret);
      assert.notEqual(it.application_receipt_id, foreignTenant.application_receipt_id);
      assert.notEqual(it.application_receipt_id, foreignService.application_receipt_id);
    }
    assert.equal(JSON.stringify(res.body).includes("Foreign tenant secret"), false);
    const audit = await sc.req("GET", `/memory/audit/${foreignTenant.application_receipt_id}?tenant_id=tenant-a&service_id=checkout`);
    assert.equal(audit.status, 404);
    assert.equal(audit.body.error.code, "MEMORY_NOT_FOUND");
    // Duplicate receipt id from another scope must not be accepted or leak.
    const crossDup = await sc.req("POST", "/memory/remember", { ...foreignTenant, scope: { tenant_id: "tenant-a", service_id: "checkout", target_id: null } });
    assert.equal(crossDup.status, 409);
  });

  test("CONTRACT: version change moves a memory to historical with reasons", async () => {
    const body = rememberBody({
      finding: "Spot migration for the reporting batch job was rejected because interruption rate exceeded budget",
      applicability: { ...APPLICABILITY, model_version: "model-7" },
      scope: { tenant_id: "tenant-a", service_id: "reporting", target_id: "asg-1" },
    });
    assert.equal((await sc.req("POST", "/memory/remember", body)).status, 201);
    const q = { scope: { tenant_id: "tenant-a", service_id: "reporting" }, query: "spot migration reporting batch interruption" };
    const same = await sc.req("POST", "/memory/recall", recallBody({ ...q, applicability: { ...APPLICABILITY, model_version: "model-7" } }));
    assert.equal(same.body.items.length, 1);
    assert.equal(same.body.items[0].application_receipt_id, body.application_receipt_id);
    assert.equal(same.body.items[0].target_id, "asg-1");
    assert.deepEqual(same.body.items[0].evidence_refs, body.evidence_refs);
    assert.equal(same.body.historical.length, 0);

    const changed = await sc.req("POST", "/memory/recall", recallBody({
      ...q,
      applicability: { ...APPLICABILITY, policy_version: "policy-v2", model_version: "model-8" },
    }));
    assert.equal(changed.body.items.length, 0);
    assert.equal(changed.body.historical.length, 1);
    assert.deepEqual(changed.body.historical[0].inapplicable_reasons, ["POLICY_VERSION_CHANGED", "MODEL_VERSION_CHANGED"]);

    // A null stored version does not constrain applicability.
    const nullTest = await sc.req("POST", "/memory/recall", recallBody({ ...q, applicability: { ...APPLICABILITY, model_version: "model-7", test_version: "t-9" } }));
    assert.equal(nullTest.body.items.length, 1);
  });

  test("CONTRACT: correction requires review and sets lineage in both directions", async () => {
    const scope = { tenant_id: "tenant-a", service_id: "search", target_id: "db-1" };
    const old = rememberBody({ scope, finding: "Search database storage tier downgrade was validated at 40 percent IOPS headroom" });
    assert.equal((await sc.req("POST", "/memory/remember", old)).status, 201);

    const noReview = rememberBody({ scope, kind: "correction", supersedes_receipt_id: old.application_receipt_id,
      finding: "Correction: search database storage tier downgrade headroom was 4 percent, not 40 percent" });
    const r1 = await sc.req("POST", "/memory/remember", noReview);
    assert.equal(r1.status, 422);
    assert.equal(r1.body.error.code, "VALIDATION_ERROR");

    const foreign = await sc.req("POST", "/memory/remember", rememberBody({
      scope: { tenant_id: "tenant-b", service_id: "search", target_id: null },
      supersedes_receipt_id: old.application_receipt_id, correction_review_id: "review-x",
    }));
    assert.equal(foreign.status, 404);

    const fix = { ...noReview, correction_review_id: "review-42" };
    const r2 = await sc.req("POST", "/memory/remember", fix);
    assert.equal(r2.status, 201);

    const again = await sc.req("POST", "/memory/remember", rememberBody({ scope, supersedes_receipt_id: old.application_receipt_id, correction_review_id: "review-43" }));
    assert.equal(again.status, 409);
    assert.equal(again.body.error.code, "SUPERSESSION_CONFLICT");

    const auditOld = await sc.req("GET", `/memory/audit/${old.application_receipt_id}?tenant_id=tenant-a&service_id=search`);
    assert.equal(auditOld.status, 200);
    assert.equal(auditOld.body.superseded_by_receipt_id, fix.application_receipt_id);
    assert.ok(auditOld.body.history.some((h: any) => h.action === "update" && h.newState?.supersededBy === r2.body.engine_memory_id));
    const auditNew = await sc.req("GET", `/memory/audit/${fix.application_receipt_id}?tenant_id=tenant-a&service_id=search`);
    assert.equal(auditNew.body.supersedes_receipt_id, old.application_receipt_id);
    assert.equal(auditNew.body.correction_review_id, "review-42");

    const state = JSON.parse(fs.readFileSync(path.join(dataDir, "state.json"), "utf-8"));
    const oldRec = state.records.find((r: any) => r.id === auditOld.body.engine_memory_id);
    const newRec = state.records.find((r: any) => r.id === r2.body.engine_memory_id);
    assert.equal(oldRec.supersededBy, newRec.id);
    assert.equal(newRec.supersedes, oldRec.id);

    const rec = await sc.req("POST", "/memory/recall", recallBody({
      scope: { tenant_id: "tenant-a", service_id: "search" }, query: "search database storage tier downgrade headroom",
    }));
    assert.deepEqual(rec.body.items.map((i: any) => i.application_receipt_id), [fix.application_receipt_id]);
    assert.equal(rec.body.historical.length, 1);
    assert.equal(rec.body.historical[0].application_receipt_id, old.application_receipt_id);
    assert.deepEqual(rec.body.historical[0].inapplicable_reasons, ["SUPERSEDED"]);
  });

  test("CONTRACT: remember -> recall -> restart -> recall; audit history persists", async () => {
    const scope = { tenant_id: "tenant-a", service_id: "durable", target_id: "i-dur" };
    const body = rememberBody({ scope, finding: "Durable finding: autoscaling floor reduction for durable-api passed the soak test" });
    const created = await sc.req("POST", "/memory/remember", body);
    assert.equal(created.status, 201);
    const q = recallBody({ scope: { tenant_id: "tenant-a", service_id: "durable" }, query: "autoscaling floor reduction durable-api soak" });
    const r1 = await sc.req("POST", "/memory/recall", q);
    assert.equal(r1.body.items[0].engine_memory_id, created.body.engine_memory_id);
    assert.ok(r1.body.trace.scores[created.body.engine_memory_id] > 0);

    assert.equal(await sc.stop(), 0, "graceful SIGTERM exit code 0");
    sc = await startSidecar(contractEnv(dataDir, fake));

    const health = await sc.req("GET", "/health");
    assert.equal(health.body.status, "ready");
    const r2 = await sc.req("POST", "/memory/recall", q);
    assert.equal(r2.body.items[0].engine_memory_id, created.body.engine_memory_id);
    assert.equal(r2.body.items[0].finding, body.finding);
    const dup = await sc.req("POST", "/memory/remember", body);
    assert.equal(dup.status, 200);
    assert.equal(dup.body.duplicate, true);

    const audit = await sc.req("GET", `/memory/audit/${body.application_receipt_id}?tenant_id=tenant-a&service_id=durable`);
    assert.equal(audit.status, 200);
    const actions = audit.body.history.map((h: any) => h.action);
    assert.equal(actions[0], "create");
    assert.ok(actions.filter((a: string) => a === "read").length >= 2, "reads before and after restart are in the ledger");
    for (const h of audit.body.history) {
      assert.equal(JSON.stringify(h).includes("\"embedding\""), false);
      if (h.details?.query) assert.ok(h.details.query.length <= 201);
    }
    assert.deepEqual(audit.body.limitations, [
      "JSON state + JSONL ledger: not transactional, not tamper-proof",
      "single-tenant sandbox; scope enforced by this wrapper, not the engine",
    ]);
    // Access counters from recall are durable (upstream touch() alone does not persist).
    const state = JSON.parse(fs.readFileSync(path.join(dataDir, "state.json"), "utf-8"));
    const rec = state.records.find((r: any) => r.id === created.body.engine_memory_id);
    assert.ok(rec.accessCount >= 2);
    const index = JSON.parse(fs.readFileSync(path.join(dataDir, "greenops-index.json"), "utf-8"));
    assert.equal(index.schema_version, 1);
    assert.equal(index.receipts[body.application_receipt_id].engine_memory_id, created.body.engine_memory_id);
  });
});
