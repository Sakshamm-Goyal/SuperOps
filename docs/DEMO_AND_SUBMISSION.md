# Demo, judging evidence and submission plan

**Prepared:** 16 October 2026  
**Status (updated 16 Oct):** The application was implemented pre-event (PREEXISTING.md). Sample-mode runs and their evidence exist. No connected sponsor results, video, deck or submission exist yet. Media must label sample/scripted runs as such and must not present them as sponsor evidence.  
**Primary track proposed:** Track 02 — The Agent That Can Explain Why, subject to the eligibility gate in [Hackathon rules](HACKATHON_RULES.md).  
**Confirmed planning inputs:** 4–5 active builders; niksm7/GreenOps is third-party inspiration for an original implementation, with no upstream code/assets reuse. Organizer track and pre-event-disclosure questions remain open.

Our competitive strategy is to make one useful result easy to inspect and hard to misinterpret: an operator can see why an attractive saving is rejected, what a better-supported candidate costs, approve a bounded action, and inspect what actually happened. The agent's evidence and corrections should be more memorable than the dashboard. No architecture or presentation can guarantee an award.

## 1. Product promise and demonstration boundary

**Working pitch to validate:** “SuperOps helps a cloud operator decide which efficiency change is justified. It combines fragmented evidence, tests proposals, remembers prior outcomes and verifies one approved sandbox action.”

The core demo is one service, six small VM histories, one investigation and one bounded target action. The data is synthetic unless a reviewed manifest explicitly establishes otherwise. The AI Efficiency Lab is a committed P0 capability using the same evidence/approval infrastructure: build the cloud path end to end first, then complete the bounded support-workflow experiment. Removing the Lab requires an explicit scope decision recorded in [decisions and risks](DECISIONS_AND_RISKS.md); it must not quietly disappear from the delivered product. Its short demo segment can show a clearly labelled prior experiment while the full reproducible evidence remains available.

The evaluator should be able to answer five questions:

1. What user decision does this change?
2. Which source records support the recommendation, and which uncertainty remains?
3. What caused the critic to reject or revise an earlier candidate?
4. What did the human approve, and what was actually executed and checked?
5. What did Meterless retain that changes the next investigation appropriately?

Basis: supplied handoff §§1–11 and the event's [Track 02 statement](https://hackathon.genai.works/event/open-agent-hackathon-2026#tracks). These are planned capabilities, not current product claims.

## 2. Evidence-first judging strategy

| Rubric | Points | What to demonstrate | Artifact required before making the claim |
|---|---:|---|---|
| Impact | 30 | One concrete operator decision; accepted outcome with useful savings/effort information; rejected unsafe option | Problem interview or clearly labelled hypothesis; matched baseline/candidate results; final decision report |
| Technical | 20 | Reproducible setup, real integrations, bounded loop, stale approval rejection, execute-once and read-back | Clean-checkout log; sponsor receipts; acceptance results; action and verification records |
| Innovation | 15 | Cross-source contradiction triggers a real critique/revision; applicable prior experiment changes subsequent work | Before/after candidate IDs, critic findings, source references and Meterless recall trace |
| Demo | 15 | A comprehensible story with a visible useful output in under four minutes | Final recording with readable text, actual run/revision IDs and honest time compression |
| Product & UX | 10 | Evidence drilldown, clear pending/rejected/verified status, exact approval scope and accessible report | Actual UI walkthrough and keyboard/readability checks |
| Sponsor tech | 10 | Zetaris is the investigation data path; Meterless contributes persistent applicable memory; Cursor development and tested NVIDIA role are visible | Provider/version manifest, query/recall evidence and accurate sponsor statement |

Source: supplied Welcome §§3/8/12, Solutioning §§8–15 and official rule §7. The framework name itself does not receive points; spend effort on observable behaviour and evidence.

## 3. The 3 minute 45 second demo

Target **225 seconds** to leave 15 seconds of margin under the official four-minute maximum. Rehearse against the actual running product. Do not script a result the system has not produced. Long experiments may be shown as a labelled replay with the original run time; a replay is not a fresh run.

