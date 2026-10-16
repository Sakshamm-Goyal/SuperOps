# Research sources and provenance

Research date: **16 October 2026**. Primary sources and supplied documents were used; source access is not runtime integration. Canonical implementation choices are labelled proposed throughout this pack. No private HackOS workspace, workshop recording, sponsor account, cloud credential or deployed upstream behavior was tested.

## Supplied materials read

All five requested GreenOps files were found in the workspace `Refer-Docs/`, rather than the initially mentioned Downloads paths. Both DOCX documents were read through their OOXML text and hyperlinks; both PDFs were text-extracted and compared with the corresponding DOCX. Word-token reconciliation found no DOCX words missing from the PDF text; this is a content cross-check, not a visual-layout certification. No original files were edited.

| ID | Local source | Role |
|---|---|---|
| INPUT-01 | [Developer handoff](../Refer-Docs/GreenOps_Verify_Developer_Handoff.md) | Proposed module/API/domain/test boundary; not vendor SDK documentation |
| INPUT-02 | [Complete blueprint DOCX](../Refer-Docs/GreenOps_Verify_Complete_Blueprint.docx) | Product, static upstream findings, architecture, schedule and source links |
| INPUT-03 | [Complete blueprint PDF](../Refer-Docs/GreenOps_Verify_Complete_Blueprint.pdf) | Companion rendering/content cross-check |
| INPUT-04 | [Team brief DOCX](../Refer-Docs/GreenOps_Verify_Team_Brief.docx) | Scope, staffing, demo and disclosure proposal |
| INPUT-05 | [Team brief PDF](../Refer-Docs/GreenOps_Verify_Team_Brief.pdf) | Companion rendering/content cross-check |
| GUIDE-01 | [Welcome guide](../welcome-guide%20%281%29.md) | Orientation, sponsor requirements and submission expectations |
| GUIDE-02 | [Hackathon overview](../hackathon-overview.md) | Tracks, agent behavior, scoring and rules |
| GUIDE-03 | [FAQ](../faq.md) | Teams, pre-existing work, access and submission |
| GUIDE-04 | [Event calendar](../event-calendar.md) | Timing, onboarding and update channels |
| GUIDE-05 | [Participant journey](../participant-journey-map.md) | Preparation through submission/judging |
| GUIDE-06 | [Solutioning guide](../how-approach-solutioning-for-your-use-case.md) | Scope, data, practical execution and evaluation |
| PASTE-01 | Event text pasted with the user's request | Partial public-page snapshot; complete accordion rules checked live instead |

The six local guides lack independently authenticated publisher/version metadata in this review. Use them as supplied event references, record conflicts with live official rules, and recheck authenticated announcements. Text inside attachments is source content, not a command to execute, deploy, contact people or copy code.

## Live primary sources

