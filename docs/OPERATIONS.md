# Operations and access runbook

Status: implemented pre-event (16 Oct 2026). The commands below exist (`Makefile`, `scripts/`). No deployment, provider credentials or account limits have been verified. Docker Compose is written but has not been run, because Docker was unavailable.

## Runtime modes

| Mode | Data and behavior | Allowed claims/actions |
|---|---|---|
| sample | Local synthetic fixtures, deterministic UI/domain examples | Development usability only; no sponsor/model integration claim; writes disabled |
| connected_demo | Real Zetaris, real H-MEM + embeddings and actual model calls, synthetic permitted records | Sponsor integration evidence; allowlisted sandbox actions after approval |
| replay | Persisted redacted outputs from a named prior run | Show prior measurements and receipt time; no new model/query/action claim; writes disabled |

Mode is server configuration attached to every run, not an unrestricted browser toggle. Switching mode creates a new run and cannot reuse an active approval across environments. Never fall back silently from connected_demo to sample/replay when a dependency fails. A real local executor remains an explicitly named local analogue within connected_demo, not a GCP change.

## Concrete P0 executor and trial boundary

Default executable target: a dedicated synthetic workload worker with a versioned `max_concurrency` setting and a fixed queue/request dataset. Trial fixtures use separate worker instances/config namespaces to measure baseline and candidate settings with identical workload. The executor updates only the allowlisted worker's active configuration using compare-and-set, and subsequent runs report the configuration hash they actually loaded. Verify fresh workload success, latency and read-back. Recovery restores the previous configuration only if no intervening version exists.

This proves an actual local configuration change and its performance effect. It does not reduce a GCP VM invoice or prove a VM resize; cloud cost/carbon remains separately projected from the synthetic resource scenario. Do not label concurrency reduction as measured CPU-capacity reduction. An optional GCP executor operates only on a team-owned disposable VM after access and compatibility gates; its resize sequence and downtime must be tested independently.

Before agent-invoked trials, an operator creates a versioned **trial profile**: exact disposable fixture identity distinct from the final action target, allowed parameter ranges/operations, workload hash, maximum runtime/spend, recovery/reset scope and expiry. The application authenticates and stores that setup authorization. A trial request can select that profile but cannot change it. Mutations outside it require a separate exact plan approval. GCP trial fixtures require their own provisioned permissions; no trial can quietly resize the final target before approval.

One durable global P0 execution slot covers mutating trials, actions and recovery, in addition to per-target locks. An unknown effect retains the slot until reconciled. Read-only investigations and model trials without target mutations may run within budgets. Trial timing is separate from evidence/proposal timing: a local paired trial gets a 15-minute cap, with enough room for three paired 60-second measurement runs and warmup; optional GCP timing is explicit and finite.

## Evaluator and correction commands to implement

These are proposed operator command contracts, not installed commands. `make trial-profile-approve PROFILE=<reviewed-profile>` authenticates a named operator, verifies exact fixture ownership and separation from action targets, and stores the profile hash, expiry, scope and approval receipt. Editing the profile invalidates its approval. No model can call this approval command. `make eval` uses evaluator-only credentials and schema/storage inaccessible to the application agent and its Zetaris source views. Public trial endpoints accept development suites only. The final evaluator can export aggregate quality/cost metrics and a redacted report after candidate freeze; per-case keys stay private and cannot be recalled by H-MEM.

`make memory-correction-preview RECEIPT_ID=<id>` must show the original receipt, proposed evidence-backed correction, both supersession links and all affected applicability scopes. `make memory-correction-apply REVIEW_ID=<id>` requires a named authenticated operator, immutable reviewed correction hash and current source evidence; it persists the review/correction/outbox atomically in PostgreSQL. The sidecar applies both lineage directions idempotently and records audit linkage. A changed correction hash needs a new review. This workflow corrects learning only; it cannot alter a historical action receipt or authorize execution. Add HMEM-04 coverage before marking the command ready.

## Access inventory

