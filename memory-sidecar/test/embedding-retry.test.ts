// Unit: one bounded retry for a transient embedding provider failure; never more, never on a 4xx.
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { EmbeddingClient, EmbeddingUnavailableError } from "../src/embedding.ts";

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

const cfg = { mode: "nvidia" as const, baseUrl: "http://embed.invalid/v1", modelId: "m", apiKey: "k", preprocessingVersion: "v1", timeoutMs: 1000 };
const ok = () => new Response(JSON.stringify({ data: [{ index: 0, embedding: [1, 2, 3] }] }), { status: 200 });

function script(...steps: Array<() => Response>) {
  let calls = 0;
  globalThis.fetch = (async () => { const s = steps[calls++]; return s(); }) as typeof fetch;
  return () => calls;
}

test("a single timeout is retried once and succeeds", async () => {
  const calls = script(() => { throw Object.assign(new Error("t"), { name: "TimeoutError" }); }, ok);
  const r = await new EmbeddingClient(cfg).embed(["hello"], "query");
  assert.equal(r.dimensions, 3);
  assert.equal(calls(), 2);
});

test("two consecutive 503s fail closed after exactly two calls", async () => {
  const calls = script(() => new Response("x", { status: 503 }), () => new Response("x", { status: 503 }), ok);
  await assert.rejects(new EmbeddingClient(cfg).embed(["hello"], "query"), EmbeddingUnavailableError);
  assert.equal(calls(), 2);
});

test("a 4xx is not retried", async () => {
  const calls = script(() => new Response("x", { status: 401 }), ok);
  await assert.rejects(new EmbeddingClient(cfg).embed(["hello"], "query"), EmbeddingUnavailableError);
  assert.equal(calls(), 1);
});
