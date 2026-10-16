# Sponsor integration research

**Checked:** 16 October 2026. **Status:** documentation and source inspection; no account authentication, dependency installation, model inference or sponsor query was performed. Public documentation establishes an available interface, not this team's access or a working integration.

This document supplements [Architecture](../ARCHITECTURE.md), [API Reference](../API_REFERENCE.md) and [Development](../DEVELOPMENT.md). All GreenOps interfaces below are proposed application contracts. Vendor interfaces are separately identified. Recheck the assigned sponsor workspace and the pinned references at implementation time.

## 1. Decisions supported by the research

| Decision | Evidence and implication |
|---|---|
| Zetaris is the evidence federation layer | It supports metadata registration over independent sources and SQL over registered sources. The demo should use real queries over at least two physical sources; target BigQuery, PostgreSQL and a supported file store. |
| Use a small private TypeScript memory service | Meterless supplies a runnable TypeScript H-MEM reference and starter. There is no supplied HTTP server or hosted memory API in the inspected reference. We own the HTTP boundary, authentication and operating safeguards. |
| Keep action state in PostgreSQL | H-MEM is memory, not an execution transaction or rollback system. Approval, idempotency and provider operation state require transactional records independent of recall. |
| Treat the starter as a reference, not a completed production engine | Its embedding function is a deterministic hash mock, persistence is JSON/JSONL, and isolation is weaker than its high-level specification suggests. A functioning CLI does not satisfy our semantic-retrieval, durability or authorization acceptance gates. |
| Start with one tenant and one memory writer | The reference has no cross-process locking, tenant authorization or transactional store/ledger commit. Single-tenant scope is explicit, and applicability filtering still covers service, target and version boundaries. |
| Prefer direct HTTP for the first NVIDIA embedding spike | The official hosted API documents the request. This avoids betting the sprint on an unverified SDK integration. Freeze the actual available model only after an authorized real call. |