| Time | Screen/action | Narration purpose | Required proof |
|---|---|---|---|
| 0:00–0:18 | Service queue and one operator question | Explain user, risk and decision: low averages can hide an unsafe resize | Synthetic-data badge; service/target scope; one sentence problem |
| 0:18–0:48 | Start investigation; open evidence panel | Show Zetaris retrieving resource demand, cost and policy across independent sources | Real query receipt; source/version IDs; common interval; unresolved gaps visible |
| 0:48–1:25 | Candidate and critic timeline | Show an aggressive proposal rejected because a genuine constraint/evidence check fails; show the revised plan | Rejection tied to peak demand/memory/policy and evidence IDs; real next-step branch, not a decorative animation |
| 1:25–1:55 | Trial comparison | Explain what the test measured and why the remaining candidate passes or why no change is appropriate | Matched workload, baseline/candidate versions, independent acceptance result; estimate/measured labels |
| 1:55–2:35 | Approval details → execute → read-back | Show the exact target/plan approved, one bounded change and resulting health/configuration verification | Authenticated approval; plan hash/version; action ID; actual before/after and health result |
| 2:35–3:05 | Repeat investigation / memory panel | Show Meterless recalling an applicable prior result, with supporting experiment and version checks | Real memory ID, source receipt and changed decision; process-restart proof available in evidence pack |
| 3:05–3:25 | AI Efficiency Lab comparison | Show one independent policy-regression rejection and the revised experiment | Real baseline/candidate traces; accepted-task denominator; pinned held-out test set; clearly labelled replay if used |
| 3:25–3:35 | Exported report | Show a usable decision record covering outcome, costs, uncertainty and next step | Report references match the runs; missing carbon says unknown; no aggregate double-counting |
| 3:35–3:45 | Final evidence/architecture card | State what was built, where sponsors contribute, and the next scoped enhancement | Repo revision, honest Cursor usage and NVIDIA contribution; limitations visibly stated |

### 3a. Recording script: connected runs of 26 October 2026 (real IDs)

Everything below exists in the local database from live runs (Zetaris 2.4.3 local platform, Nemotron 3.5 Super, Nemotron 3.5 Embed, Meterless H-MEM, Claude Haiku 4.5). Record from the web workbench at http://localhost:5173 signed in as `lead`. Start a fresh investigation live during the first segment; while it runs, cut to the completed runs below. Never present the completed runs as the live one.

| Time | Screen | Say (short) | Record IDs |
|---|---|---|---|
| 0:00–0:15 | Landing hero → *Open the workbench* | "Cloud savings advice is cheap. Proving a change is safe is the hard part." | — |
| 0:15–0:40 | Overview: proposed vs **blocked by evidence** vs verified; sponsor panel | "Two physical databases, federated through Zetaris; every number has a receipt." | `federation.receipts` count on the panel |
| 0:40–1:15 | Investigations → *New investigation* (live). Then open the completed connected run `5db3ceac…` story page | "Nemotron proposed three cheaper machines. Deterministic checks decided: `worker-freeze-01` is under a change freeze; `worker-stale-01` was **skipped by Meterless memory** (it already failed) and its telemetry is stale and incomplete. Only `worker-stg-01 → e2-standard-4` survives." (The peak-vs-average example — prod averages 10% but peaks at 6.4 vCPU — appears in labelled sample runs; the live model did not propose it.) | investigation `5db3ceac-2c13-42d7-84d7-e615811af80c`; rejected plans `ade86a0f…` (CHK-POLICY change freeze), `439eca39…` (MEM-PRIOR-FAILURE memory `d64a7738…`, coverage, freshness) |
| 1:15–1:45 | Same page: matched trial PASSED; Zetaris receipt card | "Identical offered load on two fixtures; p95 within limit; sources and result hash on the receipt." | trial `029582bb-fd37-4e23-9776-66f89a2815f2` |
| 1:45–2:25 | Plan `ecd752bb…` → approval panel → Action page | "I approve the exact plan hash and trial hash for 15 minutes. One write, read back, fresh workload: VERIFIED, measured. Local sandbox analogue, not a GCP resize." | plan `ecd752bb-2271-4209-8c4c-405d6c9e839d`; approval `2906ab78…`; action `9dc3a3a6-08e6-451f-a335-66b46175e42e` |
| 2:25–2:55 | Second run `fb8b36c6…`: memory callout | "Meterless remembered: the next run cited the verified trial and proposed one candidate instead of three." | investigation `fb8b36c6-07fe-44c7-99fe-983a7a613387` |
| 2:55–3:25 | Ops Copilot slide-over: "Can I approve this now? What blocks it?" | "Claude Haiku answers from the same records, read-only, with citations. It cannot approve anything." | conversation shown live |
| 3:25–3:40 | Terminal: `make autopilot ONCE=1` (`no_drift` / `investigation_started`) | "Autopilot watches Zetaris evidence for drift and re-investigates. It can start runs, never approve." | autopilot log line |
| 3:40–3:45 | Architecture card | "PostgreSQL holds authority; models propose; evidence decides." | repo revision |

