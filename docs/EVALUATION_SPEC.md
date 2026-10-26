# Evaluation specification

**Status: proposed protocol, 16 October 2026. No metrics below are measured results.** Numerical examples are synthetic test oracles, not vendor prices, real savings or achieved model quality. Freeze this protocol before the final evaluation; disclose amendments with date, reason and affected comparisons.

D owns independent evaluation, the support verifier, held-out labels, evaluator credentials and result reporting. D does not tune candidates. A reconciles source totals and memory receipts; B implements candidates, deterministic tools and the support workload; C implements API/job/executor boundaries. In the confirmed 4–5-builder plan, optional E presents D-approved exports in the UI/demo; with four builders C owns the minimal UI and packaging. Neither roster gives A, B, C, E, model agents or their tools access to held-out labels. The [test strategy](TEST_STRATEGY.md) maps these fixtures to implementation tests; the developer handoff (local reference, not published) supplies scope. Event requirements and team quality choices are different: the supplied Welcome Guide (local reference, not published) requires genuine sponsor use and a working submission, but does not prescribe our headroom, sample size, latency or savings targets.

## 1. Questions and honest claims

| Experiment | Question | Evidence we can produce | Limit |
|---|---|---|---|
| Cloud decision benchmark | Does evidence-based screening avoid unsafe recommendations made by a simple average-utilization threshold? | Candidate decisions against known synthetic stress/compatibility cases; later observed demand and real matched workload results | Synthetic histories are not a customer fleet or realized billing reduction |
| Support efficiency | Does a bounded configuration reduce total cost while preserving independently checked task outcomes? | Paired real model runs on fixed cases, full attempts/tokens/tool usage and verifier failures | 40 held-out cases are a small local evaluation, not broad non-inferiority proof |
| Memory ablation | Does persisted, applicable experience prevent repeated failed trials without suppressing newly valid plans? | Same investigation sequences with memory enabled/disabled, retrieval/audit evidence, call/cost overhead | Few sequences and stochastic models limit causal/general claims |
| Execution acceptance | Can one approved change be applied once, verified and durably reported? | Actual provider/configuration read-back, fresh workload, action receipt and UI reload | A disposable target does not establish production safety or always-successful recovery |

Separate four result classes in every report: `measured` (actual trial observations), `projected` (usage × rates over a stated horizon), `estimated` (method-dependent carbon/energy), and `unknown`. Also state `data_origin=synthetic|real_permitted` and `runtime_mode=sample|connected_demo|replay`. A live query against synthetic history is connected execution with synthetic data; neither label implies the other.

## 2. Dataset, splits and leakage controls

### Cloud dataset

Use six synthetic resources with 21 days of quarter-hour observations: **6 × 21 × 96 = 12,096** baseline rows. Record UTC interval boundaries, source resource identities, CPU percent, memory bytes/GiB, application latency/error rate, resource capacity and version. The complete baseline has unique `(provider, project_id, resource_id, timestamp)` keys. Missing/stale/duplicate cases are explicitly derived fault fixtures, not silently deleted rows.

| Partition | Days | Rows | Permitted purpose |
|---|---:|---:|---|
| Development | 1–14 | 8,064 | Choose features, policy thresholds and simple forecasting approach |
| Calibration | 15–17 | 1,728 | Freeze empirical residual envelope and thresholds |
| Final temporal evaluation | 18–21 | 2,304 | Report untouched later-day behavior after method freeze |

Use a daily seasonal-naive forecast (`previous day's same quarter-hour`) initially. At each daily forecast origin, predict the next 96 observations using only data available then. Fit the residual-envelope method using development/calibration only, then freeze it. In the final four days, earlier evaluation-day observations may enter the next day's rolling history only after their timestamps; never retune parameters on final errors. Report each origin/horizon and no-future-data assertion. An empirical upper envelope is a stress bound; do not call it a calibrated 95% confidence interval.

Give the six resources deliberately different scenarios: safely rightsizeable; low average/high CPU peak; memory constrained; missing/stale evidence; unsupported configuration; and policy/maintenance-window restricted. Include at least two projects with a colliding display name. Keep the ground-truth constraint ledger independent of candidate model prompts. This makes safety checks auditable but does not make the six histories representative of all workloads.

