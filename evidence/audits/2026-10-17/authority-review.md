# GreenOps Verify authority/API/worker audit — 17 October 2026

Read-only application audit. No application source, user database or user configuration was changed. The harness used uniquely named temporary PostgreSQL databases, fresh temporary sandbox directories and local sandbox processes on port offset 6000. It used the existing sample evidence database read-only and labelled scripted role/support responses; it made no paid model/sponsor/cloud calls. Both harness runs completed with exit 0, dropped their databases and stopped their subprocesses.

Command (from repository root):

```sh
PYTHONPATH="$PWD" .venv/bin/python /tmp/greenops_authority_audit_2.py
```

Artifacts: `/tmp/greenops_authority_audit.py`, `/tmp/greenops_authority_audit_2.py`, `/tmp/greenops-authority-audit-results.json`, `/tmp/greenops-authority-audit-results-2.json`, `/tmp/greenops-authority-audit-2.log`. Harness failures are asserted directly for prerequisite flows; finding outputs are factual receipts, not a claim that the defects pass acceptance.

## Prioritized findings

### P1 — Reconciliation can overwrite a human's intervening configuration

Location: `greenops/services/execution.py:214-221`, then `:174-177`.

After an action has persisted intent but crashed before its own CAS, reconciliation treats any `expected_version + 1` as this action's write. It does not verify an action operation/idempotency marker or even the expected desired configuration before claiming ownership. Verification correctly detects the wrong configuration, but recovery then rolls it back because it also checks only version.

**Reproduced against real local process and PostgreSQL:** plan approved 8→4 at v1; mark action EXECUTING (intent persisted, no action write); unrelated actor writes concurrency 6 at v2; call execution.run. Result: action **RECOVERED**, target **8 at v3**. The external value 6 is overwritten, violating conflict-aware recovery. No mock executor or health result was used.

Fix direction: stamp a durable unique action/operation identifier in the atomic target write and reconcile using both ownership and full expected content; a non-owned v+1 must produce RECOVERY_REQUIRED without a compensating write. Add the exact crash-before-write/external-CAS regression.

### P1 — First-write worker checks ignore revoked actor and target authorization

Location: `greenops/services/execution.py:111-131`; the corresponding HTTP allowlist gate exists at `greenops/services/approvals.py:123-124` only.

The worker rechecks expiry, runtime/write flag and partial version state, but not whether the actor is still enabled/in-role/in-scope, whether the target remains allowlisted, or whether the executor remains permitted. A queued job survives an administrative authorization change.

**Reproduced:** approve and queue AI change; disable approver in actors; run worker with allowed_target_ids=(); action returned **VERIFIED**, config changed **v1→v2**. The freshly started worker had an empty allowlist, so this is not simply a long-lived Settings cache.

Fix direction: reload and validate current actor/scope plus configured target/executor permission at the first external write while holding authority state; record a zero-write denial. Regression should test actor revocation and target removal independently.

### P1 — An unresolved action is marked as a successful job and can retain the global mutation slot forever

Location: `greenops/services/execution.py:207-211`, `greenops/worker/main.py:56-61`; recovery enqueue runs only at startup at `:21-30`.

On an unreadable target after interruption, reconcile returns the existing EXECUTING/PENDING state and intentionally retains the slot. worker.step treats every result except WAITING_FOR_SLOT as successful, so no durable retry remains. Ordinary subsequent worker steps cannot reconcile it even after the target is restored; unrelated mutations remain blocked until an operator restarts the worker.

**Reproduced:** queued action marked EXECUTING; temporarily move only its isolated config file away; step; restore file; step again. Result: action **EXECUTING**, job **SUCCEEDED**, execution_slot still points to action; second step returns **false**. This is an actionable recovery deadlock, not just an untested source risk.

Fix direction: distinguish terminal completion from pending reconciliation; persist a bounded requeue/reconciliation schedule retaining the slot and diagnostic state. Handle unexpected action-stage exceptions similarly; current startup-only sweep does not repair live worker failures.

### P1 — AI approvals can outlive the model/workflow/evaluator versions that were tested

Location: `greenops/services/approvals.py:40-49`; plan bindings at `greenops/services/plans.py:82-86`; requirement at `docs/DATA_AND_DOMAIN.md:92`.

versions_current validates policy, cloud workload hash and target config version only. AI model_version, workload_version, test_version and data_manifest_id are never compared. A trial run on an earlier model or verifier can authorize a change while execution instantiates the current model and uses only three smoke cases.

**Direct pure precondition reproduction:** use an AI plan with model_version=old-model, workload_version=old-workflow, test_version=old-tests and matching actual target version, but Settings model_id=audit-different-model. versions_current returns **(True, None)**. No provider call was attempted. Source trace confirms the same function governs both approval and first-write gates.

