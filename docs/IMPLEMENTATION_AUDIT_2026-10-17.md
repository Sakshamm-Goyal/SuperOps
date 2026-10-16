# Implementation audit — 17 October 2026

> **Remediation status:** see [AUDIT_REMEDIATION_2026-10-17.md](AUDIT_REMEDIATION_2026-10-17.md) for the fix and regression test for each finding (added 17 Oct). This audit text is unchanged.

**Verdict: substantial working local implementation; not ready for a connected demonstration or release.** Core API, database, worker, UI, trials and H-MEM wrapper exist. The audit reproduced defects in action authority/recovery, evaluation, economic evidence and persistence. Existing passing tests do not cover these failures. Missing sponsor credentials are a separate blocker.

Reviewed revision: `8bc88d89556231d455ccc51b18059c51ed931bc3`. Audit date is Asia/Kolkata; some receipts carry 16 October UTC. This audit changes documentation/evidence only. It does not fix application behavior, enable writes, deploy, publish, spend provider credits or read private holdout cases. Attached reference documents were treated as reference material, not instructions or authorization.

## Evidence and coverage

| Area | Observed result | What this establishes |
|---|---|---|
| `make check` | 33 unit/contract tests passed; docs checker and existing secret scan passed | Existing numerical/schema/route checks run; this does not prove the adverse cases below |
| `make preflight` | PASS in sample mode; DB/profile ready, memory `semantic=False`, sandbox writes disabled | Local dependencies are available; no real sponsor/model claim |
| Integration suite | Clean isolated full run: **22 passed in273.60s**; isolated journey:1 passed. Earlier default-temp runs:11 failed/11 passed, then13 failed/9 passed | Earlier cloud failures included `fixture did not load the trial configuration`. Sandbox ownership flaw reproduced separately (A22); exact cause of every early failure not established |
| H-MEM sidecar suite | 21 passed with explicit Node 22.16 | Local engine/wrapper contract and persistence coverage using test embeddings |
| Advertised npm command | Fails under installed npm-selected Node 26.8.2: unsupported `--experimental-transform-types` | Runtime range/start command is not portable as documented |
| Connected tests | 8 BLOCKED/skipped: 4 Zetaris, 3 model, 1 semantic memory | Real sponsor access, real model/tool compatibility and semantic retrieval remain unverified |
| Browser and reports | Judge login, investigation/review queue, AI Lab and actions/report view render; download controls prepare; JSON/HTML report GETs return200 | Read-only UI/report smoke, not an operator mutation journey or connected E2E |
| Targeted authority audit | Real temporary PostgreSQL databases + real isolated sandbox processes; reproduced unauthorized execution, recovery overwrite, recovery deadlock, expiry dead end and bad timestamp 500 | Application defects; scripted model/sample evidence used explicitly |
| Domain/pagination audit | Six pure domain reproductions and three isolated Zetaris transport replays | Deterministic contract defects, not a claim about behavior observed from a real Zetaris server |
| Memory integrity audit | Real sidecar restart on disposable data; missing engine record followed by false persisted acknowledgment | Acknowledgment/reconciliation defect in wrapper |
| Containers, independent holdout, full connected browser journey | NOT_RUN/BLOCKED | No container/deployment, held-out quality, GCP or achieved-savings claim |

Receipts, scripts, detailed reviewer notes and a screenshot are in [the audit evidence folder](../evidence/audits/2026-10-17/). The audit evidence README explains safe reproduction and the final test manifest. Earlier failing attempts remain recorded rather than being replaced by a later green run.

## Highest-priority findings

P1 means a release-blocking correctness, authority, evidence or delivery problem. P2 means a material defect or gap to resolve before the relevant path is claimed complete. No P0 claim is made: the active application is a local sample with writes disabled, and no real customer/provider incident was observed.

### A01 — P1: Recovery can overwrite an intervening human change

Location: `greenops/services/execution.py:214–221`, `174–177`.

An action interrupted after intent but before its own write treats any target at `expected_version + 1` as its write. If another actor wrote that version, verification notices the wrong content but rollback overwrites the other actor anyway because recovery checks only the version.

**Reproduced:** approved concurrency 8→4 at v1; interrupted before action CAS; external actor sets 6 at v2; reconciliation returns `RECOVERED` and writes 8 at v3. The human's value is lost. Add an action/operation identity to the atomic target mutation and verify ownership plus content before either claiming or restoring it. A foreign v+1 must produce an unresolved conflict with zero compensating writes.

