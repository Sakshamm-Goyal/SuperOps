"""Authority/recovery/budget regressions from the 17 Oct audit (A01–A03, A06, A08, A12, A13, A15, A22, A07-downstream).
Real PostgreSQL + real sandbox worker processes; scripted roles and labelled sample evidence."""
from __future__ import annotations

import dataclasses
import uuid

import pytest
from fastapi.testclient import TestClient

from greenops.adapters.sandbox import ConfigStore, LocalWorker
from greenops.db import connect
from greenops.services import execution
from greenops.services.approvals import versions_current
from greenops.worker.main import step
from tests.conftest import auth, drain, make_runtime, start_investigation
from tests.integration.test_authority import approve, cloud_plan, create_app_for

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def env(db_url, sandbox):
    rt = make_runtime(db_url, sandbox)
    return rt, TestClient(create_app_for(rt))


def ready_plan(rt, client, path="cloud"):
    iid = start_investigation(client)
    drain(rt)
    inv = client.get(f"/v1/investigations/{iid}", headers=auth("lead", False)).json()
    p = next((p for p in inv["data"]["plans"] if p["path"] == path and p["status"] == "AWAITING_APPROVAL"), None)
    assert p is not None, [(x["path"], x["status"], x["screening"].get("signature"), (x.get("critic") or {}).get("trial")) for x in inv["data"]["plans"]]
    return client.get(f"/v1/plans/{p['id']}", headers=auth("lead", False)).json()


def queue_action(rt, client, plan):
    if plan["data"]["path"] == "ai":
        grant_holdout_verdict(rt, plan)
    ap = approve(client, plan)
    assert ap.status_code == 201, ap.text
    r = client.post(f"/v1/plans/{plan['id']}/execute", headers=auth("lead"), json={"approval_id": ap.json()["approval_id"], "plan_hash": plan["data"]["plan_hash"]})
    assert r.status_code == 202, r.text
    aid = r.json()["action_id"]
    with connect(rt.db) as c:
        c.execute("UPDATE jobs SET status='SUCCEEDED' WHERE ref_id=%s", (aid,))  # take manual control
    return aid


def grant_holdout_verdict(rt, plan):
    from experiments.support.workflow import config_hash
    from greenops.domain.models import AiWorkflowConfig
    cfg_hash = config_hash(AiWorkflowConfig(**plan["data"]["core"]["action"]["after"]))
    with connect(rt.db) as c:
        c.execute("INSERT INTO evaluation_verdicts (id, tenant_id, service_id, candidate_config_hash, model_id, freeze_hash, decision, run_id, metrics) "
                  "VALUES (%s,'sandbox-tenant','support-demo',%s,%s,'sha256:test','ROLLOUT_ELIGIBLE','test-run','{}') ON CONFLICT DO NOTHING",
                  (uuid.uuid4(), cfg_hash, plan["data"]["core"]["versions"]["model_version"]))


def test_a01_foreign_write_at_expected_plus_one_is_never_claimed_or_overwritten(env):
    rt, client = env
    plan = ready_plan(rt, client)
    aid = queue_action(rt, client, plan)
    store = ConfigStore(rt.settings.sandbox_dir, plan["data"]["target_key"])
    expected = plan["data"]["core"]["action"]["expected_config_version"]
    with connect(rt.db) as c:
        c.execute("UPDATE actions SET status='EXECUTING' WHERE id=%s", (aid,))  # crashed after intent, before our CAS
    store.compare_and_set(expected, {"max_concurrency": 6}, writer="human:oncall")
    before = store.read()
    assert execution.run(rt, aid) == "RECOVERY_REQUIRED"
    after = store.read()
    assert after == before and after["max_concurrency"] == 6  # zero compensating writes
    with connect(rt.db) as c:
        assert c.execute("SELECT holder_id FROM execution_slot").fetchone()["holder_id"] is None
    # the target stays blocked until a human records a resolution
    other = ready_plan(rt, client)
    t = approve(client, other).json()
    blocked = client.post(f"/v1/plans/{other['id']}/execute", headers=auth("lead"), json={"approval_id": t["approval_id"], "plan_hash": other["data"]["plan_hash"]})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "TARGET_BUSY"
    detail = execution.resolve_manually(rt, aid, "lead", "inspected: keep the on-call value 6")
    assert detail["target_readback"]["max_concurrency"] == 6
    client.post(f"/v1/approvals/{t['approval_id']}/revoke", headers=auth("lead"), json={"reason": "test cleanup"})