### Support workflow

D creates and controls **80 independently labelled cases**, 16 per category: order status, standard returns, premium/membership exceptions, missing required fields, and required escalation/identity denial. Split each category into eight development and eight holdout cases: **40/40** total. Avoid near-duplicate orders/policy wording across splits; group variants of the same underlying scenario in one partition. Maintain balanced boundary cases near 30/60 days, not just easy positives.

Each case includes case ID, permitted customer/order data, policy version, request, required facts/actions, prohibited disclosures/actions, tool expectations and severity. The verifier must evaluate facts/actions against structured records and policy. Free-text similarity or a second LLM's approval is insufficient. An LLM can provide supplementary commentary, clearly separated from deterministic acceptance.

D releases only the 40 development cases and their labels to B for candidate implementation and tuning. A may review public verifier logic and manifest counts/hashes without seeing the private answer key. D retains the 40 holdout inputs/labels in evaluator-only storage, freezes the independent verifier and records its version. D may explain development failures but cannot change candidate prompts/configurations to fit private holdout cases. Development labels may guide up to three candidate configurations, with at most two revisions. Start with the same model. Freeze model/adapter parameters, prompt/config hash, tool code, retrieval rules and verifier before final evaluation. Store holdout inputs and labels in an evaluator-only location; commit a manifest with counts and hashes, not a tool-accessible answer key. The optimizer, its retrieval index and H-MEM ingestion must have no route to holdout labels or evaluator outputs during tuning. Evaluator credentials are separate from agent credentials. Inspect traces for attempted label access.

After B records the candidate freeze, D runs baseline and pinned candidate on the same 40 holdout cases under the locked evaluator. D is the sole label custodian and exports approved aggregate results and redacted evidence for reporting; the normal UI, memory and source views never receive the answer key. Evaluate all assigned cases, including timeouts and failures. Holdout results can enter the final report after completion, but changing the candidate after seeing them makes this set development data; obtain a fresh locked set for a new final comparison or explicitly label the reused-set result exploratory. Running three candidates on holdout and reporting only the best is forbidden by this protocol.

## 3. Numerical fixtures and independent oracles

These examples define expected outputs for future tests. Keep values in a small versioned fixture file, calculate expectations independently of production functions, and use decimal accounting. Store raw precision and round only display values.

### F-JOIN: many-to-many inflation

One resource `gcp/project-a/worker-01` has two metric rows, three AI call rows and billing rows `b1=USD 10`, `b2=USD 20` in the same interval. A raw cross join has **2 × 3 × 2 = 12 rows** and wrongly sums billing to **USD 180**. Correct resource billing total is **USD 30**. Aggregate each fact table at its intended grain before relating them; do not repair by deduplicating equal amounts, since two legitimate USD 10 bills must still total USD 20.

If a service spans two resources and its AI cost is USD 0.15, that service-level amount remains USD 0.15; displaying it twice does not make portfolio AI cost USD 0.30. Preserve cloud/AI boundaries and attribution method in the report. A second `worker-01` in `project-b` is a different resource.

### F-CAP-CPU / F-CAP-MEM: capacity and units

- Source has 8 vCPU; average CPU 10%, observed peak 80%. Approximate average demand is **0.8 vCPU**; peak demand is **6.4 vCPU**. A 2-vCPU target sees **320%** peak demand and must fail even though average utilization appears low.
- Chosen fixture policy allows demand at most 80% of target CPU capacity. A 2-vCPU target provides **1.6 vCPU** permitted demand; an 8-vCPU target provides **6.4 vCPU**. Equality passes the CPU screen only; it says nothing about memory, forecast uncertainty or measured performance.
- Peak memory is **10 GiB = 10,737,418,240 bytes**. An 8-GiB target implies **125%** usage and fails. A 16-GiB target implies **62.5%** usage and passes an 80% memory screen, subject to all other checks.
- A forecast stress demand of **7.2 vCPU** fails the 8-vCPU target's 6.4-vCPU screen. Never replace an observed peak with the lower average. Missing memory remains `unknown`, not 0 GiB.

This proportional screening assumes comparable CPU behavior; actual hardware and application performance require a matched workload trial. A hardware-family change is outside initial executor scope.