Before recording: `uptime` load below ~5, so trials are not INCOMPLETE from host contention. Make sure `make preflight` passes, and hide `.env`.

### 3b. Live AWS segment (27 October 2026)

The demo video is recorded automatically from the running web app by a Playwright recorder, which signs in with the local sandbox `lead` token on localhost only. The AWS part follows the live service `superops-aws` in this order:
1. A new investigation starts from the drawer.
2. The completed hero run's story: real CloudWatch spikes, the API downsize refused on the peak, the frozen batch instance refused by policy, and the worker's canary PASSED.
3. The plan's change runbook: downtime, the automated steps, the manual AWS CLI tab, rollback, and the downtime-acknowledged approval.
4. The real EC2 action: measured downtime, read-back, status checks and CloudWatch verification.
5. A follow-up run: memory recalls the verified change, and the runbook quotes the measured downtime.
6. A Copilot question about the live sandbox.

Every number on screen comes from those records. The sandbox stops itself at 2026-10-28 11:51 UTC; `make aws-down` removes it.

### If the result differs from the planned narrative

- A genuinely rejected candidate is valuable evidence. If no safe improvement exists, present a sourced `NO_CHANGE` result and show an approved action from a separate clearly named successful case.
- Do not hardcode a critic failure or force a predetermined model/candidate winner. Choose a reproducible adversarial input and let the actual implemented checks decide.
- If cloud access is unavailable, demonstrate an actual local worker/configuration change with measurements and read-back. Label it **local sandbox analogue**; never call it a completed GCP resize or verified invoice reduction.
- If a required sponsor is down during recording, preserve the failed live status and use a clearly labelled previously successful connected-run replay for the relevant segment. The final evidence pack must still prove real integration. An integration that has never succeeded is an unresolved delivery gap.
- If the AI Lab is incomplete, treat it as an unresolved P0 delivery gap and make an explicit scope decision. Do not present a proposed Lab screen or canned comparison as completed functionality. Do not expand the video or hide core action verification to fit it.

## 4. Demo scenarios and acceptance evidence

These scenario names describe intended tests. Fixture values and expected outcomes must be grounded in the implemented deterministic checks and independent verifier, not in presentation requirements.

| Scenario | Purpose | Outcome to verify |
|---|---|---|
| `peak-trap` | Low mean CPU, high measured peak | Over-aggressive target rejected; safe target needs full memory/policy/workload evidence |
| `missing-memory` | Evidence incompleteness | Needs evidence; no apparently validated or approvable action |
| `resource-name-collision` | Same display name in separate projects | No identity merge; receipts resolve exact provider/project/resource |
| `changed-target` | Target/configuration changes after approval | Approval becomes stale and execution is blocked |
| `duplicate-execute` | Repeated UI/API action | At most one actual mutation and one consistent durable result |
| `unhealthy-after-start` | Provider operation finishes but app check fails | Pending verification or recovery state; never false “verified” |
| `remembered-rejection` | Repeat same applicable investigation after memory restart | Real persisted Meterless record recalled with source and applicability checks |
| `changed-policy-memory` | Policy/test/workload changes | Old memory visible as history but not treated as current approval or validation |
| `no-beneficial-plan` | All candidates fail constraints or net benefit | Honest no-change report with reasons |
| `premium-return-exception` | AI Lab compression loses policy condition | Independent factual/action check rejects candidate; revised run must genuinely pass |

