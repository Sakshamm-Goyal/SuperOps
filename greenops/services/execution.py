"""Worker-side execution: recheck → slot + target lock → persist intent → CAS write → read-back → workload → receipt.

Unknown outcomes are reconciled from the target's actual version; a write is never blindly repeated.
executor=local_analogue: a real local configuration change, never reported as a GCP resize.
"""
from __future__ import annotations

from greenops.adapters.sandbox import ConfigStore, LocalWorker, TargetUnavailable, VersionConflict, config_hash, run_workload
from greenops.db import J, connect
from greenops.domain.approval import approval_expired
from greenops.services import memory_service
from greenops.services.approvals import versions_current
from greenops.services.common import Runtime, acquire_slot, append_event, now, release_slot

SMOKE_SECONDS = 6
AI_SMOKE_CASES = ("dev-017", "dev-033", "dev-025")  # premium exception, identity denial, missing order id


def _journal(conn, action_id, stage: str, detail: dict) -> None:
    conn.execute("INSERT INTO action_journal (action_id, seq, stage, detail) SELECT %s, COALESCE(MAX(seq),0)+1, %s, %s "
                 "FROM action_journal WHERE action_id=%s", (action_id, stage, J(detail), action_id))


def _set(rt, action_id, status: str, stage: str, detail: dict, **fields) -> None:
    sets = "".join(f", {k}=%s" for k in fields)
    with connect(rt.db) as c:
        c.execute(f"UPDATE actions SET status=%s, updated_at=now(){sets} WHERE id=%s", (status, *[J(v) if isinstance(v, (dict, list)) else v for v in fields.values()], action_id))
        _journal(c, action_id, stage, detail)


def _store(rt, plan) -> ConfigStore:
    return ConfigStore(rt.settings.sandbox_dir, plan["target_key"])


def _apply(rt, plan, expected_version: int) -> dict:
    a = plan["core"]["action"]
    if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
        new = _store(rt, plan).compare_and_set(expected_version, {"max_concurrency": a["after"]["max_concurrency"]})
        LocalWorker(rt.settings.sandbox_dir, plan["target_key"]).reload()
        return new
    return _store(rt, plan).compare_and_set(expected_version, {"config": a["after"]})


def _verify(rt, plan, policy_slo_ms: int, expected_version: int) -> dict:
    a = plan["core"]["action"]
    if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
        w = LocalWorker(rt.settings.sandbox_dir, plan["target_key"])
        st = w.status()
        smoke = run_workload(w, SMOKE_SECONDS, "verify")
        checks = {"readback_version": st["loaded_version"] == expected_version,
                  "readback_config": st["loaded_config"]["max_concurrency"] == a["after"]["max_concurrency"],
                  "served_by_loaded_config": smoke["config_hashes_seen"] == [st["loaded_config_hash"]],
                  "workload_no_failures": smoke["failures"] == 0,
                  "workload_p95_within_slo": smoke["p95_ms"] is not None and smoke["p95_ms"] <= policy_slo_ms}
        return {"checks": checks, "readback": st, "workload": smoke, "ok": all(checks.values())}
    from experiments.support.verifier import SupportDecision, verify
    from experiments.support.workflow import config_hash as ai_hash, load_suite, run_case
    from greenops.domain.models import AiWorkflowConfig
    from greenops.services.trials import DEV_SUITES
    loaded = _store(rt, plan).read()  # what a newly started workflow runner actually loads
    cfg = AiWorkflowConfig(**loaded["config"])
    cases, records = load_suite(DEV_SUITES["support-dev-v1"])
    smoke = [c for c in cases if c["case_id"] in AI_SMOKE_CASES]
    gateway = rt.model_factory()
    results = [run_case(gateway, c, records, cfg, None) for c in smoke]
    verdicts = [verify(c, records, SupportDecision(**r["output"]) if r["output"] else None) for c, r in zip(smoke, results)]
    checks = {"readback_version": loaded["version"] == expected_version,
              "runner_loaded_approved_config": ai_hash(cfg) == ai_hash(AiWorkflowConfig(**a["after"])),
              "smoke_cases_accepted": all(v["accepted"] for v in verdicts)}
    return {"checks": checks, "readback": {"version": loaded["version"], "config_hash": ai_hash(cfg)},
            "smoke": [{"case_id": v["case_id"], "accepted": v["accepted"]} for v in verdicts], "ok": all(checks.values())}


