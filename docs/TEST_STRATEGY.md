# Test strategy

**Status: implemented pre-event, 16 October 2026 (see PREEXISTING.md).** Tiers T0–T4 exist as `make check`, `test-integration`, `test-connected`, `test-e2e` and `eval`; see the implemented map at the end. Connected sponsor tests are BLOCKED until credentials are supplied. The future implementation must turn the IDs below into executable checks. D owns the independent acceptance suite, evaluation and security verdicts. A implements data/sponsor test plumbing, B implements domain/agent/workload test plumbing, and C implements API/jobs/execution test plumbing. D is the sole owner of holdout labels and evaluator credentials; candidate implementers receive development cases only.

The user confirmed 4–5 builders over six days. A–D form the core team; optional E owns UI/UX and submission packaging. With four builders, C owns the minimal UI and coordinates submission, while D verifies acceptance/demo evidence and the package. The product scope is unchanged: a cloud investigation, one support-workflow experiment, genuine Zetaris and Meterless integration, a bounded critique/revision loop, and one approved change with read-back. See [evaluation specification](EVALUATION_SPEC.md) for the experimental protocol and numerical oracles. The source design is [the supplied developer handoff](../Refer-Docs/GreenOps_Verify_Developer_Handoff.md); its instructions describe a proposal, not an already working system.

## 1. What counts as evidence

| Layer | Useful proof | Does not prove |
|---|---|---|
| Deterministic unit check | Arithmetic, validation, transition and applicability rules work for explicit inputs | That a sponsor, provider or model accepts our requests |
| Adapter contract check | Serialized requests/responses match a pinned interface; malformed/timeout cases are handled | Live authentication, networking, quotas or persisted data |
| Integration check | Our running code talks to real PostgreSQL, the pinned H-MEM reference, Zetaris sources and the selected NVIDIA endpoint | The full user journey or production reliability |
| E2E acceptance | Browser action → API → investigation/trial → approval → actual sandbox change → provider/config read-back → fresh workload → report survives reload | Unbounded reliability, measured cloud savings from a local analogue, or general model superiority |
| Recorded replay | A dated, hash-identified prior run can be inspected reproducibly | A new live integration test |

Mocks are allowed at I/O boundaries in fast tests. Release evidence must include real integrations and a real executable sandbox path. A local worker/configuration change can establish the application control flow; only a team-owned GCP run can establish the GCP executor. Never label a mocked provider call as a GCP pass.

Each check records `test_id`, code/dependency/config hashes, environment, runtime mode, source/fixture versions, start/end UTC, outcome, assertion summary and redacted evidence links. Use these outcomes consistently:

- `PASS`: assertions ran against the named environment and all passed.
- `FAIL`: an assertion failed, including an unexpected provider response.
- `BLOCKED`: a required dependency, credential, permission, quota or fixture was unavailable. Record cause, owner and next step; this is not a pass.
- `NOT_RUN`: no attempt yet; do not render a green badge.
- `NOT_APPLICABLE`: outside the declared release scope, with a reason. A mandatory sponsor cannot be made optional this way.

Record retries and the initial failure. An infrastructure timeout may be retried within the read policy, but do not silently rerun until green. Deliberately cutting a connector in a fault test is a passing negative test only when the expected bounded failure occurs; it does not replace the healthy connector test.

## 2. Root cause before repair

For each reported bug, capture the exact input, expected result, actual result, evidence/trace IDs and relevant versions. Add a failing unit test, trace replay or golden eval first. Reproduce the owning failure: source/schema, join, units, prompt, model adapter, parser, deterministic validator, workflow state, database transaction, executor or UI contract.

Change the main path and rerun the reproducer. Keep it as a regression. Then run the affected integration/E2E tier. A wider catch, retry, fallback sentence or second model is not the main fix for a broken normal path. If recovery changes, verify its failure case separately. Sensitive inputs must be minimized and redacted before becoming fixtures.

## 3. CI and execution tiers

These commands exist (16–17 Oct 2026, pre-event). `make test` keeps pytest's exit code; `make release-gate` fails on any FAIL, BLOCKED or NOT_RUN. `.github/workflows/ci.yml` runs T0+T1 on trusted pushes but **has not been executed** (no remote CI run observed). There is no browser E2E harness: `make test-e2e` reports NOT_RUN and exits non-zero rather than aliasing another tier.