Run the connected core scenario and clean-checkout path on the exact release revision. Keep actual results, pass/fail counts and failures. A unit test using a stub does not establish sponsor access, persistence, cloud mutation or end-to-end usability. [Test strategy](TEST_STRATEGY.md) and [evaluation specification](EVALUATION_SPEC.md) define the complete validation; this list identifies judge-visible proof priorities.

## 5. Measure value without fabricating impact

Do not fill a slide with invented percentages. Use these measures only after executing the corresponding protocol. Publish numerator/denominator, dataset version, run count, environment and limitations.

| Metric | Measurement | Interpretation limit |
|---|---|---|
| Cost comparison | Same horizon/workload; baseline and candidate billable quantities × dated rates | Projection unless actual billing records confirm savings; list discounts/commitments excluded |
| Net projected saving | Baseline minus candidate, experiment and transition costs | Exclude mutually exclusive alternatives; keep optimizer overhead visible |
| Safety/quality acceptance | Count independent checks passed; list critical failures and rejected actions | Test coverage on defined fixtures, not a claim of production safety |
| Time to useful decision | Wall-clock start to usable report, repeated runs; median and range | Include evidence fetch, retries, critic and verification; don't call model latency total runtime |
| Operator effort | Timed task comparison using same question, evidence and output requirements | Requires an actual human exercise; otherwise report a hypothesis, not measured time saved |
| Memory contribution | Same repeated investigations, versions/model/budget with memory enabled and disabled | Compare correctness, repeated failed trials, latency and total cost; no benefit assumption |
| Carbon | Versioned method, bounded scope, matching interval and uncertainty | Estimate, not measurement, unless measured evidence exists; unknown when factors unavailable |
| AI cost per accepted task | All model/tool/retry costs ÷ independently accepted tasks | Undefined at zero accepted tasks; token reduction alone does not prove carbon reduction |

For the cloud comparison, use a simple utilization-threshold baseline as well as the agent system. Keep the same fixture inputs and workload. The compelling finding may be that the baseline recommends a risky saving while Verify appropriately rejects it. If the agent adds cost or latency, report that overhead too. Handoff §§9/11 specifies the intended accounting and ablation boundary.

## 6. Slide deck outline

Prepare **eight concise slides** plus an optional evidence appendix. Slide count is a project choice; the public rule does not specify one.

| Slide | Message | Required content |
|---|---|---|
| 1. The decision | Identify operator, cloud-efficiency question and risk | Product name; one problem sentence; proposed track |
| 2. Why a cheap suggestion can fail | Show one source conflict | Actual low-average/high-peak example; dated/synthetic source label |
| 3. What Verify does | Present the finished user workflow | Evidence → proposal → critique → trial → approval → verified result |
| 4. Architecture and sponsor value | Explain concrete data/memory/model paths | Zetaris sources; Meterless H-MEM; agent loop; deterministic action service; Cursor; NVIDIA only where actually used |
| 5. A real outcome | Compare baseline, rejected candidate and accepted result | Actual run IDs, measured/projection labels, costs and uncertainty |
| 6. Reliability and reproducibility | Show why results can be inspected | Selected acceptance tests, complete run counts, clean checkout, failure case and limitations |
| 7. New work and differentiation | Make contribution assessable | Prior inspiration vs new implementation; new-work commits; applicable memory or critique ablation |
| 8. Next useful step | Present disciplined continuation | What works now, known gaps, one realistic next enhancement, judge access links |

