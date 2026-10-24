# Implementation plan and backlog

Status: updated 16 October 2026. **At the user's instruction, the work packages were implemented pre-event** (ADR-18; declared in PREEXISTING.md). Live sponsor gates remain BLOCKED pending credentials. The table below records the current status; the original plan text follows unchanged.

| Package | Status (16 Oct, pre-event) | Evidence / blocker |
|---|---|---|
| B01 baseline, provenance, manifests | Done | Local commit `10a2cfd` (docs baseline) plus implementation commit; `uv.lock`; data manifest |
| B02 schemas, migrations, plan hash, jobs/events | Done | `migrations/0001_initial.sql`, `greenops/domain/*`, unit oracles |
| B03 source manifests + Zetaris templates | Implemented; **live BLOCKED** | `sql/*.sql`, `greenops/adapters/evidence.py`; contract tests pass; ZET-01..04 BLOCKED (no workspace credentials) |
| B04 H-MEM wrapper, scope, outbox, recovery | Implemented; semantic embeddings **BLOCKED** | `memory-sidecar/` (21/21 tests), outbox and application integration tests pass; HMEM-07 BLOCKED |
| B05 ADK roles + critic loop | Implemented; real-model run **BLOCKED** | `greenops/agents/roles.py`, `greenops/adapters/model.py`; scripted-role journeys pass; NIM-01..02 BLOCKED |
| B06 capacity, forecast, cost, carbon | Done | Unit oracles; `make eval-cloud` |
| B07 UI | See README / UI agent report | `greenops/ui/` |
| B08 matched local trial | Done (local analogue) | Authority journey test: real worker processes, A/B/B/A/A/B measurement |
| B09 approval / executor / reconciler | Done (local analogue) | ACT-01..17 integration tests pass |
| B10a support workflow + candidates | Implemented; real-model dev runs **BLOCKED** | `experiments/support/`; scripted dev trial: truncated fails 32/40, relevant_sections passes 40/40 |
| B10b verifier, 40/40 split, evaluator | Implemented; independence limited | Same author for both partitions; role D should re-author the holdout |
| B11 connected cloud journey | Control flow done; connected **BLOCKED** | Needs Zetaris + NVIDIA + semantic memory |
| B12 cross-run learning | Mechanism done (hash embedder); semantic **BLOCKED** | `tests/integration/test_memory_learning.py` |
| B13 release acceptance | Not run | Needs connected PASS results |
| B14 packaging (video, deck, submission) | Not started | Requires event-window work and user authorization |
 The user confirmed **4–5 active builders** and an **original implementation**: niksm7/GreenOps is third-party inspiration, with no reuse of its code, prompts, assets or results. Track eligibility and treatment of pre-event preparation still require organizer clarification.

## Confirmed staffing plan

Map named teammates to A–D before building; add E only when the fifth builder is confirmed. Each work package has one accountable owner in either roster, a different reviewer and bounded helpers. Helpers do not acquire ownership or access to held-out answers.

| Role | Four-builder plan | Five-builder plan | Accountability boundary |
|---|---|---|---|
| A | Data, Zetaris and Meterless integration | Same; C can help with bounded memory-wrapper plumbing after API contracts | Source provenance, federation receipts, semantic memory and persistence |
| B | Agents, domain tools, workload and support candidate implementation | Same | Candidate generation/tuning and measured development trials; no held-out labels |
| C | API/auth, durable jobs, approval/executor, minimal Streamlit UI; submission coordinator | API/auth, durable jobs and approval/executor; bounded help to A after API contracts | Application authority and action state; never independent holdout owner |
| D | Independent QA, evaluation and security; demo evidence and packaging verification | Same | Sole owner of holdout labels/credentials, independent verifier and locked evaluation; no candidate tuning |
| E | Not staffed | UI/UX, report presentation, demo/deck and submission coordinator | Uses API contracts and D-approved evidence exports; no holdout labels |