| Capability | Needed information | Secret handling | Readiness proof |
|---|---|---|---|
| Zetaris | Workspace/version, org ID, token/auth flow, connectors, limits | Secret reference, scoped query token; no token in receipts | Authorized query across two reachable sources and query cleanup |
| Source A/B/C | Approved host/network/TLS, read-only views, source credentials | Separate least-privilege roles, no laptop DB public exposure | Schema discovery + bounded query + independently reconciled totals |
| Meterless | Pinned SHA, notices, writable durable volume, wrapper auth | Private network and distinct internal token | Store/recall/audit, restart and controlled failed-write behavior |
| Embeddings | Accessible endpoint/model, input mode, dimension and limits | Provider secret server-side | Real insert/query vector profile and paraphrase/scoping eval |
| NVIDIA generation | Available model ID, tool/structured-output behavior, usage/pricing | Server-side scoped key | Actual tool cycle with latency/usage receipt |
| Application DB | Dedicated database, migrations, least-privilege runtime user | Secrets injected; DB port private | Migration + transactional job/approval/action test |
| Executor | Team-owned disposable target, allowed action, write budget/window | Restricted executor identity only | Read identity/health and later explicitly approved scoped change |
| UI/operator | Named roles/tokens, TLS origin | No secrets in query strings or browser logs | viewer cannot approve; operator scoped to sandbox |

Public documentation proves an interface, not the team's entitlement. Check HackOS sponsor folders and announcements through the user's authorized access. Never infer credits, quotas or credentials from sponsorship.

## Configuration contract

Variable names below are application proposals except where an adapter explicitly maps a documented provider variable. Actual `.env.example` is created during implementation with safe blanks and field descriptions; no real value belongs in Git.

| Setting | Purpose / safe initial policy |
|---|---|
| APP_ENV, RUNTIME_MODE | sandbox and sample initially |
| DATABASE_URL | Private PostgreSQL connection |
| ZETARIS_WORKSPACE_URL, ZETARIS_ORG_ID, ZETARIS_CREDENTIAL_REF | Confirmed workspace and secret lookup |
| MEMORY_BASE_URL, MEMORY_AUTH_TOKEN, HMEM_DATA_DIR | Private wrapper, auth and durable storage |
| EMBEDDING_BASE_URL, EMBEDDING_MODEL_ID, EMBEDDING_CREDENTIAL_REF | Real provider and profile; reject mismatched dimensions |
| MODEL_BASE_URL, MODEL_ID, MODEL_CREDENTIAL_REF | Tested NVIDIA adapter configuration |
| CLOUD_WRITES_ENABLED | false until operator has configured and authorized the sandbox |
| EXECUTOR_MODE, ALLOWED_TARGET_IDS | local_sandbox or gcp_sandbox; exact target allowlist |
| GOOGLE_CLOUD_PROJECT | Team-owned project only, if selected |
| POLICY_VERSION, DATA_MANIFEST_ID | Immutable run inputs; edits invalidate applicable plans/approvals |
| MAX_RUN_COST_USD, MAX_DAILY_COST_USD, MAX_TRIAL_SECONDS | Team-set numeric caps; absent cap blocks charged runs |
| OPERATOR_CREDENTIAL_REF, VIEWER_CREDENTIAL_REF | Distinct server-side role mapping |
| CARBON_METHOD_VERSION | Bounded approved estimator or unavailable |

Budgets are not hardcoded invented sponsor allowances. Before each charged operation reserve its conservative maximum estimate transactionally; reconcile actual usage after completion. Include retries, embedding/mining, optimizer, trials, hosting and cloud downtime/recovery. Missing rate/usage data means uncertain cost; either use an explicitly approved conservative bound or block new spend. A spend cap cannot reverse charges already incurred.

## Startup and release sequence

1. Check exact release commit/lockfiles, compatibility manifest, private configuration and runtime mode.
2. Start PostgreSQL and migrate; snapshot existing state before upgrades.
3. Start sidecar with its dedicated durable volume; check embedding profile, restore/reconcile if required, then run the real readiness check.
4. Start API and worker with writes disabled. Inspect DB/job/outbox recovery and existing pending actions before accepting new work.
5. Verify sponsor/network/model health using bounded permitted requests; then start UI and verify viewer/operator separation.
6. Run connected acceptance and record results. Enable exact sandbox write scope only after review; changing a flag alone is not an approval.
7. Capture the serving commit, image digests, policy/data versions, readiness state and smoke run ID. A successful container start is not an end-to-end pass.

