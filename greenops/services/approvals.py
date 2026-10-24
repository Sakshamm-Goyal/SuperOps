"""API-side authority operations: approve, revoke, request execution. All run inside the caller's DB transaction."""
from __future__ import annotations

import uuid
from datetime import timedelta

import psycopg

from greenops.adapters.sandbox import WORKLOAD_PATH, ConfigStore, file_hash
from greenops.db import J
from greenops.domain.approval import approval_expired, require_approvable
from greenops.domain.quantities import DomainError
from greenops.services.common import AppError, Runtime, append_event, enqueue, now

STATUS = {"PLAN_CHANGED": 409, "APPROVAL_STALE": 409, "APPROVAL_EXPIRED": 409, "INVALID_STATE": 409, "TRIAL_NOT_ACCEPTED": 422,
          "VALIDATION_ERROR": 422}


def _scoped(conn, table: str, rid, tenant: str):
    try:
        uuid.UUID(str(rid))
    except ValueError:
        raise AppError("NOT_FOUND", 404, f"{table[:-1]} not found")
    row = conn.execute(f"SELECT * FROM {table} WHERE id=%s AND tenant_id=%s", (rid, tenant)).fetchone()
    if row is None:
        raise AppError("NOT_FOUND", 404, f"{table[:-1]} not found")
    return row


def target_version(rt: Runtime, plan: dict) -> int | None:
    a = plan["core"]["action"]
    if a["action_type"] in ("LOCAL_WORKER_CONFIG_UPDATE", "AI_CONFIG_UPDATE"):
        try:
            return ConfigStore(rt.settings.sandbox_dir, plan["target_key"]).read()["version"]
        except Exception:
            return None
    return None


def versions_current(rt: Runtime, plan: dict) -> tuple[bool, str | None]:
    """Every input the trial validated must still hold (audit A06). Guards approval and the worker's first write."""
    from greenops.services.plans import ai_artifact_versions
    v = plan["core"]["versions"]
    if v["policy_version"] != rt.settings.policy_version:
        return False, "POLICY_VERSION_CHANGED"
    if v["data_manifest_id"] != rt.settings.data_manifest_id:
        return False, "DATA_MANIFEST_CHANGED"
    if plan["path"] == "cloud" and v["workload_version"] != file_hash(WORKLOAD_PATH):
        return False, "WORKLOAD_VERSION_CHANGED"
    if plan["path"] == "ai":
        cur = ai_artifact_versions(rt.model_factory().model_id)
        for field, reason in (("model_version", "MODEL_VERSION_CHANGED"), ("workload_version", "WORKFLOW_VERSION_CHANGED"),
                              ("test_version", "TEST_VERSION_CHANGED")):
            if v.get(field) != cur[field]:
                return False, reason
    expected = plan["core"]["action"].get("expected_config_version")
    if expected is not None and target_version(rt, plan) != expected:
        return False, "TARGET_VERSION_CHANGED"
    return True, None


def expire_due(conn, plan_id) -> bool:
    """Lazy, atomic expiry (audit A12): an expired ACTIVE approval becomes EXPIRED and its plan returns to
    AWAITING_APPROVAL, so a fresh approval is the explicit next step instead of a dead end."""
    rows = conn.execute("UPDATE approvals SET status='EXPIRED' WHERE plan_id=%s AND status='ACTIVE' AND expires_at <= now() RETURNING id",
                        (plan_id,)).fetchall()
    if rows:
        conn.execute("UPDATE plans SET status='AWAITING_APPROVAL', updated_at=now() WHERE id=%s AND status='APPROVED'", (plan_id,))
        inv = conn.execute("SELECT investigation_id FROM plans WHERE id=%s", (plan_id,)).fetchone()["investigation_id"]
        append_event(conn, inv, "approval.expired", "application", {"plan_id": str(plan_id), "approval_ids": [str(r["id"]) for r in rows],
                     "next": "a new approval is required"})
    return bool(rows)


def holdout_verdict(conn, plan: dict) -> dict | None:
    """AI promotion gate (audit A15): the frozen holdout evaluation must have selected this exact candidate config + model."""
    from experiments.support.workflow import config_hash
    from greenops.domain.models import AiWorkflowConfig
    h = config_hash(AiWorkflowConfig(**plan["core"]["action"]["after"]))
    return conn.execute("SELECT * FROM evaluation_verdicts WHERE tenant_id=%s AND service_id=%s AND candidate_config_hash=%s AND model_id=%s "
                        "ORDER BY created_at DESC LIMIT 1", (plan["tenant_id"], plan["service_id"], h,
                                                             plan["core"]["versions"]["model_version"])).fetchone()


