# GreenOps Verify

An engineering workbench for investigating cloud and AI waste, testing a change, approving its exact scope, and verifying the outcome.

**Status, 16 October 2026: implemented end to end, before the event, at the user's explicit instruction.** All code is declared pre-existing in [PREEXISTING.md](PREEXISTING.md). Event-window work goes in [NEW_WORK.md](NEW_WORK.md).

- **Verified locally:** the investigation loop, deterministic screening, critic enforcement, matched local trials, plan-bound approval, single execution with read-back and recovery, memory persistence across restarts, and the learning effect. These were verified with labelled scripted roles, synthetic data and a hash embedder.
- **BLOCKED:** real Zetaris federation, real NVIDIA model and embedding calls, semantic recall quality, and GCP execution. They need the team's credentials. No sponsor access, deployment, publication or measured saving is claimed.

## What it does

One engineering lead investigates one service (`support-demo`):
- **Evidence:** six synthetic GCP resource histories plus one AI support workflow. Evidence comes through reviewed SQL templates executed by Zetaris across two physical sources.
- **Proposals and screening:** bounded agents built with Google ADK on an NVIDIA-hosted model propose at most three candidates per path. Deterministic code screens them: peak CPU, a forecast stress envelope, absolute memory, coverage, freshness, compatibility, policy and economics.
- **Critique:** a critic requests evidence or a revision. Failed checks cannot be overridden.
- **Trials:** eligible candidates run matched trials, either local A/B workloads on disposable fixtures or AI development-suite runs scored by an independent verifier.
- **Approval and execution:** a human approves the exact plan hash and trial hash, valid for 15 minutes. The worker re-checks everything, executes once under a global slot plus a per-target lock, reads the change back, runs a fresh workload, and recovers only when no intervening change exists.
- **Memory:** results go into Meterless H-MEM through a transactional outbox. A later investigation recalls applicable prior failures and does not repeat them. After a policy change those memories become "historical — retest required".

The executed change is a **local analogue**: the real `max_concurrency` of a sandbox worker process stands in for the e2-standard-8 → e2-standard-4 resize. It is never reported as a GCP resize. Cost and carbon figures are projections and estimates at synthetic rates.

## Quick start (sample mode, no credentials)

Prerequisites: macOS/Linux, Python 3.12 with `uv`, Node ≥ 22.12, PostgreSQL 16 client/server binaries (`initdb`, `pg_ctl`).

```bash
cp .env.example .env
```

Edit `.env` for sample mode:
- `RUNTIME_MODE=sample`, `EMBEDDING_MODE=hash_conformance`, `HMEM_DATA_DIR=var/hmem-sample`, `MAX_RUN_COST_USD=1`
- `MEMORY_AUTH_TOKEN` set to a random string of at least 16 characters

```bash
make bootstrap
```

Bootstrap installs the locked dependencies, starts a project-local PostgreSQL on :55432, generates and loads the synthetic data, migrates, creates the sandbox actors (tokens go to `var/actors.local.json`) and approves the trial profile.

```bash
make sandbox-up
```

Then run each of these in its own terminal:

```bash
make sidecar
```

```bash
make api
```

```bash
make worker
```

```bash
make ui
```

Open http://127.0.0.1:8501 and sign in with the `lead` token from `var/actors.local.json`. Start an investigation with the trial profile and memory on. Or run one from the CLI:

```bash
make demo
```

Expected in sample mode (scripted roles, illustrative only):
- **Rejected on peak:** the tempting `worker-prod-01 → e2-standard-2` and `worker-stg-01 → e2-standard-2`. The prod worker averages 10.4% CPU but peaks at 6.4 vCPU, against 1.6 allowed.
- **Evidence-driven revision:** `worker-stg-01 → e2-standard-4` passes after a telemetry-series request and a matched local trial.
- **AI path:** an AI truncated-policy candidate fails the development suite (premium exception lost, 32/40). Its revision `relevant_sections` passes 40/40 at lower cost per accepted task.
- **Approval blocked:** sample runs cannot be approved; this is shown as a blocker.

Swagger UI is at http://127.0.0.1:8000/docs. API contract: [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

## Connected demo (real sponsors)

