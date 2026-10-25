# GreenOps Verify — workbench UX specification

Status: implemented pre-event in `greenops/ui/` (16 Oct 2026), verified with Streamlit AppTest against the live sample-mode API. The approval and execute controls have not yet been exercised against a connected-mode action. Keyboard and screen-reader behavior has not been checked manually.
Use [PRODUCT_SPEC.md](PRODUCT_SPEC.md) for scope and product acceptance IDs. This document specifies visible behavior; the API remains authoritative for authorization and state.
Use [API_REFERENCE.md](API_REFERENCE.md) for public contracts and [OPERATIONS.md](OPERATIONS.md) for readiness and recovery procedures.

## Design direction

Build an engineering review desk: quiet light background, dark readable text, restrained teal for selected/verified information, amber for attention and red for blocked/failed outcomes.
Status always has text and an icon in addition to color. Prefer native Streamlit controls and readable tables; avoid decorative charts, oversized KPI tiles, hidden navigation or fragile DOM-selector styling.
Use a consistent compact spacing scale, clear page titles and plain labels. Standard text is at least 16 px, with smaller metadata still readable at browser zoom.
Keep the principal decision and its reason visible together; let source rows, receipts and detailed traces expand below them.
This is an investigation workspace with an optional request field, not a chat transcript that hides approval and operational state.

## Navigation and persistent context

Sidebar: **Story · Investigations · AI Lab · Actions & reports · Operations**. **Story** (default page, added 25 Oct 2026) retells one investigation as four moments — the peak-CPU trap, the revision that passed a matched trial, the AI candidate the verifier rejected and its passing revision, and memory skipping a known failure — plus what still needs a human. It only selects records the other pages show, and states when a moment is absent from that run (for example a trial that was not comparable). Show current service and environment at the top.
Global banner: runtime mode, authenticated actor, sandbox type, overall source health and remaining experiment budget.
Always distinguish `Connected demo`, `Recorded replay` and `Degraded read-only`. “Connected” describes integrations; data may still be synthetic and needs a separate origin badge.
Every page shows investigation ID, service, relevant policy/workload versions and last refreshed time. Show timestamps with timezone; retain UTC in receipts.
Refresh restores records from the backend. Session-state variables may store widget selection, never the only copy of approvals, pending actions or evidence.
Stable investigation/action identifiers support reopening a record after restart; authorization is checked again on every read.

## Investigation desk (P01–P04)

Top row: service selector, question, comparison horizon and experiment cap; **Start investigation** gives a durable ID immediately.
Show the current stage and bounded progress: evidence queries, candidate attempts used/remaining, trial running, critic review and next permitted action.
Do not use a fictional percent-complete indicator for unknown work. Cancellation stops at a safe boundary and explains any action that has already started.

| Area | Visible contents | Interaction |
|---|---|---|
| Review queue | Candidate ID, target, proposed operation, status/reason, evidence freshness and impact basis | Filter by path/status; open a candidate; retained rejections remain discoverable |
| Selected candidate | Before/after, why considered, constraint results, next required step | Inspect evidence; run an eligible trial; view revision lineage |
| Comparison | Baseline and at most three alternatives within one path | Choose comparable candidates; incompatible intervals/workloads are explicitly flagged |
| Activity | Time, actor/agent/tool, evidence/trial/action ID and resulting state | Open receipts and deterministic check results |

Separate cloud and AI comparisons; never put vCPU and AI quality on a shared numerical scale.
Use plain reasons such as “Rejected: observed peak exceeds target CPU capacity,” with the measured quantity and linked evidence.
Show critic findings as concise decisions and cited checks, not hidden chain-of-thought or invented reasoning transcripts.

## Evidence and comparisons (P02, P03, P07, P08)

Each evidence item exposes source system, resource/record key, observation time, retrieval time, version/hash, units, query receipt and completeness warnings.
Display evidence age against the policy freshness limit. A new retrieval timestamp cannot make an old observation fresh.
Show synthetic/live-source origin independently from live-query/replay status. Cached evidence has its original observation and retrieval context.
The evidence drawer shows selected rows and safe query metadata; redact credentials, private customer data and unnecessary raw payloads.
Source identifiers use canonical resource keys; display names are presentation only. Duplicate names cannot collapse separate targets.

Comparison columns: baseline, candidate, delta, basis and evidence. Rows include capacity, peak/headroom, workload latency/error checks, horizon, usage, cost and carbon coverage.
Use explicit basis labels: **Measured workload**, **Observed billing**, **Projected at dated rate**, **Estimated carbon**, **Unknown**.
Cloud projections include price source, currency, region/SKU, interval, experiment/transition cost and commitment assumptions. Do not call an accepted resize “money saved” before billing evidence supports that claim.
AI results include total attempts, accepted tasks, per-class checks, tokens, retries, latency and total cost. Zero accepted tasks displays “Undefined: no accepted tasks.”
Carbon shows kgCO2e only when supported by a named method and factors; otherwise “Unknown — emission factors unavailable.” Missing values never render as 0, a green check or an empty success chart.
Charts need labeled axes, units and a data-table equivalent. A forecast stress envelope must not be labelled a calibrated confidence interval without supporting validation.

## Trial workspace and AI Lab (P05, P06)

