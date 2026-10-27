# GreenOps Verify

**Prove it *before* you change it.** An engineering workbench that finds cloud and AI waste, refuses the tempting changes the evidence says are unsafe, tests the rest, binds a human approval to the exact plan, executes once, verifies the outcome, and remembers what happened so the next investigation starts smarter.

**Status, 26–27 Oct 2026 (event window):** running end to end on **live sponsor services**:
- **Zetaris federation:** a local Zetaris platform (Docker) queries two physically separate PostgreSQL servers. Source A is the host PostgreSQL 16 (cloud inventory, telemetry, billing, reference rates). Source B is a separate PostgreSQL 17 container (AI runs and calls). Both use read-only roles. Connected gates ZET-01..04 PASS.
- **NVIDIA:** Nemotron 3.5 Super runs the coordinator, investigator, optimizer and critic agents through Google ADK. Nemotron 3.5 Embed provides semantic memory. Gates NIM-01/02 PASS.
- **Meterless H-MEM** stores trial results, verified changes and rejections, and later runs recall them. HMEM-07 (paraphrase recall, restart, provider removal) PASS.
- **Claude Haiku 4.5** powers the **Ops Copilot**: a DevOps/FinOps assistant that answers from the live records, Zetaris queries and memory, read-only, with citations.
- A connected investigation reached `AWAITING_APPROVAL` with a PASSED matched trial. It was approved by exact hash, executed and **VERIFIED (measured)** with read-back, and the outcome was written to memory. The next investigation recalled it and proposed one candidate instead of three.

Pre-event work is declared in [PREEXISTING.md](PREEXISTING.md); event-window work is listed in [NEW_WORK.md](NEW_WORK.md). The executed change is a **local analogue**: the real `max_concurrency` of a sandbox worker process stands in for an e2-standard-8 → e2-standard-4 resize. It is never reported as a GCP resize. Cost and carbon figures are projections and estimates at synthetic, dated rates.

## For judges: a five-minute tour

| What to check | Where |
|---|---|
| The live connected run: 3 proposals, 2 refused with reasons, matched trial PASSED, exact-hash approval, VERIFIED action, memory written | [docs/DEMO_AND_SUBMISSION.md §3a](docs/DEMO_AND_SUBMISSION.md) (run IDs) · [NEW_WORK.md](NEW_WORK.md) |
| Sponsor integration proof: ZET-01..04, NIM-01/02, HMEM-07 8/8 PASS | [evidence/connected/](evidence/connected/) · [tests/connected/test_sponsors.py](tests/connected/test_sponsors.py) · [§8a sponsor table](docs/DEMO_AND_SUBMISSION.md) |
| Why a model can never authorize a write | [greenops/services/approvals.py](greenops/services/approvals.py) · [greenops/services/execution.py](greenops/services/execution.py) · [tests/integration/test_authority.py](tests/integration/test_authority.py) |
| Deterministic screening (peaks and forecast stress, not averages) | [greenops/domain/screening.py](greenops/domain/screening.py) · [greenops/domain/capacity.py](greenops/domain/capacity.py) |
| Zetaris adapter (paging, receipts, UTC handling, fail-closed) and two-source setup | [greenops/adapters/evidence.py](greenops/adapters/evidence.py) · [scripts/zetaris_setup.py](scripts/zetaris_setup.py) |
| Meterless H-MEM sidecar (outbox, applicability, corrections) | [memory-sidecar/](memory-sidecar/) · [greenops/services/memory_service.py](greenops/services/memory_service.py) |
| Ops Copilot (read-only tools, caller-scoped) and Autopilot (start-only role) | [greenops/copilot.py](greenops/copilot.py) · [scripts/autopilot.py](scripts/autopilot.py) |
| Bugs the live sponsors exposed, each fixed reproducer-first | [NEW_WORK.md](NEW_WORK.md) · [EVALUATION_SPEC amendments](docs/EVALUATION_SPEC.md) |
| Honest limits: synthetic data, local sandbox analogue, projected savings | [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) · the status note above |

## What it does

One engineering lead investigates one service (`support-demo`):
1. **Evidence.** Reviewed SQL templates run through **Zetaris** across two physical sources. Every query has a receipt: sources, request IDs, pages, completeness and result hash.
2. **Proposals.** Bounded **Nemotron** agents propose at most three candidates per path, cloud and AI workflow.
3. **Screening.** Deterministic code screens every candidate: observed peak and forecast stress (never averages), absolute memory, coverage, freshness, compatibility, policy and economics. A critic demands evidence or a revision, and failed checks cannot be overridden.
4. **Trials.** Matched trials run on disposable fixtures: identical offered load for cloud, and a locked development suite with an independent verifier for AI.
5. **Approval.** A human approves the exact plan hash and trial hash, valid for 15 minutes. PostgreSQL holds authority; memory, chat, confidence and button state never authorize anything.
6. **Execution.** The worker re-checks every precondition, executes once under a target lock, reads the change back, runs a fresh workload and verifies.
7. **Memory.** Outcomes go to **Meterless H-MEM** through a transactional outbox. Later runs recall applicable lessons; memories from an older policy become "historical — retest required".
8. **Autopilot.** A watcher fingerprints the deciding evidence through Zetaris and starts an investigation when it drifts. Its `automation` role can start investigations and nothing else.
9. **Ops Copilot.** **Claude Haiku 4.5** explains any of it in plain language, citing the records it read.

