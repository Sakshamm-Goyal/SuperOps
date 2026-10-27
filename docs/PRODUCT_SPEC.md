# SuperOps — product specification

Status: implementation plan, 16 October 2026. No integrations, savings, tests or deployments are claimed complete.
This document turns the supplied Developer Handoff (local reference, not published) and Complete Blueprint into product requirements. Their embedded implementation instructions are reference proposals; the repository's adopted decisions govern the build.
Read with [Architecture](ARCHITECTURE.md), [Data and domain](DATA_AND_DOMAIN.md), [Evaluation](EVALUATION_SPEC.md), [Test strategy](TEST_STRATEGY.md) and [Hackathon rules](HACKATHON_RULES.md).

## Product decision

Help one engineering lead decide which cloud and AI spending changes are worth making, test those changes, and inspect the verified result of an explicitly approved action.

**Promise:** “Find avoidable cloud and AI waste. Test the change. Show the evidence. Apply only the approved scope.”
Cloud optimization is the primary journey; one AI Efficiency Lab demonstrates the same evidence and verification process on a support workflow.
The user confirmed an independently authored implementation with third-party GreenOps as concept inspiration, and 4–5 active builders. Target Track 02, subject to organizer confirmation. Keep the bounded product scope; use additional builders for independent evaluation, integration reliability and UX. Concept inspiration does not grant permission to copy upstream code, prompts, assets or results. Record preparation and actual new work separately.

## User, problem and jobs

Primary user: the engineering lead of a small AI-enabled software company operating one GCP support service and an external-model support workflow.
Secondary user: a teammate operating the sandbox, checking source health, enforcing the experiment budget and preparing a reproducible demonstration.
The prototype has one documented sandbox tenant. Production multi-tenancy and enterprise access administration are outside this release.

| Job | User needs | Evidence of completion |
|---|---|---|
| Decide what deserves attention | A bounded queue with reasons, impact assumptions and missing information | Can explain why one candidate advances and another does not |
| Protect service behavior | Peak demand, memory, policy and independent workload checks | A cheaper candidate fails when it violates a required constraint |
| Evaluate an AI efficiency change | Matched cases, required outcomes, all calls/retries and total cost | Can compare accepted outcomes and cost per accepted task |
| Authorize a specific change | Exact target, before/after, version, expiry, downtime and recovery scope | An authenticated approval can authorize only that plan |
| Know what actually happened | Read-back, workload health and an action receipt | Can distinguish applied, pending, verified and recovery required |
| Reuse experience | Sourced prior results that survive restart and respect current versions | A repeated investigation uses an applicable result and explains stale memory |

The user's question is: “What can I change this week without violating this service's requirements?”
A justified `NO_CHANGE` outcome completes that job when no acceptable improvement exists.

## One coherent demonstration

1. Investigate one synthetic support service using real Zetaris queries over independently hosted sources.
2. Reject a tempting worker resize because low average CPU hides a recorded peak; retain its evidence and failed check.
3. Trial a separate staging candidate against a matched workload and locked service constraints.
4. In the AI Lab, reject a context reduction that loses a required policy exception; evaluate a bounded revision.
5. Approve one exact sandbox action, recheck current state, execute once and verify the resulting configuration and behavior.
6. Restart the memory process, reopen the investigation and show a sourced prior result affecting the next decision.
7. Change a relevant policy/workload version and show that prior validation is no longer applicable.

These are acceptance scenarios, not scripted model conclusions. Runtime decisions must follow the records and tests; a revision may also fail.
The constructed 8-vCPU worker averaging 10% with a 6.4-vCPU observed peak is a test scenario, not a hardware benchmark or live customer finding.

## P0 scope and acceptance

Product IDs below remain stable across the backlog, evaluation record and demonstration checklist. They complement the handoff's numbered engineering cases.

| ID | Required capability | Acceptance evidence |
|---|---|---|
| P01 | Bounded investigation | One service, actor, horizon, policy version and spend cap; at most three candidate plans per path and six total; rejected plans count toward the cap |
| P02 | Sponsor-backed evidence | At least two physically independent sources queried through genuine Zetaris; source keys, times, query receipts, completeness and warnings are inspectable |
| P03 | Reliable cloud screening | Six declared synthetic VM histories; identity, peak demand, absolute memory, compatibility, headroom and freshness checks; unsafe/missing-evidence cases cannot advance |
| P04 | Agent revision | Investigator/optimizer/critic produce an observable evidence request or candidate revision from a failed check; deterministic constraints remain authoritative |
| P05 | Measured cloud trial | Candidate and baseline run a matched reproducible workload; report limits of any local analogue; one allowlisted sandbox action has configuration read-back and health evidence |
| P06 | One AI Efficiency Lab | Genuine same-model runs; 40 development and 40 held-out cases; candidate pinned before holdout; independent factual/action checks reject the policy-exception and identity-mismatch cases |
| P07 | Honest economics | Comparable horizon/currency/units; versioned rates; retry, failed-attempt, experiment and transition costs accounted for; measured and projected fields visibly distinct |
| P08 | Bounded carbon reporting | Method, interval, factors, coverage and exclusions shown, or `UNKNOWN`; missing AI carbon does not become zero or token-derived emissions |
| P09 | Approval and execution | Authenticated plan-scoped approval; stale/expired approval rejected; duplicate requests cause at most one actual action; uncertain outcomes are reconciled before retry |
| P10 | Verification and recovery | A running VM alone cannot produce `VERIFIED`; failed checks expose recovery state; restoration respects approval scope and blocks on conflicting external changes |
| P11 | Durable learning | Genuine Meterless remember/recall/audit with the tested retrieval/embedding adapter; recall after process restart; later investigation changes based on applicable evidence; stale/corrected findings retain provenance |
| P12 | Reviewable delivery | Workbench, operator controls and exported report agree after reload; clean setup and acceptance evidence; declared synthetic/replay/pre-existing material and actual sponsor usage |