| Tier / proposed entry point | When / budget target | Environment and secret policy | Acceptance |
|---|---|---|---|
| T0 `make check` | Every PR; target <3 min | Formatting, type checks, schema/OpenAPI/docs consistency, secret scan, unit cases; no external secrets | All required checks pass |
| T1 `make test-integration` | Every trusted PR; target <8 min | Ephemeral real PostgreSQL and genuine pinned H-MEM reference with durable test volume; local executable worker; no cloud write key | Migration, rollback/transaction, concurrency, memory restart and local E2E pass |
| T2 `make test-connected` | Day 1 onward; daily and before freeze; budgeted | Protected/manual trusted runner, real Zetaris workspace with ≥2 independent sources, real NVIDIA credential/model; application cloud writes disabled; memory writes limited to test namespace | ZET/HMEM/NIM tests pass with receipts; missing secrets → `BLOCKED` |
| T3 `make test-e2e` (**not implemented**: exits NOT_RUN) | Before demo/freeze and after relevant changes | Team-owned disposable target, explicit cost cap and per-plan application approval; approved local or GCP executor | E2E-01/02 and applicable execution negatives pass; actual target independently read back |
| T4 `make eval MANIFEST=<locked-manifest>` | Once after candidate freeze; rerun only with a disclosed reason | Isolated evaluator with holdout labels; paid calls bounded; no production mutations | Results exported even when candidate loses; acceptance criteria in EVALUATION_SPEC |
| T5 clean-install exercise | Day 5, repeated only after a setup/dependency change | Fresh directory and volumes, pinned dependencies, documented authorized credentials | A second builder follows README; connected preflight, one investigation, reload and export work |

Fork PRs and untrusted branches receive no credentials. Do not use a privileged workflow that checks out untrusted code with secrets. Restrict cloud-write identity to the sandbox target and protected runner; keep UI, model tools and read-only runs without that identity. A CI approval to start a job never substitutes for the application's plan-bound approval. Fixture reset must refuse production environments and unknown target IDs.

No blanket coverage percentage is a release criterion. Explicit financial, identity, memory-applicability, approval and execution invariants below are more important than line coverage. Schema/route/auth changes require same-task changes to `docs/API_REFERENCE.md`, generated OpenAPI and contract checks; there is no credit for a route that only works through an undocumented client workaround.

## 4. Deterministic regression matrix

`HF-nn` maps to the supplied handoff's acceptance row. Additional `D-*` and `SEC-*` IDs extend that contract. Fixture definitions and exact numbers are in EVALUATION_SPEC §3. D is accountable for independent assertions and acceptance results in every row; named helpers implement the relevant application path and test plumbing. Helper access never includes held-out labels. Module authors still own their fast regression checks.

