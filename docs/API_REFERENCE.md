# Application API reference

**Status: proposed v1 contract, not implemented.** This is the canonical intended application API. No route below is claimed to exist today. Vendor contracts are separate in [sponsor research](research/SPONSOR_RESEARCH.md). During implementation, generate OpenAPI from FastAPI/Pydantic schemas and keep this file, response models, permission checks and Swagger examples accurate in the same change.

## Transport and identity

Application prefix `/v1`; JSON UTF-8; HTTPS outside localhost. A sandbox API uses distinct high-entropy bearer credentials mapped server-side to named actors/roles in the single tenant. Never use a browser-supplied `X-Actor` or tenant field as identity. UI server keeps session-bound API credentials private. This is limited sandbox authentication, not an enterprise identity platform. Public judge role has read-only access to approved demo records.

Roles: **viewer** reads scoped records; **operator** starts investigations/trials and approves/executes within configured sandbox scope; **admin** also reads operations configuration and changes deployment settings through the documented configuration procedure. No admin mutation endpoint in P0. Worker and memory sidecar use separate internal credentials. Final heldout evaluation runs through an offline evaluator command using separate evaluator-only credentials; it has no public API role or trial route. Agent and operator trial tools can choose only allowlisted development suites. Trial GET returns redacted development checks; heldout details are never exposed to normal actors, and final published aggregates require an explicit evaluator export.

Every resource lookup enforces tenant and service scope. Foreign/unknown IDs return 404. Missing/invalid token returns 401; known actor without permitted role returns 403. Every mutating request requires `Idempotency-Key` (UUID); missing keys return 400 MISSING_IDEMPOTENCY_KEY before creating work. The server binds actor + method + route + key to canonical request hash and durable response. Same request replays the original resource; changed body with same key returns 409. `X-Request-ID` is a validated optional caller correlation UUID; server assigns one when absent and returns it. It is not authorization or the same as an execution idempotency key.

Decimal quantities are JSON strings with units/currency. All timestamps are UTC RFC3339. Collection responses use `{items,next_cursor}` with default limit 25, maximum 100; cursors are opaque and scoped. Unknown request fields rejected. Request size/time limits are configured and documented in OpenAPI when implemented.

## Routes

| Method and path | Permission | Request | Success and persistence |
|---|---|---|---|
| GET /health/live | Unauthenticated | None | 200 minimal process status; no dependency names or secrets |
| GET /health/ready | Internal/operator | None | 200 ready or 503 degraded; mode-specific dependencies |
| GET /v1/services | viewer | cursor, limit | 200 service IDs/display names and supported runtime modes |
| POST /v1/investigations | operator | service_id, question, interval, runtime_mode, budget_profile_id, optional approved_trial_profile_id | 202 `{investigation_id,job_id,status,status_url}` persisted before response |
| GET /v1/investigations | viewer | service_id, status, cursor, limit | 200 scoped queue summaries |
| GET /v1/investigations/{id} | viewer | None | 200 run state, progress, candidates, evidence IDs and limitations |
| GET /v1/investigations/{id}/events | viewer | after_sequence, limit | 200 ordered persisted events + next_sequence; simple polling in P0 |
| POST /v1/investigations/{id}/cancel | operator | reason | 202 cancellation requested; no implication that in-flight provider work was undone |
| GET /v1/plans/{id} | viewer | None | 200 immutable versioned plan, trial refs, eligibility and stale reasons |
| POST /v1/plans/{id}/trials | operator | plan_hash, development suite_id/version, approved_trial_profile_id | 202 trial_id/job_id; rejects holdout suites; enforces distinct disposable trial target, allowed typed operations and finite budget |
| GET /v1/trials/{id} | viewer | None | 200 status, checks, metrics, costs and redacted artifact refs |
| POST /v1/plans/{id}/approve | operator | plan_hash, trial_id, trial_hash, acknowledge_downtime, approved_recovery_scope | 201 approval_id, ACTIVE, server expiry, exact scope; fails unless current validated evidence matches |
| POST /v1/approvals/{id}/revoke | operator | reason | 200 REVOKED before consumption; 409 after consumption; no automatic rollback |
| POST /v1/plans/{id}/execute | operator | approval_id, plan_hash | 202 action_id/job_id or original action on replay; revalidates worker-side again |
| GET /v1/actions/{id} | viewer | None | 200 factual stage, before/after, operation refs, verification, recovery and memory sync |
| GET /v1/evidence/{id} | viewer | None | 200 redacted source receipt and authorized underlying records |
| GET /v1/memories/{id} | viewer | None | 200 learning provenance, applicability and redacted audit, not internal secret state |
| GET /v1/reports/{investigation_id} | viewer | format=html or json | 200 versioned evidence report generated from committed state; no new agent run |
| GET /v1/operations | admin | None | 200 redacted dependency readiness, active policy/version, budgets and action flags |
| GET /openapi.json | operator in hosted deployment | None | 200 generated schema; accessible locally for development |
| GET /docs | operator in hosted deployment | None | 200 Swagger UI using the same authenticated schema endpoint |

Do not add SSE solely for animation; persisted event polling is enough for P0 and survives Streamlit reruns. Any future streaming endpoint must define reconnect, event ordering, auth and error semantics here.

## Representative requests

Illustrative values below are synthetic examples. Example IDs/hash strings are placeholders; runtime must use generated valid values.

```json
{
  "service_id": "support-demo",
  "question": "Find a testable saving while preserving service and support policy",
  "interval": {"start": "2026-10-01T00:00:00Z", "end": "2026-10-22T00:00:00Z"},
  "runtime_mode": "connected_demo",
  "budget_profile_id": "sandbox-approved-budget-v1"
}
```

