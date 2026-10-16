# Audit evidence

Audit source revision: `8bc88d89556231d455ccc51b18059c51ed931bc3`. See [the consolidated report](../../../docs/IMPLEMENTATION_AUDIT_2026-10-17.md). Artifacts are local sample/synthetic/contract evidence, not live sponsor acceptance. UTC receipts may be 16 October while the local review date is 17 October Asia/Kolkata.

Files include domain/authority/delivery reviewer notes, observed JSON/JSONL results, local test logs, safe reproducer scripts and `ui-ai-lab.png`. `validation.json` records final command outcomes. The original reviewer notes retain `/tmp` paths as provenance; use the copied scripts here for continued work. The authority script was extended to print cancellation-after-drain state after its saved run, so that added output is not present in the saved JSON. Cancellation remains source-confirmed with a separate reviewer observation; do not treat its early QUEUED snapshot as proof of post-cancel completion.

Run from the repository root with the existing locked environment:

```sh
PYTHONPATH=. .venv/bin/python evidence/audits/2026-10-17/repro-domain.py
PYTHONPATH=. .venv/bin/python evidence/audits/2026-10-17/repro-zetaris.py
```

These two scripts use synthetic dictionaries and mocked HTTP transport only; no provider or private dataset is queried. They print counterexamples, so exit0 means the probe ran, not that acceptance passed. Convert expected outcomes into failing assertions before fixes.

`repro-authority.py` uses the local PostgreSQL admin URL on55432, an existing sample source DB read-only, a uniquely named temporary audit DB, a fresh sandbox directory and port offset6000. It changes only those disposable targets and drops its audit database/stops its sandbox children in finally. It uses fixed synthetic test tokens internally and does not print user credentials. Run it alone after checking its ports are unused, with `PYTHONPATH=. .venv/bin/python ...`. The DB harness is coupled to this revision's schema and seeded sample evidence. Its resulting JSON currently writes to `/tmp/greenops-authority-audit-results-2.json`.

`repro-memory.mjs` creates disposable sidecar state, deliberately removes that test state's engine record, retries the remembered receipt, then stops and removes its own temporary files. Run with a compatible Node22 interpreter and `--experimental-transform-types`. It does not use the user's H-MEM data directory. The experiment tests integrity failure handling; it is not an observed spontaneous loss of user data.

The ordinary integration suite recreates the dedicated `greenops_itest` database and binds fixed ports7820–7822 and7499. Never run two copies concurrently or point TEST_PG_ADMIN_URL at a non-test instance. Default runs failed on fixture readiness; a fresh explicit basetemp was used to verify the result independently. Startup currently trusts an already-responsive port, which can bind a test to another sandbox directory; see the follow-up reproduction if present. Do not hide those failures by reporting only the later clean run.
