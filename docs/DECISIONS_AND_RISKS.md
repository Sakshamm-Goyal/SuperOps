# Decisions and risk register

Status: planning baseline, 16 October 2026. Decisions below are recommendations adopted for this documentation pack; they are not claims of user approval for deployment, spending, copying third-party code or submission. Change them with a dated rationale, affected contracts and validation plan. Preserve the old decision rather than erasing why it existed.

## Architecture decisions

| ID | Decision | Why / rejected alternative | Consequence and revisit trigger |
|---|---|---|---|
| ADR-01 | One engineering-lead workbench; cloud first and one AI lab | Connected evidence-to-action story is buildable; broad FinOps/subscription/multi-cloud platform is out of scope | Revisit only after P0 acceptance; two paths share authority/evidence infrastructure |
| ADR-02 | User-confirmed original implementation; provisional Track 02 | User confirmed on 16 October: third-party inspiration, build our own | No upstream code/prompts/assets reused; permission is no longer an open prerequisite; organizer track ruling remains separate |
| ADR-03 | Python + ADK + FastAPI + Streamlit | Preserves supplied brief's stack and shortens integration path; separate React/Nest stack adds sprint cost | Exact versions pinned after smoke; deliberate UI within Streamlit constraints |
| ADR-04 | Four model roles, deterministic domain tools | Useful criticism/revision without an agent per calculator | Critic cannot override failed policy/trial; no shell/SQL authority from model |
| ADR-05 | Zetaris federates at least two physical sources | Cross-source evidence is intrinsic to the decision | This source minimum is our quality gate, not an organizer mandate |
| ADR-06 | Real H-MEM, private TypeScript wrapper and real embeddings | Sponsor reference is usable but has mock vectors and missing application boundaries | Narrow attributed extension; one tenant/writer; no claim of production engine isolation |
| ADR-07 | PostgreSQL is transactional authority; memory uses outbox | File-backed learning cannot safely own action approval/idempotency | Reconcile memory sync separately from action success |
| ADR-08 | Durable jobs and stage events, polling UI | Model/trial/provider work can outlive HTTP requests and browser state | One worker first; no message broker or serverless durable-state shortcut |
| ADR-09 | Default local worker-config executor; optional GCP VM | Real local actuation is achievable without assuming provider permissions | Explicit local-analogue labeling; VM savings remain projected until actual evidence |
| ADR-10 | Trial profile authorizes separate disposable fixtures | A trial must not modify the final target before approval | One global mutation slot and exact profile scope; final target still needs plan approval |
| ADR-11 | Daily seasonal-naive forecast with 14/3/4 split | Transparent baseline and temporal leakage control fit 21 days of data | Residual stress envelope is not calibrated reliability; matched workload required |
| ADR-12 | Same-model AI optimization first; locked holdout | Demonstrate efficiency without conflating model substitution and quality | 40/40 split, evaluator-only paths, 38/40 minimum + zero critical regressions as local policy |
| ADR-13 | Carbon separate and possibly unknown | Defensible boundaries matter more than fabricated green claims | Never token-to-carbon shortcut or immediate verified carbon-savings assertion |
| ADR-14 | No pre-event application implementation in this task | User requested docs first and coding later | Declare docs/prepared materials; preserve true baseline and new-work history |
| ADR-15 | Private sandbox auth and read-only judge mode | Minimal inspectable permissions for six days | No production multi-tenancy/SSO claims; hosted write UI needs secure session mapping |
| ADR-16 | Single canonical docs with provenance preserved | Supplied briefs are proposals and may contain stale decisions | Canonical updates override conflicting proposal details only after recorded rationale |
| ADR-17 | User-confirmed 4–5 active builders | Replaces the earlier three-builder assumption; dedicate D to independent evaluation and E, if present, to UX/submission | Four-builder mapping keeps C on minimal UI/submission, D on holdout and evidence; final names/count pending; no product scope expansion |

Changes from the supplied blueprint: durable worker/outbox are explicit; forecast protocol is daily with 14/3/4 temporal split; local executable analogue is concretely defined; H-MEM needs real vector integration and explicit scope filtering; current Zetaris OpenAPI is documented; timing separates investigation, trials and actions. Original references remain unchanged.

## Initial policies to freeze before final evaluation

| Policy | Chosen starting point | Canonical owner |
|---|---|---|
| Candidate budget | Three per path, six per investigation | ARCHITECTURE |
| Concurrency | One global mutating execution slot + target locks | ARCHITECTURE / OPERATIONS |
| CPU/memory screening | Demand at most 80% of target capacity | DATA_AND_DOMAIN |
| Critical evidence | Full expected declared coverage, latest telemetry within 30 minutes of analysis as_of | DATA_AND_DOMAIN |
| Approval validity | 15 minutes, checked again at first external write | DATA_AND_DOMAIN |
| Trial validity | At most 24 hours and no relevant version change | DATA_AND_DOMAIN |
| Stage budget | Evidence/proposal hard 180 seconds; local trial 15 minutes; optional GCP finite configured profile | EVALUATION_SPEC / OPERATIONS |
| AI selection | At least 38/40; zero critical failures; no loss of baseline-passing cases | EVALUATION_SPEC |
| Spend | Explicit team-approved monetary and call/token bounds; no assumed credit allowance | OPERATIONS |
| Feature freeze | 26 Oct 12:00 UTC / 17:30 IST | IMPLEMENTATION_PLAN |