def test_a01_own_write_is_identified_by_operation_identity(env):
    rt, client = env
    plan = ready_plan(rt, client)
    aid = queue_action(rt, client, plan)
    store = ConfigStore(rt.settings.sandbox_dir, plan["data"]["target_key"])
    expected = plan["data"]["core"]["action"]["expected_config_version"]
    with connect(rt.db) as c:
        c.execute("UPDATE actions SET status='EXECUTING' WHERE id=%s", (aid,))
    store.compare_and_set(expected, {"max_concurrency": plan["data"]["core"]["action"]["after"]["max_concurrency"]}, writer=f"action:{aid}")
    assert execution.run(rt, aid) == "VERIFIED" and store.read()["version"] == expected + 1


@pytest.mark.parametrize("revoke", ["disable_actor", "downgrade_role", "remove_target"])
def test_a02_current_authority_rechecked_before_first_write(env, revoke):
    rt, client = env
    plan = ready_plan(rt, client)
    aid = queue_action(rt, client, plan)
    store = ConfigStore(rt.settings.sandbox_dir, plan["data"]["target_key"])
    v0 = store.read()["version"]
    run_rt = rt
    with connect(rt.db) as c:
        if revoke == "disable_actor":
            c.execute("UPDATE actors SET disabled=true WHERE actor_id='lead'")
        elif revoke == "downgrade_role":
            c.execute("UPDATE actors SET role='viewer' WHERE actor_id='lead'")
    if revoke == "remove_target":
        run_rt = dataclasses.replace(rt, settings=dataclasses.replace(rt.settings, allowed_target_ids=()))
    try:
        assert execution.run(run_rt, aid) == "FAILED"
    finally:
        with connect(rt.db) as c:
            c.execute("UPDATE actors SET disabled=false, role='operator' WHERE actor_id='lead'")
    a = client.get(f"/v1/actions/{aid}", headers=auth("lead", False)).json()
    assert a["data"]["verification"]["error"] == "AUTHORITY_REVOKED" and a["data"]["verification"]["writes"] == 0
    assert store.read()["version"] == v0


def test_a03_unresolved_reconciliation_is_rescheduled_and_keeps_slot(env):
    rt, client = env
    plan = ready_plan(rt, client)
    aid = queue_action(rt, client, plan)
    store = ConfigStore(rt.settings.sandbox_dir, plan["data"]["target_key"])
    with connect(rt.db) as c:
        c.execute("UPDATE actions SET status='EXECUTING' WHERE id=%s", (aid,))
        c.execute("UPDATE jobs SET status='QUEUED', run_after=now() WHERE ref_id=%s", (aid,))
    away = store.path.with_suffix(".away")
    store.path.rename(away)
    try:
        step(rt, "pytest")
        with connect(rt.db) as c:
            job = c.execute("SELECT status, run_after > now() AS later FROM jobs WHERE ref_id=%s ORDER BY created_at DESC LIMIT 1", (aid,)).fetchone()
            slot = c.execute("SELECT holder_id FROM execution_slot").fetchone()["holder_id"]
            st = c.execute("SELECT status FROM actions WHERE id=%s", (aid,)).fetchone()["status"]
        assert job["status"] == "QUEUED" and job["later"] and str(slot) == aid and st == "EXECUTING"
    finally:
        away.rename(store.path)
    with connect(rt.db) as c:
        c.execute("UPDATE jobs SET run_after=now() WHERE ref_id=%s", (aid,))
    drain(rt)
    with connect(rt.db) as c:
        assert c.execute("SELECT status FROM actions WHERE id=%s", (aid,)).fetchone()["status"] == "FAILED"  # write never happened
        assert c.execute("SELECT holder_id FROM execution_slot").fetchone()["holder_id"] is None