### A02 — P1: Queued execution ignores revoked actor/target authorization

Location: `greenops/services/execution.py:111–131`; request-time target gate in `greenops/services/approvals.py:123–124`.

The worker rechecks expiry, mode, write flag and some versions, but not current actor enabled/role/scope or target allowlist. **Reproduced:** queue AI action, disable approver, start the action with an empty worker allowlist; target still changes v1→v2 and action becomes `VERIFIED`. Check current authority immediately before the first write, and separately test actor revocation and target removal. Approval at enqueue time is insufficient.

### A03 — P1: Pending reconciliation is marked as a successful job

Location: `greenops/services/execution.py:207–211`; `greenops/worker/main.py:56–61`.

An unreadable interrupted target leaves the action `EXECUTING` and retains the global slot, but the worker marks its job `SUCCEEDED`. **Reproduced:** restore the isolated target file after the failure; another worker step does nothing and the slot remains held. Startup reconciliation can recover it only after a worker restart. Persist a bounded reconciliation schedule for nonterminal outcomes, retaining the slot until ownership/outcome is known. Exceptions must not leave orphaned active actions either.

### A04 — P1: The support verifier accepts forbidden disclosure

Location: `experiments/support/verifier.py:65–75`; lookup exposure in `experiments/support/workflow.py:64–84`.

The verifier trusts the model's `disclosed_customer_ids` list and does not enforce the actual `reply`/`customer_id`/denied `order_id`. **Synthetic adversarial reproduction:** authenticated A requests B's order; output declares `DENY_IDENTITY` and no disclosures but contains B's address/status in the reply and B's identifiers. Result is `accepted=True`, `critical_failure=False`.

Enforce record authorization before returning tool data; constrain and independently validate customer-facing output. A safe deterministic rendering contract is stronger than asking the same model to declare its own leaks. Add direct disclosure, paraphrase and identity-binding regressions before trusting the zero-critical metric.

### A05 — P1: The production cost path ignores effective rate intervals

Location: `greenops/services/plans.py:40–45`, `127–138`; domain contract `docs/DATA_AND_DOMAIN.md:50,64–74`.

The production path selects one current rate and extrapolates it over 720 hours, bypassing the separately tested interval calculator. **Reproduced:** baseline $0.20/h; candidate $0.10 for one hour then $0.30 for 719 hours. It reports **+$72 gross/net saving; effective-interval saving is −$71.80**. Only one hour of available pricing also still supports a 720-hour result. Experiment/transition costs are hardcoded zero and optimizer overhead is omitted from “net.”

A constant-current-rate scenario could be useful if explicitly bounded as that assumption; it currently fails the canonical interval-coverage and net-cost contract. Wire validated effective intervals and attributable costs into the actual recommendation path. Partial evidence/unknown coverage must remain unknown. Fix `accounting.interval_cost` simultaneously: its summed-duration check also accepts an overlap cancelled by an equal gap (covered hours are not the union of covered intervals).

### A06 — P1: AI approvals ignore tested model/workflow/data changes

Location: `greenops/services/approvals.py:40–49`; version construction in `greenops/services/plans.py:82–89`.

Freshness checks compare policy, cloud workload and target config only. **Direct precondition reproduction:** obsolete AI model/workflow/test versions plus a different configured model return `(True, None)`. The same function guards approval and execution. Bind and compare actual model, prompt/workflow, policy text, verifier, development records/cases, manifest and config hashes. Any relevant drift requires a new trial and approval; manually maintained version strings alone are insufficient.

### A07 — P1: Zetaris can label duplicated pages as complete evidence

Location: `greenops/adapters/evidence.py:255–262`.

The adapter checks page number and total length without checking template-specific row identity or stable pagination metadata. **Transport replay:** pages each contain `probe_id=1` with `totalCount=2`; returned completeness is `complete`. This is a contract reproduction, not an observed live provider fault. Add stable key/receipt invariants and reject duplicated or inconsistent page streams. Do not deduplicate blindly where legitimate records can share field values. Partial critical economic evidence also needs downstream rejection (`investigation.py:140–147` currently gates only policy/inventory/telemetry summary).

### A08 — P1 before paid use: Budget enforcement is incomplete