A justified rejection is a success. The headline example: `worker-prod-01 → e2-standard-2` averages 10.4% CPU but peaks at 6.4 vCPU against 1.6 allowed, so it is refused.

## Quick start: connected demo (live sponsors)

Prerequisites: macOS/Linux, Python 3.12 + `uv`, Node 22.12–22.x (`/usr/local/bin/node`; Node 26 is refused), PostgreSQL 16 binaries, Docker Desktop (8 GB, 4 CPUs; Rosetta on Apple Silicon), NVIDIA API key, Anthropic API key, and a Zetaris hackathon registry login from the Zetaris Cloud download page.

1. **Zetaris platform (local).** Download `zetaris-platform.zip` from the Zetaris Cloud dashboard → *Run locally*, run its `docker login` command, then from the unpacked folder:

   ```bash
   ./preflight.sh && docker compose pull && docker compose up -d && ./verify.sh
   ```

   If port 3000 is taken, set `UI_PORT=3001`, `ALLOWED_ORIGINS` and `GUI_URL` in its `.env`. The REST API is on `:8888`.
2. **Configure.** `cp .env.example .env`, then set:
   - `RUNTIME_MODE=connected_demo`
   - `ZETARIS_API_BASE_URL=http://127.0.0.1:8888`, `ZETARIS_ORG_ID=1`, `ZETARIS_AUTH_MODE=login_id_token` and the platform admin login
   - `ZETARIS_SOURCE_CLOUD=cloud_pg`, `ZETARIS_SOURCE_REF=cloud_ref`, `ZETARIS_SOURCE_AI=ai_pg`
   - the NVIDIA `MODEL_*`/`EMBEDDING_*` keys and `EMBEDDING_MODE=nvidia`
   - `ANTHROPIC_API_KEY`, `MEMORY_AUTH_TOKEN` (≥16 chars) and `MAX_RUN_COST_USD`
3. **Bootstrap, sources, federation:**

   ```bash
   make bootstrap NODE=/usr/local/bin/node
   ```

   ```bash
   make sources-up
   ```

   ```bash
   make zetaris-setup
   ```

   `zetaris-setup` loads both sources, creates read-only `zetaris_ro` roles, registers `cloud_pg`, `cloud_ref` (datasource views over schema `ref`) and `ai_pg` in Zetaris, and verifies the row counts through federation.
4. **Readiness and sponsor gates:**

   ```bash
   make preflight
   ```

   ```bash
   make test-connected
   ```

5. **Run** (each in its own terminal):

   ```bash
   make sandbox-up && make sidecar NODE=/usr/local/bin/node
   ```

   ```bash
   make api
   ```

   ```bash
   make worker
   ```

   ```bash
   make web
   ```

   Open **http://localhost:5173**. Sign in with a token from `var/actors.local.json` (`lead` = operator, `judge` = viewer, `admin` = admin). The Streamlit workbench (`make ui`, :8501) remains available.

To execute an approved change, set `SANDBOX_WRITES_ENABLED=true` after reviewing `ALLOWED_TARGET_IDS`. Only the local sandbox analogue targets are writable.

## Quick start: sample mode (no credentials)

Set `RUNTIME_MODE=sample`, `EMBEDDING_MODE=hash_conformance`, `HMEM_DATA_DIR=var/hmem-sample`, `MAX_RUN_COST_USD=1` and a `MEMORY_AUTH_TOKEN`, then:

```bash
make bootstrap
```

Then run `make sandbox-up`, `make sidecar`, `make api`, `make worker` and `make web` as above. Sample runs use scripted roles over one labelled local database (not federation) and cannot be approved. `SAMPLE_MODEL=nvidia` runs the real Nemotron agents over the sample evidence.

## Web workbench

| Page | What it shows |
|---|---|
| Landing `/` | Product story, the four steps, peak-vs-average, integrations |
| Overview `/app` | Proposed vs blocked vs verified savings (each with its basis), carbon estimate, rejections by check, pipeline, sponsor health, recent activity |
| Investigation story `/app/investigations/:id` | Live stage stepper; peak-vs-allowed chart over the whole interval; the revision that passed a matched trial; AI verifier rejection; memory recall; Zetaris receipt; timeline |
| Plan `/app/plans/:id` | Immutable core and hash, checks, impacts with basis, trials, approval panel driven only by server `next_allowed_actions`/`blockers` with a 15-minute countdown |
| Trial / Action / Evidence / Memory / Report | Measured metrics, execution journal and verification, query receipts and rows, H-MEM audit, decision record |
| Ops Copilot | Chat page plus a slide-over on every page, aware of the current investigation; tool chips and citations |
| Operations (admin) | Readiness, versions, execution slot, jobs, outbox, budgets |

## Commands and tests