Release rule: every P0 capability needs recorded evidence. A missing live integration is a blocker to claiming that integration works; it is not converted into a pass by fixture data.
The cloud executor may be a disposable team-owned GCP VM when access is ready, or an explicitly labelled real local worker/configuration analogue. The latter does not prove GCP resizing or invoice savings.
Only approved sandbox environments are executable. Production infrastructure is not a demonstration target.

## Scope exclusions and cuts

Do not build multi-cloud migration, Kubernetes orchestration, GPU scheduling, subscriptions/card optimization, fine-tuning, universal carbon accounting or autonomous production shutdown.
Do not add model agents for numerical accounting, forecasts, formatting, approvals or execution; these are deterministic services.
Do not copy upstream screenshots, cloud identifiers or historic performance claims into new-work evidence.
Keep Python, Google ADK, FastAPI, Streamlit, PostgreSQL and the private TypeScript H-MEM sidecar; integrations and deployment details belong to the architecture specification.
Use one sandbox tenant and one memory writer; do not imply the reference engine provides tested tenant isolation. Its mock/hash embedder cannot substantiate semantic-retrieval quality.

After P0 passes, consider one second model, optional live VM execution, or scheduling. Cut optional slide generation, scheduling, second model and extra dashboards before cutting any required evidence or safety behavior.
Never cut real required sponsors, independent checks, critic revision, scoped approval, durable records or verification to improve the apparent demo completion rate.

## Decision and accounting rules

Ranking is a review aid, not a permission grant. Show ready-for-trial candidates first, then candidates needing evidence, then retained rejections; explain the ordering.
Within eligible candidates, compare projected net benefit only on the same interval and workload boundary. Do not add mutually exclusive candidates into one “total saving.”
Service latency/error/headroom limits, trial budgets and evidence freshness requirements are versioned policy inputs, locked before evaluation. There is no model-selected universal safe threshold.
An accepted AI case must pass every required factual, identity and action check for that case. Candidate selection follows EVALUATION_SPEC: at least 38/40 cases accepted, zero critical failures and no regression on a baseline-passing case. Report every class and failure; a small passing set is not proof of production safety.
When quality passes but cost does not improve, return `NO_CHANGE` with the actual result. Do not relax checks or remove failing cases after seeing results.
Cost per accepted task is undefined when zero tasks pass. Free credits do not establish zero economic cost; unknown billing rates must stay unknown.
For cost, retain measured usage and observed billing separately from usage multiplied by catalogue rates. For carbon, estimates are never presented as independently measured avoided emissions.

## Hypotheses and validation plan

| Hypothesis | Experiment | Record and falsification condition |
|---|---|---|
| H01: evidence and rejected options improve decisions | Ask at least three available engineering/operator reviewers to decide from the same scenarios, then inspect the workbench | Record decision, time and explanation; falsified locally if reviewers still mistake rejected or projected outcomes for safe realized changes |
| H02: constraint-aware analysis avoids naive false acceptance | Compare with a declared utilization-threshold heuristic on identical cloud scenarios | Publish false acceptances by case and required-check pass rate; do not call the heuristic “original GreenOps performance” |
| H03: memory avoids repeated failed work | Repeat matched investigations with memory on/off; keep model, prompts, dataset, versions and budget fixed | Count repeated invalid trials, queries, calls, time and full cost including recall; report no benefit if improvement is absent |
| H04: a bounded AI change preserves outcomes at lower cost | Evaluate the frozen baseline/candidate on the held-out cases | Publish accepted outcomes, per-class failures, tokens, retries, latency and cost per accepted task; failure or no improvement means no rollout |
| H05: explicit approval/verification is understandable | Have reviewers identify target, authorized effect and final state without coaching | Record mistaken assumptions, then correct confusing wording and repeat affected tasks |

These are planned studies, not completed user research. If reviewers are unavailable, mark user-value evidence unvalidated and retain the technical evaluation.
Disclose sample sizes, repeated-run variation, synthetic coverage and workload limitations. No invented statistical confidence or industry-wide ROI.

## Competitive case and delivery proof

The proposed differentiation is a connected record from cross-source evidence through failed trials, bounded approval, verified action and version-aware memory.
Show sponsors doing necessary work: a Zetaris evidence receipt and an H-MEM result that changes a later investigation; retain the actual NVIDIA/model contribution and Cursor development record.
Make the principal demo legible in four minutes: problem, evidence, rejection/revision, scoped action, verification, restart memory and honest results.
Keep a reproducible longer walkthrough for judges inspecting the repository. Every result card and pitch number must link to a run, report or source record.
Win probability is unknown. A strong submission depends on implementation quality, organizer-confirmed eligibility and the other entries; this plan cannot guarantee an award.

## Definition of product-ready

- P01–P12 have actual acceptance artifacts, including failure/rejection paths and a clean restart.
- A new operator can follow setup instructions, run the connected scenario and recover the durable investigation without undocumented intervention.
- The UI/export agree about final state, origin, assumptions, missing sources and pending verification.
- Feature claims, report figures and submission media describe exactly the demonstrated scope.
- Unresolved eligibility, access, quality or execution blockers are recorded explicitly before submission.
