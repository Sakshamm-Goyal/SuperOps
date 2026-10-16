# Documentation validation record

Validation date: **16 October 2026**. Scope: the newly authored planning pack and its source references. This record does not certify a running product, API, sponsor integration, model result or deployment.

## Completed checks

| Check | Observed result |
|---|---|
| Supplied source inventory | Read five GreenOps reference files and six local event guides; user-pasted event text also reviewed |
| Original file preservation | SHA-256 hashes of all eleven original workspace source files unchanged after documentation authoring |
| DOCX/PDF content reconciliation | Extracted OOXML text/links and PDF text for both pairs; all DOCX word tokens represented in companion PDF text |
| Live event review | All ten official-rule sections expanded; timing/sponsor/scoring/pre-existing-work requirements and conflicts recorded |
| Upstream source review | Current master SHA verified; selected files inspected statically using immutable links; no upstream code executed |
| Sponsor source review | Published Zetaris OpenAPI inspected; Meterless reference revision, actual interfaces and limitations inspected; no account credentials tested |
| Local Markdown structure | All 103 local/relative links resolve; internal heading anchor valid; fenced blocks balanced and table column counts consistent |
| JSON examples | All three fenced JSON examples parsed successfully; placeholder hashes/IDs remain explicitly illustrative |
| Acceptance traceability | All 24 handoff cases map into the test strategy; 56 distinct deterministic/security/action/sponsor test IDs; 12 unique P01–P12 product acceptance IDs |
| Dates and arithmetic | UTC-to-IST schedule conversion, 143h45m window, 12,096-row dataset and numerical evaluation examples checked |
| Independent consistency review | Separate reviewers checked architecture/API/security/claims and test/evaluation consistency; material findings resolved below |
| Scope boundary | No application source, dependency installation, test implementation, remote commit/push, deployment, outreach or submission created |

The new pack contains **25 files: seven root Markdown documents, seventeen documents under docs/, and one Cursor .mdc rule**. Source files supplied by the user are additional and preserved. No `.git` repository was initialized by this documentation task.

## Review findings incorporated

- Trials now require a separately approved disposable fixture profile; the eventual action target cannot be mutated by a pre-approval trial.
- Heldout inputs/labels/per-case results are excluded from agent-readable source views, ordinary trial APIs, memory and user artifacts. Final evaluation uses separate credentials and aggregate export.
- Quick evidence/proposal deadlines are separate from the longer paired workload trial and provider-action deadlines.
- Daily seasonal-naive forecasting and the 14/3/4-day split are consistent across domain, evaluation and decisions.
- Result kind, data origin and runtime mode are separate fields; replay cannot appear as a fresh measurement.
- Retry costs are counted once, and optimizer costs are explicitly included once in net claims.
- Idempotency is required; changed keys cannot consume the same approval twice; queue delays cannot bypass approval expiry.
- A global mutation slot supplements target locks, and unknown external outcomes must be reconciled before release.
- Memory corrections have an authenticated reviewed command path; vector components may be zero but vectors must have finite components and nonzero norm.
- The local analogue is a concrete versioned worker-concurrency change, with actual workload and read-back; it does not establish VM savings.
- Per-case acceptance and aggregate AI candidate thresholds now reference the same evaluation contract.

## Confirmed planning update

On 16 October 2026, the user confirmed third-party concept inspiration with an original implementation and 4–5 active builders. The pack now assigns a dedicated independent evaluator D and optional UI/submission owner E, with a concrete four-builder allocation. Local links, Markdown tables/fences, JSON examples and all 24 handoff mappings were rechecked after this update. This updates the earlier provisional staffing and reuse assumptions; it does not authorize application implementation, deployment or submission.

## Remaining implementation gates

Exact role assignments and whether the final roster has four or five builders remain to be set. Organizer track/schedule clarifications, private HackOS materials, actual sponsor credentials/network access, model availability, embedding compatibility, spend cap and optional GCP permissions still need confirmation. These are recorded in [DECISIONS_AND_RISKS.md](DECISIONS_AND_RISKS.md).

Every proposed test is currently NOT RUN against an application. Day-one smoke tests, a clean installation and actual E2E/evaluation evidence must be produced during implementation. No documentation check is a substitute for those results. Start with [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and follow [AGENTS.md](../AGENTS.md).