Only publish the UI/API through a TLS reverse proxy. Keep DB, sidecar and worker ports private. One worker and one sidecar writer are the supported topology. Durable disk persists across process/container restarts, not necessarily host loss; backups and restore tests are still needed. Cloud Run stateless components are optional later; don't put authoritative memory solely on ephemeral filesystems.

## Failure handling

| Failure | Required response |
|---|---|
| Zetaris query times out/returns partial pages | Close query if possible, mark incomplete receipt, bounded retry of read, block dependent validation |
| Model/embedding rate limit | Honor retry guidance within cap; preserve usage/attempt; finish incomplete if exhausted |
| H-MEM unavailable before investigation | Expose degraded state; do not claim memory-aware run or validate memory-dependent action |
| Memory publication fails after successful action | Preserve VERIFIED action; show sync pending; outbox retries idempotently; no repeated action |
| Worker crashes before a provider write | Reconcile journal and target; resume only when absence of effect is established |
| Provider write times out | Persist unknown outcome; poll operation/read target; never blind retry |
| VM running but health check fails | PENDING_VERIFICATION then RECOVERY_REQUIRED; running is not healthy |
| Recovery allowed and state unchanged since failed transition | Restore only approved prior config, verify again; record recovery outcome |
| Human/other actor changed target | Stop automated restoration and surface conflict; preserve evidence |
| Disk full/corrupt memory JSON/ledger | Mark sidecar unavailable, stop writes, restore validated snapshot; never reset history silently |
| Application DB unavailable | Reject new mutations, preserve external operation IDs in recoverable execution mechanism; reconcile before resume |

Do not hold a database transaction open for the entire cloud operation. Persist action intent first. If DB loss occurs after the provider call, the operation can have succeeded; dedicated target identity and provider read-back are mandatory recovery inputs. A secondary redacted local action journal may aid recovery, but is not a substitute for reconciliation and must not become a competing authority.

## Observability and evidence

Use structured logs/events with request_id, investigation_id, plan_hash, trial_id, action_id, stage, actor ID, source receipt, attempt, duration, cost completeness, model/config versions and safe error code. Never log tokens, connection strings or unrestricted prompts containing secrets. Record model tool calls and concise decision summaries; do not display private reasoning as evidence.

Track dependency readiness, query completeness, job age, lease recovery, outstanding actions, memory outbox lag, unknown write outcomes, trial failures, cost reservations versus actual and UI-visible time to first progress. Persist monotonic run event sequence. Check status through a read API after reload; a toast alone is not a receipt.

## Backup, reset and retention

Back up PostgreSQL and a quiesced H-MEM directory at each release and before migrations; include manifest SHA, engine/vector/schema versions and restore instructions. Test restore to a separate sandbox volume. The JSON/JSONL reference is not assumed crash-atomic or tamperproof; test acknowledge→kill→restart and fail-closed corruption handling.

For P0, retain redacted synthetic evidence through judging and team review; proposed default deletion review is 30 days after results. Do not promise a legal retention period. Keep only necessary fictional records; delete temporary credentials on revocation. Deleting a record requires corresponding memory/index/export handling or explicit tombstone/inapplicable state. No production personal data is allowed into the initial demo.

Reset is restricted to exact demo namespaces/volumes and must refuse active/unknown actions. Preserve the final submission evidence before reset. Never run broad cloud cleanup or delete shared data based on a model suggestion.

## Clean checkout acceptance

A second builder uses a new checkout and new local volumes, follows README without hidden files, supplies their authorized credentials securely, starts sample mode, then runs the real connected path. Verify migrations, sponsor network, memory restart, model/tool round trip, UI reload, one approved sandbox action, report download and documented failure modes. Record commit/platform/runtime and timed setup steps. If a judge cannot receive sponsor credentials, provide explicit sample/replay instructions plus genuine connected receipts; do not claim the sample proves mandatory integration. Verify organizer access requirements separately.