With four builders, C owns the minimal UI and final packaging, while D owns acceptance/demo evidence and verifies the package. With five, E takes those UI and coordination deliverables; this frees C to help A without expanding product scope. D remains independent in both rosters. Submission coordination never grants permission to publish or submit.

## The critical path

Organizer track/disclosure clarification and access → real sponsor/model smoke tests → typed durable contracts → one evidence-backed cloud rejection/revision → measured trial → scoped action and read-back → one same-model AI experiment → connected acceptance/restart → submission.

Build the approval path early alongside the investigator. Do not finish a dashboard and only then discover sponsor networking or memory persistence cannot work. Cloud is the first complete vertical slice; the AI lab remains committed P0 after it. Any cut to P0 requires an explicit scope decision and matching product/demo/docs update, never a quiet omission.

## Before the build window

Read sources, record the confirmed inspiration-only decision, resolve organizer track/disclosure questions, map the 4–5 builders to named roles, register/finalize team, prepare accounts and obtain credential-delivery instructions, choose spend cap and local hardware, attend onboarding. The docs can be reviewed and corrected. Do not claim application features created before 22 October 00:00 UTC are new event work. Any early experiment, prepared data or code must enter PREEXISTING.md. This planning task does not create accounts, contact organizers or run charged trials.

## Day one integration spikes

Timeboxes below are team priorities, not guaranteed durations. Record actual timestamps, source versions, commands and receipts. Missing credentials are BLOCKED, not a reason to mark a fixture PASS.

| Spike | Accountable owner: 4 / 5 builders | Reviewer; bounded help | Timebox | Evidence required | If blocked |
|---|---|---|---:|---|---|
| G0 provenance and track | C / E | D; C provides baseline manifest | 1 hour after organizer info | Confirmed inspiration-only decision, disclosure baseline and selected track status | Keep track provisional; continue original preparation without copied source |
| Z0 Zetaris | A / A | D | 3 hours | Real token/auth, two reachable physical sources, paginated query, receipt and close/cleanup | Use authorized sponsor support; switch to supported approved source types; never replace federation with local SQL |
| M0 H-MEM reference | A / A | C | 2 hours after Z0 | Pinned clean install, actual remember/recall/audit, durable restart | Resolve reference build/storage before wrapper breadth |
| N0 model | B / B | D | 2 hours | Actual NVIDIA text → typed tool call → tool result → valid structured output; usage/latency captured | Test one other available model/adapter; record exact limitation |
| M1 real embeddings | A / A | D; B helps provider compatibility after N0; C helps wrapper plumbing in five-builder plan after B02 | 3 hours after M0; finish by day 2 | Narrow adapter extension, actual provider vectors, same profile on insert/query, paraphrase and incompatible-version test | Sponsor-supported alternate embedding provider; no semantic claim from mock hash vectors |
| X0 execution target | C / C | D | 1 hour | Owned disposable target, read-only identity/health, allowed transition/recovery design | Commit to real local analogue and label it; cloud writes remain disabled |
| Q0 evaluation isolation | D / D | A reviews public manifest and isolation design only | 2 hours | Evaluator-only storage/credentials, split manifest design and zero candidate access to labels | Block final evaluation until isolation is proven; development cases remain usable |

A runs Z0 then M0; M1 may finish on day two. B, C and D run their own spikes in parallel. E, when present, handles G0 and designs the minimal workbench against the proposed API. Do not assign all sponsor work and unfinished wrapper development to one day. If sponsors remain inaccessible at day-one review, use authorized team support and record the risk to submission eligibility. Required integrations cannot be removed by scope reduction.

## Dependency ordered work packages