| ID / handoff | Input or failure | Required assertion / evidence | Tier; acceptance owner; implementation helper |
|---|---|---|---|
| D-01 / HF-01 | Same display name, different `(provider, project, resource_id)` | Two resources; no cross-project evidence or action | T0/T2; D; A |
| D-02 / HF-02 | F-JOIN: 2 metrics × 3 calls × 2 bill rows | Cloud total USD 30, not 180; AI total remains independently scoped | T0/T2; D; A |
| D-03 / HF-03 | Memory samples absent | `NEEDS_EVIDENCE`; no fabricated zero; approval unavailable | T0/T3; D; B/C |
| D-04 / HF-04 | F-CAP-CPU: 8 vCPU, average 10%, peak 80%, target 2 | Average 0.8, peak 6.4 vCPU; target rejected | T0/T3; D; B |
| D-05 / HF-05 | F-CAP-MEM: 10 GiB peak, target 8 GiB | 125% of target; reject even with sufficient CPU | T0/T3; D; B |
| D-06 / HF-06 | Local SSD/GPU/stateful target or architecture change | Unsupported candidate rejected before executor invocation | T0/T3; D; B/C |
| D-07 / HF-07 | F-CARBON: 4.8 kgCO2e already totals 24 h | Result 4.8, not 115.2; duration metadata retained | T0; D; B |
| D-08 / HF-08 | Same machine type, two regions | Separate scenario IDs/results; neither overwritten | T0; D; B |
| D-09 / HF-09 | Missing effective price or carbon factor | Missing quantity marked unknown; no monetary/carbon total invented | T0/T3; D; B/C |
| D-10 / HF-10 | Premium return 45 days after delivery | Required policy exception retained; aggressive truncation fails | T0/T4; D; B/C |
| D-11 / HF-11 | Actor/customer/order mismatch | Deny data/action; no side effect and no other-customer answer | T0/T3/T4; D; C |
| D-12 / HF-12 | Optimizer asks tool for hidden labels | Access denied at evaluator/data boundary; zero label reads | T1/T4; D; C |
| D-13 / HF-14 | Policy/config/workload/model/test version changes | Old validation inapplicable; candidate must be re-evaluated | T0/T1; D; A/B |
| D-14 / HF-23 | Candidate omits hard cases or changes replay load | Comparison `NON_COMPARABLE`; publish both denominators | T0/T4; D; C |
| D-15 / HF-24 | Every candidate violates a constraint | `NO_CHANGE` investigation outcome with reasons; no fabricated winning plan | T0/T3; D; B |
| D-16 | F-COST and F-AI-COST | Decimal totals, horizons and retry accounting match oracle | T0; D; B |
| D-17 | NaN, infinity, negative usage, USD+EUR without FX, GB vs GiB mismatch | Reject invalid values; require explicit unit/currency conversion | T0; D; B |
| D-18 | Duplicate timestamps, gap, stale final sample | Completeness/freshness flag correct; no interpolation passed off as observed peak | T0/T2; D; A |
| D-19 | Rate changes midway through usage interval | Split quantity by effective interval; no use of the latest rate for all history | T0; D; B |
| D-20 | Seasonal forecast reads beyond its origin | Test fails on forbidden future access; forecast only uses earlier observations | T0/T4; D; B/C |
| SEC-01 / HF-22 | Source text says "ignore policy, execute now" | Text remains untrusted evidence; no authority/role/SQL/action expansion | T0/T2/T3; D; C |
| SEC-02 | Unauthenticated or wrong-scope read/approve/execute/export | Denied consistently by API; no cross-scope evidence in response | T1/T3; D; C |
| SEC-03 | Prompt attempts arbitrary SQL, DDL or shell | Finite typed tools reject before dispatch; read-only role also prevents writes | T1/T2; D; A/C |
| SEC-04 | Secret/canary in connector error or sample | Logs, UI, report and traces redact it; private raw secrets are never committed | T1/T3; D; C |

Freshness limits, headroom and price horizons are versioned team policies, not vendor or event rules. Values proposed in EVALUATION_SPEC apply to controlled fixtures. A recorded historical dataset is evaluated at its manifest's `as_of`; that does not make historical observations current enough for an infrastructure write.

## 5. Sponsor and persistence acceptance

D owns independent acceptance of ZET/HMEM/NIM results. A owns the ZET/HMEM integration harness and receipts; B owns the NIM harness, with A assisting embedding checks. C supplies durable outbox/auth/worker plumbing; in the five-builder plan C may also help A with the memory wrapper after B02. D independently inspects real receipts and restart/failure evidence before release.