Appendix: source register, versions, detailed tests, exact data/price/carbon methodology and reproduction instructions. Do not put fabricated future visuals alongside current screenshots without labels. The deck must satisfy all subjects in official rule 6.2 / Welcome §9.

## 7. Submission artifact manifest

The submission coordinator is **C with four builders, E with five**; resolve this to one named person before work starts. D independently verifies final claims and packaging, remains sole holdout-label owner and does not hand private labels to the coordinator. Artifact owners below are accountable for completion; A/B/C contribute receipts for their implementations.

The following are **future build outputs**, not files this documentation-only task claims to create.

| Artifact | Accountable owner: 4 / 5 builders | Reviewer | Minimum content | Completion evidence |
|---|---|---|---|---|
| Demo video | C / E | D | 1–4 minutes; main flow, challenge solved, features, Zetaris/Meterless integration | Playback and duration checked; links usable in clean browser session |
| Deck | C / E | D | Eight-slide outline fulfilled with actual screenshots and findings | Final export opened; no clipped content or unresolved placeholders |
| GitHub repository | C / C | D | All source, dependency locks, README setup/usage/dependencies, required notices | Exact final revision cloned and tested by another team member or clean environment |
| README | C / C | D | User/problem, scope, startup, required credentials/access, sample provenance, connected vs replay, tests, limitations | Commands copied and executed; no commands presented as available before implementation |
| Sponsor explanation | A / A | D | Actual roles and unique contribution of Zetaris/Meterless; B supplies NVIDIA and all builders supply actual Cursor evidence | Named versions, run IDs and evidence links; coordinator packages the statement |
| Provenance | C / E | D | Pre-existing declaration, inspiration attribution, new-work commits, data and dependency licence/permission records | Form declaration matches repository documents and confirmed original-build decision |
| Evidence index | D / D | A reviews public source totals; C checks links | Accepted, rejected, failure and memory runs with logs, output and verification | Immutable run IDs and hashes; references resolve without exposing private data or labels |
| Reproducibility guide | C / C | D | Bootstrap, health checks, small permitted data, expected states, teardown/reset | Independent clean setup succeeds with documented authorized credentials |
| API docs | C / C | D | Canonical `docs/API_REFERENCE.md` and accurate OpenAPI for actual routes/auth/contracts | Contract checks and live API behaviour agree |
| Submission receipt | C / E | D | Team/track, artifact URLs, repo revision, submitted timestamp/status | Persisted HackOS confirmation inspected after authorized submission; not merely a click or draft form |

Do not assume a public deployment, a paid service or Colab is mandatory. Rule 6.3 requires Colab links **if** agents run there. Whether a private repository is acceptable and how judges obtain access remain unknown until HackOS instructions or an organizer answer establishes it.

## 8. Sponsor explanation template

Fill this from real evidence after implementation; remove placeholders rather than implying success.

| Sponsor | Intended role | Evidence to insert | Claim boundary |
|---|---|---|---|
| Zetaris | Query fragmented resource, workload, cost and policy sources for one investigation | Workspace/version, connector types, real query/receipt IDs, source mapping and failure handling | Do not claim live federation if results came only from a local copy or replay |
| Meterless | Store and recall applicable experiment/correction records through genuine H-MEM reference | Reference revision, wrapper mapping, memory IDs, persistence test and changed second-run decision | App wrapper endpoints are ours; PostgreSQL owns transactional action/approval state |
| Cursor | Required development environment for the new implementation | Dated actual development evidence and contribution log | This docs preparation in Codex is pre-event planning, not proof of Cursor-built code |
| NVIDIA | Candidate reasoning/critique model or another useful tested role | Model/version, endpoint type, run trace and measured contribution if used | Do not say Nemotron/NIM was used because it is on a slide or in an environment example |

Keep API keys, tenant identifiers, private query contents and unnecessary personal data out of screenshots. Sponsor integration is assessed by real functionality, not repeated logos.

### 8a. Sponsor evidence (filled 26 October 2026, local machine)