1. **Load the sources.** Host two physically separate PostgreSQL databases that your Zetaris workspace can reach over TLS, with read-only roles. Load them:

   ```bash
   make sources-split SOURCE_A_URL=postgresql://…/src_a SOURCE_B_URL=postgresql://…/src_b
   ```

   Source A gets `public` (inventory, telemetry, billing, pagination probe) and `ref` (prices, policies, carbon factors). Source B gets the AI runs and calls. Register both in Zetaris.
2. **Fill in `.env`:**
   - `RUNTIME_MODE=connected_demo`
   - `ZETARIS_ORG_ID`, `ZETARIS_AUTH_MODE` (`api_key` or `login_id_token`) plus the matching credentials
   - `ZETARIS_SOURCE_CLOUD`, `ZETARIS_SOURCE_REF`, `ZETARIS_SOURCE_AI` as `datasource.schema` names
   - `MODEL_ID`, `MODEL_API_KEY`
   - `EMBEDDING_MODE=nvidia`, `EMBEDDING_API_KEY`
   - `MAX_RUN_COST_USD`
   - `SANDBOX_WRITES_ENABLED=true`, only once you have reviewed the scope
3. **Rerun bootstrap and check readiness:**

   ```bash
   make bootstrap
   ```

   ```bash
   make preflight
   ```

   Preflight fails with actionable gaps, including the case where the two sources are not distinct datasources.
4. **Prove the sponsor paths:**

   ```bash
   make test-connected
   ```

   This runs ZET-01..04, NIM-01..02 and HMEM-07 (paraphrase retrieval gate ≥ 8/10, restart, version rejection, provider removal). Missing credentials report BLOCKED, never PASS.
5. **Run the journey** from the UI: investigate → trial → approve → execute → verify → reload → report. Then freeze the AI candidate and run the evaluator-only holdout as role D:

   ```bash
   make eval-freeze PLAN=<ai plan id>
   ```

   ```bash
   make eval
   ```

## Commands and tests

| Command | What it does |
|---|---|
| `make check` | Unit and contract tests, OpenAPI snapshot, docs links and route coverage, secret scan |
| `make test-integration` | Real PostgreSQL, real sandbox worker processes, a real H-MEM sidecar process: authority (ACT/SEC) and memory-learning tests |
| `make test-sidecar` | 21 node:test contract, integrity and fail-closed tests for the memory wrapper |
| `make test-connected` | Real sponsor tests (BLOCKED without credentials) |
| `make test` | Everything, then PASS/FAIL/BLOCKED/NOT_RUN counts |
| `make eval-cloud` | Forecast temporal evaluation and the naive-heuristic decision benchmark |
| `make memory-ablation` | Memory on/off sequence |
| `make eval` | Locked holdout evaluation |
| `make reset-demo` | Resets demo namespaces only, after confirmation; refuses while actions are active |

Last local results (16 Oct, sample/scripted): unit 33 PASS · integration 22 PASS · sidecar 21 PASS · connected 8 BLOCKED · 0 FAIL. Details are in [docs/TEST_STRATEGY.md §8](docs/TEST_STRATEGY.md).

## Stack

Python 3.12 · FastAPI/Pydantic · psycopg + SQL migrations · Google ADK 2.12 + LiteLLM 1.105 → NVIDIA OpenAI-compatible endpoint · Streamlit · PostgreSQL (authority, jobs, approvals, actions, outbox) · Zetaris REST (start/page/close) · Meterless H-MEM reference `0aa7417b` vendored with three attributed patches in a zero-dependency TypeScript sidecar · Docker Compose for one host (not yet run: Docker was unavailable during the build). Versions are listed in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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
| [Upstream review](docs/research/UPSTREAM_REVIEW.md) | Immutable reference revision and static findings |
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

The build window opens **22 October 2026, 00:00 UTC**. Submission closes **27 October, 23:45 UTC**; the internal target is 27 October, 18:00 UTC. The event FAQ says work committed before the window is not eligible unless declared. This repository's implementation is therefore **pre-existing**, and it was built with Claude Code, not Cursor. Obtain an organizer ruling on Track 02 versus Wildcard before submitting; see [the rules register](docs/HACKATHON_RULES.md). niksm7/GreenOps is concept inspiration only; no upstream code or assets were copied ([ATTRIBUTION.md](ATTRIBUTION.md)). Nothing was pushed, deployed, published or submitted.