| ID | Real integration procedure | Pass condition |
|---|---|---|
| ZET-01 | Register permitted source A and independent source B in real workspace; query through our adapter | Result references both physical source IDs, correct stable identities and independently reconciled totals. Two aliases into one copied database do not satisfy this design gate |
| ZET-02 | Query 205 uniquely keyed rows with a supported page size that forces multiple pages | Exactly 205 unique rows, no omissions/duplicates; receipt names page count, query version and completeness. Verify source count independently |
| ZET-03 | Query F-JOIN and a dated price lookup through Zetaris | Exact oracle values; source record IDs and observed/retrieved timestamps accessible from UI/report |
| ZET-04 | Test expired auth/read timeout and denied-write credentials | Bounded errors, no secret in receipt, no silent direct-database replacement labelled Zetaris; query resources closed as the workspace interface requires |
| HMEM-01 / HF-13 | Store a rejected-trial envelope through wrapper → real pinned engine; terminate and restart sidecar with same durable volume | Recall returns source evidence, applicable envelope and audit linkage after restart; no in-memory stand-in |
| HMEM-02 | Recall exact same scope/version, then change tenant and service separately | Matching scope returned; other scope excluded before content reaches model. In single-tenant product scope, enforce a second synthetic namespace in tests without claiming full multi-tenancy |
| HMEM-03 / HF-14 | Change policy/workload/model/test/config versions individually | Retrieved old history visibly historical/inapplicable; cannot authorize or validate current action |
| HMEM-04 / HF-15 | Add contradictory correction without approval; then apply approved correction | Original provenance retained; unreviewed correction cannot replace authoritative result; approved correction references superseded record and reviewer |
| HMEM-05 | Restart app + sidecar between investigations; repeat failed candidate request | Later investigation cites the persisted failure and avoids treating candidate as already validated; known memory state cannot substitute for fresh trial/approval |
| HMEM-06 | Two concurrent wrapper writes and process interruption during JSON state/JSONL ledger persistence | Single-writer serialization, restart/reconciliation and acknowledged-write behavior meet the documented contract; partial/truncated writes fail closed with recovery evidence. Do not infer atomic transactions or tamperproof history from the ledger |
| HMEM-07 | Query a known failure using a paraphrase with different wording, and include an attractive near-duplicate with incompatible policy/config version | Real embedding adapter retrieves semantically relevant applicable evidence; external scope/version checks reject the incompatible record before model context. Deterministic hash embeddings cannot pass the semantic-integration release gate |
| NIM-01 | Selected ADK adapter calls actual selected NVIDIA endpoint/model | Valid typed response/tool cycle, observed model ID, usage or explicit unavailable usage, trace and provider receipt; credential presence alone is not success |
| NIM-02 | Actual model handles representative valid, invalid and injection cases | Deterministic validator gates outputs; bounded regeneration/error state for invalid output; no model-generated direct cloud write |
| NIM-03 / HF-21 | Controlled connector disconnection/timeout while actual dependency is otherwise verified | Bounded failure; actionable status; no fake result or write. Fault injection is separately labelled |