def test_a03_exception_in_action_job_does_not_orphan_action(env, monkeypatch):
    rt, client = env
    plan = ready_plan(rt, client)
    aid = queue_action(rt, client, plan)
    with connect(rt.db) as c:
        c.execute("UPDATE jobs SET status='QUEUED', run_after=now() WHERE ref_id=%s", (aid,))
    monkeypatch.setattr(execution, "run", lambda rt_, a: (_ for _ in ()).throw(RuntimeError("boom")))
    step(rt, "pytest")
    with connect(rt.db) as c:
        job = c.execute("SELECT status, last_error FROM jobs WHERE ref_id=%s ORDER BY created_at DESC LIMIT 1", (aid,)).fetchone()
    assert job["status"] == "QUEUED" and "boom" in job["last_error"]
    monkeypatch.undo()
    with connect(rt.db) as c:
        c.execute("UPDATE jobs SET run_after=now() WHERE ref_id=%s", (aid,))
    drain(rt)
    assert client.get(f"/v1/actions/{aid}", headers=auth("lead", False)).json()["status"] == "VERIFIED"


def test_a06_ai_freshness_binds_model_and_workflow_artifacts(env):
    rt, client = env
    plan = ready_plan(rt, client, path="ai")
    with connect(rt.db) as c:
        raw = c.execute("SELECT * FROM plans WHERE id=%s", (plan["id"],)).fetchone()
    assert versions_current(rt, raw) == (True, None)
    other_model = dataclasses.replace(rt, model_factory=lambda: type("G", (), {"model_id": "another-model"})())
    assert versions_current(other_model, raw) == (False, "MODEL_VERSION_CHANGED")
    for field, reason in (("workload_version", "WORKFLOW_VERSION_CHANGED"), ("test_version", "TEST_VERSION_CHANGED")):
        mutated = {**raw, "core": {**raw["core"], "versions": {**raw["core"]["versions"], field: "sha256:obsolete"}}}
        assert versions_current(rt, mutated) == (False, reason)