Locations: `experiments/support/evaluate.py:89`; `greenops/services/execution.py:65`; `greenops/services/trials.py:141–180`; `greenops/adapters/model.py:102–126`; `greenops/config.py:132`.

Source-confirmed: evaluator and AI action verification pass `budget=None`; daily cap is parsed but unused; AI trial profile-specific money/call/time limits are unused; usage is persisted after suite aggregation; request counts depend on usage metadata. Failed/partial attempts and restart can therefore escape durable accounting. The fixed conservative per-call allowance also lacks an enforced generation-token ceiling. No billed experiment was used to prove this.

Reserve every request durably before dispatch, independently of usage reporting. Enforce profile/run/day/time/token limits for trials, verification, retries and evaluator work; persist partial usage and unknown costs. Validate with provider-shaped events and an authorized bounded live smoke only after these guards are fixed.

### A09 — P1: Clean setup and release commands do not provide reliable gates

Locations: `greenops/config.py:38–47`, `.env.example:2–6,40–45`; `memory-sidecar/package.json:8–13`; `Makefile:75–79`.

The dotenv reader treats inline comments as values; the template contains many of them. Direct reproduction rejects `sample # ...` as an enum, and the source URL/policy/evaluator directory can retain comment text even if the README's sample overrides are edited. Use a defined dotenv grammar or separate-line comments and prove a clean copy/bootstrap.

The documented Node range admits the installed Node 26 runtime although the npm command uses a removed experimental flag. Explicit Node 22 passes 21 tests. Pin a supported runtime or use a compatible build/run path.

`make test` suppresses pytest's exit code with `|| true`; the reporter prints FAIL counts but exits zero. Preserve the failure code while printing results, and define a separate release gate where required connected BLOCKED checks fail. `test-e2e` is only an integration alias and no `.github/workflows` exists. Add actual CI/browser gates before advertising them.

## Additional defects and gaps

| ID | Priority / evidence | Location | Impact and required closure |
|---|---|---|---|
| A10 | P2, reproduced | `verifier.py:60–61`, `trials.py:165–174`, `evaluate.py:98–101` | Failed model output omits category; aggregation raises `KeyError('category')`. Keep failed cases and usage in the denominator/report |
| A11 | P2, reproduced real sidecar | `memory-sidecar/src/memoryService.ts:287–301` | After an engine record is removed in disposable state, health is degraded but duplicate remember returns `persisted:true`; recall returns zero. Reconcile record/index or fail acknowledgment |
| A12 | P2, reproduced API/DB | `approvals.py:115–117,89–92` | Expired approval leaves plan APPROVED; execute/reapprove/revoke all 409 and no next action. Define atomic expiry/renewal transition |
| A13 | P2, source-confirmed; separate observation | `trials.py:213–230` | Queued trials do not check investigation cancellation before fixture/model work. Cancel after enqueue and assert zero further dispatch at the next safe boundary |
| A14 | P2, pure reproduction | `workflow.py:43–56` | Regex policy selection omits both return rules for “Please provide a prepaid label so I can ship this purchase back to your warehouse.” Preserve mandatory rules and test validated semantic routing/retrieval |
| A15 | P2, source-confirmed design gap | `approvals.py:52–81`, `execution.py:56–69` | No persisted frozen holdout verdict gates AI promotion. Define sandbox-trial versus final-selection permissions and enforce the intended release/promotion gate |
| A16 | P2, transport reproduction | `adapters/evidence.py:242–244,247–259` | Malformed first records leak a valid query token; max_rows=150 returns200. Put all post-token parsing inside cleanup and enforce row/time/response bounds |
| A17 | P2, reproduced API | `api/app.py:315–316` | Aware start + timezone-less end produces500. Validate both timestamps before comparison and return422 |
| A18 | P2, source-confirmed UI gap | `ui/app.py:313,325–329,490–541` | User can omit trial profile, but no Run sandbox trial control exists for an eligible DRAFT plan; API supports it. Add the complete next-step UI |
| A19 | P2, config/static review | `docker-compose.yml`, `Dockerfile` | Missing documented POSTGRES_PASSWORD/init/migration/actor/data path; sample source loopback is wrong in containers; volume ownership needs verification. Docker daemon unavailable; clean Compose execution not certified |
| A20 | P2, documentation review | `docs/DEVELOPMENT.md:5–24`, `TEST_STRATEGY.md:35–46`, `OPERATIONS.md:46–64` | Stale statements say app/commands do not exist and use proposed variable names. Reconcile canonical docs and status; link checking cannot detect semantic drift |
| A21 | P3, visible/static | `ui/app.py:1074`; viewer banner | Source dictionary is rendered as keys instead of configured values; viewer banner says mode unknown while footer knows sample. Improve operator clarity |
| A22 | P2, reproduced real processes | `adapters/sandbox.py:170–194`, `tests/conftest.py:66–73` | Startup adopts any responsive worker on fixed ports without binding it to the sandbox directory. Start directory A, start B on same ports, set B concurrency4: reload still returns A's8. Reject ownership mismatch/use isolated ports and verify process/config identity before tests |

