"""FastAPI boundary: sandbox bearer auth, scoped reads, idempotent mutations, generated OpenAPI.

Contract: docs/API_REFERENCE.md. Long-running work is enqueued as durable jobs; no work runs inside requests.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from greenops.config import Settings, get_settings, service_config
from greenops.db import J, connect, dumps
from greenops.domain.models import RECOVERY_SCOPE
from greenops.domain.quantities import canonical_hash
from greenops.services import approvals as A, reports
from greenops.services.common import AppError, Runtime, append_event, enqueue, now

API_VERSION = "1.0.0"
ROLE_RANK = {"viewer": 0, "automation": 1, "operator": 2, "admin": 3}  # automation: start investigations only


# ---- schemas --------------------------------------------------------------------------

class Req(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Interval(Req):
    start: AwareDatetime  # timezone-less timestamps are a 422, not a comparison error (audit A17)
    end: AwareDatetime


class CreateInvestigation(Req):
    service_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    question: str = Field(min_length=3, max_length=500)
    interval: Interval
    runtime_mode: Literal["sample", "connected_demo", "replay"]
    budget_profile_id: str = Field(max_length=64)
    approved_trial_profile_id: str | None = Field(default=None, max_length=64)
    memory_mode: Literal["on", "off"] = "on"


class CancelRequest(Req):
    reason: str = Field(min_length=1, max_length=300)


class TrialRequest(Req):
    plan_hash: str
    suite_id: str
    approved_trial_profile_id: str


class ApproveRequest(Req):
    plan_hash: str
    trial_id: uuid.UUID
    trial_hash: str
    acknowledge_downtime: bool
    approved_recovery_scope: str


class RevokeRequest(Req):
    reason: str = Field(min_length=1, max_length=300)


class ExecuteRequest(Req):
    approval_id: uuid.UUID
    plan_hash: str


class CopilotMessage(Req):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    investigation_id: uuid.UUID | None = None


class CopilotReply(BaseModel):
    conversation_id: str
    message_id: str
    reply: str
    model_id: str
    tool_calls: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    suggested_prompts: list[str]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}
    retryable: bool = False
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class Accepted(BaseModel):
    investigation_id: uuid.UUID
    job_id: uuid.UUID | None
    status: str
    status_url: str


class Resource(BaseModel):
    """Read model envelope. `data` holds the record; labels and allowed actions are computed server-side."""
    schema_version: str = "1"
    id: str
    status: str
    runtime_mode: str | None = None
    result_kind: str | None = None
    data_origin: str | None = None
    next_allowed_actions: list[str] = []
    blockers: list[str] = []
    request_id: str
    data: dict[str, Any]


class Page(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None
    request_id: str


class EventPage(BaseModel):
    items: list[dict[str, Any]]
    next_sequence: int
    request_id: str


ERRORS = {s: {"model": ErrorEnvelope} for s in (400, 401, 403, 404, 409, 422, 429, 503)}


# ---- app --------------------------------------------------------------------------------

def create_app(rt: Runtime | None = None) -> FastAPI:
    settings: Settings = rt.settings if rt else get_settings()
    rt = rt or Runtime.from_settings(settings)
    hosted = settings.app_env == "hosted"
    app = FastAPI(title="SuperOps API", version=API_VERSION, docs_url=None if hosted else "/docs",
                  openapi_url=None if hosted else "/openapi.json", redoc_url=None,
                  description="Evidence-backed cloud and AI change investigation, approval and verification (sandbox, single tenant).")
    bearer = HTTPBearer(auto_error=False, description="Sandbox bearer token mapped server-side to a named actor and role")

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID")
        try:
            rid = str(uuid.UUID(rid)) if rid else str(uuid.uuid4())
        except ValueError:
            rid = str(uuid.uuid4())
        request.state.request_id = rid
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        return resp

    def err(request: Request, code: str, status: int, message: str, details: dict | None = None, retryable: bool = False):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or {},
                                                                     "retryable": retryable, "request_id": request.state.request_id}})

    @app.exception_handler(AppError)
    async def app_error(request: Request, e: AppError):
        return err(request, e.code, e.status, e.message, e.details, e.retryable)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, e: RequestValidationError):
        return err(request, "VALIDATION_ERROR", 422, "request validation failed",
                   {"errors": [{"loc": list(x["loc"]), "msg": x["msg"]} for x in e.errors()][:20]})

    @app.exception_handler(Exception)
    async def internal(request: Request, e: Exception):
        return err(request, "INTERNAL_ERROR", 500, "internal error; see server diagnostics with this request id")

    def actor_dep(min_role: str):
        def dep(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
            if cred is None or not cred.credentials:
                raise AppError("AUTH_REQUIRED", 401, "bearer token required")
            h = hashlib.sha256(cred.credentials.encode()).hexdigest()
            with connect(rt.db) as c:
                a = c.execute("SELECT * FROM actors WHERE token_sha256=%s AND NOT disabled", (h,)).fetchone()
            if a is None:
                raise AppError("AUTH_REQUIRED", 401, "invalid token")
            if ROLE_RANK[a["role"]] < ROLE_RANK[min_role]:
                raise AppError("FORBIDDEN", 403, f"{min_role} role required")
            request.state.actor = a
            return a
        return dep

    viewer, automation, operator, admin = actor_dep("viewer"), actor_dep("automation"), actor_dep("operator"), actor_dep("admin")

    def idempotent(request: Request, actor: dict, key: str | None, route: str, body: dict, handler) -> JSONResponse:
        if key is None:
            raise AppError("MISSING_IDEMPOTENCY_KEY", 400, "Idempotency-Key header (UUID) required")
        try:
            key = str(uuid.UUID(key))
        except ValueError:
            raise AppError("INVALID_IDEMPOTENCY_KEY", 400, "Idempotency-Key must be a UUID")
        rhash = canonical_hash({"method": request.method, "route": route, "path": request.url.path, "body": body})
        with connect(rt.db) as c:
            row = c.execute("INSERT INTO idempotency (actor_id, idem_key, method, route, request_hash) VALUES (%s,%s,%s,%s,%s) "
                            "ON CONFLICT DO NOTHING RETURNING idem_key", (actor["actor_id"], key, request.method, route, rhash)).fetchone()
            if row is None:  # a concurrent duplicate blocks above until the first transaction commits
                prev = c.execute("SELECT * FROM idempotency WHERE actor_id=%s AND idem_key=%s", (actor["actor_id"], key)).fetchone()
                if prev["request_hash"] != rhash:
                    raise AppError("IDEMPOTENCY_CONFLICT", 409, "Idempotency-Key reused with a different request")
                body_out = prev["response"]
                if isinstance(body_out, dict) and "error" in body_out:
                    body_out["error"]["request_id"] = request.state.request_id
                return JSONResponse(status_code=prev["status_code"], content=body_out, headers={"Idempotent-Replay": "true"})
            try:
                status, payload = handler(c)
            except AppError as e:
                if e.status >= 500:
                    raise
                status, payload = e.status, {"error": {"code": e.code, "message": e.message, "details": e.details, "retryable": e.retryable,
                                                       "request_id": request.state.request_id}}
            payload = json.loads(dumps(payload))
            c.execute("UPDATE idempotency SET status_code=%s, response=%s WHERE actor_id=%s AND idem_key=%s",
                      (status, J(payload), actor["actor_id"], key))
        return JSONResponse(status_code=status, content=payload)

    def scoped(c, table: str, rid: str, actor: dict) -> dict:
        try:
            uuid.UUID(rid)
        except ValueError:
            raise AppError("NOT_FOUND", 404, "not found")
        row = c.execute(f"SELECT * FROM {table} WHERE id=%s AND tenant_id=%s", (rid, actor["tenant_id"])).fetchone()
        if row is None:
            raise AppError("NOT_FOUND", 404, "not found")
        return row

    def res(request, rid, status, data, **kw) -> dict:
        return json.loads(dumps(Resource(id=str(rid), status=status, request_id=request.state.request_id, data=json.loads(dumps(data)), **kw).model_dump()))

    # ---- health / ops ----------------------------------------------------------------------

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "live"}

    def readiness() -> tuple[bool, dict]:
        deps: dict = {}
        try:
            with connect(rt.db) as c:
                c.execute("SELECT 1")
            deps["database"] = "ready"
        except Exception:
            deps["database"] = "unavailable"
        if settings.runtime_mode.value == "connected_demo":
            deps["zetaris"] = "configured" if settings.zetaris_configured else "not_configured"
            deps["model"] = "configured" if settings.model_configured else "not_configured"
        try:
            h = rt.memory_factory().health()
            deps["memory"] = h.get("status", "unknown")
            deps["memory_embedding_semantic"] = (h.get("embedding_profile") or {}).get("semantic")
        except Exception as e:
            deps["memory"] = f"unavailable:{getattr(e, 'code', type(e).__name__)}"
        ok = deps["database"] == "ready" and deps.get("zetaris", "configured") == "configured" and deps.get("model", "configured") == "configured" \
            and deps["memory"] == "ready"
        return ok, deps

    @app.get("/health/ready", tags=["health"], responses=ERRORS)
    def ready(request: Request, actor: dict = Depends(operator)):
        ok, deps = readiness()
        return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "degraded",
                            "runtime_mode": settings.runtime_mode.value, "dependencies": deps})

    @app.get("/v1/operations", tags=["operations"], responses=ERRORS)
    def operations(request: Request, actor: dict = Depends(admin)):
        ok, deps = readiness()
        with connect(rt.db) as c:
            slot = c.execute("SELECT holder_kind, holder_id, acquired_at FROM execution_slot WHERE id=1").fetchone()
            outbox = c.execute("SELECT status, COUNT(*) AS n FROM memory_outbox GROUP BY status").fetchall()
            active = c.execute("SELECT id, target_key, status, updated_at FROM actions WHERE status IN "
                               "('QUEUED','EXECUTING','PENDING_VERIFICATION','RECOVERING','RECOVERY_REQUIRED')").fetchall()
            jobs = c.execute("SELECT kind, status, COUNT(*) AS n, MIN(created_at) AS oldest FROM jobs WHERE status IN ('QUEUED','RUNNING') GROUP BY kind, status").fetchall()
            budgets = c.execute("SELECT * FROM budget_profiles WHERE tenant_id=%s", (actor["tenant_id"],)).fetchall()
            profiles = c.execute("SELECT id, profile_hash, approved_by, approved_at, expires_at, status FROM trial_profiles WHERE tenant_id=%s", (actor["tenant_id"],)).fetchall()
        return res(request, "operations", "ready" if ok else "degraded", {
            "runtime_mode": settings.runtime_mode.value, "dependencies": deps, "policy_version": settings.policy_version,
            "data_manifest_id": settings.data_manifest_id, "sandbox_writes_enabled": settings.sandbox_writes_enabled,
            "allowed_target_ids": settings.allowed_target_ids, "executor": "local_analogue", "gcp_executor": "not configured",
            "execution_slot": slot, "active_actions": active, "jobs": jobs, "memory_outbox": outbox, "budget_profiles": budgets,
            "trial_profiles": profiles, "zetaris_sources": settings.source_names if settings.runtime_mode.value == "connected_demo" else None,
            "model_id": settings.model_id if settings.model_configured else None}, runtime_mode=settings.runtime_mode.value)

    if hosted:
        @app.get("/openapi.json", include_in_schema=False)
        def openapi_hosted(actor: dict = Depends(operator)):
            return app.openapi()

        @app.get("/docs", include_in_schema=False)
        def docs_hosted(actor: dict = Depends(operator)):
            return get_swagger_ui_html(openapi_url="/openapi.json", title="SuperOps API")

    @app.get("/v1/me", tags=["services"], response_model=Resource, responses=ERRORS)
    def me(request: Request, actor: dict = Depends(viewer)):
        return res(request, actor["actor_id"], "active", {"actor_id": actor["actor_id"], "display_name": actor["display_name"],
                   "role": actor["role"], "tenant_id": actor["tenant_id"], "runtime_mode": settings.runtime_mode.value,
                   "sandbox_writes_enabled": settings.sandbox_writes_enabled}, runtime_mode=settings.runtime_mode.value)

    # ---- services / investigations -------------------------------------------------------

    @app.get("/v1/services", tags=["services"], response_model=Page, responses=ERRORS)
    def services(request: Request, actor: dict = Depends(viewer), cursor: str | None = None, limit: int = Query(25, ge=1, le=100)):
        if cursor:
            raise AppError("INVALID_CURSOR", 400, "services list has a single page")
        with connect(rt.db) as c:
            rows = c.execute("SELECT service_id, display_name, runtime_modes FROM services WHERE tenant_id=%s ORDER BY service_id LIMIT %s",
                             (actor["tenant_id"], limit)).fetchall()
        return {"items": rows, "next_cursor": None, "request_id": request.state.request_id}

    @app.post("/v1/investigations", tags=["investigations"], status_code=202, response_model=Accepted, responses=ERRORS)
    def create_investigation(request: Request, body: CreateInvestigation, actor: dict = Depends(automation),
                             idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        def handler(c):
            if body.runtime_mode != settings.runtime_mode.value:
                raise AppError("VALIDATION_ERROR", 422, f"server runtime mode is {settings.runtime_mode.value}")
            if body.runtime_mode == "replay":
                raise AppError("INVALID_STATE", 409, "replay runs are read-only exports of prior runs; no new investigation")
            if body.interval.start.tzinfo is None or body.interval.end <= body.interval.start:
                raise AppError("VALIDATION_ERROR", 422, "interval must be UTC with end after start")
            if not c.execute("SELECT 1 FROM services WHERE tenant_id=%s AND service_id=%s", (actor["tenant_id"], body.service_id)).fetchone():
                raise AppError("NOT_FOUND", 404, "service not found")
            b = c.execute("SELECT * FROM budget_profiles WHERE id=%s AND tenant_id=%s", (body.budget_profile_id, actor["tenant_id"])).fetchone()
            if b is None:
                raise AppError("BUDGET_NOT_CONFIGURED", 422, "budget profile not configured")
            if body.approved_trial_profile_id:
                p = c.execute("SELECT * FROM trial_profiles WHERE id=%s AND tenant_id=%s AND status='ACTIVE' AND expires_at > now()",
                              (body.approved_trial_profile_id, actor["tenant_id"])).fetchone()
                if p is None:
                    raise AppError("VALIDATION_ERROR", 422, "trial profile missing, revoked or expired")
            iid = uuid.uuid4()
            c.execute("INSERT INTO investigations (id, tenant_id, service_id, actor_id, question, interval_start, interval_end, as_of, runtime_mode, "
                      "policy_version, data_manifest_id, budget_profile_id, budget_snapshot, trial_profile_id, memory_mode, status, stage, data_origin) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'QUEUED','SCOPE',%s)",
                      (iid, actor["tenant_id"], body.service_id, actor["actor_id"], body.question, body.interval.start, body.interval.end,
                       body.interval.end, body.runtime_mode, settings.policy_version, settings.data_manifest_id, b["id"], J(b),
                       body.approved_trial_profile_id, body.memory_mode, service_config(body.service_id)["data_origin"]))
            append_event(c, iid, "investigation.created", actor["actor_id"], {"question": body.question, "memory_mode": body.memory_mode,
                         "runtime_mode": body.runtime_mode, "policy_version": settings.policy_version})
            jid = enqueue(c, "investigation", iid)
            return 202, {"investigation_id": iid, "job_id": jid, "status": "QUEUED", "status_url": f"/v1/investigations/{iid}"}
        return idempotent(request, actor, idempotency_key, "POST /v1/investigations", body.model_dump(mode="json"), handler)

    def _cursor(created_at, iid) -> str:
        return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{iid}".encode()).decode()

    @app.get("/v1/investigations", tags=["investigations"], response_model=Page, responses=ERRORS)
    def list_investigations(request: Request, actor: dict = Depends(viewer), service_id: str | None = None, status: str | None = None,
                            cursor: str | None = None, limit: int = Query(25, ge=1, le=100)):
        where, args = ["tenant_id=%s"], [actor["tenant_id"]]
        if service_id:
            where.append("service_id=%s"); args.append(service_id)
        if status:
            where.append("status=%s"); args.append(status)
        if cursor:
            try:
                ts, cid = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
                datetime.fromisoformat(ts); uuid.UUID(cid)
            except Exception:
                raise AppError("INVALID_CURSOR", 400, "invalid cursor")
            where.append("(created_at, id) < (%s, %s)"); args += [ts, cid]
        with connect(rt.db) as c:
            rows = c.execute(f"SELECT id, service_id, question, status, stage, runtime_mode, memory_mode, policy_version, created_at, updated_at, "
                             f"summary->'outcome' AS outcome FROM investigations WHERE {' AND '.join(where)} ORDER BY created_at DESC, id DESC LIMIT %s",
                             (*args, limit + 1)).fetchall()
        nxt = _cursor(rows[limit - 1]["created_at"], rows[limit - 1]["id"]) if len(rows) > limit else None
        return {"items": json.loads(dumps(rows[:limit])), "next_cursor": nxt, "request_id": request.state.request_id}

    def plan_actions(p: dict, trial: dict | None, ap: dict | None, inv: dict, verdict: dict | None = None) -> tuple[list[str], list[str]]:
        acts, blockers = [], []
        connected = inv["runtime_mode"] == "connected_demo"
        rerun = trial and (trial["status"] == "INCOMPLETE" or ((p.get("critic") or {}).get("trial") or {}).get("critic", {}).get("verdict") in ("ERROR", "MISSING"))
        if p["status"] == "DRAFT" and p["core"]["executor"] != "none" and (not trial or rerun):
            acts.append("run_trial")  # first trial, or a re-trial after an INCOMPLETE instrument or an unavailable reviewer
        if p["core"]["executor"] == "none":
            blockers.append("no executor enabled for this action type (projection only)")
        if p["status"] == "AWAITING_APPROVAL":
            (acts if connected else blockers).append("approve" if connected else f"{inv['runtime_mode']} runs cannot be approved")
            if connected and p["path"] == "ai" and (verdict is None or verdict["decision"] != "ROLLOUT_ELIGIBLE"):
                blockers.append("AI promotion requires a ROLLOUT_ELIGIBLE frozen holdout verdict for this candidate (make eval-freeze; make eval)")
        if p["status"] == "APPROVED" and ap and ap["status"] == "ACTIVE":
            if connected and settings.sandbox_writes_enabled:
                acts.append("execute")
            else:
                blockers.append("server writes disabled")
            acts.append("revoke_approval")
        if p["status"] == "STALE":
            blockers.append(f"stale: {p['stale_reason']} — re-investigate and seek a new approval")
        return acts, blockers

    @app.get("/v1/investigations/{investigation_id}", tags=["investigations"], response_model=Resource, responses=ERRORS)
    def get_investigation(request: Request, investigation_id: str, actor: dict = Depends(viewer)):
        with connect(rt.db) as c:
            inv = scoped(c, "investigations", investigation_id, actor)
            plans = c.execute("SELECT id, path, candidate_no, revision, status, target_key, action_type, plan_hash, screening, critic, impacts, "
                              "memory_refs, stale_reason, rationale, core->'executor' AS executor, core->'projection' AS projection, updated_at "
                              "FROM plans WHERE investigation_id=%s ORDER BY path, candidate_no", (inv["id"],)).fetchall()
            trials = c.execute("SELECT t.id, t.plan_id, t.status, t.trial_hash, t.suite_id, t.finished_at FROM trials t JOIN plans p ON p.id=t.plan_id "
                               "WHERE p.investigation_id=%s ORDER BY t.created_at", (inv["id"],)).fetchall()
            actions = c.execute("SELECT a.id, a.plan_id, a.status, a.memory_sync_status FROM actions a JOIN plans p ON p.id=a.plan_id WHERE p.investigation_id=%s",
                                (inv["id"],)).fetchall()
            ev = c.execute("SELECT id, kind, subject FROM evidence WHERE investigation_id=%s ORDER BY retrieved_at", (inv["id"],)).fetchall()
            calls = c.execute("SELECT role, COUNT(*) AS n, SUM(requests) AS requests, SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
                              "FROM model_calls WHERE investigation_id=%s GROUP BY role", (inv["id"],)).fetchall()
        summ = inv["summary"]
        order = {"AWAITING_APPROVAL": 0, "APPROVED": 0, "VALIDATED": 0, "DRAFT": 1, "NEEDS_EVIDENCE": 2, "STALE": 3, "REJECTED": 4}
        queue = sorted(plans, key=lambda p: (order.get(p["status"], 5), p["path"], p["candidate_no"]))
        acts = ["cancel"] if inv["status"] in ("QUEUED", "RUNNING") else []
        data = {"investigation": {k: inv[k] for k in ("id", "service_id", "question", "status", "stage", "actor_id", "interval_start", "interval_end",
                                                       "as_of", "policy_version", "data_manifest_id", "memory_mode", "trial_profile_id", "created_at", "updated_at")},
                "progress": {"stage": inv["stage"], "rounds": summ.get("rounds", 0), "candidates_used": {p: sum(1 for x in plans if x["path"] == p) for p in ("cloud", "ai")},
                             "candidate_cap_per_path": 3, "model_calls": calls,
                             "budget": {"max_model_calls": inv["budget_snapshot"]["max_model_calls"], "max_run_cost_usd": inv["budget_snapshot"]["max_run_cost_usd"],
                                        "conservative_cost_per_call_usd": inv["budget_snapshot"]["max_conservative_cost_per_call_usd"],
                                        "model_requests_used_by_roles": sum(int(c["requests"] or 0) for c in calls)}},
                "queue_order": "ready-for-approval first, then ready-for-trial, then needs-evidence, stale, and retained rejections",
                "plans": queue, "trials": trials, "actions": actions, "evidence": ev, "federation": summ.get("federation"),
                "forecast": summ.get("forecast"), "memory": summ.get("memory"), "investigator": summ.get("investigator"),
                "outcome": summ.get("outcome"), "feedback": summ.get("feedback")}
        return res(request, inv["id"], inv["status"], data, runtime_mode=inv["runtime_mode"], data_origin=inv["data_origin"], next_allowed_actions=acts,
                   blockers=[summ["outcome"]["error"]["message"]] if (summ.get("outcome") or {}).get("error") else [])

    @app.get("/v1/investigations/{investigation_id}/events", tags=["investigations"], response_model=EventPage, responses=ERRORS)
    def events(request: Request, investigation_id: str, actor: dict = Depends(viewer), after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
        with connect(rt.db) as c:
            inv = scoped(c, "investigations", investigation_id, actor)
            rows = c.execute("SELECT seq, at, kind, actor, payload FROM investigation_events WHERE investigation_id=%s AND seq > %s ORDER BY seq LIMIT %s",
                             (inv["id"], after_sequence, limit)).fetchall()
        return {"items": json.loads(dumps(rows)), "next_sequence": rows[-1]["seq"] if rows else after_sequence, "request_id": request.state.request_id}

    @app.post("/v1/investigations/{investigation_id}/cancel", tags=["investigations"], status_code=202, responses=ERRORS)
    def cancel(request: Request, investigation_id: str, body: CancelRequest, actor: dict = Depends(operator),
               idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        def handler(c):
            inv = scoped(c, "investigations", investigation_id, actor)
            if inv["status"] not in ("QUEUED", "RUNNING", "NEEDS_REVIEW", "AWAITING_APPROVAL"):
                raise AppError("INVALID_STATE", 409, f"investigation is {inv['status']}")
            c.execute("UPDATE investigations SET cancel_requested=true, updated_at=now() WHERE id=%s", (inv["id"],))
            if inv["status"] in ("NEEDS_REVIEW", "AWAITING_APPROVAL"):
                c.execute("UPDATE investigations SET status='CANCELLED' WHERE id=%s", (inv["id"],))
            append_event(c, inv["id"], "investigation.cancel_requested", actor["actor_id"], {"reason": body.reason,
                         "note": "in-flight provider work is not undone; stops at a safe stage boundary"})
            return 202, {"investigation_id": inv["id"], "status": "CANCEL_REQUESTED"}
        return idempotent(request, actor, idempotency_key, "POST /v1/investigations/{id}/cancel", body.model_dump(mode="json"), handler)

    # ---- plans / trials -----------------------------------------------------------------------

    @app.get("/v1/plans/{plan_id}", tags=["plans"], response_model=Resource, responses=ERRORS)
    def get_plan(request: Request, plan_id: str, actor: dict = Depends(viewer)):
        with connect(rt.db) as c:
            p = scoped(c, "plans", plan_id, actor)
            if A.expire_due(c, p["id"]):
                p = c.execute("SELECT * FROM plans WHERE id=%s", (p["id"],)).fetchone()
            inv = c.execute("SELECT * FROM investigations WHERE id=%s", (p["investigation_id"],)).fetchone()
            trials = c.execute("SELECT id, status, trial_hash, suite_id, finished_at FROM trials WHERE plan_id=%s ORDER BY created_at", (p["id"],)).fetchall()
            ap = c.execute("SELECT id, status, expires_at, actor_id, consumed_action_id, plan_hash, trial_id, trial_hash, created_at FROM approvals WHERE plan_id=%s ORDER BY created_at DESC LIMIT 1", (p["id"],)).fetchone()
            verdict = A.holdout_verdict(c, p) if p["path"] == "ai" else None
            executed = c.execute("SELECT id, status, memory_sync_status, updated_at FROM actions WHERE plan_id=%s ORDER BY created_at DESC LIMIT 1",
                                 (p["id"],)).fetchone()
            from greenops.services.plans import runbook
            book = runbook(c, p)
        acts, blockers = plan_actions(p, trials[-1] if trials else None, ap, inv, verdict)
        if executed:
            blockers.append(f"already executed: action {executed['id']} is {executed['status']}; a new change needs a new investigation and approval")
        ok, why = A.versions_current(rt, p) if p["status"] in ("AWAITING_APPROVAL", "APPROVED") else (True, None)
        if not ok:
            blockers.append(f"current state differs: {why}; approval would be rejected")
        data = {**{k: p[k] for k in ("id", "investigation_id", "path", "candidate_no", "revision", "target_key", "action_type", "plan_hash",
                                      "screening", "critic", "impacts", "memory_refs", "stale_reason", "created_at", "updated_at")},
                "core": p["core"], "canonical_json": p["canonical_json"], "rationale_untrusted_model_text": p["rationale"], "trials": trials,
                "latest_approval": ap, "executed_action": executed, "runbook": book, "recovery_scope": RECOVERY_SCOPE,
                "holdout_verdict": verdict and {k: verdict[k] for k in ("decision", "run_id", "freeze_hash", "created_at")}}
        return res(request, p["id"], p["status"], data, runtime_mode=inv["runtime_mode"], data_origin=inv["data_origin"],
                   result_kind=(p["impacts"] or {}).get("result_kind"), next_allowed_actions=acts, blockers=blockers)

    @app.post("/v1/plans/{plan_id}/trials", tags=["plans"], status_code=202, responses=ERRORS)
    def create_trial(request: Request, plan_id: str, body: TrialRequest, actor: dict = Depends(operator),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        def handler(c):
            from greenops.services.trials import create_trial as ct
            p = scoped(c, "plans", plan_id, actor)
            if body.plan_hash != p["plan_hash"]:
                raise AppError("PLAN_CHANGED", 409, "plan hash does not match")
            if p["status"] != "DRAFT" or (p["screening"] or {}).get("outcome") != "ELIGIBLE_FOR_TRIAL":
                raise AppError("INVALID_STATE", 409, f"plan is {p['status']} / {(p['screening'] or {}).get('outcome')}; not ready for trial")
            if "holdout" in body.suite_id:
                raise AppError("FORBIDDEN", 403, "held-out suites are evaluator-only")
            from greenops.services.investigation import suite_for
            expected_suite = suite_for(p)
            if body.suite_id != expected_suite:
                raise AppError("VALIDATION_ERROR", 422, f"suite must be {expected_suite} for this plan")
            if c.execute("SELECT 1 FROM trials WHERE plan_id=%s AND status IN ('QUEUED','RUNNING')", (p["id"],)).fetchone():
                raise AppError("INVALID_STATE", 409, "a trial is already queued or running for this plan")
            tid = ct(c, rt, p, body.approved_trial_profile_id, actor["actor_id"], body.suite_id)
            c.execute("UPDATE investigations SET stage='TRIALS', status=CASE WHEN status IN ('NEEDS_REVIEW','NO_CHANGE') THEN 'RUNNING' ELSE status END "
                      "WHERE id=%s", (p["investigation_id"],))
            return 202, {"trial_id": tid, "status": "QUEUED", "status_url": f"/v1/trials/{tid}"}
        return idempotent(request, actor, idempotency_key, "POST /v1/plans/{id}/trials", body.model_dump(mode="json"), handler)

    @app.get("/v1/trials/{trial_id}", tags=["plans"], response_model=Resource, responses=ERRORS)
    def get_trial(request: Request, trial_id: str, actor: dict = Depends(viewer)):
        with connect(rt.db) as c:
            t = scoped(c, "trials", trial_id, actor)
        return res(request, t["id"], t["status"], t, result_kind=(t["result"] or {}).get("result_kind"),
                   data_origin=(t["result"] or {}).get("data_origin"), runtime_mode=(t["result"] or {}).get("runtime_mode"))

    # ---- approval / execution -------------------------------------------------------------------

    @app.post("/v1/plans/{plan_id}/approve", tags=["approvals"], status_code=201, responses=ERRORS)
    def approve(request: Request, plan_id: str, body: ApproveRequest, actor: dict = Depends(operator),
                idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        def handler(c):
            ap = A.approve(c, rt, actor, plan_id, body)
            p = c.execute("SELECT core FROM plans WHERE id=%s", (ap["plan_id"],)).fetchone()
            return 201, {"approval_id": ap["id"], "status": ap["status"], "expires_at": ap["expires_at"], "plan_hash": ap["plan_hash"],
                         "trial_id": ap["trial_id"], "trial_hash": ap["trial_hash"], "target": p["core"]["target_key"], "action": p["core"]["action"],
                         "requires_downtime": p["core"]["requires_downtime"], "recovery_scope": ap["recovery_scope"],
                         "note": "approval does not execute; use POST /v1/plans/{id}/execute"}
        return idempotent(request, actor, idempotency_key, "POST /v1/plans/{id}/approve", body.model_dump(mode="json"), handler)

    @app.post("/v1/approvals/{approval_id}/revoke", tags=["approvals"], responses=ERRORS)
    def revoke(request: Request, approval_id: str, body: RevokeRequest, actor: dict = Depends(operator),
               idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        def handler(c):
            ap = A.revoke(c, actor, approval_id, body.reason)
            return 200, {"approval_id": ap["id"], "status": ap["status"]}
        return idempotent(request, actor, idempotency_key, "POST /v1/approvals/{id}/revoke", body.model_dump(mode="json"), handler)

    @app.post("/v1/plans/{plan_id}/execute", tags=["approvals"], status_code=202, responses=ERRORS)
    def execute(request: Request, plan_id: str, body: ExecuteRequest, actor: dict = Depends(operator),
                idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        def handler(c):
            a, created = A.request_execution(c, rt, actor, plan_id, body.approval_id, body.plan_hash)
            return 202, {"action_id": a["id"], "status": a["status"], "replayed_existing_action": not created, "status_url": f"/v1/actions/{a['id']}"}
        return idempotent(request, actor, idempotency_key, "POST /v1/plans/{id}/execute", body.model_dump(mode="json"), handler)

    @app.get("/v1/actions/{action_id}", tags=["approvals"], response_model=Resource, responses=ERRORS)
    def get_action(request: Request, action_id: str, actor: dict = Depends(viewer)):
        with connect(rt.db) as c:
            a = scoped(c, "actions", action_id, actor)
            j = c.execute("SELECT seq, at, stage, detail FROM action_journal WHERE action_id=%s ORDER BY seq", (a["id"],)).fetchall()
            ex = c.execute("SELECT core->>'executor' AS e FROM plans WHERE id=%s", (a["plan_id"],)).fetchone()["e"]
        label = ("aws: real EC2 instance-type change in the SuperOps sandbox (stop, modify, start, verify)" if ex == "aws"
                 else "local_analogue: real local config change, not a GCP resize")
        return res(request, a["id"], a["status"], {**a, "journal": j, "executor": ex, "executor_label": label},
                   result_kind="measured" if a["status"] == "VERIFIED" else None)

    # ---- evidence / memory / reports ----------------------------------------------------------

    @app.get("/v1/evidence/{evidence_id}", tags=["evidence"], response_model=Resource, responses=ERRORS)
    def get_evidence(request: Request, evidence_id: str, actor: dict = Depends(viewer)):
        with connect(rt.db) as c:
            e = scoped(c, "evidence", evidence_id, actor)
            r = c.execute("SELECT * FROM query_receipts WHERE id=%s", (e["receipt_id"],)).fetchone()
        rows = e["data"]["rows"]
        receipt = {k: v for k, v in r["receipt"].items()}
        hourly = None
        if e["kind"] == "telemetry_series":  # peak-preserving view of the whole interval for charts (raw rows stay capped at 500)
            buckets: dict[str, dict] = {}
            for row in rows:
                h = str(row.get("observed_at", ""))[:13] + ":00:00Z"
                b = buckets.setdefault(h, {"hour": h, "cpu_percent_max": None, "memory_bytes_max": None, "samples": 0})
                b["samples"] += 1
                for k, out in (("cpu_percent", "cpu_percent_max"), ("memory_bytes", "memory_bytes_max")):
                    if row.get(k) is not None and (b[out] is None or float(row[k]) > float(b[out])):
                        b[out] = row[k]
            hourly = [buckets[k] for k in sorted(buckets)]
        return res(request, e["id"], r["completeness"], {**{k: e[k] for k in ("id", "kind", "subject", "observed_from", "observed_to", "retrieved_at",
                   "quality_flags")}, "receipt": receipt, "source_system": r["source_system"], "rows": rows[:500], "rows_truncated": len(rows) > 500,
                   "row_count": len(rows), "series_hourly_peak": hourly}, result_kind=e["result_kind"], data_origin=e["data_origin"], runtime_mode=r["runtime_mode"])

    @app.get("/v1/memories/{memory_id}", tags=["memory"], response_model=Resource, responses=ERRORS)
    def get_memory(request: Request, memory_id: str, actor: dict = Depends(viewer)):
        try:
            uuid.UUID(memory_id)
        except ValueError:
            raise AppError("NOT_FOUND", 404, "not found")
        with connect(rt.db) as c:
            m = c.execute("SELECT * FROM memory_outbox WHERE application_receipt_id=%s AND tenant_id=%s", (memory_id, actor["tenant_id"])).fetchone()
        if m is None:
            raise AppError("NOT_FOUND", 404, "not found")
        audit, audit_error = None, None
        if m["status"] == "SENT":
            try:
                audit = rt.memory_factory().audit(memory_id, m["tenant_id"], m["service_id"])
            except Exception as e:
                audit_error = getattr(e, "code", type(e).__name__)
        from greenops.services.memory_service import applicable
        cur = {"policy_version": settings.policy_version}
        reasons = applicable({"policy_version": m["envelope"]["applicability"].get("policy_version")}, cur)
        return res(request, memory_id, m["status"], {"envelope": m["envelope"], "kind": m["receipt_kind"], "source_ref": m["source_ref"],
                   "engine_memory_id": m["engine_memory_id"], "sync_status": m["status"], "audit": audit, "audit_error": audit_error,
                   "current_policy_applicability": reasons or ["APPLICABLE_TO_CURRENT_POLICY"],
                   "note": "memory informs investigations; it never authorizes an action"})

    # ---- overview / copilot ---------------------------------------------------------------------

    @app.get("/v1/overview", tags=["services"], responses=ERRORS)
    def overview(request: Request, actor: dict = Depends(viewer)):
        from greenops.services import overview as O
        return {**json.loads(dumps(O.build(rt, actor["tenant_id"]))), "request_id": request.state.request_id}

    def caller_get(request: Request):
        """In-process GET with the caller's own token: the copilot sees exactly what the caller may see."""
        from fastapi.testclient import TestClient
        tc = TestClient(app, raise_server_exceptions=False)
        auth = request.headers.get("authorization", "")

        def get(path: str):
            r = tc.get(path, headers={"Authorization": auth})
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, {"error": {"code": "NON_JSON"}}
        return get

    @app.post("/v1/copilot/messages", tags=["copilot"], response_model=CopilotReply, responses=ERRORS)
    def copilot_message(request: Request, body: CopilotMessage, actor: dict = Depends(viewer),
                        idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        from greenops import copilot
        get = caller_get(request)

        def handler(c):
            out = copilot.converse(rt, actor, body.message, body.conversation_id and str(body.conversation_id),
                                   body.investigation_id and str(body.investigation_id), get)
            return 200, out
        return idempotent(request, actor, idempotency_key, "POST /v1/copilot/messages", body.model_dump(mode="json"), handler)

    @app.get("/v1/copilot/conversations/{conversation_id}", tags=["copilot"], responses=ERRORS)
    def copilot_conversation(request: Request, conversation_id: str, actor: dict = Depends(viewer)):
        from greenops import copilot
        return {**copilot.conversation(rt, actor, conversation_id), "request_id": request.state.request_id}

    @app.get("/v1/reports/{investigation_id}", tags=["reports"], responses={**ERRORS, 200: {"content": {"application/json": {}, "text/html": {}}}})
    def report(request: Request, investigation_id: str, actor: dict = Depends(viewer), format: Literal["json", "html"] = "json"):
        try:
            uuid.UUID(investigation_id)
        except ValueError:
            raise AppError("NOT_FOUND", 404, "not found")
        r = reports.build(rt.db, actor["tenant_id"], investigation_id)
        if format == "html":
            return HTMLResponse(reports.to_html(r))
        return JSONResponse(json.loads(dumps(r)))

    return app


app = None


def get_app() -> FastAPI:  # uvicorn factory entry point
    return create_app()