The service, budget and optional approved trial profile must exist and be permitted to the actor. Without a trial profile the investigation is read-only and cannot dispatch a mutating trial. The only runtime modes are sample, connected_demo and replay; the requested mode must match server policy. sample/replay cannot approve, execute or claim connected trials. The read model uses result_kind=measured|projected|estimated|unknown and data_origin=synthetic|real_permitted from DATA_AND_DOMAIN. The server snapshots policy, source manifest, budget and scenario `as_of`; it does not accept arbitrary cloud project IDs, spend caps or write flags from this request. A connected historical scenario cannot authorize a real target without fresh target inspection and an appropriate matched trial.

```json
{
  "plan_hash": "sha256:<generated-plan-digest>",
  "trial_id": "<uuid>",
  "trial_hash": "sha256:<generated-trial-digest>",
  "acknowledge_downtime": true,
  "approved_recovery_scope": "restore_exact_pre_change_config_if_no_intervening_change"
}
```

Approval does not automatically execute. Return target, before/after, evidence/trial IDs, downtime, expiry and recovery scope for review. `acknowledge_downtime=false` is valid only where the plan requires no such acknowledgment; never default user acknowledgment to true. Approval of recovery does not permit unrelated cleanup or reverting subsequent human changes.

## Read model and error envelope

Run responses include schema_version, id, status, progress stage, updated_at, evidence IDs, `runtime_mode`, `result_kind`, `data_origin`, `next_allowed_actions`, blockers and request_id. Compute allowed actions server-side; revalidate them on POST. Every plan/action exposes distinct trial, approval, execution, verification and memory-sync status so a successful request cannot masquerade as a completed change.

```json
{
  "error": {
    "code": "APPROVAL_STALE",
    "message": "The target configuration changed after approval.",
    "details": {"reason": "TARGET_VERSION_CHANGED", "action_id": null},
    "retryable": false,
    "request_id": "<uuid>"
  }
}
```

| HTTP | Stable error codes and behavior |
|---|---|
| 400 | INVALID_CURSOR, INVALID_IDEMPOTENCY_KEY, MISSING_IDEMPOTENCY_KEY; no job created |
| 401 / 403 / 404 | AUTH_REQUIRED, FORBIDDEN, NOT_FOUND; redact existence across scopes |
| 409 | PLAN_CHANGED, APPROVAL_STALE, APPROVAL_EXPIRED, IDEMPOTENCY_CONFLICT, TARGET_BUSY, INVALID_STATE; no new write |
| 422 | VALIDATION_ERROR, EVIDENCE_INCOMPLETE, TRIAL_NOT_ACCEPTED, UNSUPPORTED_ACTION, BUDGET_NOT_CONFIGURED |
| 429 | RATE_LIMITED, BUDGET_EXCEEDED; include safe Retry-After only where meaningful |
| 503 | DEPENDENCY_UNAVAILABLE, MEMORY_NOT_READY; no silent fixture fallback |
| 500 | INTERNAL_ERROR with correlation ID; never raw SQL, credentials or provider stack trace |

For the same actor and consumed approval, execute with a new idempotency key returns the existing action when plan/scope match; a changed plan returns 409. Different actors cannot replay or consume another actor's approval and receive 403. Approval/action uniqueness prevents a second operation chain irrespective of key. The worker checks expiry again immediately before the first provider write; expired queued work fails without mutation even though approval is already marked consumed.

If a queued action later fails or becomes uncertain, its GET resource remains 200 with factual status/error details. Do not return 500 for every non-VERIFIED action. An HTTP timeout after a POST does not prove the operation failed; retry with the same idempotency key or read the known action.

## Private memory wrapper

These are **our private routes**, not Meterless vendor API endpoints. Internal auth, strict envelope schemas, single writer and durable persistence are mandatory. Caller must supply an application receipt identity; wrapper response contains engine IDs, data version and sync state.

| Route | Contract |
|---|---|
| POST /memory/remember | MemoryEnvelope → engine_memory_id, application_receipt_id, stored_at, embedding_profile, persisted acknowledgment |
| POST /memory/recall | tenant/service scope + query + applicability versions + bounded top_k → candidate IDs, scores, reasons and provenance; caller filters again |
| GET /memory/audit/{id} | Scoped audit history, linked source receipts, correction relations and limitations |
| GET /health | Authenticated internal readiness, engine SHA, embedding profile and durable-store status |

Audit and recall do not expose holdout keys or grant actions. The wrapper must not claim a successful durable write until actual persistence completes. Schema migrations, vector profile changes and recovery failures return explicit unavailable/degraded status.

## Version preconditions and trial profiles

Plan hashes, current target/config versions and accepted trial hashes serve as explicit mutation preconditions; a client cannot resubmit a changed desired state under an older plan ID. Supported action types and fields are the discriminated union in DATA_AND_DOMAIN. Trial-profile setup is an authenticated operator command documented in OPERATIONS, with immutable profile hash, fixture identity, scope, budget and expiry. This authorizes only disposable trials and never substitutes for approval of the final target.

## OpenAPI implementation gate

Implement typed request/response/error models, security schemes, role descriptions, status codes, pagination, examples and enum values. Snapshot the generated schema and test representative requests against it; ensure every implemented route appears and no nonexistent route is advertised. Validate `/docs` and `/openapi.json` under local and hosted auth. Any intentional deviation from this proposal updates this file and the decision log before merging. API docs are part of API correctness. [FastAPI OpenAPI support](https://fastapi.tiangolo.com/features/).
