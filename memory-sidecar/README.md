# GreenOps memory sidecar (private)

A private HTTP sidecar that wraps the **vendored Meterless H-MEM reference engine**
(`@meterless/hmem-reference` 0.1.0, Apache-2.0) for SuperOps. On top of the engine it adds:

- receipt idempotency
- tenant/service scope, enforced before ranking
- version applicability
- correction lineage in both directions
- a real embedding provider boundary that fails closed
- corruption detection

The routes are **GreenOps' own private contract**, not a Meterless API. Run the sidecar only
on a private network. The browser must never call it.

Status: implemented and contract-tested locally with a fake embedding server. **The real NVIDIA
embedding path has not been exercised** (no account, key or spend cap was available).
Semantic recall quality is therefore unproven.

## Run

Supported runtime: **Node `>=22.12 <23`** (`engines.node`; `.nvmrc` pins `22.16.0`). Only
v22.16.0 has been tested. Node 26 is known not to work: it rejects
`--experimental-transform-types`. Other majors are untested and are refused. There are no
runtime npm dependencies.

```bash
cd memory-sidecar
MEMORY_AUTH_TOKEN=$(openssl rand -hex 24) \
HMEM_DATA_DIR=/var/lib/greenops/hmem \
EMBEDDING_MODE=nvidia EMBEDDING_API_KEY=... \
npm start
npm test        # node:test suite; spawns the real server against temp dirs
```

`npm start` and `npm test` first run `scripts/check-node.mjs` (plain JavaScript, so it runs on
any Node). It exits 1 with a message naming the Node binary when the major is not 22, the
version is below 22.12, or that binary rejects `--experimental-transform-types`. Run it on its
own with `npm run check-node`.

**Pointing at Node 22.** npm runs scripts with the first `node` on `PATH`, and it overwrites a
`NODE` variable you set, so choose the runtime through `PATH`, nvm, or by calling the binary
directly. On a machine where `/usr/local/bin/node` is v22 and Homebrew's `node` is v26:

```bash
nvm use                                    # reads .nvmrc, if you use nvm
PATH=/usr/local/bin:$PATH npm test         # put a Node 22 install first on PATH
PATH=/usr/local/bin:$PATH npm start

# Without npm (cwd memory-sidecar):
NODE=/usr/local/bin/node
"$NODE" scripts/check-node.mjs
"$NODE" --experimental-transform-types --test test/*.test.ts
"$NODE" --experimental-transform-types src/server.ts
```

The test helpers spawn the sidecar with the same binary that runs the tests
(`process.execPath`), so a direct run never mixes runtimes.

`--experimental-transform-types` is required because upstream uses TypeScript constructor
parameter properties. `tsconfig.json` is only for editor checking. Full type checking also
needs `typescript` and `@types/node`, which are not installed here.

## Environment

| Variable | Default | Notes |
|---|---|---|
| `MEMORY_AUTH_TOKEN` | required | At least 16 characters, otherwise the process exits 1. Required on every route. |
| `HMEM_DATA_DIR` | required | A durable directory. Holds `state.json` and `ledger.jsonl` (engine files) and `greenops-index.json` (wrapper index). |
| `PORT` / `HOST` | `7410` / `127.0.0.1` | `PORT=0` picks a free port, which tests use. |
| `EMBEDDING_MODE` | required | `nvidia`, `openai_compatible` or `hash_conformance`. `hash_conformance` is only for deterministic tests and is labelled `semantic:false`. |
| `EMBEDDING_BASE_URL` | `https://integrate.api.nvidia.com/v1` | The sidecar calls `POST {base}/embeddings`. |
| `EMBEDDING_MODEL_ID` | `nvidia/nemotron-3.5-embed-1b` | Ignored in `hash_conformance` mode. |
| `EMBEDDING_API_KEY` | none | Required for `nvidia`. Sent as a Bearer token and never logged. |
| `EMBEDDING_PREPROCESSING_VERSION` | `v1` | `v1` applies Unicode NFC normalization only. |
| `EMBEDDING_TIMEOUT_MS` | `15000` | Allowed range 100..120000. |

## Routes

