// UNIT: the registered embedder fails closed. A missing prepared vector must throw rather
// than silently fall back to the hash mock. Runs in its own process (global embedder state).

import assert from "node:assert/strict";
import { test } from "node:test";
import { HMEM } from "../vendor/hmem/src/index.ts";
import { embed, setEmbedder } from "../vendor/hmem/src/embeddings.ts";
import { EmbeddingUnavailableError, installFailClosedEmbedder, withPreparedVectors } from "../src/embedding.ts";

test("UNIT: vendored embed() uses the hash mock only when no embedder is registered", () => {
  setEmbedder(null);
  assert.equal(embed("hello world").length, 64);
  setEmbedder(() => [1, 0, 0]);
  assert.deepEqual(embed("anything"), [1, 0, 0]);
  setEmbedder(null);
});

test("UNIT: engine add/query without a prepared vector throw (fail closed)", () => {
  installFailClosedEmbedder();
  const hmem = new HMEM();
  assert.throws(() => hmem.add({ content: "unprepared text", source: "t" }), EmbeddingUnavailableError);
  assert.equal(hmem.store.all().length, 0);
  const vec = [0.6, 0.8, 0];
  const rec = withPreparedVectors([["prepared text", vec]], () => hmem.add({ content: "prepared text", source: "t" }));
  assert.deepEqual(rec.embedding, vec);
  // Cache is cleared after the scoped call.
  assert.throws(() => hmem.retrieval.query("prepared text"), EmbeddingUnavailableError);
  const q = withPreparedVectors([["prepared text", vec]], () => hmem.retrieval.query("prepared text", { threshold: 0 }));
  assert.equal(q.memories[0].memory.id, rec.id);
  setEmbedder(null);
});

test("UNIT: patched query filter is applied before scoring", () => {
  setEmbedder(null);
  const hmem = new HMEM();
  const a = hmem.add({ content: "alpha finding about latency", source: "a" });
  const b = hmem.add({ content: "alpha finding about latency", source: "b" });
  const seen: string[] = [];
  const q = hmem.retrieval.query("alpha finding about latency", {
    threshold: 0,
    filter: (m) => { seen.push(m.id); return m.id === a.id; },
  });
  assert.deepEqual(q.memories.map((m) => m.memory.id), [a.id]);
  assert.equal(b.id in q.trace.scores, false);
  assert.deepEqual(seen.sort(), [a.id, b.id].sort());
  // Excluded record was not touched/logged as read.
  assert.equal(hmem.store.get(b.id)!.accessCount, 0);
  assert.equal(hmem.ledger.history(b.id).some((e) => e.action === "read"), false);
});
