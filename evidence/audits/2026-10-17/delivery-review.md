# GreenOps Verify delivery audit (17 Oct 2026)

Scope: read-only review of UI, API surface, quickstart, Compose, docs, and release checks. I did not start paid providers, deploy, edit the app, or print credentials. Local Docker daemon was unavailable, so Compose findings are static except for `docker compose config` parsing.

## P1 — fresh quickstart fails on the supplied `.env.example`

- `README.md:26-35` tells a new user to copy the template, edit four sample-mode values, and run `make bootstrap`. `.env.example:2-3,6,29,31,40,42` places descriptions after values on the same line. `greenops/config.py:38-47` reads everything after `=` literally, including `# ...`; `get_settings()` converts `RUNTIME_MODE` to the enum at `config.py:100-103` and therefore fails before bootstrap migrates or creates actors. `MAX_RUN_COST_USD` also cannot parse if left as the supplied blank-plus-comment.
- Reproduced without touching repo state using temporary `.env`: `load_dotenv()` set `RUNTIME_MODE` to `'sample                   # sample | connected_demo | replay'`; `RuntimeMode(...)` raised `ValueError`.
- Fix the template to use full-line comments and truly empty optional values, or make the parser strip unquoted inline comments with tests for `#` in quoted secrets. Then exercise `cp .env.example .env` in a clean environment.

## P1 — Compose is not a runnable deployment path

- `docker-compose.yml:7-8,25,31-39` requires `POSTGRES_PASSWORD`, while `.env.example` has no such setting and README/OPERATIONS provide no Compose bootstrap. `docker compose --env-file .env config --services` fails with `POSTGRES_PASSWORD ... missing a value` (placeholder value makes the static config parse).
- Compose defines no migration, actor seed, trial-profile approval, synthetic-data load, or sample source database. `Dockerfile:4-10` omits `data/generated`; `greenops/config.py:120` retains a host-loopback `SAMPLE_SOURCE_URL`, so a sample-mode container cannot read the sample source even if the app DB is manually initialized. `scripts/bootstrap.py:22-51` is local-host oriented, and Compose never invokes it. API/worker depend only on DB health, not on sidecar readiness. `worker` starts sandbox child processes inside a container as UID 10001 (`Dockerfile:14`) against an uninitialized named volume; likely volume permissions also need verification.
- Compose itself has not been run: Docker daemon currently unavailable. Treat this as a static readiness blocker, not an observed end-to-end failure. Add a deterministic init/migration/load path, container-resolvable source configuration, durable volume ownership, health/dependency ordering, and a clean `docker compose up` acceptance run. If Compose is not supported yet, label it experimental in README/OPERATIONS.

## P1 — aggregate test command can report success after test failures

- `Makefile:77-79` runs `uv run pytest tests -q -rs || true` then `scripts/test_report.py`. `test_report.py:6-10` prints counts but never exits nonzero for `FAIL`, `BLOCKED`, or missing results. Thus `make test` exits 0 after a failing pytest session if the report file exists, masking release failure. This is visible by shell semantics; no intentionally failing test was injected into shared state.
- Preserve pytest's exit status while still printing the report, and establish which BLOCKED categories fail the release gate. Include a contract test for the command.

## P1 — E2E and CI evidence do not match stated tier

- `Makefile:75` defines `test-e2e` as an alias for `test-integration`; there is no browser automation in `tests/` (`rg AppTest|playwright|selenium|browser tests` found none). `docs/TEST_STRATEGY.md:44,135` describes an authenticated browser, real Zetaris/H-MEM/model, approval, actual target readback, reload, and report agreement. The alias only exercises scripted roles and sample evidence from `tests/conftest.py:1-3,112-127`. It cannot certify that E2E journey.
- `.github/workflows` is absent, while `docs/TEST_STRATEGY.md:35-48` calls for per-PR T0/T1 and protected connected gates. No automated PR gate is installed. `Makefile:60-64` also does not run the formatting or typing checks promised for T0 in `TEST_STRATEGY.md:41`.
- Add true browser/API acceptance and CI workflows, or relabel current tiers as local integration only. Never represent the present `test-e2e` as connected or browser proof.

## P2 — UI cannot start an eligible trial after a run without a profile

- `greenops/ui/app.py:313,325-329` permits an investigation with trial profile unchecked. The API exposes `run_trial` on eligible DRAFT plans (`greenops/api/app.py:365-369,459-480`), and the UX contract explicitly calls for a **Run sandbox trial** control (`docs/UX_SPEC.md:32-34,56-60`). UI `candidate_detail()` renders trial summaries and approval controls (`greenops/ui/app.py:490-541`) but has no POST to `/v1/plans/{id}/trials` anywhere in `greenops/ui/app.py` (only GET calls at lines 553 and 850). Such a user is stuck in `NEEDS_REVIEW` from the UI despite an API-permitted next step.
- Add the plan-bound trial form/button, or remove the unchecked path if manual trials are intentionally out of scope; align API `next_allowed_actions`, UI and UX spec. Test via actual API/UI flow.

## P2 — canonical documentation still claims implementation does not exist

- `docs/DEVELOPMENT.md:5-24,50-52` says app folders and commands are future work and not runnable, contradicting actual code and `README.md:3,23-66`. `docs/TEST_STRATEGY.md:35-46` similarly says tiers do not exist yet, while its own section 8 says they ran. `docs/OPERATIONS.md:46-64` lists proposed variables such as `CLOUD_WRITES_ENABLED` and `EXECUTOR_MODE` instead of implemented `SANDBOX_WRITES_ENABLED`; this can mislead a new operator because setting the proposed names does nothing.
- Reconcile these with present implementation, retaining explicit BLOCKED/NOT_RUN outcomes. The documentation checker only validates links, OpenAPI snapshot, and route-name presence (`scripts/verify_docs.py:11-29`), so it cannot catch these stale claims.

## P3 — Operations UI displays the wrong Zetaris source values

- `greenops/api/app.py:278` returns `zetaris_sources` as a dict of logical key to configured source name. `greenops/ui/app.py:1074` joins the dict directly, displaying `cloud, ai, ref` rather than the configured `datasource.schema` values the operator needs to verify. Render key/value pairs or a small table.

## Evidence and limits

- Reproduced the dotenv parse with a temporary file and `python3`; reproduced Compose variable failure with `docker compose config`. Confirmed no `.github` directory and no browser test references. Did not run the existing full suite; root agent is running main checks separately. Docker daemon was unavailable (`docker info` could not connect), so do not claim a container runtime result.
- No app files changed by this audit.