def approve(conn, rt: Runtime, actor: dict, plan_id, body) -> dict:
    plan = _scoped(conn, "plans", plan_id, actor["tenant_id"])
    conn.execute("SELECT 1 FROM plans WHERE id=%s FOR UPDATE", (plan["id"],))
    if expire_due(conn, plan["id"]):
        plan = conn.execute("SELECT * FROM plans WHERE id=%s", (plan["id"],)).fetchone()
    inv = conn.execute("SELECT * FROM investigations WHERE id=%s", (plan["investigation_id"],)).fetchone()
    trial = conn.execute("SELECT * FROM trials WHERE id=%s AND plan_id=%s AND tenant_id=%s", (body.trial_id, plan["id"], actor["tenant_id"])).fetchone()
    ok, why = versions_current(rt, plan)
    if not ok and plan["status"] == "AWAITING_APPROVAL":
        conn.execute("UPDATE plans SET status='STALE', stale_reason=%s, updated_at=now() WHERE id=%s", (why, plan["id"]))
        append_event(conn, inv["id"], "plan.stale", "application", {"plan_id": str(plan["id"]), "reason": why})
    from greenops.services.investigation import context
    ttl = context(rt, inv)["policy"].approval_ttl_minutes
    try:
        require_approvable(plan_status=plan["status"], plan_hash=plan["plan_hash"], requested_plan_hash=body.plan_hash,
                           trial_status=trial and trial["status"], trial_hash=trial and trial["trial_hash"], requested_trial_hash=body.trial_hash,
                           trial_finished_at=trial and trial["finished_at"], trial_validity_hours=24, now=now(),
                           requires_downtime=plan["core"]["requires_downtime"], acknowledge_downtime=body.acknowledge_downtime,
                           recovery_scope=plan["core"]["recovery_scope"], requested_recovery_scope=body.approved_recovery_scope,
                           versions_current=ok, runtime_mode=inv["runtime_mode"])
    except DomainError as e:
        raise AppError(e.code, STATUS.get(e.code, 409), str(e), {"reason": why})
    if plan["path"] == "ai":
        verdict = holdout_verdict(conn, plan)
        if verdict is None or verdict["decision"] != "ROLLOUT_ELIGIBLE":
            raise AppError("HOLDOUT_VERDICT_REQUIRED", 422, "AI promotion needs a frozen holdout evaluation selecting this exact candidate "
                           "config and model (make eval-freeze; make eval)", {"verdict": verdict and verdict["decision"]})
    created = now()
    aid = uuid.uuid4()
    conn.execute("INSERT INTO approvals (id, plan_id, tenant_id, service_id, actor_id, plan_hash, trial_id, trial_hash, policy_version, recovery_scope, "
                 "acknowledge_downtime, created_at, expires_at, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE')",
                 (aid, plan["id"], plan["tenant_id"], plan["service_id"], actor["actor_id"], plan["plan_hash"], trial["id"], trial["trial_hash"],
                  plan["core"]["versions"]["policy_version"], plan["core"]["recovery_scope"], body.acknowledge_downtime, created,
                  created + timedelta(minutes=ttl)))
    conn.execute("UPDATE plans SET status='APPROVED', updated_at=now() WHERE id=%s", (plan["id"],))
    append_event(conn, inv["id"], "approval.created", actor["actor_id"], {"approval_id": str(aid), "plan_id": str(plan["id"]), "plan_hash": plan["plan_hash"],
                 "expires_at": (created + timedelta(minutes=ttl)).isoformat()})
    return conn.execute("SELECT * FROM approvals WHERE id=%s", (aid,)).fetchone()


def revoke(conn, actor: dict, approval_id, reason: str) -> dict:
    ap = _scoped(conn, "approvals", approval_id, actor["tenant_id"])
    conn.execute("SELECT 1 FROM approvals WHERE id=%s FOR UPDATE", (ap["id"],))
    ap = conn.execute("SELECT * FROM approvals WHERE id=%s", (ap["id"],)).fetchone()
    if ap["status"] != "ACTIVE":
        raise AppError("INVALID_STATE", 409, f"approval is {ap['status']}; no automatic rollback is implied")
    conn.execute("UPDATE approvals SET status='REVOKED' WHERE id=%s", (ap["id"],))
    conn.execute("UPDATE plans SET status='AWAITING_APPROVAL', updated_at=now() WHERE id=%s AND status='APPROVED'", (ap["plan_id"],))
    inv_id = conn.execute("SELECT investigation_id FROM plans WHERE id=%s", (ap["plan_id"],)).fetchone()["investigation_id"]
    append_event(conn, inv_id, "approval.revoked", actor["actor_id"], {"approval_id": str(ap["id"]), "reason": reason[:300]})
    return conn.execute("SELECT * FROM approvals WHERE id=%s", (ap["id"],)).fetchone()