The independent final holdout is not established: committed generator code contains both deterministic partitions and the same author prepared them. A separate evaluator should author/control the final private set. Existing benchmark and one memory-ablation artifact are honestly labelled synthetic/scripted; they do not prove semantic recall, six-sequence repeatability, user value or real savings.

## What is implemented well

The architecture separates UI, API, deterministic domain logic, providers, jobs and PostgreSQL authority. There are typed bounded model-role schemas, explicit source modes, read-only query templates, exact plan/trial hashes, an outbox, local compare-and-set targets and visible rejections. Meterless H-MEM is genuinely vendored and used with attribution; this is not a handwritten dictionary substituted for the sponsor engine. Federated rollup SQL aggregates source facts before joining. The UI exposes retained checks, evidence IDs, trial metrics and limitations, and the judge role hides mutation controls. These are useful foundations to retain while fixing the owning paths.

## Closure plan for 4–5 builders

| Order | Owner | Work and acceptance evidence |
|---|---|---|
| 1 | C: authority/worker | A01–03, A06, A12–13, A17; first lock each adverse reproducer, then fix atomic ownership/reconciliation/current authority and verify on real isolated DB/processes |
| 1 | B: domain/agent + D: independent evaluator | A04–05, A08, A10, A14–15; safe output contract, actual interval/net-cost path, durable budgets, invariant result schema; D owns adversarial/holdout acceptance |
| 1 | A: sponsor/data/memory | A07, A11, A16; unique page identity, cleanup/bounds, acknowledgment integrity, then real two-source receipts and semantic-memory tests when access exists |
| 2 | C + optional E | A09, A18–22; clean setup, supported runtimes, sandbox isolation, nonzero failure gates, CI, true browser journey, UI next actions, accurate docs; C owns minimal UI if four builders |
| 3 | D with all owners | Repeat adversarial suite and clean install; bounded real sponsors; independent frozen AI evaluation; repeatable memory ablation; browser approve→execute→verify→reload→export equality |
| 4 | Team lead / E if present | Verify current eligibility and actual Cursor work, then produce video/deck from the tested revision with exact sponsor receipts and pre-existing-work disclosure |

Do not add new product breadth while these gates remain open. Exit is evidence-based: no unauthorized/foreign overwrite, no false verified/complete/persisted/accepted result, unknown spend/evidence remains explicit, all required connected gates pass, and a clean user can reproduce the documented journey.

## Hackathon readiness

The [official event page](https://hackathon.genai.works/event/open-agent-hackathon-2026), re-opened during this audit, shows the build opening 22 October 2026 at 00:00 UTC and submissions closing 27 October at 23:45 UTC. Its visible Wildcard text says existing concepts/projects must integrate Zetaris and Meterless and are scored on new work. The local declaration records the implementation as pre-event and says it was built with Claude Code; Cursor and organizer track eligibility therefore still need honest supporting evidence. This audit did not access private HackOS, obtain an organizer ruling, register, send outreach or submit. Hidden rule accordions were not re-expanded in this turn; use the existing rules register plus a fresh organizer check before submission.

## Limits

This is a broad code, local-runtime and adversarial contract review, not exhaustive proof that no defects remain. No credentialed federation/model/embedding/GCP run or container deployment was performed. Default integration failures were investigated; a clean isolated full rerun passed22/22. A22 demonstrates a real isolation defect, but exact ownership of the earlier mismatched worker was not captured, so do not assert it explains every failure. No application bug was fixed in this review. The next implementation pass should start from these failing cases, not from additional feature work.