Every route requires `Authorization: Bearer <MEMORY_AUTH_TOKEN>`; the comparison is
constant-time. Without it the response is `401 {"error":{"code":"AUTH_REQUIRED",...}}`.

Errors always have the shape `{"error":{"code","message"}}`. Common error responses:

| Status | Code | Cause |
|---|---|---|
| 400 | `MALFORMED_JSON` | Body is not valid JSON. |
| 413 | `PAYLOAD_TOO_LARGE` | Body exceeds 64 KiB. |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Content type is not JSON. |
| 422 | `VALIDATION_ERROR` | Includes any unknown field or query parameter. |
| 404 | `NOT_FOUND` | Unknown route. |
| 405 | `METHOD_NOT_ALLOWED` | Wrong method for the route. |

All engine-touching handlers, including health and recall, run through one serial queue
(single writer). Upstream `query()` mutates access counters, which is why recall is queued too.

### `GET /health`

Returns 200 when `ready`, otherwise 503.

```json
{"status":"ready|degraded|unavailable","reasons":[],"engine":{"package":"@meterless/hmem-reference","version":"0.1.0","upstream_sha":"0aa7417b..."},
 "embedding_profile":{...},"store":{"records":0,"receipts":0,"data_dir":"...","unindexed_engine_records":0,"missing_engine_records":0,"missing_engine_receipt_ids":[],"reconcilable_orphans":0}}
```

Possible `reasons`:

| Reason | Status | Meaning |
|---|---|---|
| `MEMORY_STATE_CORRUPT` | unavailable | The state, ledger or index file could not be parsed at startup. The files are never reset or overwritten. |
| `EMBEDDING_PROFILE_MISMATCH` | degraded | The stored profile differs from the configuration. `stored_embedding_profile` is included. Remember and recall return `503 MEMORY_NOT_READY` until a reindex. |
| `INDEX_ENGINE_MISMATCH` | degraded | Index entries without a matching engine record, or engine records without an index entry. Recall still works, and unindexed records are excluded. |
| `ENGINE_RECORD_MISSING` | degraded | Added alongside `INDEX_ENGINE_MISMATCH` when an index entry's engine record is gone (or carries another receipt's source). `store.missing_engine_records` counts them; `store.missing_engine_receipt_ids` lists up to 50 receipt ids, sorted. Startup logs `memory_missing_engine_records` with the ids. Those receipts are not recallable until a same-hash remember retry reconciles them (see below). |

`embedding_profile` has these fields: `{kind, model_id, dimensions, preprocessing_version,
normalization:"l2", semantic, profile_hash}`. `profile_hash` is
`sha256:` + the SHA-256 of the canonical JSON of the other fields. Dimensions are learned from
the first real provider response and stored in the index.

### `POST /memory/remember`

The request body has these fields:

| Field | Type / limits |
|---|---|
| `application_receipt_id` | UUID |
| `kind` | One of: `screening_rejection`, `rejected_trial`, `validated_plan`, `verified_outcome`, `ai_eval_aggregate`, `correction` |
| `scope` | `{tenant_id, service_id, target_id: string\|null}` |
| `finding` | 1..2000 chars |
| `evidence_refs` | ≤50 strings |
| `applicability` | `{policy_version, workload_version, config_version, model_version: string\|null, test_version: string\|null}` |
| `content_hash` | `"sha256:<64 hex>"` |
| `supersedes_receipt_id` | Optional |
| `correction_review_id` | Optional |
| `tags` | Optional, ≤20 |

Responses:

| Status | Body or code | When |
|---|---|---|
| 201 | `{engine_memory_id, application_receipt_id, stored_at, embedding_profile, persisted:true, duplicate:false}` | New receipt stored. |
| 200 | Same body with `duplicate:true` | Same receipt id, same `content_hash`, same tenant+service, and the indexed engine record exists. No new engine record is created. |
| 201 | Same body with `duplicate:true, reconciled:true` and a new `engine_memory_id` | Same receipt id, hash and tenant+service, but the indexed engine record is missing. The record is re-created (see below). |
| 409 | `IDEMPOTENCY_CONFLICT` | Same receipt id with a different hash or scope, whether or not its engine record exists. Nothing is written. |
| 422 | `VALIDATION_ERROR` | `supersedes_receipt_id` is set without `correction_review_id`. |
| 404 | `MEMORY_NOT_FOUND` | The superseded receipt is missing or belongs to another tenant/service. |
| 409 | `SUPERSESSION_CONFLICT` | The superseded receipt is already superseded. |
| 201 | Same body with `duplicate:true, reconciled:true` | Crash orphan adopted (see below). No second engine record is created. |
| 409 | `ORPHAN_CONFLICT` | An unindexed engine record with this receipt's source exists but its content differs from `finding`, or more than one exists. Nothing is written. |
| 503 | `MEMORY_EMBEDDING_UNAVAILABLE` | Provider failure or an invalid vector (non-finite, wrong count or order, zero norm, dimension change). Nothing is written. |
| 500 | `MEMORY_WRITE_FAILED` | An engine or index write failed, or the record was not found when `state.json` was read back. |

`persisted:true` is returned only after the sidecar reads `state.json` back from disk and finds
the acknowledged `engine_memory_id` with this receipt's source. This applies to every 200 and
201 response.

A successful correction sets the new record's `supersedes` and calls
`store.update(old, {supersededBy: new})`, so lineage exists in both directions in the engine
and in the index.

How the write is performed:

1. The sidecar calls `hmem.add` with `type:"factual"`, `layer:"long_term"`, `confidence:0.9`,
   `source:"greenops:receipt:<id>"` and `provenance.refs = evidence_refs`.
2. The engine persists first.
3. The index is written (atomically) afterwards.

**Crash reconciliation.** A crash between steps 2 and 3 leaves an orphan: an engine record
whose `source` is exactly `greenops:receipt:<id>` with no index entry. When the same receipt
is retried, the sidecar checks for an orphan before adding:

- If exactly one orphan exists and its content equals `finding`, it is adopted. The sidecar
  re-embeds it with the configured provider (so its vector matches the stored profile),
  applies the same lineage checks and updates, writes the index entry, and returns 201 with
  `duplicate:true, reconciled:true`.
- Otherwise it returns 409 `ORPHAN_CONFLICT` and writes nothing.

Health reports adoptable orphans as `store.reconcilable_orphans`, and startup logs their
receipt ids. Adoption trusts the retried request's scope and applicability, because the
engine record carries neither.

**Missing engine record.** The opposite case: an index entry exists but its engine record is
gone from `state.json` (for example, lost or edited state). The sidecar never acknowledges
such a receipt as a plain duplicate. On a remember retry:

- If the request's `content_hash` and tenant+service equal the indexed ones, the sidecar
  re-creates the engine record from the request (embedding `finding` with the configured
  provider). If an unindexed orphan with this receipt's source and the same content exists
  (a crash part-way through an earlier reconciliation), it is adopted and re-embedded instead,
  so no second record appears. It then re-links supersession from the index in both directions:
  the new record `supersedes` the predecessor's engine record, the predecessor gets
  `supersededBy`, and the same is done for a successor. A linked receipt whose own record is
  also missing is linked when it is reconciled in turn. Finally it re-points the index
  entry's `engine_memory_id`, persists, and returns 201 with `duplicate:true, reconciled:true`.
  The index entry's kind, applicability, evidence refs, lineage and `stored_at` are kept.
- If the hash or scope differs, it returns 409 `IDEMPOTENCY_CONFLICT` and writes nothing.
- An orphan with different content, or more than one, returns 409 `ORPHAN_CONFLICT`.

### `POST /memory/recall`

The request body has these fields:

| Field | Type / limits |
|---|---|
| `scope` | `{tenant_id, service_id}` |
| `query` | 1..1000 chars |
| `applicability` | Same shape as in remember |
| `top_k` | 1..10, default 5 |
| `threshold` | 0..1, default 0.2 |

The sidecar runs two H-MEM queries. Each uses the patched pre-scoring `filter`, so only
indexed records in exactly this tenant+service are ever scored:

- `items`: memories that are applicable. Every non-null stored version equals the request's
  version, and the memory is not superseded.