def request_execution(conn, rt: Runtime, actor: dict, plan_id, approval_id, plan_hash: str) -> tuple[dict, bool]:
    """Returns (action, created). Consumes the approval atomically with action creation."""
    plan = _scoped(conn, "plans", plan_id, actor["tenant_id"])
    ap = _scoped(conn, "approvals", approval_id, actor["tenant_id"])
    conn.execute("SELECT 1 FROM approvals WHERE id=%s FOR UPDATE", (ap["id"],))
    ap = conn.execute("SELECT * FROM approvals WHERE id=%s", (ap["id"],)).fetchone()
    if ap["plan_id"] != plan["id"]:
        raise AppError("NOT_FOUND", 404, "approval not found for this plan")
    if ap["actor_id"] != actor["actor_id"]:
        raise AppError("FORBIDDEN", 403, "an approval can only be executed by the actor who granted it")
    if plan_hash != plan["plan_hash"] or ap["plan_hash"] != plan["plan_hash"]:
        raise AppError("PLAN_CHANGED", 409, "plan hash does not match the approved plan")
    if ap["status"] == "CONSUMED":
        return conn.execute("SELECT * FROM actions WHERE id=%s", (ap["consumed_action_id"],)).fetchone(), False
    if ap["status"] != "ACTIVE":
        raise AppError("APPROVAL_EXPIRED" if ap["status"] == "EXPIRED" else "APPROVAL_STALE" if ap["status"] == "STALE" else "INVALID_STATE",
                       409, f"approval is {ap['status']}")
    if approval_expired(now(), ap["expires_at"]):
        expire_due(conn, plan["id"])
        raise AppError("APPROVAL_EXPIRED", 409, "approval expired; the plan is awaiting a new approval")
    inv = conn.execute("SELECT * FROM investigations WHERE id=%s", (plan["investigation_id"],)).fetchone()
    if inv["runtime_mode"] != "connected_demo" or rt.settings.runtime_mode.value != "connected_demo":
        raise AppError("INVALID_STATE", 409, "writes are disabled outside connected_demo")
    if not rt.settings.sandbox_writes_enabled:
        raise AppError("INVALID_STATE", 409, "SANDBOX_WRITES_ENABLED is false on the server")
    if plan["target_key"] not in rt.settings.allowed_target_ids:
        raise AppError("FORBIDDEN", 403, "target is not in ALLOWED_TARGET_IDS")
    if plan["core"]["executor"] != "local_analogue":
        raise AppError("UNSUPPORTED_ACTION", 422, "no executor is enabled for this action type (GCP executor not configured)")
    ok, why = versions_current(rt, plan)
    if not ok:
        conn.execute("UPDATE approvals SET status='STALE' WHERE id=%s", (ap["id"],))
        conn.execute("UPDATE plans SET status='STALE', stale_reason=%s WHERE id=%s", (why, plan["id"]))
        raise AppError("APPROVAL_STALE", 409, "the target or policy changed since approval", {"reason": why})
    aid = uuid.uuid4()
    try:
        with conn.transaction():
            conn.execute("INSERT INTO actions (id, approval_id, plan_id, tenant_id, service_id, actor_id, target_key, executor, status, before_state, after_state) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'QUEUED',%s,%s)",
                         (aid, ap["id"], plan["id"], plan["tenant_id"], plan["service_id"], actor["actor_id"], plan["target_key"], plan["core"]["executor"],
                          J(plan["core"]["action"]["before"]), J(plan["core"]["action"]["after"])))
    except psycopg.errors.UniqueViolation:
        raise AppError("TARGET_BUSY", 409, "another action is active on this target")
    conn.execute("UPDATE approvals SET status='CONSUMED', consumed_action_id=%s WHERE id=%s", (aid, ap["id"]))
    enqueue(conn, "action", aid)
    append_event(conn, inv["id"], "action.queued", actor["actor_id"], {"action_id": str(aid), "approval_id": str(ap["id"]), "plan_id": str(plan["id"])})
    return conn.execute("SELECT * FROM actions WHERE id=%s", (aid,)).fetchone(), True
