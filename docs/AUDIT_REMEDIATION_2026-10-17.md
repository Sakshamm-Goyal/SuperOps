# Audit remediation — 17 October 2026

Response to [the implementation audit](IMPLEMENTATION_AUDIT_2026-10-17.md). This work is pre-event and is declared in [PREEXISTING.md](../PREEXISTING.md).

Method, per AGENTS.md: each finding was first reproduced as a failing regression test, then the main path was fixed, then the reproducer was re-run. The failing runs from before the fixes are kept in [evidence/audits/2026-10-17/remediation/](../evidence/audits/2026-10-17/remediation/): 20 unit and 16 integration reproducers failed before the fixes. Real sponsor validation is still **BLOCKED** on credentials. Nothing here is a claim about live Zetaris, NVIDIA, semantic memory, GCP or Docker behavior.

## Status by finding

| ID | Fix (main path) | Regression evidence | Status |
|---|---|---|---|
| A01 | Every compare-and-set write records an operation identity (`writer`). Reconciliation and recovery treat a version as their own only if version, writer **and** content all match the approved change. A foreign v+1 ends `RECOVERY_REQUIRED` with zero compensating writes. Added the authenticated operator procedure `make resolve-action` → `RESOLVED_MANUALLY` | `test_a01_foreign_write…`, `test_a01_own_write…`, `test_act09…`, `test_act07…` | Fixed |
| A02 | The worker re-checks current authority immediately before the first write: actor enabled, operator/admin role, same tenant, approval consumed by this action, target still allowlisted. Failure → `AUTHORITY_REVOKED`, zero writes, plan back to `AWAITING_APPROVAL` | `test_a02_current_authority…[disable_actor / downgrade_role / remove_target]` | Fixed |
| A03 | An unreadable interrupted target returns `RECONCILE_PENDING`. The worker reschedules with bounded backoff and keeps the global slot. A crashing action handler is rescheduled, never marked successful | `test_a03_unresolved_reconciliation…`, `test_a03_exception_in_action_job…` | Fixed |
| A04 | Lookup tools enforce record authorization before returning data. Verifier v2 checks the reply and fields itself (foreign names, emails, IDs, addresses, foreign `customer_id`, denied order ID/status/address); all are critical failures | `test_a04_*` (5 leak variants, clean-denial control, tool authorization) | Fixed (deterministic patterns; paraphrased leaks that avoid every record token remain a limit) |
| A05 | Projection uses `interval_cost` over `[as_of, as_of+720h)` across every effective rate. Partial or ambiguous coverage → `UNKNOWN`. Interval coverage is the union of intervals: overlap → error, gap → incomplete. Net = gross − experiment − transition − optimizer overhead, attributed after the trial; any unknown term → net unknown. Screening economics uses horizon cost | `test_a05_*` (−71.80 USD oracle, partial coverage, overlap and gap), domain oracles | Fixed |
| A06 | AI plans bind actual artifact hashes: workflow + prompt + policy text; verifier + development cases/records + manifest; plus the model ID. Approval and the worker compare all of them, along with the data manifest and target config version | `test_a06_ai_freshness…` | Fixed |
| A07 | Each template declares a unique key. The adapter rejects duplicate/keyless rows, paging metadata that changes between pages, and mismatched page numbers. Investigations need **complete** evidence for every decision input; only carbon may degrade, to UNKNOWN | `test_a07_*` (unit) + `test_a07_incomplete_economic_evidence…` (integration) | Fixed (contract level; live Zetaris BLOCKED) |
| A08 | `budget_reservations`: every model request reserves durably before dispatch, independent of usage reporting. Per-investigation, per-trial (profile `max_model_calls`/`max_cost_usd`/`max_seconds`), daily (`MAX_DAILY_COST_USD`) and evaluator (`eval_run`) scopes. AI action verification and the evaluator use budgets. Per-case usage is persisted as each case completes. `MODEL_MAX_OUTPUT_TOKENS` sets a generation ceiling | `test_a08_budget_is_durable…` | Fixed; a bounded live paid smoke is still needed |
| A09 | Defined dotenv grammar (quoted = literal; unquoted ends at a whitespace-preceded `#`), with a test that `.env.example` parses. Node pinned `>=22.12 <23` with a fail-fast check; Makefile `NODE ?=`. `make test` keeps pytest's exit code. `make release-gate` fails on FAIL/BLOCKED/NOT_RUN. `make test-e2e` reports NOT_RUN instead of aliasing another tier. Added `.github/workflows/ci.yml` (not yet executed) | `test_a09_*`; sidecar 24/24 on Node 22; Node 26 fails fast | Fixed (CI run NOT_RUN) |
| A10 | Failed or invalid model output keeps its category and stays in the denominator | `test_a10_…` | Fixed |
| A11 | Sidecar: an indexed receipt whose engine record is missing is re-created (same hash) or refused (409). `persisted:true` is only returned after disk read-back. New health reason `ENGINE_RECORD_MISSING` | `memory-sidecar/test/integrity.test.ts` (3 new tests) | Fixed |
| A12 | Lazy, atomic expiry: an expired ACTIVE approval → EXPIRED, and the plan returns to `AWAITING_APPROVAL` (on read, approve or execute). Zero-write worker failures also return the plan for re-approval | `test_a12_*` (3) | Fixed |
| A13 | Trials check cancellation before any fixture/model work and at each pair/case boundary → `CANCELLED`; the investigation then ends `CANCELLED` | `test_a13_cancel_stops_queued_trials` | Fixed |
| A14 | `relevant_sections` always keeps §1, 3, 4, 5, 10, 11, 12, 13; only peripheral sections are optional | `test_a14_*` | Fixed |
| A15 | `evaluation_verdicts` table written by `make eval`. Approving an AI plan requires a ROLLOUT_ELIGIBLE verdict for the exact candidate config hash and model; otherwise 422 `HOLDOUT_VERDICT_REQUIRED` | `test_a15_ai_approval_requires…` | Fixed |
| A16 | All parsing after the query token sits inside cleanup; 5 MiB page cap; row budget truncates to `max_rows` and marks the result partial | `test_a16_*` | Fixed |
| A17 | `AwareDatetime` interval fields → 422 | `test_a17_…` | Fixed |
| A18 | UI "Run sandbox trial" control (operators only, stable idempotency key) | UI agent AppTest against a stub API (39/39); not yet run against the live API | Fixed in UI; live check pending |
| A19 | Compose: sample-source DB init, one-shot `bootstrap` service (migrate, data, actors, trial profile), container URLs, volume ownership baked into images, `POSTGRES_PASSWORD` documented | `docker compose config` valid | Not executed (no Docker daemon) |
| A20 | DEVELOPMENT, TEST_STRATEGY and OPERATIONS rewritten to match the implementation; API_REFERENCE and ARCHITECTURE updated with the new states and codes | `make verify-docs` | Fixed |
| A21 | Operations sources table; viewer banner mode from `/v1/me`; distinct action-state icons | UI AppTest (stub API) | Fixed in UI |
| A22 | Workers report their real config path; the adapter refuses a responsive worker serving another sandbox (`SandboxOwnershipError`); `start_workers` never adopts one | `test_a22_sandbox_refuses…` | Fixed |

