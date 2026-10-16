"""HMEM-01/02/03/05 at the application level with a real sidecar process (hash_conformance embedder: deterministic,
labelled semantic=false — semantic recall quality is certified only by tests/connected with real embeddings).
Runs in sample mode: connected_demo deliberately refuses a non-semantic embedding profile (tested below)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from greenops.db import connect
from greenops.services import memory_service
from tests.conftest import auth, drain, make_runtime, start_investigation

pytestmark = pytest.mark.integration


def _app(rt):
    from greenops.api.app import create_app
    return TestClient(create_app(rt))


def _inv(client, iid):
    return client.get(f"/v1/investigations/{iid}", headers=auth("lead", False)).json()


@pytest.fixture(scope="module")
def first_run(db_url, sandbox, sidecar):
    rt = make_runtime(db_url, sandbox, memory=sidecar, mode="sample")
    client = _app(rt)
    iid = start_investigation(client, memory="on", mode="sample")
    drain(rt)
    return rt, client, _inv(client, iid)


def test_hmem01_outbox_delivered_and_survives_restart(first_run, sidecar):
    rt, client, inv = first_run
    with connect(rt.db) as c:
        rows = c.execute("SELECT * FROM memory_outbox WHERE tenant_id='sandbox-tenant'").fetchall()
    kinds = {r["receipt_kind"] for r in rows}
    assert {"screening_rejection", "rejected_trial", "validated_plan"} <= kinds
    assert all(r["status"] == "SENT" and r["engine_memory_id"] for r in rows)
    sidecar.restart()  # same durable data dir
    rec = rt.memory_factory().recall("sandbox-tenant", "support-demo", "failed truncated policy context support workflow trial",
                                     {"policy_version": "pol-v1", "workload_version": "support-workflow-v1",
                                      "config_version": "1", "model_version": "scripted-sample-v1", "test_version": None}, top_k=10)
    assert rec["items"] or rec["historical"]
    audit = client.get(f"/v1/memories/{rows[0]['application_receipt_id']}", headers=auth("teammate", False)).json()
    assert audit["data"]["audit"]["history"], audit
    # duplicate delivery of the same receipt does not create a second engine record
    again = rt.memory_factory().remember(rows[0]["envelope"])
    assert again["duplicate"] and again["engine_memory_id"] == rows[0]["engine_memory_id"]


def test_hmem05_later_investigation_uses_applicable_failures(first_run, db_url, sandbox, sidecar):
    rt, client, inv1 = first_run
    iid = start_investigation(client, memory="on", mode="sample", question="Repeat: what can we change this week?")
    drain(rt)
    inv2 = _inv(client, iid)
    mem = inv2["data"]["memory"]
    assert mem["status"] == "used" and mem["applicable"]
    sigs2 = {p["screening"]["signature"] for p in inv2["data"]["plans"]}
    failed1 = {p["screening"]["signature"] for p in inv1["data"]["plans"] if p["status"] == "REJECTED"}
    assert not (sigs2 & failed1), "previously failed candidates were repeated despite applicable memory"
    with connect(rt.db) as c:
        t1 = c.execute("SELECT COUNT(*) AS n FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s", (inv1["id"],)).fetchone()["n"]
        t2 = c.execute("SELECT COUNT(*) AS n FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s", (iid,)).fetchone()["n"]
    assert t2 < t1  # repeated failed trial avoided
    assert any(p["status"] == "AWAITING_APPROVAL" for p in inv2["data"]["plans"])  # a fresh trial still required for success


def test_memory_guard_blocks_repeat_even_if_optimizer_ignores_memory(first_run, db_url, sandbox, sidecar):
    from greenops.agents.roles import scripted_optimizer
    forgetful = lambda payload, tools: scripted_optimizer({**payload, "memory": [], "feedback": [], "round": 1}, tools)
    rt = make_runtime(db_url, sandbox, memory=sidecar, scripts={"optimizer": forgetful}, mode="sample")
    client = _app(rt)
    iid = start_investigation(client, memory="on", mode="sample")
    drain(rt)
    plans = _inv(client, iid)["data"]["plans"]
    guarded = [p for p in plans if any(c["check_id"] == "MEM-PRIOR-FAILURE" for c in p["screening"]["checks"])]
    assert guarded and all(p["status"] == "REJECTED" and p["memory_refs"] for p in guarded)
    with connect(rt.db) as c:
        assert not c.execute("SELECT 1 FROM trials WHERE plan_id = ANY(%s)", ([p["id"] for p in guarded],)).fetchone()


def test_hmem03_policy_change_makes_prior_results_historical(first_run, db_url, sandbox, sidecar):
    rt = make_runtime(db_url, sandbox, memory=sidecar, policy_version="pol-v2", mode="sample")
    client = _app(rt)
    iid = start_investigation(client, memory="on", trials=False, mode="sample")
    drain(rt)
    mem = _inv(client, iid)["data"]["memory"]
    assert not mem["applicable"] and mem["historical"]
    assert all("POLICY_VERSION_CHANGED" in m["inapplicable_reasons"] for m in mem["historical"])


def test_hmem02_foreign_scope_never_returned(first_run, sidecar):
    rt, client, inv = first_run
    rec = rt.memory_factory().recall("other-tenant", "support-demo", "rejected worker downsizing", {"policy_version": "pol-v1",
                                     "workload_version": "x", "config_version": "x", "model_version": None, "test_version": None})
    assert rec["items"] == [] and rec["historical"] == []


def test_memory_unavailable_blocks_memory_aware_run(db_url, sandbox):
    class Down:
        url, auth = "http://127.0.0.1:1", "x" * 20
    rt = make_runtime(db_url, sandbox, memory=Down(), mode="sample")
    client = _app(rt)
    iid = start_investigation(client, memory="on", trials=False, mode="sample")
    drain(rt)
    inv = _inv(client, iid)
    assert inv["status"] == "FAILED" and inv["data"]["outcome"]["error"]["code"] == "MEMORY_NOT_READY"


def test_connected_mode_refuses_non_semantic_embeddings(db_url, sandbox, sidecar):
    rt = make_runtime(db_url, sandbox, memory=sidecar)
    client = _app(rt)
    iid = start_investigation(client, memory="on", trials=False)
    drain(rt)
    inv = _inv(client, iid)
    assert inv["status"] == "FAILED" and "semantic" in inv["data"]["outcome"]["error"]["message"]