| ID | Accountable owner: 4 / 5 builders | Reviewer; bounded help | Prerequisite | Deliverable | Acceptance and evidence |
|---|---|---|---|---|---|
| B01 | C / C | D; submission coordinator maintains declarations | G0 status recorded | Team-owned baseline, provenance and dependency manifests | Actual baseline SHA; no credentials or copied upstream source; documented lock selection |
| B02 | C / C | D; B supplies domain schema definitions | B01 | Pydantic domain/API schemas, migrations, plan hash, jobs/events | Malformed unit/unknown action rejection; durable restart; API docs and OpenAPI agree |
| B03 | A / A | D | Z0+B02 | Source manifests and parameterized Zetaris templates | Exact identity, two physical sources, F-JOIN totals, no arbitrary SQL |
| B04 | A / A | D; C supplies outbox contract and, with five builders, bounded wrapper plumbing | M0+M1+B02 | H-MEM wrapper, scope filters, outbox and recovery | Real semantic recall, audit, restart, duplicates, corrections and stale-version tests |
| B05 | B / B | D | N0+B02+B03 | Bounded ADK roles and typed critic loop | Actual evidence-driven rejection/revision, six-candidate cap, timeout and NO_CHANGE |
| B06 | B / B | D; A reconciles source grain | B03 | Capacity, daily-naive forecast, cost/carbon tools | Independent arithmetic fixtures, chronological split, missing data blocks, no double totals |
| B07 | C / E | D; C owns API responses in either roster | B02 | Minimal UI queue, detail, evidence and operations view | Persisted state after browser refresh, clear sources/unknowns, keyboard flow |
| B08 | B / B | D; C provides approved trial runner boundary | B05+B06 | Matched cloud/local workload trial | Fixed manifest, measured A/B runs, genuine failed and passing screening cases |
| B09 | C / C | D | B02+X0 | Authenticated approval/executor/reconciler | Stale/expired/forged/duplicate blocked; actual allowlisted change and health/read-back |
| B10a | B / B | D | B05+B08; development manifest from B10b | One support workflow and bounded candidate configurations | Real development model calls; policy-exception failure and revised candidate pinned before final evaluation |
| B10b | D / D | A reviews public verifier logic/manifest; no label access | B02+Q0; final run waits for B10a freeze | Independent verifier, 80-case manifest, 40/40 split and locked paired evaluation | Private holdout custody; zero label leakage; every assigned case reported; no candidate tuning by D |
| B11 | C / C | D; UI owner integrates views | B07+B08+B09 | Complete connected cloud user journey | Investigate → trial → approve → execute → verify → reload → report, actual receipts |
| B12 | A / A | D; B supplies frozen investigation configuration | B04+B11 | Cross-run learning demonstration | Restart, paraphrased recall, changed policy invalidation; D runs/audits memory-on/off comparison |
| B13 | D / D | C reviews public evidence and reproducibility; A/B fix their defects | B10a+B10b+B11+B12 | Release acceptance and claims register | Tests/evals run; no critical blocked real integration; all metrics labelled and traceable |
| B14 | C / E | D verifies packaging; A/B provide source/model receipts | B13 for final completion; preparation may start earlier | Clean setup, video, deck, submission materials | Fresh checkout on second environment; 1–4 minute video; accessible links and declarations |

Every item produces a reviewable increment, not only an internal module. API/UI work can begin with clearly labelled development fixtures, but its connected acceptance remains pending until B11. Do not report UI fixture screenshots as sponsor evidence.

## Six day schedule

Dates below are UTC workdays; use the stated local conversions for team coordination. Avoid scheduling all integrations for one builder at the same moment.

