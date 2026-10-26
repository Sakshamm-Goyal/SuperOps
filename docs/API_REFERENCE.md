# Application API reference

**Status: implemented v1 contract, 16 October 2026 (pre-event implementation — see [PREEXISTING.md](../PREEXISTING.md)).** Routes below exist in `greenops/api/app.py`; the generated schema is snapshotted at [docs/openapi.json](openapi.json) (`make openapi`) and checked against runtime routes and this file by `tests/unit/test_scenarios_and_contracts.py` and `make verify-docs`. Vendor contracts are separate in [sponsor research](research/SPONSOR_RESEARCH.md). Any route, field, auth or error change must update this file, the response models and the snapshot in the same change.

## Transport and identity

Application prefix `/v1`; JSON UTF-8; HTTPS outside localhost (TLS reverse proxy, see [OPERATIONS.md](OPERATIONS.md)). Sandbox bearer tokens (`Authorization: Bearer …`) are stored only as SHA-256 hashes in `actors` and map server-side to a named actor, tenant and role. Tokens are created by `scripts/bootstrap.py` and written once to the git-ignored `var/actors.local.json`. The browser never supplies actor or tenant. This is limited sandbox authentication, not an enterprise identity platform.

Roles: **viewer** reads scoped records; **operator** also starts investigations/trials, approves, revokes and executes within the sandbox scope; **admin** also reads `/v1/operations`. No admin mutation endpoint exists. The worker and memory sidecar use separate internal credentials (DB URL; `MEMORY_AUTH_TOKEN`). The holdout evaluator is an offline command (`make eval`) with a separate `EVALUATOR_MODEL_API_KEY`; it has no API role or route.

Every lookup is scoped to the actor's tenant; foreign or unknown IDs return 404. Missing/invalid token → 401 `AUTH_REQUIRED`; known actor without the role → 403 `FORBIDDEN`. Every mutating request requires `Idempotency-Key` (UUID): missing → 400 `MISSING_IDEMPOTENCY_KEY`, malformed → 400 `INVALID_IDEMPOTENCY_KEY`. The server binds actor + key to a canonical hash of method, route, path and body and stores the durable response (including 4xx error envelopes). The same request replays the stored response (header `Idempotent-Replay: true`); a changed body with the same key → 409 `IDEMPOTENCY_CONFLICT`. Concurrent duplicates serialize on the idempotency row. `X-Request-ID` (UUID) is optional; the server assigns one when absent or invalid and returns it on every response. It is not authorization.

Decimal quantities are JSON strings. Timestamps are UTC RFC3339. Collections return `{items, next_cursor, request_id}` (default limit 25, max 100; opaque cursor). Unknown request fields are rejected with 422.

## Routes