### F-COST: horizons and net projected savings

Fictional on-demand rates, same currency and interval: baseline USD 0.20/hour, candidate USD 0.12/hour, horizon 720 hours, experiment cost USD 3.00, transition cost USD 1.20. In this fixture the USD 3.00 experiment cost already includes optimizer overhead; do not subtract it twice.

```text
baseline projected cost = 0.20 × 720 = USD 144.00
candidate projected cost = 0.12 × 720 = USD 86.40
gross projected reduction = USD 57.60 (40% of baseline)
net projected saving = 144.00 - 86.40 - 3.00 - 1.20 = USD 53.40
```

Do not subtract the USD 4.20 again if it is already included in candidate total. If the account has unchanged prepaid committed spend, label resource-price reduction separately from invoice saving; the latter may be zero or unknown. Mutually exclusive candidate savings must not be summed.

Rate-boundary oracle: 10 hours usage, USD 0.20/hour for the first four hours and USD 0.10/hour for the next six yields **USD 1.40**, not USD 1.00 or USD 2.00. No currency conversion exists unless a dated FX source is supplied.

### F-AI-COST: accepted task accounting

Fictional rates: USD 1/million input tokens and USD 2/million output tokens. Baseline uses 100,000 input and 20,000 output tokens plus USD 0.01 tool cost across 40 cases, including retries and failed attempts: **USD 0.15 total**. If 38 tasks are independently accepted, cost per accepted task is **USD 0.003947368421...**.

Candidate uses 70,000 input and 15,000 output tokens plus USD 0.01 tools: **USD 0.11 total**. At the same 38 accepted tasks, cost per accepted task is **USD 0.002894736842...**; gross batch reduction is **USD 0.04 = 26.6667%**. An additional USD 0.03 optimizer experiment overhead leaves **USD 0.01** net benefit for this batch. These counts are an arithmetic fixture, not an expected experiment result.

Tokens above already include retry calls: do not add those tokens twice. If provider usage is absent, mark the total incomplete and explain any separate tokenizer estimate. Free sponsor credits can mean measured billed cost is USD 0 while catalogue-equivalent cost is nonzero; report them separately. With zero accepted tasks, cost per accepted task is **undefined/null**, never zero. Baseline acceptance zero makes a relative quality-change percentage undefined too.

### F-CARBON: dimensions and coverage

An estimated 2 kWh at a dated intensity 0.4 kgCO2e/kWh yields **0.8 kgCO2e**. If that energy already includes data-centre overhead, applying PUE again is double counting. A source field explicitly reporting **4.8 kgCO2e for the whole 24-hour interval** remains 4.8; multiplying by 24 again incorrectly yields 115.2.

Same type in regions A/B with 2 kWh each and intensities 0.4/0.2 yields **0.8 / 0.4 kgCO2e**, represented as distinct scenarios. Unknown factor yields unknown estimate, not zero. Keep operational and embodied values distinct; external model tokens alone do not determine model carbon. Carbon is not a required success metric when defensible factors are unavailable.

### F-SUPPORT: independently decidable policy cases

For this synthetic policy only: standard returns permitted through day 30 after delivery; premium through day 60; order/customer identity must match; missing identity requires clarification without data disclosure; uncertain or prohibited exceptions require escalation. Use whole elapsed UTC days as the fixture's defined convention.

| Request facts | Expected structured outcome |
|---|---|
| Matching standard customer, delivered 30 days ago | Return eligible; boundary is inclusive |
| Matching standard customer, delivered 31 days ago | Not eligible under standard policy; no return side effect |
| Matching premium customer, delivered 45 days ago | Return eligible; answer must preserve premium exception |
| Matching premium customer, delivered 61 days ago | Not eligible under current policy; do not invent extension |
| Customer A asks for customer B's order | Deny disclosure/action; no address/status leakage |
| Order ID absent | Ask for required identifier; zero order-action side effects |

If the support trial includes only read-only tools, report action *recommendations* as such. Do not claim a refund or return was executed without a separate real sandbox action receipt.

## 4. Cloud comparison protocol