| Sponsor | What it actually does here | Evidence |
|---|---|---|
| Zetaris | Local Zetaris platform 2.4.3 (Docker, hackathon registry images) federates **two physical PostgreSQL servers**: A is host PostgreSQL 16 (`cloud_pg`, and `cloud_ref` as datasource views over schema `ref`); B is a separate PostgreSQL 17 container (`ai_pg`). Read-only `zetaris_ro` roles. All investigation evidence and the Copilot's live queries go through `query/sql/start|page|close` | `make zetaris-setup` output; connected gates ZET-01..04 PASS (`evidence/connected/`); query receipts with request IDs and result hashes on every evidence record; adapter fix for Spark's zone-less timestamps (UTC session verified, fails closed otherwise) |
| Meterless | Vendored H-MEM reference `0aa7417b` in our sidecar with semantic embeddings; outbox-delivered outcomes; recall with application-side applicability checks changes the next run | HMEM-07 PASS (paraphrase recall 9/10 on 25 Oct, restart, version rejection, provider removal); memory records SENT for action `9dc3a3a6…`; run `fb8b36c6…` proposed 1 candidate after recall vs 3 before |
| NVIDIA | Nemotron 3.5 Super (coordinator, investigator, optimizer, critic via Google ADK + LiteLLM); Nemotron 3.5 Embed for memory | NIM-01/02 PASS; per-role tokens and durations in `model_calls`; fixes recorded with reproducers (timeouts, truncated output) |
| Anthropic | Claude Haiku 4.5 Ops Copilot: read-only tool use over the caller-scoped API, H-MEM recall and Zetaris templates | `tests/unit/test_copilot.py` (no mutating tool, allowlist); conversations persisted in `copilot_messages` |
| Cursor | Not used for this implementation (built with Claude Code); disclose honestly | `README.md` provenance section |

## 9. Recording and release procedure

1. Freeze scope and pin the release candidate. Confirm rules, chosen track and prior-work declaration.
2. Rebuild from a clean checkout with fresh application state and documented authorized credentials. Run required acceptance and connected integration checks.
3. Generate a fresh evidence pack from real runs. Keep an immutable copy of input versions, model configuration, logs, timestamps and outcomes. Store secrets separately.
4. Prepare demo state using a documented reset/seed procedure. Do not manually edit output records to make the story look successful.
5. Record an uninterrupted source run before making a shortened presentation cut. If compressing waits or replaying prior runs, label those segments visibly and retain the underlying run evidence.
6. Verify exact approval, action status, report persistence and subsequent recall. A success toast alone is insufficient.
7. Review audio, captions, legibility, duration, data labels and redaction. Use actual product captures; conceptual diagrams carry a diagram label.
8. Open final repo/video/deck links from a judge-like clean session. Check permissions using the supported sharing workflow; do not publish credentials or private evidence.
9. Have a teammate reproduce the shortest judge path without undocumented help. Record any required commercial account access honestly.
10. Submit only when explicitly authorized to perform the external submission; inspect persisted acceptance and keep the receipt. The current user request does not authorize publication or submission.

## 10. Schedule and ownership

Assign named people to the confirmed A–D core roles and optional E before building. A owns sponsors/data/memory, B agents/domain/workload/candidates, C API/auth/jobs/executor, and D independent QA/evaluation/security. D alone controls held-out labels and the locked verifier. With four builders C also owns the minimal UI and coordinates submission; D owns acceptance/demo evidence and verifies packaging. With five, E owns UI/UX, report presentation, demo/deck and submission coordination; C may help A with bounded memory-wrapper plumbing after API contracts. The fifth builder improves delivery quality without adding product scope.