- `historical`: in-scope memories that are not applicable. Each carries `inapplicable_reasons`,
  drawn from `POLICY_VERSION_CHANGED`, `WORKLOAD_VERSION_CHANGED`, `CONFIG_VERSION_CHANGED`,
  `MODEL_VERSION_CHANGED`, `TEST_VERSION_CHANGED` and `SUPERSEDED`.

`excluded_unscoped` counts engine records that have no index entry. Records from other scopes
are silently excluded and are not counted. After querying, the sidecar persists access
counters.

The response also includes `trace: {retrieval_reason, scores, candidates, threshold, top_k}`
and `embedding_profile`.

### `GET /memory/audit/{application_receipt_id}?tenant_id=&service_id=`

The lookup is scope-checked: a receipt from another tenant or service returns 404
`MEMORY_NOT_FOUND`. The response contains:

- `application_receipt_id`, `engine_memory_id`, `kind`, `scope`, `applicability`,
  `evidence_refs`, `stored_at`
- `correction_review_id`, `supersedes_receipt_id`, `superseded_by_receipt_id`
- `engine_record_present`
- `history`: the engine's `ledger.history`, with embeddings removed and `details.query`
  truncated to 200 characters
- `limitations`

Audit stays available while the service is degraded, but not when state is corrupt.

### `POST /memory/reindex`

Takes the body `{}`. It fetches new vectors for every engine record from the configured
provider. Only after all vectors have arrived does it write them through `store.update`.
It then records the new profile, which clears `EMBEDDING_PROFILE_MISMATCH`. If the provider
fails, the response is 503 and nothing is written.

## Tests and evidence

Run `npm test` (node:test). Every test spawns the real server as a child process, with the real
vendored engine and real files in a temp directory. The groups are:

- **CONTRACT**: these use a local fake OpenAI-compatible embedding server with deterministic
  bag-of-words vectors. They prove the wrapper's contract (auth, validation, scope,
  applicability, idempotency, lineage, restart durability, outage, corruption, reindex). They
  are **not** semantic-recall evidence.
- **CONFORMANCE**: `hash_conformance` mode, labelled `semantic:false`.
- **UNIT**: the fail-closed embedder and the pre-scoring filter patch.

The suite has 24 tests (16 top-level tests plus 8 subtests in one CONTRACT group), including the A11
regressions in `test/integrity.test.ts` (missing engine record, supersession re-link in both
orders, and a crash during reconciliation).

**BLOCKED**: there is no real NVIDIA (`nvidia` mode) integration test, because it needs
authorized model access and a spend cap. See `docs/research/SPONSOR_RESEARCH.md` §5 for the
smoke-test gate.

## Limitations

- JSON state plus JSONL ledger are not transactional and not tamper-proof. The engine file and
  the index file are separate writes. A crash between them leaves an orphan engine record:
  health reports `INDEX_ENGINE_MISMATCH` and `reconcilable_orphans`, and recall excludes the
  record. The orphan is adopted only when the caller retries the same receipt with the same
  finding. Likewise, an index entry whose engine record is missing (`ENGINE_RECORD_MISSING`)
  is repaired only by a same-hash retry from the caller, which must still hold the finding.
  Nothing repairs either case automatically at startup.
- This is a single-tenant sandbox. Scope is enforced by this wrapper, not the engine. Scope
  comes from the request body of an authenticated service caller; there is no per-tenant
  credential.
- Upstream enrichment (entities, `relatedTo`, domain) is heuristic. It can link records
  across scopes inside engine state. Those links are never returned.
- Recall writes data: it updates access counters and appends `read` ledger entries that
  contain the query text. The ledger grows without bound.
- Health is queued behind in-flight operations. It can wait up to the embedding timeout.
- Sleep, dreaming, mining and feedback are not exposed.

## Attribution

`vendor/hmem/` contains source from Meterless H-MEM. It is © its authors, licensed under
Apache-2.0 (`vendor/hmem/LICENSE`), and taken from upstream SHA
`0aa7417ba5c826396d91e891328be78c45e6fbf6`. The modifications are listed in `PATCHES.md`, with
the diff in `vendor/hmem.patch`. Hashes of the original files are in `reference-manifest.json`.
Everything outside `vendor/` is GreenOps' own code.