| Command | What it does |
|---|---|
| `make check` | Unit and contract tests, OpenAPI snapshot, docs links and route coverage, secret scan |
| `make test-integration` | Real PostgreSQL, real sandbox worker processes, real H-MEM sidecar: authority (ACT/SEC) and memory learning |
| `make test-sidecar` | node:test contract, integrity, fail-closed and retry tests for the memory wrapper (Node 22; `NODE=` to select) |
| `make test-connected` | Live sponsor gates ZET-01..04, NIM-01/02, HMEM-07 (missing credentials report BLOCKED, never PASS) |
| `make sources-up` / `make zetaris-setup` | Source B container; Zetaris datasource registration and verification |
| `make autopilot` (`ONCE=1`) | Drift-triggered investigations: fingerprints inventory, telemetry, billing, prices and policy through Zetaris and starts an investigation as the `automation` actor when they change; it can never approve or execute |
| `make web` / `make web-build` | React workbench dev server (:5173) / type-checked production build |
| `make test` / `make release-gate` | Everything in one session with PASS/FAIL/BLOCKED/NOT_RUN counts / fail unless all PASS |
| `make eval-freeze PLAN=…` then `make eval` | Freeze an AI candidate, then the evaluator-only holdout (role D) |
| `make eval-cloud` / `make memory-ablation` | Forecast and naive-baseline benchmark / memory on-off sequence |
| `make correct-memory RECEIPT=… ACTOR=… NOTE=…` | Supersede a wrong memory with a reviewed correction (lineage kept; recall marks the original SUPERSEDED) |
| `make resolve-action ACTION=… ACTOR=… NOTE=…` | Operator record of a human resolution for `RECOVERY_REQUIRED` |

Latest results are recorded with dates in [NEW_WORK.md](NEW_WORK.md) and [docs/TEST_STRATEGY.md §8](docs/TEST_STRATEGY.md).

## Stack

Python 3.12 · FastAPI/Pydantic · psycopg + SQL migrations · Google ADK + LiteLLM → NVIDIA Nemotron 3.5 Super (OpenAI-compatible endpoint) · NVIDIA Nemotron 3.5 Embed · Claude Haiku 4.5 (Messages API, tool use) · PostgreSQL (authority, jobs, approvals, actions, outbox) · Zetaris platform 2.4.3 REST (login, `query/sql/start|page|close`, SQL-editor DDL for setup only) · Meterless H-MEM reference `0aa7417b` vendored with three attributed patches in a zero-dependency TypeScript sidecar · React 18 + Vite + TypeScript + Tailwind (web) · Streamlit (legacy workbench).

## Documentation map

| Document | Owns |
|---|---|
| [Hackathon rules](docs/HACKATHON_RULES.md) | Event requirements, dates, discrepancies, track and disclosure |
| [Product specification](docs/PRODUCT_SPEC.md) | User, scope, acceptance and value hypotheses |
| [UX specification](docs/UX_SPEC.md) | Review workflow, operator controls, accessibility and truthful states |
| [Architecture](docs/ARCHITECTURE.md) | Stack, boundaries, agents, persistence and recovery |
| [Data and domain](docs/DATA_AND_DOMAIN.md) | Schemas, joins, accounting, forecasting, approval invariants |
| [API reference](docs/API_REFERENCE.md) | Implemented application contract; snapshot in [openapi.json](docs/openapi.json) |
| [Sponsor research](docs/research/SPONSOR_RESEARCH.md) | Verified vendor capabilities, actual interfaces and access gaps |
| [Test strategy](docs/TEST_STRATEGY.md) | Regression, integration, end-to-end and release checks; implemented map |
| [Evaluation specification](docs/EVALUATION_SPEC.md) | Datasets, independent oracles, ablations and result reporting |
| [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | Backlog with current status |
| [Development](docs/DEVELOPMENT.md) | Coding practices, dependency policy, PR and agent handoff workflow |
| [Operations](docs/OPERATIONS.md) | Access, runtime modes, deployment, budgets, recovery and observability |
| [Decisions and risks](docs/DECISIONS_AND_RISKS.md) | Accepted design choices (ADR-18..23 added 16 Oct) and blockers |
| [Demo and submission](docs/DEMO_AND_SUBMISSION.md) | Judge evidence, video, deck and submission checklist |
| [Source register](docs/SOURCES.md) | Supplied materials, research provenance and limits |
| [Memory sidecar](memory-sidecar/README.md) | Private H-MEM wrapper routes, patches and limitations |

## Event timing and provenance

The build window opens **22 October 2026, 00:00 UTC**. Submission closes **27 October, 23:45 UTC**; the internal target is 27 October, 18:00 UTC. The event FAQ says work committed before the window is not eligible unless declared. This repository's implementation is therefore **pre-existing**, and it was built with Claude Code, not Cursor. Obtain an organizer ruling on Track 02 versus Wildcard before submitting; see [the rules register](docs/HACKATHON_RULES.md). niksm7/GreenOps is concept inspiration only; no upstream code or assets were copied ([ATTRIBUTION.md](ATTRIBUTION.md)). Nothing has been deployed, published or submitted.
