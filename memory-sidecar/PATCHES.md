# Vendored H-MEM patches

Upstream: [Meterless/Meterless](https://github.com/Meterless/Meterless) at
`0aa7417ba5c826396d91e891328be78c45e6fbf6` (commit date 2026-07-22T23:14:36Z),
`engines/hmem/reference/src/*.ts`, licensed Apache-2.0 (`vendor/hmem/LICENSE`).
No NOTICE file exists upstream at that SHA.

Per Apache-2.0 section 4(b), the files below were modified by the GreenOps Verify team.
Each change is marked in the source with `// GreenOps patch (Apache-2.0 modification):`.
The exact unified diff versus upstream is `vendor/hmem.patch`. Original file SHA-256
values are in `reference-manifest.json`. All other vendored files are byte-identical to
upstream.

| # | File | Change | Why |
|---|---|---|---|
| 1 | `vendor/hmem/src/embeddings.ts` | Added `setEmbedder(fn \| null)`. `embed(text)` calls the registered function when one is set; otherwise it runs the original FNV-1a hash mock unchanged. | The upstream embedder is a synchronous hash mock that is hard-imported by the store and retrieval code. The sidecar fetches real provider vectors asynchronously first, then registers a lookup that throws on a cache miss, so it can never fall back to the hash silently. |
| 2 | `vendor/hmem/src/memoryRetrieval.ts` | `query()` options accept `filter?: (m: MemoryRecord) => boolean`. The filter runs before scoring. | Tenant/service scope and version applicability must be enforced before ranking. Records the filter rejects are never scored, touched or logged as read. |
| 3 | `vendor/hmem/src/memoryStore.ts` | `persist()` writes `state.json` atomically: it writes a temp file, fsyncs it, then renames it over the original. | A crash in the middle of `writeFileSync` could truncate `state.json`. |

Not patched, deliberately (handled in the wrapper or listed as limitations):

- `index.ts` facade `query()` does not forward the `filter` type. The sidecar calls `hmem.retrieval.query` directly.
- `store.touch()` does not persist. The sidecar calls `store.persist()` after each recall.
- `discoverRelationships()` may set `supersedes` heuristically on a new record, possibly across scopes. The sidecar resets it to the approved value through `store.update`. It may also add `relatedTo` links across scopes. The sidecar never returns `relatedTo`, but the links do exist in engine state.
- `ledger.jsonl` appends and `state.json` writes are still separate, non-transactional operations.
