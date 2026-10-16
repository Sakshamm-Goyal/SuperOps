# GreenOps Verify — developer and operator commands. Every target uses the locked environment (uv.lock / npm lock).
export PYTHONPATH := $(CURDIR)
PY := uv run python
NODE ?= node   # must be Node 22.12–22.x (memory-sidecar/.nvmrc); override e.g. NODE=/usr/local/bin/node
PG_PORT ?= 55432
PG_DIR := var/pg
SAMPLE_SRC := postgresql://greenops@127.0.0.1:$(PG_PORT)/greenops_sample_src

.PHONY: bootstrap db-up db-down sample-data sources-split preflight dev api worker ui sidecar sandbox-up sandbox-down \
        check test-unit test-integration test-connected test-e2e test test-sidecar eval eval-freeze eval-cloud \
        memory-ablation trial-profile-approve reset-demo demo openapi verify-docs

bootstrap:            ## locked Python + Node deps, local PostgreSQL, generated data, migrations, actors
	uv sync --frozen
	cd memory-sidecar && $(NODE) scripts/check-node.mjs && npm ci --ignore-scripts
	$(MAKE) db-up sample-data
	$(PY) scripts/bootstrap.py
	$(PY) scripts/trial_profile_approve.py config/trial-profiles/sandbox-trials-v1.json --actor lead

db-up:                ## project-local PostgreSQL 16 on port $(PG_PORT) (no system service changes)
	@test -d $(PG_DIR) || LC_ALL=en_US.UTF-8 initdb -D $(PG_DIR) -U greenops --auth=trust -E UTF8 >/dev/null
	@pg_isready -h 127.0.0.1 -p $(PG_PORT) >/dev/null || LC_ALL=en_US.UTF-8 pg_ctl -D $(PG_DIR) -o "-p $(PG_PORT) -k /tmp" -l var/pg.log start
	@sleep 1; for d in greenops_app greenops_sample_src greenops_src_cloud greenops_src_ai; do createdb -h 127.0.0.1 -p $(PG_PORT) -U greenops $$d 2>/dev/null || true; done

db-down:
	pg_ctl -D $(PG_DIR) stop

sample-data:          ## regenerate deterministic synthetic data + support cases and load the sample source DB
	$(PY) scripts/generate_data.py
	$(PY) experiments/support/generate_cases.py >/dev/null
	$(PY) scripts/load_sources.py --group cloud=$(SAMPLE_SRC)#cloud --group ref=$(SAMPLE_SRC)#ref --group ai=$(SAMPLE_SRC)#ai

sources-split:        ## load source A (cloud+ref) and source B (ai) into SEPARATE databases for Zetaris registration
	$(PY) scripts/load_sources.py --group cloud=$(SOURCE_A_URL)#public --group ref=$(SOURCE_A_URL)#ref --group ai=$(SOURCE_B_URL)#public

preflight:            ## redacted readiness of configured capabilities (fails with actionable missing inputs)
	$(PY) scripts/preflight.py

sidecar:              ## H-MEM memory sidecar (foreground)
	set -a; . ./.env; set +a; mkdir -p "$$HMEM_DATA_DIR"; export HMEM_DATA_DIR="$$(cd "$$HMEM_DATA_DIR" && pwd)"; \
	cd memory-sidecar && $(NODE) scripts/check-node.mjs && $(NODE) --experimental-transform-types src/server.ts

api:
	uv run uvicorn greenops.api.app:get_app --factory --host 127.0.0.1 --port 8000

worker:
	$(PY) -m greenops.worker.main

ui:
	uv run streamlit run greenops/ui/app.py --server.port 8501 --server.headless true

sandbox-up:           ## start the local executable sandbox workers (action target + two trial fixtures)
	$(PY) scripts/sandbox.py up

sandbox-down:
	$(PY) scripts/sandbox.py down

dev: sandbox-up       ## print the processes to run (each in its own terminal)
	@echo "Run in separate terminals: make sidecar | make api | make worker | make ui"

check: test-unit openapi verify-docs   ## T0: unit + contract tests, OpenAPI snapshot, docs consistency, secret scan
	$(PY) scripts/secret_scan.py

test-unit:
	uv run pytest tests/unit -q

test-integration:     ## T1: real PostgreSQL, real sandbox processes, real H-MEM sidecar process
	uv run pytest tests/integration -q

test-sidecar:
	cd memory-sidecar && $(NODE) scripts/check-node.mjs && $(NODE) --experimental-transform-types --test test/*.test.ts

test-connected:       ## T2: real Zetaris / NVIDIA / real embeddings. Missing credentials => BLOCKED (never PASS)
	uv run pytest tests/connected -q -rs

test-e2e:             ## browser E2E is NOT implemented; the API/worker journey is covered by test-integration
	@echo "NOT_RUN: no browser E2E harness exists yet (docs/TEST_STRATEGY.md §8). Use make test-integration for the control-flow journey."; exit 2

test: test-sidecar   ## everything in one pytest session; prints PASS/FAIL/BLOCKED/NOT_RUN and keeps pytest's exit code
	uv run pytest tests -q -rs; code=$$?; $(PY) scripts/test_report.py; exit $$code

release-gate: test   ## fails unless every check PASSed: any FAIL, BLOCKED (e.g. missing sponsor credentials) or NOT_RUN blocks release
	$(PY) scripts/test_report.py --release-gate

eval-freeze:          ## freeze a validated AI candidate: make eval-freeze PLAN=<plan_id>
	$(PY) -m experiments.support.evaluate freeze --plan $(PLAN)

eval:                 ## T4: evaluator-only locked holdout run (role D)
	$(PY) -m experiments.support.evaluate run

eval-cloud:           ## forecast temporal evaluation + naive-baseline decision benchmark
	$(PY) scripts/eval_cloud.py

memory-ablation:
	$(PY) scripts/memory_ablation.py

trial-profile-approve:   ## make trial-profile-approve PROFILE=config/trial-profiles/sandbox-trials-v1.json ACTOR=lead
	$(PY) scripts/trial_profile_approve.py $(PROFILE) --actor $(ACTOR)

resolve-action:       ## record a human resolution: make resolve-action ACTION=<id> ACTOR=lead NOTE="..."
	$(PY) scripts/resolve_action.py $(ACTION) --actor $(ACTOR) --note "$(NOTE)"

reset-demo:
	$(PY) scripts/reset_demo.py --confirm support-demo

demo:                 ## one investigation through the real API + worker, printed queue
	$(PY) scripts/drive.py

openapi:              ## regenerate the committed OpenAPI snapshot from the implemented schemas
	$(PY) -c "import json; from greenops.api.app import create_app; print(json.dumps(create_app().openapi(), indent=1, sort_keys=True))" > docs/openapi.json

verify-docs:
	$(PY) scripts/verify_docs.py