Fix direction: compare all relevant persisted hashes/version identifiers against actual current model/workflow/dev dataset/records/policy/verifier and config; stale trials require a fresh trial. Hash actual files, not only a manually edited manifest string.

### P2 — Expired approval leaves its plan in a permanent dead end

Location: `greenops/services/approvals.py:115-117`, `:89-92`, `:64`; `greenops/domain/approval.py:28-29`.

Execute sets only the approval EXPIRED, leaving plan APPROVED. A new approve requires AWAITING_APPROVAL and revoke requires ACTIVE; there is no reset/renew endpoint. This directly contradicts the returned instruction “a new approval is required.” A queued action expiring before its first write leaves a related consumed-plan dead end.

**Reproduced via API with real DB:** initial approve 201; expire DB timestamp; execute 409 APPROVAL_EXPIRED; reapprove 409 `plan is APPROVED, not AWAITING_APPROVAL`; revoke 409; GET plan status APPROVED and next_allowed_actions=[].

Fix direction: atomically expire approval and return the unchanged valid plan to a reviewable state, or define an explicit renewal transition; preserve invalid/stale trial gates. Test expiry before request and while queued, including retry/reapproval UX.

### P2 — Budget contract is not fully enforced

Source evidence: `greenops/services/execution.py:64-65` runs AI verification with budget=None and does not persist usage; `greenops/services/trials.py:141-159` ignores ai_dev_suite max_model_calls/max_cost_usd/max_seconds; `greenops/config.py:132` parses MAX_DAILY_COST_USD but there are no reads elsewhere; `greenops/services/investigation.py:55-61` constructs per-run budget from recorded usage only; `greenops/services/trials.py:176-180` records AI usage only after a complete suite.

The documented daily cap cannot stop any call. AI trial profile-specific bounds and its wall deadline are not used. Verification calls run outside the investigation cap/accounting. A crash/exception during a suite loses the already-reserved call count because reservations are in memory. `docs/OPERATIONS.md:62` says absent caps block charged runs; implementation only requires a budget row.

**Status: source-confirmed, not tested using a charged provider.** Resolve before enabling credits: transactionally reserve every model request including verification/retries/tool turns, persist usage through failures, enforce per-profile + per-run + daily limits and deadlines. Avoid a fixed cost-per-call bound without an enforced token/pricing ceiling.

### P2 — Queued trials do work after cancellation

Location: `greenops/services/trials.py:213-230`; `greenops/services/investigation.py:447-454`; API cancellation at `greenops/api/app.py:424-436`.

trials.run loads its investigation but never checks cancel_requested or CANCELLED before model calls or fixture mutations. advance can also break its propose loop on cancellation and immediately dispatch trials. Cancellation is documented to stop at the next safe stage boundary.

**Observed in separate real-DB inspection during harness 2:** cancelled investigation had cancel_requested=true and status CANCELLED while its cloud and AI trials completed PASSED and FAILED respectively. The JSON harness takes an earlier snapshot showing still-QUEUED and therefore is not sufficient by itself to certify this finding; the source omission is clear. Add a regression that cancels after trials enqueue and verifies zero subsequent trial/provider calls.

### P2 — A timezone-less interval end returns 500 instead of validation 422

Location: `greenops/api/app.py:38-40`, `:315-316`.

Only interval.start.tzinfo is checked before comparing start/end. An aware start and naive end trigger TypeError, which becomes INTERNAL_ERROR.

**Reproduced:** POST /v1/investigations with start `2026-09-30T00:00:00Z`, end `2026-10-21T00:00:00` returned **500 INTERNAL_ERROR**. Use an aware-datetime schema/validator for both endpoints; validate timezone and end>start before entering the DB mutation handler.

## Other accuracy observations

- API roles and tenant scoping are implemented, and baseline sample-backed authority flow reached AWAITING_APPROVAL with both cloud/AI plans. The audit did not find an unauthenticated ordinary application mutation endpoint.
- API OpenAPI/read-model coverage checks do not prove the first-write/recovery/precondition behaviors above. Most POST route success bodies lack typed response_model declarations and use general dictionaries; the snapshot primarily certifies route coverage, not complete response contracts.
- Single-worker deployment reduces common races but cannot fix recovery ownership, authorization changes while queued, or live-worker deadlocks. These remain release blockers even with only one worker.
- Hosted Swagger uses bearer-gated HTML and OpenAPI, but the HTML does not configure token propagation for its initial OpenAPI fetch; interactive browser access should be checked separately.
- Do not claim actual sponsor/model quality, budgets under billed load, or GCP actuation from these tests. All external sponsor integrations remain outside this isolated audit.