Before a trial: display exact plan/configuration hash, workload/test-set version, required constraints, estimated run budget and environment.
Use **Run sandbox trial** only when preconditions and remaining budget permit it. The server enforces the same checks when the request arrives.
During a run: stage, elapsed time, attempts completed, known spend and cancellable boundary. Do not imply no further cost when a request is already in flight.
After a run: required-check summary, measured results, baseline comparability, failures and receipts. Failed results stay visible beside revised candidates.
AI Lab exposes development-case diagnostics for tuning. Held-out labels and answer-level evaluator data are inaccessible to optimizer identities and memory during tuning.
Final held-out reports are available to the authorized evaluator after the candidate is pinned; revising afterward requires a new evaluation protocol, not silent retuning on the same holdout.
Clearly identify recorded trials with run time and dataset/model/configuration versions. A replay control never claims to execute a new experiment.

## Approval, action and verification (P09, P10)

Approval is a dedicated form available only to an authorized human actor; a chat phrase or a checked box alone does not establish authority.
The form shows exact target/environment, before/after, plan hash, target/policy versions, downtime, trial result, allowed operation, expiry and recovery boundary.
Use separate **Approve this plan** and **Execute approved change** controls. Approval alone does not start a change.
Submit with a stable request key; rerenders and repeated clicks must resolve to the existing durable request/action. Disable busy controls as a usability aid, not the correctness mechanism.
If state changes, show “Approval stale — target changed since approval,” identify the changed version and require fresh evidence/approval.
The action panel shows provider operation ID when present, configuration read-back, health/workload checks and unresolved effects.
`EXECUTING` and `PENDING_VERIFICATION` are visibly different. An accepted API request or running instance is not success.
For recovery, show what can be restored, whether restoration was attempted, actual resulting state and the human step still needed. Do not promise automatic recovery.

| Stored state/outcome | User-facing meaning | Primary control |
|---|---|---|
| `DRAFT`, `NEEDS_EVIDENCE` | Draft / evidence required | Inspect gaps or collect allowed evidence |
| `REJECTED` | Required check failed; reason retained | Inspect failure or create a distinct revision |
| `VALIDATED`, `AWAITING_APPROVAL` | Checks passed / waiting for human review | Inspect trial or open approval form |
| `APPROVED` | Scoped approval recorded; execution still pending | Execute while approval and state remain valid |
| `STALE` | Prior plan/approval no longer matches current facts | Reinvestigate and seek a new approval |
| `EXECUTING`, `PENDING_VERIFICATION` | Change in progress / effect not yet verified | Inspect progress; no blind retry |
| `VERIFIED` | Intended state and required health checks confirmed | Inspect receipt and export |
| `RECOVERY_REQUIRED`, `RECOVERED`, `FAILED` | Intervention needed / restoration verified / operation failed | Inspect precise outcome and permitted next step |
| `NO_CHANGE` | Investigation completed without an acceptable change | Inspect reasons; retain learning and report |

`NO_CHANGE` is an investigation outcome, not a substitute for a candidate or action lifecycle state. Source-health and execution states must not share one ambiguous “success” label.

## Memory and reopening (P11)

Show **Prior experiment used** with memory ID, original run, supporting receipts, applicability versions and retrieval time.
Explain the visible effect: “Skipped repeating candidate C02 because trial T07 already failed under the same policy/workload.” Recheck current applicability server-side.
Mark outdated memory “Historical — retest required,” preserving its original finding, supersession/correction links and audit record.
Reopening after a process restart must restore the same investigation and action state from authoritative storage; recalled prose cannot reconstruct an approval.
If memory is unavailable, say which contextual check is unavailable and why writes are blocked. Do not show a fabricated empty history as “no prior failures.”

## Operations and operator controls (P12)

Operations shows required sources, connector/model/memory health, last successful check, evidence age, loaded revisions and sanitized error reasons.
Provide safe connectivity/readiness checks and authorized sample-load/reset instructions. Health checks cannot run arbitrary model-generated SQL or shell commands.
Display experiment budget limit, known incurred cost, reserved/in-flight allowance and remaining allowance. Unknown price coverage blocks a claim that the cap is enforceable.
Show current policies, freshness limits, maintenance window, action allowlist and write-enable state. P0 presents these read-only; authorized operators use the documented configuration procedure to create a new version and invalidate affected approvals.
Default writes off. Enabling a capability is separate from approving a particular plan; the UI cannot supply cloud write credentials to the browser.
Show durable-storage readiness and memory revision so restart readiness is inspectable. Authentication/authorization remains in the API; hidden navigation is not access control.
Replay disables execution. Degraded mode identifies unavailable dependencies and affected actions while preserving access to authorized historical evidence.

## Accessibility, errors and acceptance checks

Use keyboard-operable controls with explicit labels, visible focus, sensible tab order and descriptive links. Follow the [W3C keyboard guidance](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html).
Check normal-text contrast at 4.5:1 and large text at 3:1; apply the W3C large-text definitions, not an arbitrary CSS size. See [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
At 200% zoom and narrow widths, stack comparison cards and let wide evidence tables scroll; do not hide approval scope or verification warnings. See [W3C resize-text guidance](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html).
Associate field errors with inputs, preserve entered values and identify how to correct the error. Loading/status changes must be perceivable without animation or color alone.
Manually verify the native Streamlit screen-reader and keyboard experience; record any framework limitation instead of claiming untested accessibility compliance.
Empty queue: “No candidates yet” with the next allowed action. Completed no-change: explain evaluated options and failed constraints. Outage: name the source and last known observation time.
Do not display exceptions, secrets or full stack traces to users; provide a request ID linked to sanitized operational diagnostics.
Before release, verify keyboard review/approval, refresh during execution, duplicate submission, stale approval, slow query, source outage, missing price/carbon, replay, restart recall and report/UI agreement.
Export the same durable evidence, rejected plans, assumptions, trial identity and final action status shown on screen; include generated-at time and redact secrets.