## Also found during remediation

- **No resolution path for RECOVERY_REQUIRED.** A RECOVERY_REQUIRED action correctly blocked its target forever, but there was no procedure to resolve it. Added `resolve_manually` / `make resolve-action`: the actor is authenticated, the target is read back, and a journal entry is written.
- **Noisy trial gate (flaky integration tests).** With identical configurations, the gate failed about 1 run in 5 under full-suite load.
  - **First fix:** pooled p95 plus a majority of paired windows, threshold unchanged. It helped, but 6→4 trials still failed intermittently under load.
  - **Root cause, measured:** p95 spikes coincided with 34–40 ms load-generator schedule lag (normally 2–4 ms). In those windows the generator fell behind and burst requests, so the manifest's offered load was never delivered.
  - **Second finding:** client-observed p95 still wandered (87–139 ms) while server queue wait was 0 and service time was ~70 ms. The in-process client itself was noisy.
  - **Fix:** the gate now measures server-side latency (queue + delivered service, reported by the worker per request). Windows whose generator lagged (p95 > 10 ms or max > 25 ms) are discarded, recorded and re-measured (at most 4 times); with no clean pair the trial is INCOMPLETE. The 10% threshold is unchanged.
  - **Result:** 4v4 20/20 PASSED (pair ratios ≈1.000); 6v4 18 PASSED + 2 INCOMPLETE, no false FAIL; 8v2 3/3 FAILED (ratio ≈14).
  - **Evidence:** `remediation/trial-gate-noise.json` and `trial-gate-fidelity.json`. Both changes are dated amendments in [EVALUATION_SPEC](EVALUATION_SPEC.md).
- **Slot waits backed off like failures.** A trial waiting for the global slot backed off exponentially. Slot waits now retry every 2 s; only unresolved outcomes back off.

## Still open (not claimed done)

- Real Zetaris two-source federation, NVIDIA model/tool cycle, semantic embeddings (HMEM-07) and a bounded paid budget smoke: BLOCKED on credentials.
- An independently authored holdout set (role D).
- A browser E2E harness.
- A CI run on GitHub.
- A Docker Compose run.
- A clean install on a second machine.
- UI controls exercised against a connected-mode action.
- Paraphrase-level disclosure that avoids every record token cannot be caught by verifier v2's token checks. A constrained, deterministic rendering contract would be stronger.