| When | Accountable owner: 4 / 5 builders | Reviewer / helpers | Deliverable |
|---|---|---|---|
| Before 22 Oct | C / E | D reviews; A prepares sponsor-access checklist | Confirmed original-build provenance, organizer track/pre-event questions, named roster and preparation inventory; documentation only before window |
| 22–23 Oct | A / A | D inspects receipts; B helps embedding-provider compatibility | Real source query and persistent memory with real embeddings; M1 may finish day 2 |
| 22–23 Oct | B / B | D tests outcomes; C connects durable runs | Cloud investigation, critique/revision and measured workload trial |
| 24 Oct | C / C | D independently checks; UI owner integrates | First complete action/read-back/reload journey and adverse execution cases |
| 24 Oct | B / B | D reviews development results only | Committed P0 AI workflow; candidate frozen before D opens final evaluation |
| 25 Oct | D / D | A supplies memory/source receipts; B/C resolve development defects | Locked paired AI evaluation, memory ablation and real connected acceptance evidence |
| 26 Oct, 12:00 UTC / 17:30 IST | C / C | D records readiness; A/B and E if present freeze their areas | Feature freeze on one release revision; prioritize correctness and packaging |
| 26 Oct onward | C / E | D verifies evidence/claims/package; A/B provide integration details | Clean-checkout package, deck, video, sponsor explanation and link/access checks |
| 27 Oct, 12:00 UTC / 17:30 IST | D / D | Implementation owners address only verified blockers | Final release validation, redaction and packaging review |
| **27 Oct, 18:00 UTC / 23:30 IST** | **C / E** | **D verifies final package and receipt** | **Internal submission target after authorized publication/submission** |
| 27 Oct, 23:45 UTC / 28 Oct, 05:15 IST | C / E | D verifies persisted status | Official cutoff; do not plan work into this margin |

Finalize team membership **before creating the first submission**, because that action locks the roster. The guides allow updates until cutoff; public details about whether update time affects tie-breaking are not specified. Submit a complete valid entry early, then follow confirmed platform rules for necessary updates.

## 11. Claims checklist for the final story

- [ ] Every savings number names horizon, baseline, rate source, experiment/transition overhead and projection versus actual result.
- [ ] Synthetic inputs, local analogues, cached samples, recorded replays and live observations are visibly distinguished.
- [ ] Every “verified” result has configuration read-back and relevant workload/health checks.
- [ ] An old memory is never presented as current policy or execution authorization.
- [ ] Every sponsor use has genuine current-team evidence.
- [ ] The cloud path works on more than the hero scenario, including rejection/no-change cases.
- [ ] Test counts match the final revision and distinguish unit, integration, acceptance and connected runs.
- [ ] No “production-ready”, “zero risk”, “guaranteed savings” or “carbon-neutral” claim exceeds the evidence.
- [ ] Prior authors and pre-event preparation are credited accurately; new work is explicit.
- [ ] Repository, deck, video and submission form describe the same product state.

## 12. Sources and interpretation

- [Official event rules and rubric](https://hackathon.genai.works/event/open-agent-hackathon-2026#rules), expanded and read on 16 October 2026: §§6–7 define submission and scoring; §2.2 defines team lock.
- Welcome guide (local reference, not published), §§3/8/9/11/12: meaningful agents, sponsor use, required components, build rhythm and evaluation.
- FAQ (local reference, not published), §§5/7/8: pre-existing data/code, runnable setup, submission updates, deadlines and judging.
- Solutioning guide (local reference, not published), §§8–15/18–19: narrow useful scope, critique loops, bounded runs, evidence and sponsor fit. Its 5–10 minute runtime budget is guidance, not a published hard limit; a video cut must not hide actual execution time.
- Event calendar (local reference, not published), §§3/8: preparation, validation and suggested reminders; conflicting dates are preserved in the rules document.
- Participant journey (local reference, not published), §§5.3–6.2 and Stage 7: agent interaction, packaging and final checks.
- Hackathon overview (local reference, not published), §§12–16: reproducibility, scoring and practical success criteria.
- Developer handoff (local reference, not published), §§1–15: proposed product, evidence/memory roles, cloud/AI trials, metrics, acceptance cases and cut order.

The storyboard, eight-slide format, internal deadlines and evidence requirements above are project decisions. They are intentionally stricter than a logo-level sponsor demonstration, but they are not additional official rules.