Baseline B0 is deliberately simple and frozen: if average CPU <20%, recommend the next smaller permitted size. Record its inputs and omitted checks so comparison is fair; do not caricature it as an industry-standard optimizer. B1 is GreenOps Verify with peak/stress CPU, absolute memory, completeness, compatibility, policy, window and matched trial constraints. Both evaluate the same six resources at the same origins/rates.

Report candidate count, known-unsafe proposals, feasible candidates retained, unsupported/needs-evidence cases, and no-change outcomes. Score against the independent constraint ledger before model-generated explanations. The ledger's binary rule compliance is separate from real workload performance. No unsafe acceptance is allowed in the fixed regression suite; this is an invariant over these fixtures, not a measured universal error rate.

Before running any mutation-based trial, require an approved trial profile for a disposable fixture distinct from the eventual action target; the public trial tool cannot mutate the action target or run holdout suites. For one feasible trial fixture, run baseline and candidate on an identical workload manifest: same request IDs/mix, input bytes, concurrency, warmup, duration, dependency state and target environment. Proposed small trial: 30-second warmup then three paired 60-second measurements, alternate order A/B then B/A then A/B, at a fixed offered rate. Record completed tasks, failures, p50/p95 latency, CPU/memory and interval cost. Requests that time out remain failures. If external traffic, offered load or dataset changes materially, mark `NON_COMPARABLE`; do not normalize it away without explanation.

GCP resize trials have stop/start downtime and changed cache state; record both and warm up after restart. A local worker trial supports only local performance conclusions. Projecting a month of catalogue cost from a one-minute trial remains a projection. Report any application budget or spend cap hit as a real outcome, not a reason to omit the attempt.

## 5. Support comparison and uncertainty

Run baseline/candidate in interleaved randomized order with a recorded ordering seed. Fix model identity, generation settings, tool datasets and policy. Temperature zero may reduce variability; it does not guarantee deterministic output. Preserve all raw responses/tool events in the redacted evidence bundle. One paired 40-case run is the mandatory minimum for this scope; if budget permits, repeat both conditions with a preregistered count, report every run and do not treat repetitions of the same 40 cases as new independent cases.

Primary quality metric: number of cases satisfying **all** required facts/actions and zero prohibited behaviors, divided by all 40 assigned cases. Also publish category-level counts, critical-failure count and paired discordance: both pass, baseline only passes, candidate only passes, neither passes. Secondary metrics: total input/output tokens, number of model/tool calls, retries, wall latency per case, total actual/estimated cost, cost per accepted task and net benefit after experiment overhead. Missing usage gets an explicit completeness percentage.

Proposed selection gate: zero critical failures; candidate loses none of the baseline-passing cases; candidate passes at least 38/40 overall; and its cost per accepted task improves when price/usage coverage is complete. This deliberately conservative local gate does not prove statistical non-inferiority. A candidate with lower cost but a premium-policy regression fails even if aggregate accuracy is unchanged. If baseline itself is below 38/40, fix baseline on development data before freezing or report that the quality target was missed; do not hide this through relative improvement.

For each proportion report numerator/denominator and a 95% Wilson interval. With 40/40 passes, the two-sided Wilson lower bound is only about **91.2%**; perfect observed performance on 40 cases does not prove 99% reliability. Use case-paired bootstrap intervals for differences/cost ratios only as exploratory summaries, preserving paired cases and categories; label the tiny-sample limitations. Do not claim statistically significant superiority unless the preregistered analysis actually supports it. Published p95 latency from 40 observations is unstable; include raw counts, p50/p95 and maximum rather than implying a production SLA.

## 6. Memory ablation

Create six short investigation sequences: repeated rejected CPU candidate; repeated memory-constrained candidate; successful prior plan; policy revision invalidating prior success; corrected source superseding a prior conclusion; and similar names in a different tenant/service namespace. Each has an initial investigation and a later related investigation. Start memory-on and memory-off from identical clean snapshots; fix source versions, prompt/model settings and budgets, and randomize condition order.

Memory-on must use real persisted H-MEM and survive a restart between sequence steps. Replace the reviewed reference's deterministic 64-dimensional hash embedder with a pinned real embedding adapter before claiming semantic recall. Add paraphrased recall requests and near-duplicate records with incompatible policy/config versions to each relevant sequence. Count a retrieval as useful only when the expected source is retrieved and external applicability checks allow it; high similarity alone is insufficient. Explicitly reject unscoped records before context injection. Record embedding model/version, dimensions, index rebuild state and embedding cost.