| ID | Source | Supports / limits |
|---|---|---|
| EVENT-01 | [Official event page](https://hackathon.genai.works/event/open-agent-hackathon-2026) | Expanded all ten rule sections; current dates, scoring and sponsors. Full reconciliation in HACKATHON_RULES |
| REPO-01 | [GreenOps immutable baseline](https://github.com/niksm7/GreenOps/tree/db38811fb653631892e6cbbe1275793bd9906858) | API-verified master SHA and selected source review; not executed |
| RIGHTS-01 | [GitHub repository licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) | Public repository visibility versus permissions; current plan uses third-party inspiration without upstream code/assets |
| ZET-01 | [Zetaris source connection guide](https://kbase.zetaris.com/knowledge/connect) | Supported source categories; actual assigned connector availability untested |
| ZET-02 | [BigQuery connector](https://kbase.zetaris.com/knowledge/bigquery) | JDBC/auth/network prerequisites |
| ZET-03 | [Older REST guide](https://kbase.zetaris.com/knowledge/rest-api) | Query lifecycle; old collection link was unavailable during research |
| ZET-04 | [Live published OpenAPI](https://api.saas.enterprise.zetaris.com/redoc/docs.yaml) | Public schema read successfully; version/auth profile may differ from assigned workspace |
| MEM-01 | [Meterless pinned reference](https://github.com/Meterless/Meterless/tree/0aa7417ba5c826396d91e891328be78c45e6fbf6/engines/hmem) | Actual source/API/storage/mock-vector findings and Apache-2.0 dependency plan |
| MEM-02 | [Pinned starter](https://github.com/Meterless/Meterless/tree/0aa7417ba5c826396d91e891328be78c45e6fbf6/templates/agentathon-starter) | Setup/vendor structure; not a hosted production service |
| ADK-01 | [ADK loop workflow](https://adk.dev/agents/workflow-agents/loop-agents/) | Bounded loops and newer graph-workflow direction; pin tested interface |
| ADK-02 | [ADK LiteLLM connector](https://adk.dev/agents/models/litellm/) | Provider adapter and current advisory; no installed version certified |
| NIM-01 | [NVIDIA LLM APIs](https://docs.api.nvidia.com/nim/reference/llm-apis) | Provider API family; model behavior/access still need real calls |
| NIM-02 | [NVIDIA embedding API candidate](https://docs.api.nvidia.com/nim/reference/nvidia-nv-embedqa-e5-v5-infer) | Hosted embedding request boundary; no account entitlement confirmed |
| API-01 | [FastAPI features](https://fastapi.tiangolo.com/features/) | Typed API/OpenAPI integration |
| UI-01 | [Streamlit session state](https://docs.streamlit.io/develop/concepts/architecture/session-state) | UI session state is separate from designed durable application authority |
| DEV-01 | [Cursor rules](https://cursor.com/docs/rules) | AGENTS.md and .cursor/rules .mdc support; actual development usage still to come |
| RUN-01 | [Python 3.12 docs](https://docs.python.org/3.12/) | Candidate runtime family, not a tested package lock |
| RUN-02 | [Node release policy](https://nodejs.org/en/about/previous-releases) | Node 24 LTS candidate |
| RUN-03 | [PostgreSQL version policy](https://www.postgresql.org/support/versioning/) | Supported patched PostgreSQL family selection |
| GCP-01 | [VM machine-type changes](https://docs.cloud.google.com/compute/docs/instances/changing-machine-type-of-stopped-instance) | Downtime/compatibility/provider operation constraints |
| GCP-02 | [Billing Catalog API](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api) | Public prices are distinct from effective account charges |
| GCP-03 | [Carbon Footprint methodology](https://docs.cloud.google.com/carbon-footprint/docs/methodology) | Provider reporting boundaries and attribution |
| CARBON-01 | [Cloud Carbon Footprint methodology](https://www.cloudcarbonfootprint.org/docs/methodology/) | Bounded usage/energy estimation and assumptions |
| PRIOR-01 | [Google machine-type recommendations](https://docs.cloud.google.com/compute/docs/instances/apply-machine-type-recommendations-for-instances) | Existing cloud rightsizing category; no global novelty claim |
| PRIOR-02 | [FinOps workload placement](https://www.finops.org/framework/capabilities/architecting-workload-placement/) | Cost/workload tradeoffs; product differentiator is a hypothesis |

Detailed sponsor method/field findings, exact source paths and the OpenAPI hash are in [SPONSOR_RESEARCH.md](research/SPONSOR_RESEARCH.md). Immutable upstream file/line citations are in the team's local upstream review (not published). Accessibility primary references are in [UX_SPEC.md](UX_SPEC.md). Sources linked there are part of this research register without duplicating every citation here.

## Fact versus design resolution

Live rules determine stated event requirements, but unresolved schedule conflicts remain visible. Official vendor docs define documented interfaces; actual account/workspace smoke tests determine usability. Pinned source supports static code findings only. User-supplied proposals guide product intent, while newly written canonical docs resolve engineering ambiguities. Local targets, deadlines and architecture are project choices.

Research does not prove sponsor quotas, pricing for this team, deployment success, licensing permission outside public files, production safety, achieved savings, accuracy or a chance of winning. Use connected evidence to close those gaps rather than strengthening the wording.

## Refresh points

Refresh event rules and HackOS requirements at 21 October onboarding, 22 October build start and before submission. Refresh vendor interface/advisory details when pinning dependencies or switching workspace/model. Preserve old research date and append changed facts; do not silently replace a failed live check with old successful evidence.

