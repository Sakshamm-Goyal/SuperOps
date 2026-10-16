# GreenOps Verify

An engineering workbench for investigating cloud and AI waste, testing a change, approving its exact scope, and verifying the outcome.

**Current status — 16 October 2026:** research and implementation documentation only. No application, connected sponsor integration, deployment, or measured saving exists in this workspace. All implementation commands and contracts below describe work to build later. The original reference files are preserved.

## Start here

1. Read [AGENTS.md](AGENTS.md) before changing anything. [AGENT.md](AGENT.md) is a compatibility pointer to the same instructions.
2. Read [the product specification](docs/PRODUCT_SPEC.md), [architecture](docs/ARCHITECTURE.md), and [decisions and open risks](docs/DECISIONS_AND_RISKS.md).
3. Follow [the implementation plan](docs/IMPLEMENTATION_PLAN.md). Begin with access and compatibility checks, then one connected vertical slice.
4. Use [the test strategy](docs/TEST_STRATEGY.md) and [evaluation specification](docs/EVALUATION_SPEC.md) as release gates.

## The recommended build

Build an original implementation, as confirmed by the user on 16 October 2026, with third-party GreenOps used only as concept inspiration. Target **Track 02 — The Agent That Can Explain Why**, provisionally pending organizer clarification. One engineering lead investigates one GCP support service: six resource histories, one AI support workflow, at most three candidate plans per path, and one action at a time.

The differentiator to demonstrate is a rejected attractive saving, an evidence-driven revision, an approved change with measured read-back, and persistent memory that improves a later investigation. Novelty and business value remain hypotheses until evaluated. Winning is not guaranteed.

| Layer | Chosen direction |
|---|---|
| Interface | Streamlit investigation workbench |
| API and domain logic | Python, FastAPI, Pydantic, deterministic calculators and validators |
| Agent workflow | Google ADK; coordinator, investigator, optimizer, critic |
| Cross-source evidence | Real Zetaris federation across at least two physical sources |
| Experiment memory | Real Meterless H-MEM reference, private TypeScript wrapper, tested embedding adapter |
| Durable workflow authority | PostgreSQL; jobs, approvals, actions, evidence and memory outbox |
| Model | Tested NVIDIA-hosted model; Nemotron candidate if access and behavior pass |
| Development and deployment | Cursor, locked dependencies, Docker Compose on one controlled host |

Version families and compatibility gates are in [architecture](docs/ARCHITECTURE.md); no untested package combination is presented as a working installation.

## Documentation map

| Document | Owns |
|---|---|
| [Hackathon rules](docs/HACKATHON_RULES.md) | Event requirements, dates, discrepancies, track and disclosure |
| [Product specification](docs/PRODUCT_SPEC.md) | User, scope, acceptance and value hypotheses |
| [UX specification](docs/UX_SPEC.md) | Review workflow, operator controls, accessibility and truthful states |
| [Architecture](docs/ARCHITECTURE.md) | Stack, boundaries, agents, persistence and recovery |
| [Data and domain](docs/DATA_AND_DOMAIN.md) | Schemas, joins, accounting, forecasting, approval invariants |
| [API reference](docs/API_REFERENCE.md) | Proposed application contracts, permissions, errors and OpenAPI policy |
| [Sponsor research](docs/research/SPONSOR_RESEARCH.md) | Verified vendor capabilities, actual interfaces and access gaps |
| [Upstream review](docs/research/UPSTREAM_REVIEW.md) | Immutable reference revision and static findings |
| [Test strategy](docs/TEST_STRATEGY.md) | Regression, integration, end-to-end and release checks |
| [Evaluation specification](docs/EVALUATION_SPEC.md) | Datasets, independent oracles, ablations and result reporting |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Dependency-ordered backlog, owners and six-day schedule |
| [Development](docs/DEVELOPMENT.md) | Coding practices, dependency policy, PR and agent handoff workflow |
| [Operations](docs/OPERATIONS.md) | Access, runtime modes, deployment, budgets, recovery and observability |
| [Decisions and risks](docs/DECISIONS_AND_RISKS.md) | Accepted design choices, provisional assumptions and blockers |
| [Demo and submission](docs/DEMO_AND_SUBMISSION.md) | Judge evidence, video, deck and submission checklist |
| [Source register](docs/SOURCES.md) | Supplied materials, research provenance and limits |
| [Planning validation](docs/PLANNING_VALIDATION.md) | Checks performed on this documentation pack |

## Event timing and provenance

The official build window opens **22 October 2026, 00:00 UTC / 05:30 IST**. Submission closes **27 October, 23:45 UTC / 28 October, 05:15 IST**. Target submission internally by **27 October, 18:00 UTC / 23:30 IST**. Registration and judging-start discrepancies are documented in [the rules register](docs/HACKATHON_RULES.md). Recheck HackOS announcements before acting. [Official event](https://hackathon.genai.works/event/open-agent-hackathon-2026).

This pack is pre-event planning and must be disclosed in [PREEXISTING.md](PREEXISTING.md). [NEW_WORK.md](NEW_WORK.md) will record actual eligible implementation. The user confirmed that the upstream repository is third-party inspiration and that we will build our own implementation. No upstream source or assets are to be reused under this plan; follow [ATTRIBUTION.md](ATTRIBUTION.md). No remote repository was changed or published in this task.

The user confirmed **4–5 active builders**. The plan assigns A to data/sponsors/memory, B to agents/domain/trials, C to API/auth/execution and D to independent QA/evaluation/security; the fifth builder E owns UI/UX and submission packaging when available. With four, C owns the minimal UI and submission coordination while D verifies acceptance and evidence. Named assignments and the final four-or-five-person roster remain to be set. Sponsor workspace access, available NVIDIA models/embeddings and a spend cap remain open.
