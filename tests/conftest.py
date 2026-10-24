"""Shared fixtures. Integration tests use a real PostgreSQL test DB, real sandbox worker processes (offset ports,
temp dir) and, where marked, a real H-MEM sidecar process. Evidence uses the labelled local sample DB and roles use
the scripted gateway: these tests certify control flow and authority, never sponsor connectivity or model quality.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import secrets
import subprocess
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import psycopg
import pytest

from greenops.config import ROOT, RuntimeMode, get_settings

PG = os.environ.get("TEST_PG_ADMIN_URL", "postgresql://greenops@127.0.0.1:55432/postgres")
TEST_DB = "greenops_itest"
TOKENS = {"lead": ("operator", "tok-lead-" + "x" * 20), "teammate": ("viewer", "tok-viewer-" + "x" * 20),
          "operator2": ("operator", "tok-op2-" + "x" * 20), "admin": ("admin", "tok-admin-" + "x" * 20)}


def _pg_available() -> bool:
    try:
        psycopg.connect(PG, connect_timeout=2).close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_url():
    if not _pg_available():
        pytest.skip("BLOCKED: local PostgreSQL not reachable (start var/pg; see README)")
    with psycopg.connect(PG, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        c.execute(f"CREATE DATABASE {TEST_DB}")
    url = PG.rsplit("/", 1)[0] + "/" + TEST_DB
    from greenops.db import migrate, connect, J
    from greenops.domain.quantities import canonical_hash
    migrate(url)
    doc = json.loads((ROOT / "config/trial-profiles/sandbox-trials-v1.json").read_text())
    doc["local_worker_pair"].update({"warmup_s": 1, "measure_s": 3})
    with connect(url) as c:
        c.execute("INSERT INTO services VALUES ('sandbox-tenant','support-demo','Support demo',%s)", (["sample", "connected_demo"],))
        c.execute("INSERT INTO budget_profiles (id, tenant_id, max_run_cost_usd, max_model_calls, max_conservative_cost_per_call_usd) "
                  "VALUES ('sandbox-approved-budget-v1','sandbox-tenant',5,2000,0.001)")
        for aid, (role, tok) in TOKENS.items():
            c.execute("INSERT INTO actors (actor_id, tenant_id, display_name, role, token_sha256) VALUES (%s,'sandbox-tenant',%s,%s,%s)",
                      (aid, aid, role, hashlib.sha256(tok.encode()).hexdigest()))
        c.execute("INSERT INTO actors (actor_id, tenant_id, display_name, role, token_sha256) VALUES ('foreign','other-tenant','x','operator',%s)",
                  (hashlib.sha256(b"tok-foreign-xxxxxxxxxxxxxxxxxx").hexdigest(),))
        c.execute("INSERT INTO trial_profiles VALUES ('sandbox-trials-v1','sandbox-tenant','support-demo',%s,%s,'lead',now(),now()+interval '7 days','ACTIVE')",
                  (J(doc), canonical_hash(doc)))
    return url


@pytest.fixture(scope="session")
def sandbox(tmp_path_factory):
    d = tmp_path_factory.mktemp("sandbox")
    os.environ["SANDBOX_PORT_OFFSET"] = "300"
    from greenops.adapters.sandbox import start_workers, stop_workers
    start_workers(d)
    yield d
    stop_workers(d)


@pytest.fixture(scope="session")
def sidecar(tmp_path_factory):
    """Real H-MEM sidecar process (hash_conformance: deterministic, labelled semantic=false)."""
    data = tmp_path_factory.mktemp("hmem")
    token = secrets.token_urlsafe(24)
    port = 7499
    env = {**os.environ, "MEMORY_AUTH_TOKEN": token, "HMEM_DATA_DIR": str(data), "PORT": str(port), "EMBEDDING_MODE": "hash_conformance"}

    def start():
        p = subprocess.Popen(["node", "--experimental-transform-types", "src/server.ts"], cwd=ROOT / "memory-sidecar", env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", headers={"Authorization": f"Bearer {token}"}, timeout=1).status_code == 200:
                    return p
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        p.kill()
        pytest.skip("BLOCKED: memory sidecar did not start")

    state = {"proc": start()}

    class Handle:
        url, auth = f"http://127.0.0.1:{port}", token
        data_dir = data

        def restart(self):
            state["proc"].terminate()
            state["proc"].wait(5)
            state["proc"] = start()

    yield Handle()
    state["proc"].terminate()


def make_runtime(db_url, sandbox_dir, *, mode="connected_demo", memory=None, policy_version="pol-v1", scripts=None, writes=True):
    from greenops.adapters.evidence import SampleSqlClient
    from greenops.adapters.memory import MemoryClient, MemoryUnavailable
    from greenops.adapters.model import ScriptedGateway
    from greenops.agents.roles import SCRIPTS
    from greenops.services.common import Runtime
    from experiments.support.workflow import scripted_support
    s = dataclasses.replace(get_settings(), runtime_mode=RuntimeMode(mode), database_url=db_url, sandbox_dir=Path(sandbox_dir),
                            sandbox_writes_enabled=writes, policy_version=policy_version,
                            memory_base_url=memory.url if memory else "http://127.0.0.1:1", memory_auth_token=memory.auth if memory else "unset-token-xxxxxxxx",
                            app_env="sandbox")
    gw = ScriptedGateway({**SCRIPTS, "support": scripted_support, **(scripts or {})})

    def mem():
        return MemoryClient(s)
    return Runtime(s, lambda: SampleSqlClient(s.sample_source_url), lambda: gw, mem)


def auth(actor: str, key: bool = True) -> dict:
    h = {"Authorization": f"Bearer {TOKENS[actor][1]}"}
    if key:
        h["Idempotency-Key"] = str(uuid.uuid4())
    return h


INTERVAL = {"start": "2026-09-30T00:00:00Z", "end": "2026-10-21T00:00:00Z"}


def drain(rt, timeout_s: float = 600) -> None:
    """Run worker steps until no job is QUEUED or RUNNING (including rescheduled ones), or fail loudly."""
    from greenops.db import connect
    from greenops.worker.main import step
    end = time.time() + timeout_s
    while time.time() < end:
        if not step(rt, "pytest"):
            with connect(rt.db) as c:
                waiting = c.execute("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()["n"]
            if not waiting:
                return
            time.sleep(0.5)
    raise AssertionError("worker jobs still pending after drain timeout")


def start_investigation(client, *, mode="connected_demo", memory="off", trials=True, question="Find a testable saving"):
    body = {"service_id": "support-demo", "question": question, "interval": INTERVAL, "runtime_mode": mode,
            "budget_profile_id": "sandbox-approved-budget-v1", "memory_mode": memory}
    if trials:
        body["approved_trial_profile_id"] = "sandbox-trials-v1"
    r = client.post("/v1/investigations", json=body, headers=auth("lead"))
    assert r.status_code == 202, r.text
    return r.json()["investigation_id"]


# ---- PASS / FAIL / BLOCKED / NOT_RUN accounting (TEST_STRATEGY §1) ---------------------------
_RESULTS: dict[str, str] = {}


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        if report.skipped:
            reason = str(report.longrepr[-1]) if isinstance(report.longrepr, tuple) else str(report.longrepr)
            _RESULTS[report.nodeid] = "BLOCKED" if "BLOCKED" in reason else "NOT_RUN"
        else:
            _RESULTS[report.nodeid] = "PASS" if report.passed else "FAIL"


def pytest_sessionfinish(session, exitstatus):
    if not _RESULTS:
        return
    out = ROOT / "var" / "test-results"
    out.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    counts = {k: sum(1 for v in _RESULTS.values() if v == k) for k in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")}
    (out / "latest.json").write_text(json.dumps({"finished_at": datetime.now(timezone.utc).isoformat(), "counts": counts,
                                                 "results": _RESULTS}, indent=1, sort_keys=True))