def _finish(rt, action, plan, status: str, detail: dict, inv) -> None:
    with connect(rt.db) as c:
        sync = "NOT_REQUIRED"
        if inv["memory_mode"] == "on" and status in ("VERIFIED", "RECOVERED", "RECOVERY_REQUIRED", "FAILED"):
            from greenops.services.investigation import current_versions
            v = current_versions(rt, inv, None)[plan["path"]]
            memory_service.enqueue(c, tenant_id=inv["tenant_id"], service_id=inv["service_id"], kind="verified_outcome",
                                   source_ref=f"action:{action['id']}", finding=f"Action {action['id']} on {plan['target_key']} ({plan['screening'].get('signature')}) "
                                   f"finished {status}: {detail.get('summary', '')}"[:2000], evidence_refs=plan["core"]["evidence_ids"] + [f"action:{action['id']}"],
                                   applicability=v, signature=None if status != "VERIFIED" else f"{plan['path']}:verified:{plan['screening'].get('signature')}",
                                   target_id=plan["target_key"])
            sync = "PENDING"
        c.execute("UPDATE actions SET status=%s, verification=%s, memory_sync_status=%s, verified_at=CASE WHEN %s='VERIFIED' THEN now() END, "
                  "updated_at=now() WHERE id=%s", (status, J(detail), sync, status, action["id"]))
        _journal(c, action["id"], status, {k: v for k, v in detail.items() if k != "workload"})
        release_slot(c, action["id"])
        if status == "VERIFIED":
            c.execute("UPDATE investigations SET status='COMPLETED', updated_at=now() WHERE id=%s", (inv["id"],))
        append_event(c, inv["id"], f"action.{status.lower()}", "executor", {"action_id": str(action["id"]), "summary": detail.get("summary")})


def run(rt: Runtime, action_id) -> str:
    with connect(rt.db) as c:
        action = c.execute("SELECT * FROM actions WHERE id=%s", (action_id,)).fetchone()
        plan = c.execute("SELECT * FROM plans WHERE id=%s", (action["plan_id"],)).fetchone()
        ap = c.execute("SELECT * FROM approvals WHERE id=%s", (action["approval_id"],)).fetchone()
        inv = c.execute("SELECT * FROM investigations WHERE id=%s", (plan["investigation_id"],)).fetchone()
        if action["status"] in ("VERIFIED", "FAILED", "RECOVERED", "RECOVERY_REQUIRED"):
            return action["status"]
        if not acquire_slot(c, "action", action_id):
            return "WAITING_FOR_SLOT"
    from greenops.services.investigation import context
    slo = context(rt, inv)["policy"].workload.slo_p95_ms
    a = plan["core"]["action"]
    expected = a["expected_config_version"]
    status = action["status"]

    if status == "QUEUED":
        # Fresh checks immediately before the first external write.
        if approval_expired(now(), ap["expires_at"]):
            _finish(rt, action, plan, "FAILED", {"error": "APPROVAL_EXPIRED", "writes": 0, "summary": "approval expired before the first write"}, inv)
            return "FAILED"
        if not rt.settings.sandbox_writes_enabled or rt.settings.runtime_mode.value != "connected_demo":
            _finish(rt, action, plan, "FAILED", {"error": "WRITES_DISABLED", "writes": 0, "summary": "server write flag/mode disallows execution"}, inv)
            return "FAILED"
        ok, why = versions_current(rt, plan)
        if not ok:
            with connect(rt.db) as c:
                c.execute("UPDATE plans SET status='STALE', stale_reason=%s WHERE id=%s", (why, plan["id"]))
                c.execute("UPDATE approvals SET status='STALE' WHERE id=%s", (ap["id"],))
            _finish(rt, action, plan, "FAILED", {"error": "APPROVAL_STALE", "reason": why, "writes": 0, "summary": f"stale: {why}"}, inv)
            return "FAILED"
        try:
            before = _store(rt, plan).read()
        except TargetUnavailable as e:
            _finish(rt, action, plan, "FAILED", {"error": "DEPENDENCY_UNAVAILABLE", "writes": 0, "summary": str(e)}, inv)
            return "FAILED"
        _set(rt, action_id, "EXECUTING", "INTENT", {"expected_version": expected, "before_config_hash": config_hash(before),
             "change": a["after"], "approval_id": str(ap["id"]), "plan_hash": plan["plan_hash"]})
        try:
            new = _apply(rt, plan, expected)
        except VersionConflict as e:
            _finish(rt, action, plan, "FAILED", {"error": "APPROVAL_STALE", "writes": 0, "summary": str(e)}, inv)
            return "FAILED"
        except TargetUnavailable as e:
            # The CAS file write may have happened before reload failed: reconcile, never retry blindly.
            _set(rt, action_id, "EXECUTING", "WRITE_OUTCOME_UNKNOWN", {"error": str(e)})
            return reconcile(rt, action_id)
        with connect(rt.db) as c:
            c.execute("UPDATE actions SET operation_ids=%s WHERE id=%s", (J([f"cas:{plan['target_key']}:v{new['version']}"]), action_id))
        _set(rt, action_id, "PENDING_VERIFICATION", "WRITE_APPLIED", {"new_version": new["version"], "config_hash": config_hash(new)})
        status = "PENDING_VERIFICATION"
    if status == "EXECUTING":
        return reconcile(rt, action_id)
    if status in ("PENDING_VERIFICATION",):
        return _verify_and_finish(rt, action, plan, inv, expected + 1, slo)
    if status == "RECOVERING":
        return reconcile(rt, action_id)
    return status


