"""Worker-side execution: recheck → slot + target lock → persist intent → CAS write → read-back → workload → receipt.

Unknown outcomes are reconciled from the target's actual state; a write is never blindly repeated. A target version
counts as ours only when its recorded writer is this action's operation identity AND its content is the approved
change (audit A01); anything else is a foreign change that automation never claims or overwrites.
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
RECONCILE_PENDING = "RECONCILE_PENDING"
REAPPROVE_ERRORS = {"APPROVAL_EXPIRED", "AUTHORITY_REVOKED", "WRITES_DISABLED", "WRITE_NOT_OBSERVED", "DEPENDENCY_UNAVAILABLE"}


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


def op_id(action_id) -> str:
    return f"action:{action_id}"


def _change(plan) -> dict:
    a = plan["core"]["action"]
    return {"max_concurrency": a["after"]["max_concurrency"]} if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE" else {"config": a["after"]}


def _restore(plan) -> dict:
    a = plan["core"]["action"]
    return {"max_concurrency": a["before"]["max_concurrency"]} if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE" else {"config": a["before"]}


def _is_ours(cur: dict, plan, action_id, version: int) -> bool:
    return cur["version"] == version and cur.get("writer") == op_id(action_id) and all(cur.get(k) == v for k, v in _change(plan).items())


def _apply(rt, plan, expected_version: int, action_id) -> dict:
    new = _store(rt, plan).compare_and_set(expected_version, _change(plan), writer=op_id(action_id))
    if plan["core"]["action"]["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
        LocalWorker(rt.settings.sandbox_dir, plan["target_key"]).reload()
    return new


def _verify(rt, plan, policy_slo_ms: int, expected_version: int) -> dict:
    a = plan["core"]["action"]
    if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
        w = LocalWorker(rt.settings.sandbox_dir, plan["target_key"])
        st = w.status()
        smoke = run_workload(w, SMOKE_SECONDS, "verify")
        smoke.pop("latencies_ms", None)
        smoke.pop("server_latencies_ms", None)
        checks = {"readback_version": st["loaded_version"] == expected_version,
                  "readback_config": st["loaded_config"]["max_concurrency"] == a["after"]["max_concurrency"],
                  "served_by_loaded_config": smoke["config_hashes_seen"] == [st["loaded_config_hash"]],
                  "workload_no_failures": smoke["failures"] == 0,
                  "workload_p95_within_slo": smoke["p95_ms"] is not None and smoke["p95_ms"] <= policy_slo_ms}
        return {"checks": checks, "readback": st, "workload": smoke, "ok": all(checks.values())}
    from experiments.support.verifier import SupportDecision, verify
    from experiments.support.workflow import config_hash as ai_hash, load_suite, run_case
    from greenops.domain.models import AiWorkflowConfig
    from greenops.services.budget import DurableBudget, investigation_limits
    from greenops.services.trials import DEV_SUITES
    loaded = _store(rt, plan).read()  # what a newly started workflow runner actually loads
    cfg = AiWorkflowConfig(**loaded["config"])
    cases, records = load_suite(DEV_SUITES["support-dev-v1"])
    smoke = [c for c in cases if c["case_id"] in AI_SMOKE_CASES]
    gateway = rt.model_factory()
    with connect(rt.db) as c:
        inv = c.execute("SELECT * FROM investigations WHERE id=%s", (plan["investigation_id"],)).fetchone()
    budget = DurableBudget(rt.db, investigation_id=inv["id"], limits=investigation_limits(inv), daily_cap_usd=rt.settings.max_daily_cost_usd)
    results = [run_case(gateway, c, records, cfg, budget) for c in smoke]
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
            v = current_versions(rt, inv)[plan["path"]]
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
        if status == "FAILED" and detail.get("writes") == 0 and detail.get("error") in REAPPROVE_ERRORS:
            # Zero-write failure: the plan is not a dead end; it needs a fresh approval (audit A12).
            c.execute("UPDATE plans SET status='AWAITING_APPROVAL', updated_at=now() WHERE id=%s AND status='APPROVED'", (plan["id"],))
        append_event(c, inv["id"], f"action.{status.lower()}", "executor", {"action_id": str(action["id"]), "summary": detail.get("summary")})


def _authority(rt, action, plan, ap) -> str | None:
    """Current authority immediately before the first write (audit A02): approval enqueue time is not enough."""
    with connect(rt.db) as c:
        actor = c.execute("SELECT * FROM actors WHERE actor_id=%s", (action["actor_id"],)).fetchone()
        ap_now = c.execute("SELECT status, consumed_action_id FROM approvals WHERE id=%s", (ap["id"],)).fetchone()
    if actor is None or actor["disabled"]:
        return "approving actor is disabled"
    if actor["role"] not in ("operator", "admin") or actor["tenant_id"] != action["tenant_id"]:
        return f"approving actor no longer holds an operator role in tenant {action['tenant_id']}"
    if ap_now["status"] != "CONSUMED" or str(ap_now["consumed_action_id"]) != str(action["id"]):
        return f"approval is {ap_now['status']}, not consumed by this action"
    if plan["target_key"] not in rt.settings.allowed_target_ids:
        return "target removed from ALLOWED_TARGET_IDS"
    return None


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
        if why := _authority(rt, action, plan, ap):
            _finish(rt, action, plan, "FAILED", {"error": "AUTHORITY_REVOKED", "writes": 0, "summary": why}, inv)
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
             "change": a["after"], "operation_id": op_id(action_id), "approval_id": str(ap["id"]), "plan_hash": plan["plan_hash"]})
        try:
            new = _apply(rt, plan, expected, action_id)
        except VersionConflict as e:
            _finish(rt, action, plan, "FAILED", {"error": "APPROVAL_STALE", "writes": 0, "summary": str(e)}, inv)
            return "FAILED"
        except TargetUnavailable as e:
            # The CAS file write may have happened before reload failed: reconcile, never retry blindly.
            _set(rt, action_id, "EXECUTING", "WRITE_OUTCOME_UNKNOWN", {"error": str(e)})
            return reconcile(rt, action_id)
        with connect(rt.db) as c:
            c.execute("UPDATE actions SET operation_ids=%s WHERE id=%s", (J([f"cas:{plan['target_key']}:v{new['version']}:{op_id(action_id)}"]), action_id))
        _set(rt, action_id, "PENDING_VERIFICATION", "WRITE_APPLIED", {"new_version": new["version"], "config_hash": config_hash(new),
             "operation_id": op_id(action_id)})
        status = "PENDING_VERIFICATION"
    if status in ("EXECUTING", "RECOVERING"):
        return reconcile(rt, action_id)
    if status == "PENDING_VERIFICATION":
        return _verify_and_finish(rt, action, plan, inv, expected + 1, slo)
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
    """Restore the exact pre-change config only if the target still holds OUR write (version + operation identity +
    content). Any other state is an intervening change: zero compensating writes, human step required."""
    store = _store(rt, plan)
    try:
        cur = store.read()
        if not _is_ours(cur, plan, action["id"], new_version):
            raise VersionConflict(f"target at version {cur['version']} written by {cur.get('writer')!r}, not this action's "
                                  f"write v{new_version}: intervening change")
        restored = store.compare_and_set(new_version, _restore(plan), writer=f"recovery:{action['id']}")
        if plan["core"]["action"]["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
            st = LocalWorker(rt.settings.sandbox_dir, plan["target_key"]).reload()
            ok = st["loaded_config"]["max_concurrency"] == plan["core"]["action"]["before"]["max_concurrency"]
        else:
            ok = store.read()["config"] == plan["core"]["action"]["before"]
        status = "RECOVERED" if ok else "RECOVERY_REQUIRED"
        detail = {"verification": verification, "recovery": {"restored_version": restored["version"], "readback_ok": ok},
                  "summary": "verification failed; exact prior config restored" if ok else "restore did not read back"}
    except (VersionConflict, TargetUnavailable) as e:
        status = "RECOVERY_REQUIRED"
        detail = {"verification": verification, "recovery": {"attempted": False, "blocked": str(e)}, "writes_during_recovery": 0,
                  "summary": "verification failed; automated restore blocked — human step required"}
    with connect(rt.db) as c:
        c.execute("UPDATE actions SET recovery=%s WHERE id=%s", (J(detail["recovery"]), action["id"]))
    _finish(rt, action, plan, status, detail, inv)
    return status


def reconcile(rt: Runtime, action_id) -> str:
    """Decide from the target's actual state after an interruption; never repeat the write.

    Returns RECONCILE_PENDING (slot retained, job rescheduled by the worker) while the target cannot be read (audit A03).
    """
    with connect(rt.db) as c:
        action = c.execute("SELECT * FROM actions WHERE id=%s", (action_id,)).fetchone()
        plan = c.execute("SELECT * FROM plans WHERE id=%s", (action["plan_id"],)).fetchone()
        inv = c.execute("SELECT * FROM investigations WHERE id=%s", (plan["investigation_id"],)).fetchone()
        acquire_slot(c, "action", action_id)
    from greenops.services.investigation import context
    slo = context(rt, inv)["policy"].workload.slo_p95_ms
    expected = plan["core"]["action"]["expected_config_version"]
    try:
        cur = _store(rt, plan).read()
    except TargetUnavailable as e:
        _set(rt, action_id, action["status"], "RECONCILE_BLOCKED", {"error": str(e), "next": "rescheduled; slot retained until resolved"})
        return RECONCILE_PENDING
    if action["status"] == "RECOVERING":
        return _recover(rt, action, plan, inv, expected + 1, {"note": "resumed after interruption"}, slo)
    if _is_ours(cur, plan, action_id, expected + 1):
        if plan["core"]["action"]["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
            try:
                LocalWorker(rt.settings.sandbox_dir, plan["target_key"]).reload()
            except TargetUnavailable:
                pass
        _set(rt, action_id, "PENDING_VERIFICATION", "RECONCILED", {"observed_version": cur["version"], "write": "observed (operation identity matches)"})
        return _verify_and_finish(rt, action, plan, inv, expected + 1, slo)
    if cur["version"] == expected:
        _finish(rt, action, plan, "FAILED", {"error": "WRITE_NOT_OBSERVED", "writes": 0,
                "summary": "interrupted before the write took effect; not retried — a new approval is required"}, inv)
        return "FAILED"
    _finish(rt, action, plan, "RECOVERY_REQUIRED", {"error": "FOREIGN_CHANGE", "observed_version": cur["version"], "observed_writer": cur.get("writer"),
            "writes_during_recovery": 0, "summary": "target changed by another actor; this action never claims or overwrites it — human step required"}, inv)
    return "RECOVERY_REQUIRED"


def resolve_manually(rt: Runtime, action_id, actor_id: str, note: str) -> dict:
    """Operator procedure for RECOVERY_REQUIRED: after a human has inspected and settled the target, record that
    decision with the actual target read-back and release the target. Automation never takes this step itself."""
    if not note.strip():
        raise ValueError("a resolution note describing the human decision is required")
    with connect(rt.db) as c:
        actor = c.execute("SELECT * FROM actors WHERE actor_id=%s AND NOT disabled", (actor_id,)).fetchone()
        if actor is None or actor["role"] not in ("operator", "admin"):
            raise PermissionError("an enabled operator or admin must resolve an action")
        action = c.execute("SELECT * FROM actions WHERE id=%s FOR UPDATE", (action_id,)).fetchone()
        if action is None or action["status"] != "RECOVERY_REQUIRED":
            raise ValueError(f"action is {action and action['status']}, not RECOVERY_REQUIRED")
        plan = c.execute("SELECT * FROM plans WHERE id=%s", (action["plan_id"],)).fetchone()
        try:
            readback = _store(rt, plan).read()
        except TargetUnavailable as e:
            readback = {"unavailable": str(e)}
        detail = {"actor": actor_id, "note": note[:1000], "target_readback": readback}
        c.execute("UPDATE actions SET status='RESOLVED_MANUALLY', updated_at=now(), recovery = COALESCE(recovery, '{}'::jsonb) || %s WHERE id=%s",
                  (J({"manual_resolution": detail}), action_id))
        _journal(c, action_id, "RESOLVED_MANUALLY", detail)
        release_slot(c, action_id)
        append_event(c, plan["investigation_id"], "action.resolved_manually", actor_id, {"action_id": str(action_id), "note": note[:300]})
    return detail