| Method and path | Permission | Request | Success and persistence |
|---|---|---|---|
| GET /health/live | Unauthenticated | None | 200 `{status:"live"}`; no dependency names |
| GET /health/ready | operator | None | 200 ready / 503 degraded: `{status, runtime_mode, dependencies{database, memory, memory_embedding_semantic, zetaris?, model?}}` |
| GET /v1/me | viewer | None | 200 `Resource` with the authenticated actor's id, display name, role, tenant, server runtime mode and write flag (no token data) |
| GET /v1/services | viewer | limit | 200 page of `{service_id, display_name, runtime_modes}` |
| POST /v1/investigations | operator | `CreateInvestigation`: service_id, question, interval{start,end}, runtime_mode, budget_profile_id, optional approved_trial_profile_id, optional memory_mode `on`(default)/`off` | 202 `{investigation_id, job_id, status:"QUEUED", status_url}`; investigation + first event + job committed before the response |
| GET /v1/investigations | viewer | service_id, status, cursor, limit | 200 page of queue summaries |
| GET /v1/investigations/{id} | viewer | None | 200 `Resource`: progress (stage, rounds, candidates used/cap), ordered plans, trials, actions, evidence IDs, federation receipt, forecast, memory recall, investigator report, outcome, feedback |
| GET /v1/investigations/{id}/events | viewer | after_sequence, limit (≤500) | 200 `{items:[{seq, at, kind, actor, payload}], next_sequence}` — persisted, monotonic; polling only |
| POST /v1/investigations/{id}/cancel | operator | reason | 202 `CANCEL_REQUESTED`; stops at the next safe stage boundary; in-flight provider work is not undone |
| GET /v1/plans/{id} | viewer | None | 200 `Resource`: immutable `core`, `canonical_json`, `plan_hash`, screening checks, critic verdict (with enforcement notes), impacts (labelled basis), memory_refs, trials, latest approval (an expired ACTIVE approval is lazily set EXPIRED and the plan returns to `AWAITING_APPROVAL`), `holdout_verdict` for AI plans, `recovery_scope`, `next_allowed_actions`, `blockers` |
| POST /v1/plans/{id}/trials | operator | plan_hash, suite_id (`support-dev-v1` for AI plans, `workload-wl-v1` for cloud plans), approved_trial_profile_id | 202 `{trial_id, status, status_url}`; holdout suites → 403; wrong suite → 422; plan not `DRAFT`+`ELIGIBLE_FOR_TRIAL` → 409 |
| GET /v1/trials/{id} | viewer | None | 200 `Resource`: status, trial_hash, checks, measured metrics, development per-case checks (development labels only), costs with usage basis |
| POST /v1/plans/{id}/approve | operator (AI plans also need a persisted holdout verdict) | `ApproveRequest`: plan_hash, trial_id, trial_hash, acknowledge_downtime, approved_recovery_scope | 201 `{approval_id, status:"ACTIVE", expires_at (server-set, policy TTL 15 min), plan_hash, trial_id, trial_hash, target, action, requires_downtime, recovery_scope}`; does not execute |
| POST /v1/approvals/{id}/revoke | operator | reason | 200 `REVOKED` before consumption (plan returns to `AWAITING_APPROVAL`); 409 after consumption; no automatic rollback |
| POST /v1/plans/{id}/execute | operator (the approving actor) | approval_id, plan_hash | 202 `{action_id, status, replayed_existing_action, status_url}`; consumes the approval atomically with action creation; a consumed approval returns the same action |
| GET /v1/actions/{id} | viewer | None | 200 `Resource`: factual status (incl. terminal `RESOLVED_MANUALLY` after the operator procedure), before/after, operation IDs, stage journal, verification checks, recovery, `memory_sync_status`, executor label |
| GET /v1/evidence/{id} | viewer | None | 200 `Resource`: query receipt (template/version, parameter hash, sources, request IDs, pages, completeness, result hash, close status), up to 500 source rows, labels; for `telemetry_series` also `series_hourly_peak` `[{hour, cpu_percent_max, memory_bytes_max, samples}]` over every row (peak-preserving chart view) |
| GET /v1/memories/{id} | viewer | None (id = application receipt id) | 200 `Resource`: envelope, sync status, engine id, sidecar audit history, current-policy applicability |
| GET /v1/overview | viewer | None | 200 dashboard read model from committed state: `{runtime_mode, service_id, generated_at, investigations{total, by_status}, plans{total, by_status}, savings{proposed_monthly_usd, blocked_monthly_usd, verified_monthly_usd, latest_investigation_id, basis}, carbon{proposed_monthly_kgco2e, basis}, rejections_by_check[{check_id, n}], memory{status, semantic, embedding_model, engine, engine_sha, records, pending, recalls, applicable_hits}, federation{mode, sources[{group, name}], receipts, last_receipt_at}, model{agent_model_id, copilot_model_id}, recent[{at, kind, investigation_id, actor, summary}], request_id}`. Savings are projections with the stated basis, never invoice savings; no agent run |
| POST /v1/copilot/messages | viewer | `CopilotMessage`: message (1–4000 chars), optional conversation_id, optional investigation_id (context) | 200 `CopilotReply` `{conversation_id, message_id, reply (markdown), model_id, tool_calls[{tool, input, ok, duration_ms}], citations[{kind, id, label}], suggested_prompts}`; both turns persisted in `copilot_messages`, the call recorded in `model_calls` (role `copilot`). Advisory only, see [Ops Copilot](#ops-copilot). 503 `DEPENDENCY_UNAVAILABLE` when `ANTHROPIC_API_KEY` is absent or the model is unavailable; foreign conversation → 404 |
| GET /v1/copilot/conversations/{id} | viewer (the conversation's own actor) | None | 200 `{conversation_id, investigation_id, messages[{message_id, role, content, at, tool_calls, citations}], request_id}` |
| GET /v1/reports/{id} | viewer | format=`json`\|`html` | 200 versioned report from committed state only (no agent run), with `content_hash` |
| GET /v1/operations | admin | None | 200 redacted readiness, policy/data versions, write flag, allowed targets, execution slot, active actions, jobs, outbox, budgets, trial profiles |
| GET /openapi.json | open when `APP_ENV=sandbox`; operator when `APP_ENV=hosted` | None | Generated schema |
| GET /docs | same as above | None | Swagger UI over the same schema |

Persisted event polling is the only progress channel; there is no SSE.

### Runtime modes and authority

`runtime_mode` must equal the server's configured mode (else 422); `replay` cannot create investigations (409). The server snapshots policy version, data manifest, budget profile and scenario `as_of` (= `interval.end`). It never accepts project IDs, spend caps or write flags from a request. `sample` runs can investigate and run trials (labelled sample) but approval returns 409 `INVALID_STATE` and execution is refused. Execution additionally requires `RUNTIME_MODE=connected_demo`, `SANDBOX_WRITES_ENABLED=true`, the target in `ALLOWED_TARGET_IDS` and an enabled executor (`local_analogue`; the GCP executor is not configured → 422 `UNSUPPORTED_ACTION`).

### Representative requests

```json
{"service_id": "support-demo", "question": "Find a testable saving while preserving service and support policy",
 "interval": {"start": "2026-09-30T00:00:00Z", "end": "2026-10-21T00:00:00Z"}, "runtime_mode": "connected_demo",
 "budget_profile_id": "sandbox-approved-budget-v1", "approved_trial_profile_id": "sandbox-trials-v1", "memory_mode": "on"}
```

```json
{"plan_hash": "sha256:<plan digest>", "trial_id": "<uuid>", "trial_hash": "sha256:<trial digest>",
 "acknowledge_downtime": false, "approved_recovery_scope": "restore_exact_pre_change_config_if_no_intervening_change"}
```

`acknowledge_downtime` must be true when `core.requires_downtime` is true (GCP resize plans); the local analogue reloads without downtime.

## Read model and error envelope

`Resource` = `{schema_version, id, status, runtime_mode, result_kind, data_origin, next_allowed_actions, blockers, request_id, data}`. Allowed actions (`run_trial`, `approve`, `execute`, `revoke_approval`, `cancel`) are computed server-side and revalidated on POST. Plans, trials, approvals and actions keep separate statuses.

```json
{"error": {"code": "APPROVAL_STALE", "message": "the target or policy changed since approval",
           "details": {"reason": "TARGET_VERSION_CHANGED"}, "retryable": false, "request_id": "<uuid>"}}
```

| HTTP | Stable error codes |
|---|---|
| 400 | INVALID_CURSOR, INVALID_IDEMPOTENCY_KEY, MISSING_IDEMPOTENCY_KEY |
| 401 / 403 / 404 | AUTH_REQUIRED, FORBIDDEN, NOT_FOUND |
| 409 | PLAN_CHANGED, APPROVAL_STALE, APPROVAL_EXPIRED, IDEMPOTENCY_CONFLICT, TARGET_BUSY, INVALID_STATE |
| 422 | VALIDATION_ERROR (including timezone-less timestamps), EVIDENCE_INCOMPLETE, TRIAL_NOT_ACCEPTED, UNSUPPORTED_ACTION, BUDGET_NOT_CONFIGURED, HOLDOUT_VERDICT_REQUIRED (AI promotion without a ROLLOUT_ELIGIBLE frozen holdout verdict for this exact candidate config and model) |
| 503 | DEPENDENCY_UNAVAILABLE, MEMORY_NOT_READY (surfaced on investigation/action records; readiness returns 503) |
| 500 | INTERNAL_ERROR with request id; never SQL, credentials or stack traces |

An action that later fails or becomes uncertain stays readable with 200 and its factual status. An HTTP timeout after a POST does not prove failure: retry with the same key or read the action. Budget exhaustion during a run ends the investigation `NEEDS_REVIEW` with `BUDGET_EXCEEDED` in `outcome.error`; there is no 429 route in P0.

## Ops Copilot

A conversational DevOps assistant on Claude Haiku 4.5 (`COPILOT_MODEL_ID`, default `claude-haiku-4-5-20251001`; key `ANTHROPIC_API_KEY`). It is advisory and holds no authority:

- **API tools** call only allowlisted GET routes of this API, in-process, with the caller's own bearer token, so it reads exactly what the caller may read: investigations (+events), plans, trials, actions, evidence, memories, reports, overview, me, and operations (admin callers only). Any other path is refused before the call.
- **recall_memory** runs scoped Meterless H-MEM recall with the same application-side applicability re-checks as investigations.
- **query_evidence** runs one reviewed SQL template with validated parameters through the configured evidence path (Zetaris federation in `connected_demo`, the labelled sample database otherwise). Results are returned to the conversation and are not stored as investigation evidence.
- No tool can start, approve, revoke, execute or cancel anything. Replies cite the records they used. Model text is never parsed for authority.

## Private memory wrapper (memory-sidecar/)

Our private routes, not Meterless vendor endpoints. Bearer `MEMORY_AUTH_TOKEN` on every route, single writer, strict envelopes (unknown fields → 422), 64 KiB body limit. Full details in [memory-sidecar/README.md](../memory-sidecar/README.md).

| Route | Contract |
|---|---|
| POST /memory/remember | MemoryEnvelope → 201 `{engine_memory_id, application_receipt_id, stored_at, embedding_profile, persisted:true, duplicate:false}`; same receipt + same hash → 200 `duplicate:true`; crash-orphan adoption, or re-creation of a missing engine record for an indexed receipt with the same hash → 201 `duplicate:true, reconciled:true`; `persisted:true` is returned only after the record is read back from disk (otherwise 500 `MEMORY_WRITE_FAILED`); different hash → 409 `IDEMPOTENCY_CONFLICT`; orphan with different content → 409 `ORPHAN_CONFLICT`; correction without review → 422; superseded record already superseded → 409 `SUPERSESSION_CONFLICT`; provider failure → 503 `MEMORY_EMBEDDING_UNAVAILABLE` (nothing written) |
| POST /memory/recall | scope + query + applicability + top_k ≤10 (+ threshold) → `{items (applicable), historical (with inapplicable_reasons), excluded_unscoped, trace, embedding_profile}`; scope filtered before scoring |
| GET /memory/audit/{receipt_id}?tenant_id=&service_id= | Scoped ledger history, lineage, limitations; foreign scope → 404 |
| POST /memory/reindex | Re-embed every record under the configured profile after a profile change |
| GET /health | `{status: ready\|degraded\|unavailable, reasons (e.g. INDEX_ENGINE_MISMATCH, ENGINE_RECORD_MISSING, EMBEDDING_PROFILE_MISMATCH, MEMORY_STATE_CORRUPT), engine{package, version, upstream_sha}, embedding_profile{kind, semantic, …}, store{…, reconcilable_orphans, missing_engine_receipt_ids}}`; 200 only when ready |

Recall and audit never expose holdout data or grant actions. The application re-checks scope and applicability on every returned memory before use and never reconstructs an approval or action from memory.

## Version preconditions and trial profiles

Plan hash, the target's current config version, policy version, data manifest, workload file hash (cloud) and the AI model id plus artifact hashes (workflow + prompt + policy text; verifier + development cases/records + manifest) are mutation preconditions. They are checked at approval and again by the worker immediately before the first write. At that point the worker also re-checks current authority: approving actor enabled with an operator role, approval consumed by this action, target still in `ALLOWED_TARGET_IDS`. A target version counts as the action's own only if its recorded writer is the action's operation identity and its content is the approved change. Foreign changes are never claimed or overwritten, and the action ends `RECOVERY_REQUIRED` until an operator runs `make resolve-action`. Trial profiles are created only by the operator command `make trial-profile-approve PROFILE=… ACTOR=…` (authenticated, fixture-separation checked, hash + expiry stored); editing the profile file invalidates it.