Memory-off bypasses recall/remember while all other application validation remains enabled. Do not remove safety checks from memory-off to manufacture benefit. Keep holdout labels out of both conditions and all memory records. H-MEM's JSON state/JSONL ledger restart/crash behavior is tested separately from PostgreSQL transaction behavior; this evaluation does not claim tamperproof history or engine-native tenant isolation.

Report repeated failed trials avoided, newly valid plans incorrectly suppressed, invalid memories prevented from applying, final decision correctness, model/tool calls, elapsed time and total cost. Count the memory write/recall and any model-assisted mining costs. Require zero cross-scope exposure and zero stale-memory authorization in the fixed cases. Improvement in latency/cost is a hypothesis, not a promise; memory overhead may outweigh savings at this scale. Six sequences support an illustrative ablation, not a broad causal claim.

## 7. Proposed operational targets

All values below are **team-chosen initial targets**, subject to documented day-one evidence. They are not sponsor guarantees, event requirements or current measurements. Business-owner policy remains authoritative for an actual target.

| Area | Initial target | Measurement / consequence |
|---|---|---|
| Evidence completeness | Baseline fixtures 100% of expected rows; for an executable candidate, no unexplained gaps in critical CPU/memory/health evidence | Missing critical evidence blocks approval; historical sample `as_of` is explicit |
| Freshness for sandbox execution | Target state re-read immediately before mutation; telemetry latest sample ≤30 min; price interval covers planned horizon | Recheck on execute; stale approval/evidence blocks write. Adjust only with versioned policy |
| Capacity screen | Demand ≤80% of target CPU and memory | Preliminary filter; matched workload must also pass |
| Workload quality | No new functional failures; measured p95 no more than 10% above baseline and below declared workload SLO | Require adequate observations and report noise; a 60-second trial does not establish long-term SLA |
| Support quality | ≥38/40 accepted, zero critical failures, no baseline-pass → candidate-fail regressions | Local selection gate; no broad reliability claim |
| Efficiency aspiration | ≥15% lower cost per accepted task on matched cases | Aspirational; report actual result or `NO_CHANGE`, never manipulate thresholds to force a win |
| Read/UI response | API read p95 <1 s over 30 warm reads excluding external investigation work | Show measurement sample; do not block correctness work for cosmetic speed |
| Evidence/proposal responsiveness | Initial progress visible <2 s; evidence/proposal stage target <120 s for six resources, excluding separately budgeted trials | Async UI with stage clocks; no claim that the complete experiment fits this target |
| Dependency budget | Read call 15 s, at most 2 transient retries, model call 45 s; evidence/proposal stage hard limit 180 s; local paired trial cap 15 min | Each persisted stage has a finite deadline; full workflow/optional GCP deadlines are configured separately. Writes reconcile unknown outcomes |
| Execution | One target at a time; expiry checked at action time | GCP operations have a separately configured deadline; pending is not verified |
| Spend | Explicit finite per-run cap required before connected model/trial jobs | Reserve approved conservative monetary bounds plus request/token caps when actual rates are unavailable; otherwise block new spend. Never label an unknown monetary cap as enforced |

## 8. Evidence bundle and reporting template

Each final run writes a manifest containing run ID/time, code commit, dependency lock hashes, model/adapter version, prompt/config/policy/workload/test-set hashes, source versions, runtime/data-origin labels, pricing/carbon method versions, baseline/candidate identity, seeds/order, hardware/environment and budgets. Record complete test outcome counts and block reasons. Hash the manifest and point exported reports to it. Redact personal data, secrets and private provider identifiers before public release; retain authorized internal evidence separately.

The result bundle should contain `manifest.json`, `cases.jsonl`, `metrics.json`, redacted `traces.jsonl`, source/query receipts, memory audit references, action/read-back receipts, numerical reconciliation and a concise report. These are planned filenames, not existing outputs. The report begins with the actual question and result, lists denominators and failures, and distinguishes measured workload performance from projected cost/carbon. Every screenshot/video overlay includes live/replay, synthetic/real data and executor mode where relevant.