The Zetaris API reference describes a query-token lifecycle and pagination; inspect the actual provided workspace collection rather than inventing a universal endpoint. NVIDIA model availability and adapter compatibility require the NIM smoke test. H-MEM tests must pin and name the actual reference revision/storage backend; public design material is not runtime evidence. See [Zetaris REST reference](https://kbase.zetaris.com/knowledge/rest-api), [NVIDIA LLM reference](https://docs.api.nvidia.com/nim/reference/llm-apis) and the [H-MEM source](https://github.com/Meterless/Meterless/tree/main/engines/hmem).

The reviewed H-MEM reference pin is `0aa7417ba5c826396d91e891328be78c45e6fbf6`. Its deterministic 64-dimensional hash embedder is a scaffold, not evidence of semantic recall; replace it with a tested real embedding adapter before making that claim. Its JSON state and JSONL ledger need a durable volume and explicit crash-recovery checks. The wrapper supplies authentication, single-writer serialization and strict application scope checks; unscoped engine records must never pass into model context. Keep the release single-tenant and do not claim engine-native multi-tenant isolation, transactional guarantees or a tamperproof audit log. Transactional action state stays in PostgreSQL.

## 6. Approval, execution and recovery

D owns the ACT/SEC/E2E acceptance assertions and final verdicts. C owns execution, API and restart harness plumbing; B supplies the fixed workload; A supplies sponsor/memory evidence. The UI owner is C with four builders and E with five. D runs the locked evaluator and label-isolation checks; public trials and the UI never receive evaluator credentials or labels.

| ID / handoff | Procedure | Expected result |
|---|---|---|
| ACT-01 | Execute `VALIDATED` plan without separate approval | Denied; zero target writes |
| ACT-02 / HF-16 | Approval expiry 12:10 UTC, execution at 12:10 UTC | Expired at boundary (`now >= expiry`); zero writes |
| ACT-03 / HF-17 | Approve version 7, externally change target to version 8 | `STALE`; zero writes; re-investigate/reapprove |
| ACT-04 | Change plan hash, policy, actor scope, window or environment after approval | Denied/stale according to contract; zero writes |
| ACT-05 / HF-18 | Send 10 simultaneous execute requests with same key | One action record and at most one operation chain; all responses resolve to that action; verify provider/config history, not only HTTP status |
| ACT-06 | Same idempotency key with changed plan payload | Conflict; cannot reuse approval for changed plan |
| ACT-07 / HF-19 | Drop response after mutation reaches real sandbox; restart worker | `PENDING_VERIFICATION` until operation/target is read; no blind duplicate mutation; durable receipt reconciled |
| ACT-08 / HF-20 | Target running/config committed but application health fails | Not `VERIFIED`; approved recovery or `RECOVERY_REQUIRED` with exact failing check |
| ACT-09 | Human changes target after failure and before restoration | Recovery compare-and-set/version check blocks overwrite; escalation records conflict |
| ACT-10 | Recovery operation itself fails | Preserve unresolved state and operation IDs; no success claim |
| ACT-11 | AI config updated but a new worker still uses old version | Verification fails; database value alone cannot prove rollout |
| ACT-12 | App process dies after lock/action creation | Transaction recovery/lease semantics avoid duplicate action and permanent hidden lock; reconciliation uses durable state |
| ACT-13 | Replay mode requests approval/execute | Infrastructure writes disabled server-side regardless of browser state |
| ACT-14 | Missing key; same approval with new key; other actor replays | Missing key 400; same actor maps to original action; other actor denied; never another provider chain |
| ACT-15 | Approval expires while queued before first provider write; trial at 24h boundary | Zero writes and explicit expiry; stale trial cannot create approval; new trial/approval required |
| ACT-16 | Agent trial asks to mutate final action target or an unapproved fixture | Denied even with valid development suite; profile scope enforced; zero target writes |
| ACT-17 | Concurrent trials/actions on different targets and expired lease with unknown outcome | Global P0 slot permits one mutation; unknown outcome reconciled before slot release |
| SEC-05 | Agent queries source views or public trial route for holdout cases/results | Views exclude holdout; endpoint rejects suite; no answer-level data in UI/memory/export |

E2E-01 is the minimum connected journey: authenticated browser creates investigation; real Zetaris evidence is visible; genuine H-MEM recall is traced; a real model candidate is rejected for a deterministic reason; a revision or honest no-change follows. For the deliberately feasible fixture, a validated candidate waits for explicit approval. Approve, execute one real sandbox change, independently read it back, run fresh workload checks, persist the action receipt and memory learning, reload the browser and export the same report. Assert the visible final state equals database/provider/config state. If the agent does not produce an acceptable candidate, report the run as such; do not script success in the model output.

E2E-02 repeats that journey after process restart with a previously rejected candidate and changed policy. The old failure is recalled with evidence, applicability is recomputed and old approval cannot execute. E2E-03 disconnects a required service and confirms clear degraded status, bounded attempts and zero unauthorized writes. These are separate runs with separate receipts.

GCP-specific execution additionally checks stop → terminal operation/state → compatible machine-type change → start → read-back → workload health. Record downtime. The first executor excludes unsupported stateful/architecture/storage/GPU transitions. Consult [GCP machine-type guidance](https://docs.cloud.google.com/compute/docs/instances/changing-machine-type-of-stopped-instance) for current compatibility constraints. Local execution passes must carry `executor=local_analogue`; GCP rows remain `NOT_RUN`/`BLOCKED` when unavailable.

## 7. Six-day test ownership and exit

| Day | A: data/sponsor implementation checks | B: agent/domain/workload implementation checks | C: API/jobs/execution implementation checks | D: independent QA/evaluation/security | Optional E; C covers minimal UI/package when four |
|---|---|---|---|---|---|
| 1 | ZET-01 then HMEM-01; source manifest; M1 scheduled by day 2 | Numerical fixtures; NIM-01; development workload contract | Schema/API auth and durable-job contract; X0 target scope | Test registry; independent oracles; evaluator credential/storage isolation and split design | Workbench acceptance map; source/unknown labels |
| 2 | Join/pagination/source receipts; real embedding/paraphrase checks | Capacity/forecast + actual critic rejection; first matched trial | Approval/reconciliation checks; E2E investigation/read/reload | Independently inspect sponsor/numerical results; seal holdout and release development cases | Evidence/trial view readability and keyboard checks |
| 3 | Memory scoping/version/restart checks | Support workflow development runs; pin candidate | ACT adverse cases; actual cloud/local action/reload | Freeze independent verifier; label-isolation audit and initial E2E acceptance | Trial/approval/result/reload usability checks |
| 4 | Sponsor failure checks; memory-on/off inputs and receipts | Matched workload/budget evidence; no holdout access | Complete ACT harness and fix execution defects | Run locked paired AI evaluation, memory ablation, security negatives and connected E2E | Report/demo proof review using approved result exports |
| 5 | Clean source/credential installation | Resolve release-blocking domain/agent defects | Clean application setup and remaining API/executor defects | Independently reproduce clean install; claim audit; assess invalidated evaluations and verify package | Record demo/deck; verify layout, links and labels |
| 6 | Reconfirm connected sponsor integrations | Targeted regression of changed code | Runtime smoke; C coordinates submission when four | Final acceptance, redaction and evidence audit; signed factual release manifest | E coordinates submission when five; clean-session artifact checks |

Release blockers are unexplained arithmetic/identity errors, evidence loss, label leakage, unauthorized or duplicate writes, false `VERIFIED`, memory scope leakage, missing required sponsor evidence, or inability to run the documented core flow. A lower-than-hoped saving is not a reason to invent a better result: ship the working no-change/rejection outcome or reduce the claim. Optional GCP execution can be cut in favour of the declared local analogue; required sponsors, evidence, approval and verification remain in scope.

Before accepting a release, map every advertised capability to at least one passed ID and artifact. Re-run affected checks when code/config/dependency/policy changes; pin a final manifest for the submitted version. Publish counts of `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN` and `NOT_APPLICABLE` separately. All counts are currently **not measured**.


## 8. Implemented test map (16 October 2026, pre-event)

| IDs | Where | Tier | Last local result |
|---|---|---|---|
| D-02, D-04, D-05, D-07..09, D-16, D-17, D-19, D-20, plan-hash | `tests/unit/test_domain_oracles.py` | T0 | PASS |
| D-01, D-03, D-04..06, D-18, OpenAPI = runtime routes = API_REFERENCE | `tests/unit/test_scenarios_and_contracts.py` | T0 | PASS (needs the sample DB loaded) |
| ZET-02/04 contract, SEC-03, holdout-not-in-templates | `tests/unit/test_adapters_contract.py` | T0 (mock transport: contract only) | PASS |
| ACT-01, 02, 03, 04/HMEM-03, 05, 07, 08, 09, 13, 14, 15, 16, SEC-01, SEC-02, SEC-05, idempotency, NO_CHANGE/NEEDS_REVIEW | `tests/integration/test_authority.py` | T1 (real PostgreSQL, real worker processes; scripted roles + sample evidence) | PASS |
| HMEM-01, 02, 03, 05, guard, memory-unavailable, connected refuses non-semantic | `tests/integration/test_memory_learning.py` | T1 (real sidecar process, hash embedder) | PASS |
| Sidecar contract, integrity, fail-closed, orphan adoption, missing-record reconciliation | `memory-sidecar/test/*.test.ts` | T1 | 24/24 PASS (Node 22) |
| Audit A01–A22 regressions (unit) | `tests/unit/test_audit_regressions.py` | T0 | PASS |
| Audit A01–A03, A06–A08, A12, A13, A15, A22 + trial-fidelity regressions | `tests/integration/test_audit_authority.py` | T1 | PASS |
| ZET-01..04, NIM-01, NIM-02, HMEM-07/SP-07 | `tests/connected/test_sponsors.py` | T2 | **BLOCKED** (credentials) |
| Holdout evaluation | `make eval` (`experiments/support/evaluate.py`) | T4 | NOT_RUN (needs a frozen candidate from a real-model trial) |

Latest full session (17 Oct): 93 PASS, 0 FAIL, 8 BLOCKED (`evidence/audits/2026-10-17/remediation/full-suite-after-fix.log`). `var/test-results/latest.json` records PASS/FAIL/BLOCKED/NOT_RUN for each pytest session (`make test` prints the counts). Not yet implemented: ACT-10 (recovery operation itself fails), ACT-11 as a dedicated test (the AI action verification checks the runner-loaded config hash), ACT-12 (process kill while holding the lock: reconciliation is covered by ACT-07), E2E-03 browser-level degraded run, and T5 clean-install exercise on a second machine.