| Date | A: data/sponsors/memory | B: agents/domain/workload | C: API/jobs/execution | D: independent QA/evaluation/security | E if staffed; otherwise C owns UI/package | Daily exit |
|---|---|---|---|---|---|---|
| 22 Oct | Z0 then M0; B03 source manifest | N0; B02 domain input; B05 skeleton | B01/B02 jobs/auth/contracts; X0; G0 when four builders | Q0; test registry, independent oracles and B10b split design | G0 when five; API-aligned workbench design; four-builder C adds only minimal queue | Real two-source query, persisted memory round trip, actual model tool loop; schema and evaluator-isolation contracts recorded |
| 23 Oct | M1; finish core B03/B04; accept bounded C wrapper help only when five | B06 + B05; first B08 matched trial | B09 approval/reconciliation; B11 integration; minimal B07 when four | Sponsor receipt checks, arithmetic/critic negatives; publish 40 development cases while sealing holdout | B07 evidence/trial views and report layout | Cloud rejection/revision and measured trial; local action path; real semantic recall or explicit blocker |
| 24 Oct | Source/memory failure tests; B12 fixture preparation | B10a development runs and bounded revisions; pin candidate | Complete B11 action/reload; close B09 adverse cases | B10b verifier frozen; inspect label isolation; ACT/E2E checks | Connect approval/result/reload UX; four-builder C keeps minimal UI | Complete cloud action/reload; AI candidate and verifier pinned for final evaluation |
| 25 Oct | B12 restart/applicability evidence and source reconciliation | Trial robustness; explain development failures without seeing private labels | Resolve execution/API integration defects; verify report persistence | Locked paired AI evaluation, memory ablation and B13 connected acceptance | Usability/claim labels; prepare storyboard from D-approved exports | Both paths and memory proof; no critical sponsor path mocked; complete results including failures |
| 26 Oct | Clean sponsor install and reproducible receipts | Fix release-blocking agent/domain defects; D decides whether evaluation is invalidated | Freeze API/action path; four-builder C prepares B14 with D evidence | Independent clean install, security/claim audit; verify package and evaluation validity | B14 demo/deck/export/link packaging | Feature freeze at 12:00 UTC / 17:30 IST; coherent reviewed demo and package |
| 27 Oct | Reconfirm data/sponsor access | Targeted release smoke; unresolved findings documented | Runtime/API smoke; four-builder submission coordination | Final acceptance, redaction and evidence audit by 12:00 UTC / 17:30 IST | Final links/declarations and authorized submission coordination | Validation by 12:00 UTC / 17:30 IST; target submit 18:00 UTC / 23:30 IST only after authorization |

Official closing: 27 Oct 23:45 UTC / 28 Oct 05:15 IST. The public judging-start discrepancy is unresolved, so a coherent demo must exist by 26 October. [Rules and calendar](HACKATHON_RULES.md).

## Scope and staffing decisions

Plan for the confirmed 4–5 builders using the role table above. Four is the executable baseline; the fifth improves UI, presentation and integration capacity without adding features. Keep one model, one local sandbox action, two physical sources, a deterministic report and the minimal Streamlit workbench until P0 passes. If staffing drops below four, replan explicitly before redistributing work; never merge independent holdout custody into candidate implementation or silently remove P0 acceptance.

Cut optional work in this order: generated slides, scheduled reporting, second model, additional dashboards/connectors, live GCP resize. A true local analogue remains acceptable engineering scope only with honest labeling; organizer acceptance of that demo format is an open question. Required sponsor integration, critique/revision, independent tests, scoped approval and verification cannot be cut. Do not pursue an in-kind prize feature before core acceptance passes.

## Ready for implementation handoff

The next coding agent should first read AGENTS.md, DECISIONS_AND_RISKS, API_REFERENCE and sponsor research; inspect actual workspace changes and access status; select the earliest unblocked work package; create its reproduction/acceptance harness; implement; verify; update NEW_WORK and backlog facts. Do not infer credentials exist from variable names. Do not install arbitrary latest packages or run/copy the inspiration repository. Independently author the implementation; use required sponsor dependencies only under their reviewed licenses and notices.

Suggested first implementation request:

> Implement B01/B02 and the authorized day-one sponsor/model spikes from this documentation pack. Preserve provenance, start with real integration evidence, and keep cloud writes disabled. Resolve concrete compatibility issues in the main path, update contracts and tests together, and report verified versus blocked access. Do not deploy or submit unless separately authorized.

This is a future handoff prompt, not an instruction to implement during the current documentation-only turn.