These thresholds are team design choices. A versioned change is allowed before final freeze with justification; changing a threshold after a failed holdout requires disclosure and a fresh evaluation strategy.

## Open risks and gates

| ID | Risk / current evidence | Owner | Closure evidence and operating response |
|---|---|---|---|
| RISK-01 | Resolved for current scope: third-party inspiration and original implementation confirmed by user | Team lead | No upstream code/assets reused; reopen only if user changes reuse scope; retain attribution |
| RISK-02 | Track 02 versus pre-existing concept/Wildcard interpretation unresolved | Team lead | Written organizer clarification covering concept and pre-event docs; keep track provisional |
| RISK-03 | Zetaris workspace/auth/source network untested | A | Two-source query/pagination/cleanup receipts against assigned workspace; source substitution stays real federation |
| RISK-04 | H-MEM async embedding extension and crash semantics unimplemented | A+B | Pin, clean build, real embedding eval, restart/corruption/correction tests; reference mock cannot certify final behavior |
| RISK-05 | NVIDIA model/embedding access, tool support, prices and limits unknown | B | Actual authorized tool/embedding cycles and cost bounds; no purchased capacity without authorization |
| RISK-06 | GCP trial/write permission may be unavailable | C | Default local analogue; optional owned VM only with permission/compatibility/budget; no cloud success claim |
| RISK-07 | 4–5 builders confirmed; exact roster, names and availability still pending | Team lead | Assign A–D and optional E using implementation plan; protect independent evaluation and cut optional breadth before P0 |
| RISK-08 | Holdout leakage through source views, artifacts, memory or API | D | Separate evaluator credentials/schema; negative query/API tests; no optimizer label access |
| RISK-09 | Source fan-out/units create attractive false savings | A+B | Independent numerical oracles through real query/calculator path |
| RISK-10 | GCP resize has downtime and non-atomic external races | C | Dedicated restricted sandbox, fresh checks, operation reconciliation, actual health results; no production guarantee |
| RISK-11 | Data too synthetic/small to establish user value | Team lead | Clearly disclose; seek authorized operator feedback and record findings; no invented interviews or ROI |
| RISK-12 | Source schedules conflict; private HackOS material not read | Submission owner | Recheck official announcements at onboarding/build/submission; use earlier planning deadlines |
| RISK-13 | Judges cannot reproduce private sponsor calls | D, supported by A and submission coordinator | Confirm access policy; clean checkout + secure credential instructions + genuine receipts + labelled replay |
| RISK-14 | Dependency drift/advisories break provider adapter | B | Lock exact compatible releases after smoke, vulnerability review and rebuild; no guessed latest pin |
| RISK-15 | Carbon factors unavailable or unsupported | B | UNKNOWN with coverage instead of invented total; performance/cost evidence remains separately useful |
| RISK-16 | Duplicate/unknown writes or failed rollback | C | Journal, global slot, idempotency, provider read-back and conflict-aware recovery; surface unresolved state |

No risk here requires stopping this documentation task. Access questions gate their corresponding implementation steps. Prepared organizer questions are in [HACKATHON_RULES.md](HACKATHON_RULES.md); no outreach was sent.

## Judge strategy and differentiation hypothesis

The strongest story is one operational decision with visible proof: an apparently attractive resize fails peak/memory checks; evidence causes a revision; independent workload and support-policy checks test the candidate; a scoped local/cloud change is verified; remembered failures improve the next investigation. Sponsor technologies participate in those actual steps.

Cloud recommendation and workload optimization are established categories: [Google documents applying machine-type recommendations](https://docs.cloud.google.com/compute/docs/instances/apply-machine-type-recommendations-for-instances), and [FinOps describes architecture/workload placement tradeoffs](https://www.finops.org/framework/capabilities/architecting-workload-placement/). Our differentiation hypothesis is the inspectable experiment-and-approval record across cloud and AI changes, with version-aware memory. This research is not an exhaustive competitor or patent search, and does not support a “world first” claim.

To improve winning chances, spend effort in rubric order: credible user problem and evidence (Impact 30), functioning integration/control flow (Technical 20), demonstrate the specific new loop (Innovation 15), then a clear short demo (15), usable review experience (10) and meaningful sponsor use (10). A claim requires a run/receipt or a labelled assumption. No score or prize is promised.

## Decision update template

For each revision record: actual date, decision ID, owner, new fact/source, alternatives, chosen change, affected files/API/data/tests, acceptance evidence and whether prior approvals/evaluations become stale. Implementation agents must not silently treat documentation drift as authorization.