def _verify_and_finish(rt, action, plan, inv, new_version: int, slo: int) -> str:
    try:
        v = _verify(rt, plan, slo, new_version)
    except TargetUnavailable as e:
        v = {"checks": {"target_reachable": False}, "ok": False, "error": str(e)}
    if v["ok"]:
        _finish(rt, action, plan, "VERIFIED", {**v, "executor": "local_analogue", "summary": "configuration read back and fresh workload passed"}, inv)
        return "VERIFIED"
    failing = [k for k, ok in v["checks"].items() if not ok]
    _set(rt, action["id"], "RECOVERING", "VERIFICATION_FAILED", {"failing_checks": failing})
    return _recover(rt, action, plan, inv, new_version, {**v, "failing_checks": failing}, slo)


def _recover(rt, action, plan, inv, new_version: int, verification: dict, slo: int) -> str:
    """Restore the exact pre-change config only if the target is still at our written version (no intervening change)."""
    a = plan["core"]["action"]
    store = _store(rt, plan)
    try:
        cur = store.read()
        if cur["version"] != new_version:
            raise VersionConflict(f"target at version {cur['version']}, not our version {new_version}: intervening change")
        restore = {"max_concurrency": a["before"]["max_concurrency"]} if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE" else {"config": a["before"]}
        restored = store.compare_and_set(new_version, restore)
        if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
            st = LocalWorker(rt.settings.sandbox_dir, plan["target_key"]).reload()
            ok = st["loaded_config"]["max_concurrency"] == a["before"]["max_concurrency"]
        else:
            ok = store.read()["config"] == a["before"]
        status = "RECOVERED" if ok else "RECOVERY_REQUIRED"
        detail = {"verification": verification, "recovery": {"restored_version": restored["version"], "readback_ok": ok},
                  "summary": "verification failed; exact prior config restored" if ok else "restore did not read back"}
    except (VersionConflict, TargetUnavailable) as e:
        status = "RECOVERY_REQUIRED"
        detail = {"verification": verification, "recovery": {"attempted": False, "blocked": str(e)},
                  "summary": "verification failed; automated restore blocked — human step required"}
    with connect(rt.db) as c:
        c.execute("UPDATE actions SET recovery=%s WHERE id=%s", (J(detail["recovery"]), action["id"]))
    _finish(rt, action, plan, status, detail, inv)
    return status


def reconcile(rt: Runtime, action_id) -> str:
    """Decide from the target's actual state after an interruption; never repeat the write."""
    with connect(rt.db) as c:
        action = c.execute("SELECT * FROM actions WHERE id=%s", (action_id,)).fetchone()
        plan = c.execute("SELECT * FROM plans WHERE id=%s", (action["plan_id"],)).fetchone()
        inv = c.execute("SELECT * FROM investigations WHERE id=%s", (plan["investigation_id"],)).fetchone()
        acquire_slot(c, "action", action_id)
    from greenops.services.investigation import context
    slo = context(rt, inv)["policy"].workload.slo_p95_ms
    a = plan["core"]["action"]
    expected = a["expected_config_version"]
    try:
        cur = _store(rt, plan).read()
    except TargetUnavailable as e:
        _set(rt, action_id, action["status"], "RECONCILE_BLOCKED", {"error": str(e)})
        return action["status"]  # slot retained: unknown outcome stays unresolved until the target is readable
    if action["status"] == "RECOVERING":
        return _recover(rt, action, plan, inv, expected + 1, {"note": "resumed after interruption"}, slo)
    if cur["version"] == expected + 1:
        if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
            try:
                LocalWorker(rt.settings.sandbox_dir, plan["target_key"]).reload()
            except TargetUnavailable:
                pass
        _set(rt, action_id, "PENDING_VERIFICATION", "RECONCILED", {"observed_version": cur["version"], "write": "observed"})
        return _verify_and_finish(rt, action, plan, inv, expected + 1, slo)
    if cur["version"] == expected:
        _finish(rt, action, plan, "FAILED", {"error": "WRITE_NOT_OBSERVED", "writes": 0,
                "summary": "interrupted before the write took effect; not retried — a new approval is required"}, inv)
        return "FAILED"
    _finish(rt, action, plan, "RECOVERY_REQUIRED", {"error": "UNEXPECTED_TARGET_VERSION", "observed_version": cur["version"],
            "summary": "target version changed by another actor; automated recovery blocked"}, inv)
    return "RECOVERY_REQUIRED"