def test_a12_expired_approval_returns_plan_to_awaiting_approval(env):
    rt, client = env
    plan = ready_plan(rt, client)
    ap = approve(client, plan).json()
    with connect(rt.db) as c:
        c.execute("UPDATE approvals SET expires_at=now() WHERE id=%s", (ap["approval_id"],))
    r = client.post(f"/v1/plans/{plan['id']}/execute", headers=auth("lead"), json={"approval_id": ap["approval_id"], "plan_hash": plan["data"]["plan_hash"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "APPROVAL_EXPIRED"
    p = client.get(f"/v1/plans/{plan['id']}", headers=auth("lead", False)).json()
    assert p["status"] == "AWAITING_APPROVAL" and "approve" in p["next_allowed_actions"]
    assert approve(client, p).status_code == 201  # a fresh approval is possible


def test_a12_lazy_expiry_on_read(env):
    rt, client = env
    plan = ready_plan(rt, client)
    ap = approve(client, plan).json()
    with connect(rt.db) as c:
        c.execute("UPDATE approvals SET expires_at=now() WHERE id=%s", (ap["approval_id"],))
    p = client.get(f"/v1/plans/{plan['id']}", headers=auth("lead", False)).json()
    assert p["status"] == "AWAITING_APPROVAL" and p["data"]["latest_approval"]["status"] == "EXPIRED"


def test_a12_worker_side_expiry_returns_plan_to_awaiting_approval(env):
    rt, client = env
    plan = ready_plan(rt, client)
    aid = queue_action(rt, client, plan)
    with connect(rt.db) as c:
        c.execute("UPDATE approvals SET expires_at=now() WHERE consumed_action_id=%s", (aid,))
    assert execution.run(rt, aid) == "FAILED"
    assert client.get(f"/v1/plans/{plan['id']}", headers=auth("lead", False)).json()["status"] == "AWAITING_APPROVAL"


def test_a13_cancel_stops_queued_trials(env):
    rt, client = env
    iid = start_investigation(client)
    for _ in range(10):  # run only the investigation job until trials are queued
        with connect(rt.db) as c:
            n = c.execute("SELECT COUNT(*) AS n FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s", (iid,)).fetchone()["n"]
        if n:
            break
        from greenops.services.common import claim, finish
        job = claim(rt.db, "pytest", ("investigation",))
        from greenops.services import investigation
        investigation.advance(rt, job["ref_id"])
        finish(rt.db, job["id"], True)
    assert client.post(f"/v1/investigations/{iid}/cancel", headers=auth("lead"), json={"reason": "stop"}).status_code == 202
    drain(rt)
    with connect(rt.db) as c:
        trials = c.execute("SELECT t.status, t.result FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s", (iid,)).fetchall()
        inv = c.execute("SELECT status FROM investigations WHERE id=%s", (iid,)).fetchone()
    assert trials and all(t["status"] == "CANCELLED" and "kind" not in (t["result"] or {}) for t in trials)
    assert inv["status"] == "CANCELLED"


def test_a15_ai_approval_requires_frozen_holdout_verdict(env):
    rt, client = env
    plan = ready_plan(rt, client, path="ai")
    r = approve(client, plan)
    assert r.status_code == 422 and r.json()["error"]["code"] == "HOLDOUT_VERDICT_REQUIRED"
    grant_holdout_verdict(rt, plan)
    assert approve(client, plan).status_code == 201


def test_a08_budget_is_durable_and_trial_profile_limits_apply(env, db_url, sandbox):
    rt, client = env
    from greenops.adapters.model import BudgetExceeded
    from greenops.services.budget import DurableBudget
    scope = uuid.uuid4()
    b1 = DurableBudget(rt.db, investigation_id=None, trial_id=None, eval_run=str(scope), limits={"max_calls": 3, "max_cost_usd": "1",
                       "per_call_usd": "0.001"})
    for _ in range(3):
        b1.reserve()
    b2 = DurableBudget(rt.db, investigation_id=None, trial_id=None, eval_run=str(scope), limits={"max_calls": 3, "max_cost_usd": "1",
                       "per_call_usd": "0.001"})
    with pytest.raises(BudgetExceeded):
        b2.reserve()  # a new process/instance cannot reset the count
    with connect(rt.db) as c:
        c.execute("UPDATE trial_profiles SET document = jsonb_set(document, '{ai_dev_suite,max_model_calls}', '10'), "
                  "profile_hash = 'pending' WHERE id='sandbox-trials-v1'")
        from greenops.domain.quantities import canonical_hash
        doc = c.execute("SELECT document FROM trial_profiles WHERE id='sandbox-trials-v1'").fetchone()["document"]
        c.execute("UPDATE trial_profiles SET profile_hash=%s WHERE id='sandbox-trials-v1'", (canonical_hash(doc),))
    try:
        iid = start_investigation(client)
        drain(rt)
        with connect(rt.db) as c:
            ai = c.execute("SELECT t.status, t.result FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s AND p.path='ai'",
                           (iid,)).fetchall()
        assert ai and all(t["status"] == "INCOMPLETE" and "budget" in str(t["result"]["checks"]).lower() for t in ai)
    finally:
        with connect(rt.db) as c:
            c.execute("UPDATE trial_profiles SET document = jsonb_set(document, '{ai_dev_suite,max_model_calls}', '400') WHERE id='sandbox-trials-v1'")
            doc = c.execute("SELECT document FROM trial_profiles WHERE id='sandbox-trials-v1'").fetchone()["document"]
            c.execute("UPDATE trial_profiles SET profile_hash=%s WHERE id='sandbox-trials-v1'", (canonical_hash(doc),))


def test_a07_incomplete_economic_evidence_blocks_investigation(db_url, sandbox):
    from greenops.adapters.evidence import SampleSqlClient
    base = make_runtime(db_url, sandbox)

    class PartialPrices(SampleSqlClient):
        def query(self, template_id, params, max_rows=5000):
            r = super().query(template_id, params, max_rows)
            if template_id == "prices":
                r.completeness, r.receipt["completeness"] = "partial", "partial"
            return r
    rt = dataclasses.replace(base, evidence_factory=lambda: PartialPrices(base.settings.sample_source_url))
    client = TestClient(create_app_for(rt))
    iid = start_investigation(client)
    drain(rt)
    inv = client.get(f"/v1/investigations/{iid}", headers=auth("lead", False)).json()
    assert inv["status"] == "FAILED" and inv["data"]["outcome"]["error"]["code"] == "EVIDENCE_INCOMPLETE"


def test_a22_sandbox_refuses_to_adopt_a_worker_owned_by_another_directory(sandbox, tmp_path):
    from greenops.adapters.sandbox import SandboxOwnershipError, start_workers
    with pytest.raises(SandboxOwnershipError):
        start_workers(tmp_path)  # same ports, different sandbox directory
    w = LocalWorker(tmp_path, "local/sandbox/trial-fixture-a")
    with pytest.raises(SandboxOwnershipError):
        w.status()


def test_trial_window_with_load_generator_lag_is_remeasured_not_judged(env, monkeypatch):
    """Root cause of the flaky trial gate: a lagging load generator bursts requests. Such windows are discarded and
    re-measured; persistent lag yields INCOMPLETE (non-comparable), never PASS/FAIL."""
    import json as _json
    from greenops.config import ROOT
    from greenops.domain.models import ServicePolicy
    from greenops.services import trials as T
    rt, client = env
    real = T.run_workload
    calls = {"n": 0}

    def lagging_first_window(w, d, label):
        r = real(w, d, label)
        calls["n"] += 1
        return {**r, "schedule_lag_p95_ms": 40.0} if calls["n"] == 3 else r  # first measured window lags (after 2 warmups)
    monkeypatch.setattr(T, "run_workload", lagging_first_window)
    monkeypatch.setattr(T, "cancelled", lambda rt_, t: False)
    doc = _json.loads((ROOT / "config/trial-profiles/sandbox-trials-v1.json").read_text())
    doc["local_worker_pair"].update({"warmup_s": 1, "measure_s": 2})
    pol = ServicePolicy.model_validate_json((ROOT / "config/policies/support-demo-pol-v1.json").read_text())
    plan = {"core": {"action": {"before": {"max_concurrency": 4}, "after": {"max_concurrency": 4}}}}
    out = T._cloud_trial(rt, {"id": "t1", "plan_id": None}, plan, doc, pol)
    disc = out["summary"]["discarded_windows"]
    # the injected lagged window is discarded (natural laptop lag may discard more); the verdict uses clean windows only
    assert out["outcome"] == "PASSED" and any(w["pair"] == 0 and w["attempt"] == 0 and w["schedule_lag_p95_ms"] == 40.0 for w in disc)
    monkeypatch.setattr(T, "run_workload", lambda w, d, label: {**real(w, d, label), "schedule_lag_p95_ms": 40.0})
    out = T._cloud_trial(rt, {"id": "t2", "plan_id": None}, plan, doc, pol)
    assert out["outcome"] == "INCOMPLETE"


def test_incomplete_cloud_trial_does_not_judge_the_candidate(env, monkeypatch):
    """25 Oct: a non-comparable (INCOMPLETE) trial rejected an eligible plan and fed 'FAILED' back to the agents.
    INCOMPLETE means the instrument failed, so the plan stays DRAFT, can be re-trialled, and feedback says INCOMPLETE."""
    from greenops.services import trials as T
    rt, client = env
    real = T.run_workload
    monkeypatch.setattr(T, "run_workload", lambda w, d, label: {**real(w, d, label), "schedule_lag_p95_ms": 40.0})
    iid = start_investigation(client)
    drain(rt)
    inv = client.get(f"/v1/investigations/{iid}", headers=auth("lead", False)).json()
    incomplete = {t["plan_id"] for t in inv["data"]["trials"] if t["status"] == "INCOMPLETE" and t["suite_id"] == "workload-wl-v1"}
    assert incomplete, inv["data"]["trials"]
    plans = [p for p in inv["data"]["plans"] if p["id"] in incomplete]
    assert all(p["status"] == "DRAFT" for p in plans), [(p["status"], p["screening"]["signature"]) for p in plans]
    sigs = {p["screening"]["signature"] for p in plans}
    assert all(f["outcome"] == "INCOMPLETE" for f in inv["data"]["feedback"] if f.get("signature") in sigs and f.get("trial_id"))
    assert inv["status"] in ("NEEDS_REVIEW", "AWAITING_APPROVAL")
    comparable = next(c for t in inv["data"]["trials"] if t["plan_id"] in incomplete
                      for c in client.get(f"/v1/trials/{t['id']}", headers=auth("lead", False)).json()["data"]["result"]["checks"]
                      if c["check_id"] == "TRIAL-COMPARABLE")
    assert comparable["status"] == "FAIL" and "identical offered load" not in comparable["detail"]  # FAIL never reads as a pass
    monkeypatch.setattr(T, "run_workload", real)
    p = plans[0]
    r = client.post(f"/v1/plans/{p['id']}/trials", headers=auth("lead"), json={
        "plan_hash": p["plan_hash"], "approved_trial_profile_id": "sandbox-trials-v1", "suite_id": "workload-wl-v1"})
    assert r.status_code == 202, r.text


def test_post_trial_critic_outage_does_not_reject_a_passed_trial(db_url, sandbox):
    """26 Oct (connected run 298a9c62): NVIDIA returned HTTP 500 for the post-trial critic and the plan whose matched
    trial PASSED was REJECTED. A provider outage is not a verdict: the plan stays DRAFT, can be re-trialled, and no
    failure memory is written."""
    from greenops.adapters.model import ModelError
    from greenops.agents.roles import SCRIPTS

    def critic(payload, tools):
        if any(c.get("stage") == "post_trial" for c in payload["candidates"]):
            raise ModelError("DEPENDENCY_UNAVAILABLE", "critic: model provider error InternalServerError")
        return SCRIPTS["critic"](payload, tools)
    rt = make_runtime(db_url, sandbox, scripts={"critic": critic})
    client = TestClient(create_app_for(rt))
    iid = start_investigation(client)
    drain(rt)
    inv = client.get(f"/v1/investigations/{iid}", headers=auth("lead", False)).json()
    passed = {t["plan_id"] for t in inv["data"]["trials"] if t["status"] == "PASSED"}
    assert passed, inv["data"]["trials"]
    plans = [p for p in inv["data"]["plans"] if p["id"] in passed]
    assert all(p["status"] == "DRAFT" for p in plans), [(p["status"], p["screening"]["signature"]) for p in plans]
    p = client.get(f"/v1/plans/{plans[0]['id']}", headers=auth("lead", False)).json()
    assert "run_trial" in p["next_allowed_actions"], p
    with connect(rt.db) as c:
        tids = [f"trial:{t['id']}" for t in inv["data"]["trials"] if t["status"] == "PASSED"]
        assert not c.execute("SELECT 1 FROM memory_outbox WHERE source_ref = ANY(%s)", (tids,)).fetchone()


def test_ai_trial_with_provider_outages_is_incomplete_not_failed(db_url, sandbox):
    """26 Oct (run a721458e): six candidate cases hit NVIDIA HTTP 500s and were scored as wrong answers, so outages
    counted against quality. Cases the provider never answered were not judged: the AI trial is INCOMPLETE."""
    from experiments.support.workflow import scripted_support
    from greenops.adapters.model import ModelError
    calls = {"n": 0}

    def flaky_support(payload, tools):
        calls["n"] += 1
        if calls["n"] % 13 == 0:
            raise ModelError("DEPENDENCY_UNAVAILABLE", "support: model provider error InternalServerError")
        return scripted_support(payload, tools)
    rt = make_runtime(db_url, sandbox, scripts={"support": flaky_support})
    client = TestClient(create_app_for(rt))
    iid = start_investigation(client)
    drain(rt)
    inv = client.get(f"/v1/investigations/{iid}", headers=auth("lead", False)).json()
    ai = [t for t in inv["data"]["trials"] if t["suite_id"] == "support-dev-v1"]
    assert ai and all(t["status"] == "INCOMPLETE" for t in ai), ai
    checks = client.get(f"/v1/trials/{ai[0]['id']}", headers=auth("lead", False)).json()["data"]["result"]["checks"]
    assert next(c for c in checks if c["check_id"] == "AI-COMPARABLE")["status"] == "FAIL"
    assert all(p["status"] == "DRAFT" for p in inv["data"]["plans"] if p["id"] in {t["plan_id"] for t in ai})