Source basis: [Zetaris connectivity](https://kbase.zetaris.com/knowledge/connect), [Zetaris SQL manual](https://kbase.zetaris.com/knowledge/sql-manual), [H-MEM reference README](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/README.md), and the source files linked below.

## 2. Event-specific access and rules

The supplied local `faq.md` and `welcome-guide (1).md` say every submission must integrate **Zetaris and Meterless**, use **Cursor** for development, and use NVIDIA where it contributes. Sponsor setup material and support are in the corresponding **Resources** folders and **Help** channels on HackOS. This research did not access those authenticated folders or recordings. Therefore workspace allocation, credits, quotas and hackathon-specific deployment requirements remain unverified.

The public [event page](https://hackathon.genai.works/event/open-agent-hackathon-2026) is the event context. Meterless' separate [community hackathon guide](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/docs/community/hackathon-guide.md) describes different tracks and a 25% Meterless criterion. **Do not import that rubric into this event.** The supplied Open Agent Hackathon materials and public event page give Sponsor Tech 10 points within their own 100-point rubric.

Before implementation, the team must obtain its assigned Zetaris API base URL, organization ID, access method, source-connection permissions and supported connector list. Record who verified access, the workspace version and the date. Do not place credentials, private workspace screenshots or access tokens in submission evidence.

## 3. Zetaris: verified public API and connector findings

### 3.1 The actual public REST contract

The current [API access guide](https://kbase.zetaris.com/knowledge/accessing-zetaris-using-api) links to [Zetaris ReDoc](https://api.saas.enterprise.zetaris.com/redoc/index.html). Its HTML identifies `./docs.yaml` as the specification. A read-only HTTP request retrieved the [OpenAPI YAML](https://api.saas.enterprise.zetaris.com/redoc/docs.yaml) successfully; the browser search reader could not render that host.

Inspected specification metadata: OpenAPI `3.1.0`, `info.version: v1`, SHA-256 `4ec254d6bd6cf7a761c4550a298faee5bd96528a15083c7930ba6a027ec6e385`. This is a snapshot fingerprint, not a Zetaris product-version claim. Do not assume the public SaaS contract equals the assigned hackathon deployment.

| Vendor method and path | operationId | Authentication declared by this specification |
|---|---|---|
| `GET /api/v1.0/auth/login` | `OrgUserLogin` | HTTP Basic username/password |
| `GET /api/v1.0/auth/refresh` | `RefreshToken` | JWT Bearer token; exact refresh-token use must be confirmed against the workspace |
| `POST /api/v1.0/query/sql/start` | `OpenSqlQuery` | API token via Bearer |
| `GET /api/v1.0/query/sql/page` | `PageSqlQuery` | API token via Bearer |
| `DELETE /api/v1.0/query/sql/close/{queryToken}` | `CloseSqlQuery` | API token via Bearer |

Every operation above requires `X-Request-ID` as a UUID and `X-Org-ID` as an `int64`. Login returns `idToken` and `refreshToken`. The newer guide says to use a console API key as the Bearer credential beyond login. The older [REST walkthrough](https://kbase.zetaris.com/knowledge/rest-api) describes the `idToken` as the Bearer credential instead. These are conflicting public descriptions: verify the actual assigned deployment and store one explicit, tested authentication profile; do not silently try unrelated credentials or log them.

The older walkthrough's Postman collection link points to `https://github.com/zetaris/zetaris-public`, which returned 404 during this review. The live OpenAPI above provides documented query routes despite that broken link. Request the workspace-specific collection/specification through sponsor support if behavior differs.

Query shapes from the OpenAPI snapshot:

| Operation | Request | Response fields |
|---|---|---|
| Start | JSON with required `select: string` and `pageLimit: integer`; description limits page size to 1–100 | Required `pageNumber`, `pageLimit`, `totalCount`, `totalPages`, `queryToken`; optional `records` array |
| Page | Required query parameters `queryToken`, `pageLimit`, `pageNumber` | Required `queryToken`, `pageNumber`, `totalCount`, `totalPages`; optional `records` array |
| Close | `queryToken` in path | HTTP 200 documented, no response body required |

The specification does not establish the initial page-number base, token expiry, stable-snapshot semantics, cancellation behavior, rate limits or server-side parameter binding. Resolve these with the first integration spike. Treat missing `records`, malformed values and unexpected pagination as explicit integration errors or incomplete evidence; never declare a partial result complete because HTTP returned 200.

### 3.2 GreenOps adapter design — ours

`query_evidence(template_id, validated_parameters, as_of, max_rows)` is our adapter, not a Zetaris endpoint. Its result contains normalized rows, source references, an application query receipt ID, observation/retrieval times, source versions, completeness and warnings.

Use a closed set of reviewed SQL templates. The inspected REST request exposes a SQL string, not a documented bind-parameter object. Implement parameter handling for the verified dialect with typed allowlists and tested escaping; do not concatenate user/model text. Grant read-only source and Zetaris permissions as a second independent control. Query creation, connector registration and pipeline mutation are setup operations, never agent tools.

The adapter must enforce row, byte, time and page budgets; paginate deterministically; verify counts and duplicate IDs; and close the query in cleanup even after errors. If a budget stops retrieval, return `completeness=partial` with the reason and prohibit a plan that requires complete evidence. Keep query tokens transient and redact them from logs. Store template/version, safe parameter digest, request UUIDs, source identifiers, counts, durations and result digest in the receipt.

### 3.3 Sources and network constraints

| Source | Publicly documented support | GreenOps setup implication |
|---|---|---|
| BigQuery | `com.simba.googlebigquery.jdbc.Driver`, OAuth; project and optional default dataset filters; backend-accessible private key path | Use a dedicated read account. The guide identifies Data Viewer and Job User for reads/query jobs; Data Owner is optional and unnecessary for our investigation path. Confirm whether the workspace supports a keyless alternative; do not assume it. |
| PostgreSQL | JDBC sources are supported; SQL manual includes `org.postgresql.Driver` with `jdbc:postgresql://...` in its Greenplum example | Confirm the assigned workspace's PostgreSQL connector/driver/TLS settings before committing to it. Expose only approved read views, excluding approvals, secrets and arbitrary execution tables. |
| Policy/price/carbon files | File sources include CSV, JSON, Parquet and others; named examples include S3 and Azure Blob | Use a sponsor-supported reachable store with least-privilege access. Do not infer GCS support from the fact BigQuery is supported. Confirm GCS or choose an explicitly supported store. |

The [BigQuery guide](https://kbase.zetaris.com/knowledge/bigquery) places keys in the Zetaris backend filesystem or its NDP `key-trust-store`, using a local backend path or `dffs:///...`. This is not a path on the developer's laptop. A hosted Zetaris backend similarly cannot reach a laptop's `localhost` PostgreSQL; host permitted samples on an approved reachable endpoint with TLS and restricted ingress. Test connection from the Zetaris workspace, not only from our API host. Public documentation does not prove cross-source transactional snapshot consistency; capture source timestamps and reconcile known drift.

Use immutable resource identity and aggregate each source at its own grain before joining. A CPU history × individual AI-call join must not multiply billing totals. Known-answer queries should independently reconcile totals, nulls, duplicate identities, date ranges and pagination before any recommendation depends on the results.

## 4. Meterless H-MEM: exact reference and capability boundary

### 4.1 Reference pin, licence and installation

Inspected repository: [Meterless/Meterless](https://github.com/Meterless/Meterless). Its `main` resolved on the checked date to **`0aa7417ba5c826396d91e891328be78c45e6fbf6`**, with commit timestamp `2026-07-22T23:14:36Z`, using GitHub's public commit API. Both root and engine [LICENSE](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/LICENSE) files identify Apache-2.0. The inspected tree did not expose a `NOTICE` file. Preserve applicable licence/attribution, document modifications and recheck notices for the chosen vendored files and dependencies.

The [starter](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/templates/agentathon-starter/README.md) documents `npm install` followed by mandatory `npm run setup`; setup copies the H-MEM reference into `vendor/hmem`. The CLI's `.notebook/` directory supplies persistence across invocations. The actual [package.json](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/templates/agentathon-starter/package.json) runs an unpinned `degit .../reference` followed by `npm install`. For our build, record an immutable upstream revision and use committed reviewed lockfiles, rather than resolving moving `main` during every bootstrap. The upstream starter tree also contains `node_modules` including a Windows binary; do not copy those artifacts into this repository or trust them as a portable install.

The reference package is `@meterless/hmem-reference`, version `0.1.0`, marked private, ESM and zero runtime dependencies; its development tools include `tsx` and `vitest`. This is source to vendor/extend with attribution, not evidence that an installable production npm SDK exists. No setup command was executed in this documentation task.

### 4.2 Actual in-process interfaces

The [facade source](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/src/index.ts) exposes:

| Reference interface | Meaning |
|---|---|
| `new HMEM({ clock?, persistDir?, actor?, minerFn? })` | Construct store, ledger, mining, retrieval, conflict, sleep and dreaming services |
| `hmem.add(input)` | Store a sourced record through `MemoryStoreService` |
| `await hmem.mine(event, text, { chatId? })` | Invoke `MemoryMiningService`; accepted event types are enumerated in `types.ts` |
| `hmem.query(text, { topN?, threshold?, chatId? })` | Retrieve ranked memories, context and retrieval trace |
| `hmem.feedback(id, kind)` | Apply `helpful`, `not_helpful` or `wrong` feedback |
| `hmem.ledger.history(id)` | Read mutation/read history for a memory |
| `hmem.sleep.preview()` / `execute(preview)` | Preview or perform consolidation work |

`AddInput` accepts `content`, mandatory `source`, optional type/layer/tags/confidence/provenance, `chatId`, `missionId`, `goalRunId`, `supersedes` and `derivedFrom`. It does **not** accept our arbitrary `tenant_id`, version hashes or evidence envelope as native typed fields. Store the canonical application envelope in PostgreSQL, use its immutable receipt as the memory's source, put evidence links in `provenance.refs`, and maintain a memory-ID mapping. Tags/content support retrieval but never enforce authorization.

Use direct `add` for verified experiment receipts so no accepted/rejected result disappears because prose extraction skipped a sentence. Mining may enrich safe narrative context, with its extracted output validated and linked to the original source; it is not the authoritative accounting or approval path. [Mining source](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/src/memoryMining.ts) shows that the default heuristic only keeps bounded sentences matching signal words. Its optional `minerFn` returns strings and does not itself prove factual accuracy.

### 4.3 Important differences between the specification and reference

These are static source findings to turn into reproducing tests during implementation, not claims of tests already run.

| Finding | Source evidence | Required GreenOps response |
|---|---|---|
| Embeddings are a deterministic hash mock | [embeddings.ts](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/src/embeddings.ts) hashes tokens into 64 dimensions | Preserve this mode only for deterministic conformance/unit testing. Use and evaluate real embeddings before claiming semantic recall in the connected demo. |
| Optional IDs do not supply tenant or goal-run isolation | [memoryRetrieval.ts](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/src/memoryRetrieval.ts) only filters `chatId`, and allows records without it | Authenticate a single sandbox tenant; filter authorized/current scope before ranking and prompt formatting. Add service, target and version applicability checks; fail closed on unknown mapping. Test with adversarial cross-scope records. |
| Querying changes ranking state | The same source touches `lastAccessed`/`accessCount` and logs reads | Recall is not operationally a pure read. Serialize it with writes; account for privacy and ledger growth. |
| Query-only access counters are not immediately durable | `query()` calls `store.touch()`, whose implementation does not persist | Reproduce a query → restart loss case and fix the persistence boundary if these fields affect our demonstrated behavior. |
| Store and ledger are separate writes | [memoryStore.ts](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/src/memoryStore.ts) overwrites `state.json`; [trustLedger.ts](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/reference/src/trustLedger.ts) appends JSONL separately | One writer, a durable private volume and backups are baseline. Add reconciliation/corruption detection and recovery tests; do not claim transactional crash safety or tamper-proof audit. |
| Supersession is not automatically complete | `add({supersedes})` records the forward link; retrieval penalizes `supersededBy`, which conflict resolution sets | An approved correction must update both lineage directions through audited store operations and the application envelope, then prove stale content is excluded from actionable context. |
| Enrichment is heuristic | Store source uses keyword classification, entity patterns and similarity relationships | Preserve source evidence. Similarity does not resolve cloud resource identity or authorize source corrections. |

The [H-MEM privacy guidance](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/docs/privacy-and-local-first.md) recommends privacy filtering before reinjection. GreenOps should store small synthetic/redacted findings, not raw credentials, private traces or hold-out labels. Disable automatic dreaming/sleep mutation for the first release; preview and reviewed corrections are sufficient.

### 4.4 Proposed private HTTP wrapper — ours

| Our route | Maps to reference behavior | Our additional controls |
|---|---|---|
| `POST /memory/remember` | Validated direct store; optional mining enrichment | Authenticated tenant, source receipt, envelope schema, duplicate-write key, scoped mapping, explicit persistence |
| `POST /memory/recall` | Retrieval and ranking services | Filter before scoring/reinjection, version applicability, real embedding provider, prompt-data boundary, returned memory/evidence IDs |
| `GET /memory/audit/{id}` | `ledger.history(id)` | Authorize the mapped record; redact sensitive query/source text |
| `GET /health` | Application health only; not supplied by H-MEM | Engine commit, storage readiness, embedding profile, no secrets |

These endpoints do not exist until implemented and must be documented in the canonical API reference. The reference has no built-in HTTP auth, rate limiting, TLS, API key, hosted persistence or managed service entitlement. Restrict the wrapper to the private Compose network and require service authentication; the browser never calls it directly. Persist memory outside container-ephemeral storage. An authenticated tenant field from a request body alone is not a trusted scope.

## 5. Minimal real embedding boundary and gated spike

Our proposed interface is `embed(texts, purpose, embedding_profile) -> vectors + provider receipt`, with `purpose` equal to `passage` or `query`. It is an application boundary, not a claimed H-MEM extension hook. The inspected H-MEM `embed(text)` is synchronous and hard-imported in store/retrieval modules. A remote async provider is **not** a drop-in constructor option.

Plan a narrow, attributed extension: await embedding generation before storage/query scoring, accept prepared vectors at those boundaries, and preserve H-MEM's ranking, provenance and ledger behavior. Record model ID, provider revision where available, dimensions, normalization and profile hash. Store and query vectors must share one compatible profile; re-embed when it changes. All similarity consumers, including relationship/conflict helpers, must use consistent vectors. Do not leave a hidden hash path inside connected semantic retrieval. Keep deterministic conformance tests separate from real-provider integration tests.

The official [NVIDIA hosted embedding reference](https://docs.api.nvidia.com/nim/reference/nvidia-nv-embedqa-e5-v5-infer) documents `POST https://integrate.api.nvidia.com/v1/embeddings`, Bearer authentication, and a model such as `nvidia/nv-embedqa-e5-v5`. It requires the appropriate `input_type` (`query` or `passage`), supports float encoding, and describes `truncate: NONE` as returning an error rather than silently discarding excess input. This is a documented candidate, not a selected or account-verified model.

The [NIM embedding response reference](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/reference.html) specifies indexed vector results, served-model identity and usage. Validate array length/order, finite numeric components and nonzero vector norm (zero-valued components are valid) and consistent dimensions; normalize before the reference's dot-product cosine calculation. Do not assume self-hosted NIM health/model endpoints are also exposed by the hosted gateway.

Smoke-test gate:

1. Obtain authorized model access and a spend cap; confirm the actual account model, endpoint and terms. Make one short passage call and one short query call, preserving redacted request IDs, model, usage, dimensions and duration.
2. Store several new synthetic experiment receipts through the actual H-MEM service. Include a failed capacity trial, a permitted exception, an unrelated target and a superseded policy.
3. Retrieve using a paraphrased question, not copied receipt text. Confirm the relevant permitted/current finding ranks above unrelated content; test at least ten fixed retrieval questions including an unknown case.
4. Restart the service and retrieve again. Show source IDs, ranking trace and durable history. Then change the policy version and show the obsolete finding cannot become actionable advice.
5. Deliberately remove provider access. Surface `MEMORY_EMBEDDING_UNAVAILABLE` with a clear incomplete/degraded status. Never silently swap to the hash embedder and still label output as connected semantic recall.

Final acceptance uses real calls and real persistence. The hash reference remains useful for repeatable formula/conformance tests; it is insufficient evidence for semantic relevance.

## 6. First integration spikes and required evidence

| ID | Task | Pass evidence | Failure action |
|---|---|---|---|
| SP-01 | Obtain assigned Zetaris deployment contract/auth profile | Redacted workspace/version record; successful allowed query and rejected unauthorized request | Resolve with Help Zetaris; do not fabricate a successful adapter |
| SP-02 | Query two independent sources through Zetaris | Known-answer join, source identities and independent count/totals reconciliation | Change to a supported reachable sample store while keeping two physical sources |
| SP-03 | Exhaust pagination and cleanup | More than 100 known rows retrieved exactly once; returned counts reconcile; query close recorded after success and failure | Fix the adapter before investigation logic depends on it |
| SP-04 | Reproduce source staleness/absence | Missing source, incomplete page and stale observation block unsafe conclusions | Correct evidence completeness semantics, not a generic success fallback |
| SP-05 | Pin and install H-MEM from a clean environment | Revision/licence manifest; reproducible dependency install; engine source named; no copied `node_modules` | Fix reproducibility before building the wrapper |
| SP-06 | Run reference tests and conformance | Genuine test output against chosen revision and our extension | Reproduce mismatch, fix contract, retain regression |
| SP-07 | Real embeddings and meaningful recall | Provider receipts, fixed retrieval eval, no hash path in connected mode | Keep semantic capability explicitly blocked until tested |
| SP-08 | Scope, provenance and version safety | Foreign-target/policy record never enters prompt; correct source mapping persists | Fix filter placement before scoring/reinjection |
| SP-09 | Restart, corruption and duplicate writes | Recall survives restart; duplicate receipt not duplicated; corrupted state detected/recovered honestly | Repair persistence/reconciliation; do not call JSON writes transactional |
| SP-10 | Sponsor value shown end to end | First investigation rejects a plan using federated evidence; later run recalls that failure and adjusts only when applicable | Revise actual workflow; do not add decorative sponsor badges |

The reference's [conformance suite](https://github.com/Meterless/Meterless/blob/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem/conformance/README.md) accepts an implementation exporting `HMEM`; it checks specified formulas, boundaries and service behavior. Passing it does not establish network authentication, privacy, crash recovery, semantic retrieval quality or cloud execution safety. Those remain our integration/acceptance tests.

## 7. Unresolved facts to carry into the build

- Team entitlement, workspace version and API-key/token behavior; Zetaris rate limits, query lifetime and page-number convention.
- Available source drivers, TLS/auth options, source ingress rules, GCS support and a keyless BigQuery credential option.
- Cross-source consistency guarantees and whether returned records carry any vendor query/source lineage beyond the published schema; our receipt must not claim vendor-supplied lineage it manufactured.
- The accepted hackathon interpretation of using/extending H-MEM's Apache-licensed reference, and any updated sponsor package in authenticated Resources.
- NVIDIA account model availability, price/credits, quotas, embedding profile, and the real-call ADK/model tool-use compatibility covered by the stack spike.
- Measured latency, retrieval relevance, clean-install portability and restart/recovery behavior: none has been measured in this documentation turn.

Keep these as explicit gates in the implementation plan. Public source verification is complete for the interfaces described here; account and runtime verification begins when implementation is authorized.