| Result field | Current value |
|---|---|
| Zetaris connected-source acceptance | Not run |
| H-MEM persisted/restarted retrieval | Not run |
| NVIDIA adapter/model acceptance | Not run |
| Cloud fixture / workload outcome | Not measured |
| Support holdout quality / cost | Not measured |
| Memory ablation effect / overhead | Not measured |
| Approved change / read-back / recovery | Not run |
| Clean installation | Not run |

Final claim audit: each number resolves to a run and formula; every success has a denominator; all retries/failures remain counted; required sponsor checks are passed rather than skipped; replay is dated and labelled; a locally executed analogue is named accurately; limitations fit visibly in the report and demo. A well-evidenced rejection is a successful verification outcome even when no cost-saving change is approved.


## Protocol amendments

| Date | Amendment | Reason | Affected comparisons |
|---|---|---|---|
| 2026-10-17 | Local matched-trial p95 gate: p95 is computed over **all pooled request latencies per side**, and a regression must also exceed the limit in a **majority of paired windows**. Per-pair ratios and sample counts are reported. The 10% threshold is unchanged | With identical configurations on both sides, the earlier median-of-window-p95 over 3-second test windows failed about 1 run in 5 under load (identical 4 vs 4 configs; evidence in `evidence/audits/2026-10-17/remediation/`). After the change: 15/15 identical-config PASS, and the 8→2 regression still FAILS | Development cloud trials only. No final evaluation had been run, so nothing was invalidated |
| 2026-10-17 | Offered-load fidelity and gate metric. (a) Every window records load-generator schedule lag. A pair with lag p95 > 10 ms or lag max > 25 ms in any window is non-comparable: it is discarded, recorded and re-measured, at most 4 times. With no clean pair the trial is INCOMPLETE, never PASS/FAIL. (b) The regression gate uses **server-side latency** (queue wait + delivered service, reported per request by the worker), pooled per side with the majority-of-pairs rule and the unchanged 10% threshold. The SLO check stays client-observed end to end | Measured root cause: client-observed p95 varied 87–139 ms in windows where server queue p95 was 0 ms and service p95 was ~70 ms, so the noise was the in-process load generator, not the system under test. Spikes with real queueing coincided with send bursts. Afterwards: 4v4 20/20 PASSED with server-side pair ratios ≈1.000; 6v4 18 PASSED + 2 INCOMPLETE (no false FAIL); 8v2 3/3 FAILED with ratio ≈14 (`remediation/trial-gate-fidelity.json`) | Development cloud trials only |
| 2026-10-26 | AI development-suite comparability. A case the provider never answered (`DEPENDENCY_UNAVAILABLE`, e.g. HTTP 500) on either side is unjudged: check `AI-COMPARABLE` FAILs and the trial is INCOMPLETE (plan stays DRAFT, no outcome memory), never FAILED. Invalid model output (`MODEL_OUTPUT_INVALID`) is still a quality failure. An outage-damaged baseline is not cached for re-trials. Separately, an unavailable post-trial critic leaves a PASSED trial's plan DRAFT instead of REJECTED | Connected run a721458e: 6 candidate cases hit NVIDIA HTTP 500s and were scored as wrong answers; run 298a9c62: a post-trial critic HTTP 500 rejected a passed trial and wrote a false failure memory (superseded by correction e386e3d5). Gates (38/40, zero critical, no regression, cost per accepted) unchanged | Development AI trials; post-trial review |
| 2026-10-17 | Support verifier v2 judges disclosure independently of the model's self-declared `disclosed_customer_ids`: it checks foreign names, emails, IDs and addresses in the reply, foreign `customer_id`, and denied-order status/address. Lookup tools enforce record authorization before returning data. Failed outputs keep their category | Audit A04/A10 counterexamples were accepted by v1 | Any v1 development result is superseded; v1 numbers must not be reported as v2 |
| 2026-10-17 | `relevant_sections` routing always keeps the decision-critical sections (§1, 3, 4, 5, 10, 11, 12, 13); only peripheral sections are optional | Audit A14: keyword routing dropped both return rules | Development AI trials; token savings are smaller than before |
