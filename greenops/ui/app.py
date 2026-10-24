"""GreenOps Verify investigation workbench (Streamlit).

Contract: docs/UX_SPEC.md for visible behavior, docs/API_REFERENCE.md for routes. The workbench talks to the
API only over HTTP (greenops.ui.client); it never imports services, the database, adapters or executor code.

State rules:
- The sandbox bearer token lives only in st.session_state; never in URLs, query parameters or logs.
- Session state otherwise holds widget selections, per-intent Idempotency-Key UUIDs and one-shot notices.
  Every record shown is re-read from the API on each rerun; a browser refresh restores from the backend.
- Hiding controls is a usability aid. The API enforces roles, approvals and state transitions.

Run: PYTHONPATH=. uv run streamlit run greenops/ui/app.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import streamlit as st

from greenops.ui import present as P
from greenops.ui.client import ApiClient, ApiResponse

log = logging.getLogger("greenops.ui")

BUDGET_PROFILE = "sandbox-approved-budget-v1"
TRIAL_PROFILE = "sandbox-trials-v1"
DEFAULT_QUESTION = "Find a testable saving while preserving service and support policy"
DEFAULT_START, DEFAULT_END = date(2026, 9, 30), date(2026, 10, 21)
ROLES_THAT_WRITE = ("operator", "admin")


# ---- context ----------------------------------------------------------------------------------

@dataclass
class Ctx:
    api: ApiClient
    role: str
    ready: ApiResponse | None
    services: list[dict]
    service: str | None

    @property
    def can_write(self) -> bool:
        return self.role in ROLES_THAT_WRITE

    @property
    def ready_body(self) -> dict | None:
        if self.ready is not None and isinstance(self.ready.body, dict) and "runtime_mode" in self.ready.body:
            return self.ready.body
        return None

    @property
    def runtime_mode(self) -> str | None:
        return (self.ready_body or {}).get("runtime_mode")


# ---- session helpers ----------------------------------------------------------------------------

def idem_key(intent: str) -> str:
    """One Idempotency-Key per user intent, reused across reruns and repeated clicks."""
    keys = st.session_state.setdefault("idem_keys", {})
    if intent not in keys:
        keys[intent] = str(uuid.uuid4())
    return keys[intent]


def mutate(ctx: Ctx, intent: str, path: str, body: dict) -> ApiResponse:
    r = ctx.api.post(path, body, idem_key(intent))
    if not r.ok and not r.outcome_unknown:
        # Definitive rejection: nothing was applied, so a later attempt is a new intent with a new key.
        # Unknown outcomes keep the key so a retry replays the original request instead of repeating it.
        st.session_state.get("idem_keys", {}).pop(intent, None)
    return r


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def flash(kind: str, text: str) -> None:
    st.session_state.setdefault("flash", []).append((kind, text))


def show_flashes() -> None:
    for kind, text in st.session_state.pop("flash", []):
        {"success": st.success, "info": st.info, "warning": st.warning}.get(kind, st.info)(
            text, icon={"success": ":material/check_circle:", "warning": ":material/warning:"}.get(kind, ":material/info:"))


def picker(label: str, options: list, sel_key: str, widget_key: str, fmt: Callable[[Any], str]) -> Any:
    """Selectbox whose choice survives page switches (kept under sel_key, not only the widget key)."""
    if not options:
        return None
    sel = st.session_state.get(sel_key)
    if st.session_state.get(widget_key) not in options:
        st.session_state[widget_key] = sel if sel in options else options[0]
    choice = st.selectbox(label, options, key=widget_key, format_func=fmt)
    st.session_state[sel_key] = choice
    return choice


# ---- rendering helpers ----------------------------------------------------------------------------

def show_error(r: ApiResponse, *, mutation: bool = False) -> None:
    e = r.error
    lines = [f"**{e['code']}** — {e['message']}"]
    if e["code"] == "APPROVAL_STALE":
        lines.insert(0, "Approval stale — target changed since approval. Gather fresh evidence and seek a new approval.")
    det = e.get("details") or {}
    if det.get("reason"):
        lines.append(f"Reason: {det['reason']}")
    for x in (det.get("errors") or [])[:5]:
        lines.append(f"Field `{'.'.join(str(p) for p in x.get('loc', []))}`: {x.get('msg')}")
    if e.get("request_id"):
        lines.append(f"Request ID: `{e['request_id']}`")
    if mutation and r.outcome_unknown:
        lines.append("The outcome is unknown. Retrying from this screen reuses the same request key, so the API "
                     "returns the original result instead of repeating the change.")
    st.error("  \n".join(lines), icon=":material/error:")


def badge(text: str, status: Any) -> None:
    st.badge(text, icon=P.icon(status), color=P.badge_color(status))


def table(rows: list[dict], **kw) -> None:
    if rows:
        st.dataframe([{k: P.cell(v, 240) for k, v in r.items()} for r in rows], hide_index=True, width="stretch", **kw)


def kv_table(pairs: list[tuple[str, Any]]) -> None:
    table([{"Field": k, "Value": v} for k, v in pairs])


def guarded(fn: Callable[[Ctx], None], ctx: Ctx) -> None:
    """Never show tracebacks; log server-side (no token in the log) and keep the page usable."""
    try:
        fn(ctx)
    except Exception:
        log.exception("workbench view failed: %s", getattr(fn, "__name__", fn))
        st.error("This view could not be rendered. No action was taken. Refresh to retry; if it persists, "
                 "check the workbench server log.", icon=":material/error:")


# ---- login, context, banner --------------------------------------------------------------------------

def login_page() -> None:
    st.title("GreenOps Verify")
    st.write("Sign in with a sandbox bearer token. The token is held only in this session's server memory, "
             "never in the page address, and is sent to the API in the Authorization header.")
    for kind, text in st.session_state.pop("flash", []):
        st.warning(text, icon=":material/warning:")
    with st.form("login", clear_on_submit=True):
        tok = st.text_input("Sandbox bearer token", type="password", key="login_token")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        tok = (tok or "").strip()
        if not tok:
            st.error("Enter a sandbox bearer token to sign in.", icon=":material/error:")
            return
        r = ApiClient(tok).get("/v1/services")
        if r.ok:
            st.session_state["token"] = tok
            st.rerun()
        elif r.status == 401:
            st.error("Token not accepted (AUTH_REQUIRED). Check the token and try again.", icon=":material/error:")
        else:
            show_error(r)


def build_ctx(token: str) -> Ctx | None:
    api = ApiClient(token)
    svc = api.get("/v1/services")
    if svc.status == 401:
        st.session_state.pop("token", None)
        flash("warning", "The session token is no longer accepted. Sign in again.")
        st.rerun()
    services = (svc.body or {}).get("items", []) if svc.ok else []
    me = api.get("/v1/me")
    who = ((me.body or {}).get("data") or {}) if me.ok else {}
    role = who.get("role", "unknown")
    st.session_state["actor_name"] = who.get("display_name") or who.get("actor_id")
    st.session_state["server_runtime_mode"] = who.get("runtime_mode")
    ready = api.get("/health/ready")
    service = st.session_state.get("service")
    ids = [s["service_id"] for s in services]
    if service not in ids:
        service = ids[0] if ids else None
    ctx = Ctx(api=api, role=role, ready=ready if ready.status != 403 else None, services=services, service=service)
    if not svc.ok:
        show_error(svc)
    return ctx


def sidebar(ctx: Ctx) -> None:
    with st.sidebar:
        ids = [s["service_id"] for s in ctx.services]
        names = {s["service_id"]: s.get("display_name") or s["service_id"] for s in ctx.services}
        if ids:
            ctx.service = st.selectbox("Current service", ids, index=ids.index(ctx.service) if ctx.service in ids else 0,
                                       format_func=lambda s: f"{names[s]} ({s})", key="service")
        else:
            st.warning("No services visible to this token.")
        st.caption("Environment: sandbox (single tenant)")
        st.caption(f"Signed in: **{st.session_state.get('actor_name') or '—'}** ({ctx.role})")
        st.caption(f"API: {ctx.api.base_url}")
        if st.button("Sign out", icon=":material/logout:", key="signout"):
            st.session_state.clear()
            st.rerun()


def selected_origin(ctx: Ctx) -> str | None:
    inv = st.session_state.get("sel_inv")
    if not inv:
        lst = ctx.api.get("/v1/investigations", {"service_id": ctx.service, "limit": 50} if ctx.service else {"limit": 50})
        items = (lst.body or {}).get("items", []) if lst.ok else []
        inv = items[0]["id"] if items else None
    if not inv:
        return None
    r = ctx.api.get(f"/v1/investigations/{inv}")
    return (r.body or {}).get("data_origin") if r.ok else None


def banner(ctx: Ctx) -> None:
    with st.container(border=True):
        row = st.container(horizontal=True, gap="small")
        with row:
            rb = ctx.ready_body
            mode = ctx.runtime_mode
            if rb is None:
                st.badge("Mode: unknown (readiness needs operator role)" if ctx.role == "viewer" else "Mode: unknown",
                         icon=":material/help:", color="gray")
            else:
                st.badge(f"Mode: {P.mode_label(mode)}", icon=":material/science:" if mode == "sample" else
                         ":material/history:" if mode == "replay" else ":material/hub:", color="blue")
                if rb.get("status") != "ready":
                    st.badge("Degraded read-only", icon=":material/warning:", color="orange")
            origin = selected_origin(ctx)
            st.badge(f"Data origin: {origin or 'not yet loaded'}", icon=":material/dataset:",
                     color="orange" if origin == "synthetic" else "gray")
            st.badge(f"Actor: {st.session_state.get('actor_name') or '—'} ({ctx.role})", icon=":material/badge:", color="gray")
            st.badge(f"Executor: {P.EXECUTOR_LABEL}", icon=":material/memory:", color="gray")
        if ctx.ready_body is not None:
            deps = ctx.ready_body.get("dependencies") or {}
            parts = [f"{k}: {P.dep_glyph(v)}" for k, v in deps.items() if k != "memory_embedding_semantic"]
            sem = deps.get("memory_embedding_semantic")
            emb = "" if sem is None else (" · memory embedder: semantic" if sem else
                                          " · memory embedder: reference hash (not semantic recall evidence)")
            overall = ctx.ready_body.get("status")
            st.markdown(f"**Source/memory health:** {P.glyph(overall)} · " + " · ".join(parts) + emb)
        elif ctx.role == "viewer":
            st.markdown("**Source/memory health:** ? not visible to the viewer role (readiness requires operator)")
        else:
            st.markdown("**Source/memory health:** ? UNKNOWN — readiness check did not respond")
            if ctx.ready is not None and not ctx.ready.ok:
                show_error(ctx.ready)
        st.caption(f"Service: {ctx.service or '—'} · Environment: sandbox (single tenant) · "
                   f"Server mode: {st.session_state.get('server_runtime_mode') or '—'} · Refreshed {P.now_utc()}")
    show_flashes()


# ---- shared investigation selection -----------------------------------------------------------------

def list_investigations(ctx: Ctx) -> tuple[list[dict], ApiResponse]:
    params = {"limit": 50, **({"service_id": ctx.service} if ctx.service else {})}
    r = ctx.api.get("/v1/investigations", params)
    return ((r.body or {}).get("items", []) if r.ok else []), r


def investigation_picker(ctx: Ctx, items: list[dict], page: str) -> str | None:
    ids = [i["id"] for i in items]
    qp = st.query_params.get("inv")
    if qp and "sel_inv" not in st.session_state:
        st.session_state["sel_inv"] = qp  # reopen the record named in the address after a browser refresh
    sel = st.session_state.get("sel_inv")
    if sel and sel not in ids:
        r = ctx.api.get(f"/v1/investigations/{sel}")  # reopen an older record by its stable ID
        if r.ok:
            inv = r.body["data"]["investigation"]
            items = [{**inv, "outcome": r.body["data"].get("outcome")}] + items
            ids = [sel] + ids
    by = {i["id"]: i for i in items}
    choice = picker("Investigation", ids, "sel_inv", f"inv_pick_{page}",
                    lambda i: f"{P.fmt_ts(by[i].get('created_at'))} · {by[i].get('status')} · {i}")
    if choice:
        st.query_params["inv"] = choice  # a stable record ID only; never the token
    return choice


# ---- Investigations page ---------------------------------------------------------------------------------

def start_form(ctx: Ctx, has_items: bool) -> None:
    mode = ctx.runtime_mode
    with st.expander("Start investigation", expanded=not has_items, icon=":material/play_arrow:"):
        if mode is None:
            st.warning("The server runtime mode is unavailable from /health/ready, so a run cannot be started.")
        elif mode == "replay":
            st.info("Recorded replay is read-only: it exports prior runs and cannot start a new investigation.")
        ids = [s["service_id"] for s in ctx.services] or ["support-demo"]
        with st.form("start_investigation"):
            service = st.selectbox("Service", ids, index=ids.index(ctx.service) if ctx.service in ids else 0)
            question = st.text_area("Question", DEFAULT_QUESTION, max_chars=500)
            c1, c2 = st.columns(2)
            start = c1.date_input("Interval start (00:00 UTC)", DEFAULT_START)
            end = c2.date_input("Interval end (00:00 UTC)", DEFAULT_END)
            budget = st.selectbox("Budget profile", [BUDGET_PROFILE])
            use_trial = st.checkbox(f"Use approved trial profile {TRIAL_PROFILE} (runs real local sandbox trials)", value=True)
            memory_on = st.toggle("Memory of prior experiments", value=True)
            st.caption(f"Runtime mode: **{P.mode_label(mode)}** — set by the server, not chosen here.")
            submitted = st.form_submit_button("Start investigation", type="primary", disabled=mode in (None, "replay"))
        if submitted:
            q = (question or "").strip()
            if len(q) < 3:
                st.error("Question: enter at least 3 characters.", icon=":material/error:")
                return
            if not (isinstance(start, date) and isinstance(end, date)) or end <= start:
                st.error("Interval: the end date must be after the start date.", icon=":material/error:")
                return
            body = {"service_id": service, "question": q,
                    "interval": {"start": f"{start.isoformat()}T00:00:00Z", "end": f"{end.isoformat()}T00:00:00Z"},
                    "runtime_mode": mode, "budget_profile_id": budget,
                    "approved_trial_profile_id": TRIAL_PROFILE if use_trial else None,
                    "memory_mode": "on" if memory_on else "off"}
            nonce = st.session_state.get("create_nonce", 0)
            r = mutate(ctx, f"create:{nonce}:{digest(body)}", "/v1/investigations", body)
            if r.ok:
                iid = str(r.body["investigation_id"])
                st.session_state["sel_inv"] = iid
                st.session_state.pop("inv_pick_inv", None)
                st.query_params["inv"] = iid
                flash("success", (f"Investigation {iid} accepted (status {r.body.get('status')}). It runs in the background; "
                                  "press Refresh to follow its stage.") +
                      (" This repeated submission returned the existing investigation (same request key)." if r.replayed else ""))
                st.rerun()
            else:
                show_error(r, mutation=True)
        st.caption("Submitting identical inputs again reopens the same investigation (one request key per intent).")
        if st.button("Allow a separate run with identical inputs", key="new_create_nonce", icon=":material/add:"):
            st.session_state["create_nonce"] = st.session_state.get("create_nonce", 0) + 1
            st.toast("The next submission will start a separate investigation.")


def page_investigations(ctx: Ctx) -> None:
    st.title("Investigations")
    items, lst = list_investigations(ctx)
    if ctx.can_write:
        start_form(ctx, bool(items))
    else:
        st.info("Read-only view (viewer role). Starting investigations, trials, approvals and execution require the "
                "operator role; the API enforces this independently of what is shown here.", icon=":material/visibility:")
    st.subheader("Investigation list")
    if not lst.ok:
        show_error(lst)
        return
    if not items:
        st.info("No investigations yet. Next step: start one with the form above (operator role).")
        return
    table([{"Created": P.fmt_ts(i.get("created_at")), "Status": P.glyph(i.get("status")), "Stage": i.get("stage"),
            "Outcome": P.glyph((i.get("outcome") or {}).get("status")) if i.get("outcome") else "—",
            "Mode": P.mode_label(i.get("runtime_mode")), "Memory": i.get("memory_mode"), "Service": i.get("service_id"),
            "Investigation ID": i.get("id")} for i in items])
    if (lst.body or {}).get("next_cursor"):
        st.caption("Showing the 50 most recent investigations for this service.")
    inv_id = investigation_picker(ctx, items, "inv")
    if inv_id:
        investigation_detail(ctx, inv_id)


def investigation_header(ctx: Ctx, res: dict, page: str) -> None:
    d = res["data"]
    inv, prog = d["investigation"], d["progress"]
    st.subheader(f"Investigation {inv['id']}")
    row = st.container(horizontal=True, gap="small")
    with row:
        badge(f"Status: {res['status']}", res["status"])
        st.badge(f"Stage: {prog.get('stage')}", icon=":material/flag:", color="gray")
        st.badge(f"Mode: {P.mode_label(res.get('runtime_mode'))}", icon=":material/science:", color="blue")
        st.badge(f"Data origin: {res.get('data_origin') or 'unknown'}", icon=":material/dataset:", color="orange")
    meaning = P.STATUS_MEANING.get(res["status"])
    if meaning:
        st.caption(meaning)
    used = prog.get("candidates_used") or {}
    cap = prog.get("candidate_cap_per_path", 3)
    st.markdown(f"**Stage** {prog.get('stage')} · **Rounds** {prog.get('rounds', 0)} · "
                f"**Cloud candidates** {used.get('cloud', 0)} of {cap} used · **AI candidates** {used.get('ai', 0)} of {cap} used")
    st.caption(f"Service {inv['service_id']} · policy {inv['policy_version']} · data manifest {inv['data_manifest_id']} · "
               f"interval {P.fmt_ts(inv['interval_start'])} → {P.fmt_ts(inv['interval_end'])} · memory {inv['memory_mode']} · "
               f"trial profile {inv.get('trial_profile_id') or 'none'} · created {P.fmt_ts(inv['created_at'])} by {inv['actor_id']} · "
               f"updated {P.fmt_ts(inv['updated_at'])} · last refreshed {P.now_utc()}")
    st.button("Refresh from API", key=f"refresh_{page}_{inv['id']}", icon=":material/refresh:")
    for b in res.get("blockers") or []:
        st.error(f"Blocked: {b}", icon=":material/block:")
    if res["status"] == "FAILED" and not res.get("blockers"):
        st.error("The investigation failed and the API recorded no failure reason. Check Activity for the last stage "
                 "reached; no change was made.", icon=":material/error:")
    if res["status"] in ("QUEUED", "RUNNING"):
        st.info(f"In progress at stage {prog.get('stage')}. Remaining work is not known in advance, so no percentage is "
                "shown. Press Refresh to update.", icon=":material/hourglass_top:")


def investigation_detail(ctx: Ctx, inv_id: str) -> None:
    r = ctx.api.get(f"/v1/investigations/{inv_id}")
    if not r.ok:
        show_error(r)
        return
    res = r.body
    d = res["data"]
    with st.container(border=True):
        investigation_header(ctx, res, "inv")
        if ctx.can_write and "cancel" in (res.get("next_allowed_actions") or []):
            with st.expander("Cancel investigation", icon=":material/stop_circle:"):
                with st.form(f"cancel_{inv_id}"):
                    reason = st.text_input("Reason (required)", max_chars=300)
                    go = st.form_submit_button("Request cancellation")
                st.caption("Cancellation stops at a safe stage boundary; in-flight work is not undone.")
                if go:
                    if not reason.strip():
                        st.error("Reason: enter why the run should stop.", icon=":material/error:")
                    else:
                        cr = mutate(ctx, f"cancel:{inv_id}:{digest(reason.strip())}", f"/v1/investigations/{inv_id}/cancel",
                                    {"reason": reason.strip()})
                        if cr.ok:
                            flash("info", f"Cancellation requested for {inv_id}; it stops at the next safe boundary.")
                            st.rerun()
                        show_error(cr, mutation=True)
        calls = (d.get("progress") or {}).get("model_calls") or []
        if calls:
            with st.expander("Agent model calls (counts and tokens)"):
                table([{"Role": c.get("role"), "Calls": c.get("n"), "Requests": c.get("requests"),
                        "Input tokens": c.get("input_tokens") if c.get("input_tokens") is not None else "unknown (not reported)",
                        "Output tokens": c.get("output_tokens") if c.get("output_tokens") is not None else "unknown (not reported)"}
                       for c in calls])
    outcome = d.get("outcome") or {}
    if res["status"] == "NO_CHANGE" or outcome.get("status") == "NO_CHANGE":
        no_change_explanation(d)
    t_queue, t_ev, t_mem, t_act = st.tabs(["Review queue", "Evidence & federation", "Prior experiments (memory)", "Activity"])
    with t_queue:
        review_queue(ctx, res)
    with t_ev:
        evidence_tab(ctx, d, inv_id)
    with t_mem:
        memory_tab(d)
    with t_act:
        activity_tab(ctx, inv_id)


def no_change_explanation(d: dict) -> None:
    with st.container(border=True):
        st.markdown(":material/radio_button_unchecked: **No change — the investigation completed without an acceptable change.** "
                    "This is a valid decision: nothing was modified. Evaluated options and why each was not accepted:")
        plans = d.get("plans") or []
        if plans:
            table([{"Candidate": f"{p['path']}#{p['candidate_no']}", "Signature": (p.get("screening") or {}).get("signature"),
                    "Status": P.glyph(p.get("status")), "Why not accepted": P.plan_reason(p, d.get("feedback"))} for p in plans])
        else:
            st.caption("No candidate passed initial generation; see Activity for the evaluated scope.")


def review_queue(ctx: Ctx, res: dict) -> None:
    d = res["data"]
    plans = d.get("plans") or []
    if not plans:
        nxt = ("The investigation is still running — press Refresh to see candidates as they are screened."
               if res["status"] in ("QUEUED", "RUNNING") else
               "Next step: start a new investigation with a different question or interval (operator role).")
        st.info(f"No candidates yet. {nxt}", icon=":material/inbox:")
        return
    st.caption(f"Order from the API: {d.get('queue_order')}.")
    path = st.segmented_control("Filter by path", ["All", "cloud", "ai"], default="All", key=f"pathf_{res['id']}") or "All"
    shown = [p for p in plans if path == "All" or p["path"] == path]
    table([{"Path#": f"{p['path']}#{p['candidate_no']}", "Signature": (p.get("screening") or {}).get("signature"),
            "Status": P.glyph(p.get("status")), "Reason": P.plan_reason(p, d.get("feedback")),
            "Evidence freshness": P.freshness(p), "Impact basis": P.impact_basis(p.get("impacts"))} for p in shown])
    if not shown:
        st.caption("No candidates on this path.")
        return
    by = {p["id"]: p for p in shown}
    pid = picker("Open candidate", list(by), f"sel_cand_{res['id']}", f"cand_pick_{res['id']}",
                 lambda i: f"{by[i]['path']}#{by[i]['candidate_no']} · {by[i]['status']} · {(by[i].get('screening') or {}).get('signature')}")
    if pid:
        candidate_detail(ctx, pid, d)


def candidate_detail(ctx: Ctx, pid: str, inv_data: dict) -> None:
    r = ctx.api.get(f"/v1/plans/{pid}")
    if not r.ok:
        show_error(r)
        return
    p = r.body
    d = p["data"]
    core = d.get("core") or {}
    with st.container(border=True):
        st.markdown(f"#### Candidate {d['path']}#{d['candidate_no']} (revision {d['revision']})")
        badge(f"{p['status']}", p["status"])
        if P.STATUS_MEANING.get(p["status"]):
            st.caption(P.STATUS_MEANING[p["status"]])
        for b in p.get("blockers") or []:
            st.warning(f"Blocked: {b[:1].upper() + b[1:]}", icon=":material/block:")
        ex = core.get("executor")
        kv_table([("Target", f"{d['target_key']} ({P.environment_of(d['target_key'])})"), ("Action type", d["action_type"]),
                  ("Executor", P.EXECUTOR_LABEL if ex == "local_analogue" else "none — projection only, not executable" if ex == "none" else ex),
                  ("Signature", (d.get("screening") or {}).get("signature")), ("Plan hash", d["plan_hash"]),
                  ("Versions", ", ".join(f"{k}={v}" for k, v in (core.get("versions") or {}).items())),
                  ("Requires downtime", "yes" if core.get("requires_downtime") else "no"), ("Updated", P.fmt_ts(d.get("updated_at")))])
        st.markdown("**Before / after** (`core.action`)")
        table(P.before_after_rows(core.get("action")))

        scr = d.get("screening") or {}
        st.markdown(f"**Screening checks** ({scr.get('version')}) — outcome {P.glyph(scr.get('outcome'))}")
        table([{"Check": c.get("check_id"), "Result": P.glyph(c.get("status")), "Measured": P.fmt_num(c.get("measured")),
                "Limit": P.fmt_num(c.get("limit")), "Detail": c.get("detail")} for c in scr.get("checks") or []])

        crit = d.get("critic") or {}
        if crit:
            st.markdown(f"**Critic decision:** {P.glyph(crit.get('verdict'))} — cites checks "
                        f"{', '.join(crit.get('check_ids') or []) or 'none'}; evidence "
                        f"{', '.join(P.short_id(e) for e in crit.get('evidence_ids') or []) or 'none'}")
            if crit.get("note"):
                st.caption(f"Critic note: {crit['note']}")
            if crit.get("evidence_requests"):
                st.caption(f"Evidence requested by critic: {P.cell(crit['evidence_requests'])}")
            tr = crit.get("trial") or {}
            if tr:
                tc = tr.get("critic") or {}
                st.markdown(f"**Trial review:** trial {P.short_id(tr.get('trial_id'))} {P.glyph(tr.get('status'))}; critic "
                            f"{P.glyph(tc.get('verdict'))}" + (f" — cites {', '.join(tc['check_ids'])}" if tc.get("check_ids") else ""))
        trial_summary(ctx, d)
        impacts_section(d)
        refs = d.get("memory_refs") or []
        st.markdown("**Memory references:** " + (", ".join(f"`{m}`" for m in refs) if refs else
                                                 "none — this candidate did not cite a prior experiment"))
        if d.get("rationale_untrusted_model_text"):
            with st.expander("Model rationale (untrusted model text; not evidence or authority)"):
                st.text(d["rationale_untrusted_model_text"])
        approval_panel(ctx, p)


def trial_summary(ctx: Ctx, d: dict) -> None:
    trials = d.get("trials") or []
    st.markdown("**Sandbox trials**")
    if not trials:
        st.caption("No trial recorded for this candidate.")
        return
    table([{"Trial ID": t["id"], "Status": P.glyph(t["status"]), "Suite": t.get("suite_id"), "Trial hash": t.get("trial_hash"),
            "Finished": P.fmt_ts(t.get("finished_at"))} for t in trials])
    latest = trials[-1]
    tr = ctx.api.get(f"/v1/trials/{latest['id']}")
    if not tr.ok:
        show_error(tr)
        return
    result = tr.body["data"].get("result") or {}
    if d["path"] == "ai":
        cand = result.get("candidate") or {}
        if cand:
            st.caption(f"Latest trial: candidate accepted {cand.get('accepted')}/{cand.get('cases')}, critical failures "
                       f"{cand.get('critical_failures')}. Full baseline-vs-candidate metrics are on the AI Lab page.")
        else:
            st.caption("Latest trial has no measured result; see its checks below.")
    checks = result.get("checks") or []
    if checks:
        table([{"Trial check": c.get("check_id"), "Result": P.glyph(c.get("status")), "Detail": c.get("detail")} for c in checks])
    summ = result.get("summary")
    if summ:
        st.caption("Measured workload: baseline p95 {} ms, candidate p95 {} ms; failures {} vs {}. {}".format(
            P.fmt_num(summ.get("baseline_p95_ms"), 1), P.fmt_num(summ.get("candidate_p95_ms"), 1),
            summ.get("baseline_failures"), summ.get("candidate_failures"), "; ".join(result.get("limitations") or [])))


def impacts_section(d: dict) -> None:
    imp = d.get("impacts") or {}
    st.markdown(f"**Impact basis:** {P.impact_basis(imp)}")
    if imp.get("result_kind") == "projected":
        cur = imp.get("currency", "")
        table([
            {"Quantity": f"Hourly rate ({cur}/hour)", "Baseline": P.fmt_num(imp.get("baseline_usd_per_hour")),
             "Candidate": P.fmt_num(imp.get("candidate_usd_per_hour")), "Basis": "Projected at dated rate"},
            {"Quantity": f"Cost over {imp.get('horizon_hours')} h ({cur})", "Baseline": P.fmt_num(imp.get("baseline_cost")),
             "Candidate": P.fmt_num(imp.get("candidate_cost")), "Basis": "Projected at dated rate"},
            {"Quantity": f"Projected net difference over {imp.get('horizon_hours')} h ({cur})", "Baseline": "—",
             "Candidate": P.fmt_num(imp.get("net_saving")), "Basis": f"Projected at dated rate; one-time costs {imp.get('one_time_costs')}"},
        ])
        st.caption(f"Price basis: {imp.get('price_basis')} · {imp.get('commitment_assumption')} · {imp.get('note')}. "
                   "A proposed saving is not an achieved saving.")
    carbon = imp.get("carbon")
    basis = P.carbon_basis(carbon)
    st.markdown(f"**Carbon:** {basis}")
    if basis == "Estimated carbon":
        table([{"Quantity": f"kgCO2e over {imp.get('horizon_hours')} h", "Baseline": P.fmt_num(carbon.get("baseline_kg_co2e")),
                "Candidate": P.fmt_num(carbon.get("candidate_kg_co2e")), "Basis": "Estimated carbon"}])
        st.caption(f"Method {carbon.get('method_version')} · factor {carbon.get('factor_kg_per_kwh')} kg/kWh "
                   f"({carbon.get('factor_source')}, {carbon.get('region')}) · coverage: {carbon.get('coverage')} · {carbon.get('note')}")


def approval_panel(ctx: Ctx, p: dict) -> None:
    d = p["data"]
    acts = p.get("next_allowed_actions") or []
    ap = d.get("latest_approval")
    st.markdown("#### Approval and execution")
    if ap:
        st.markdown(f"Latest approval `{ap['id']}` — {P.glyph(ap['status'])} · expires {P.fmt_ts(ap.get('expires_at'))} · "
                    f"granted by {ap.get('actor_id')}" + (f" · consumed by action `{ap['consumed_action_id']}`" if ap.get("consumed_action_id") else ""))
    if not ctx.can_write:
        st.caption("Read-only (viewer role): approval, execution and revocation controls are not shown. "
                   "The API enforces this independently.")
        return
    shown = False
    if p["status"] == "AWAITING_APPROVAL":
        shown = True
        if "approve" in acts:
            approval_form(ctx, p)
        else:
            why = "; ".join(p.get("blockers") or []) or "the API does not currently allow approval"
            st.warning(f"Approval form unavailable: {why[:1].upper() + why[1:]}.", icon=":material/block:")
    if "execute" in acts and ap:
        shown = True
        st.caption("Execution needs the active approval above and re-checks target, policy and expiry on the server.")
        if st.button("Execute approved change", type="primary", key=f"exec_{p['id']}_{ap['id']}", icon=":material/play_arrow:"):
            r = mutate(ctx, f"execute:{p['id']}:{ap['id']}", f"/v1/plans/{p['id']}/execute",
                       {"approval_id": ap["id"], "plan_hash": d["plan_hash"]})
            if r.ok:
                st.session_state["sel_action"] = str(r.body.get("action_id"))
                flash("info", f"Execution requested: action {r.body.get('action_id')} is {r.body.get('status')}"
                      + (" (existing action returned)" if r.body.get("replayed_existing_action") else "")
                      + ". An accepted request is not success — follow verification on Actions & reports.")
                st.rerun()
            show_error(r, mutation=True)
    elif p["status"] == "APPROVED":
        shown = True
        st.info("Execution is not currently permitted: " + ("; ".join(p.get("blockers") or []) or "see API state") + ".")
    if "revoke_approval" in acts and ap:
        shown = True
        with st.expander("Revoke approval", icon=":material/undo:"):
            with st.form(f"revoke_{ap['id']}"):
                reason = st.text_input("Reason (required)", max_chars=300)
                go = st.form_submit_button("Revoke approval")
            if go:
                if not reason.strip():
                    st.error("Reason: enter why the approval is withdrawn.", icon=":material/error:")
                else:
                    r = mutate(ctx, f"revoke:{ap['id']}:{digest(reason.strip())}", f"/v1/approvals/{ap['id']}/revoke",
                               {"reason": reason.strip()})
                    if r.ok:
                        flash("info", f"Approval {ap['id']} is now {r.body.get('status')}. Revocation does not roll back any change.")
                        st.rerun()
                    show_error(r, mutation=True)
    if not shown:
        st.caption("No approval step applies to this candidate in its current state.")


def approval_form(ctx: Ctx, p: dict) -> None:
    d = p["data"]
    core = d.get("core") or {}
    passed = [t for t in d.get("trials") or [] if t.get("status") == "PASSED"]
    if not passed:
        st.warning("Approval requires a passed sandbox trial; none is recorded for this plan.", icon=":material/block:")
        return
    t = passed[-1]
    needs_downtime = bool(core.get("requires_downtime"))
    versions = core.get("versions") or {}
    with st.form(f"approve_{p['id']}"):
        st.markdown("**Human approval** — this form records a scoped approval only; it does not start the change.")
        kv_table([("Target", d["target_key"]), ("Environment", P.environment_of(d["target_key"])),
                  ("Action type", d["action_type"]), ("Plan hash", d["plan_hash"]), ("Trial ID", t["id"]),
                  ("Trial hash", t.get("trial_hash")), ("Policy version", versions.get("policy_version")),
                  ("Workload / test version", f"{versions.get('workload_version')} / {versions.get('test_version')}"),
                  ("Downtime", "required" if needs_downtime else "none expected"),
                  ("Recovery scope", d.get("recovery_scope")),
                  ("Expiry", "Valid for 15 minutes after it is granted; execution after expiry is refused and needs a new approval.")])
        st.markdown("Before / after")
        table(P.before_after_rows(core.get("action")))
        ack = st.checkbox("I acknowledge this change requires downtime on the target.") if needs_downtime else False
        submitted = st.form_submit_button("Approve this plan", type="primary", icon=":material/verified:")
    if submitted:
        if needs_downtime and not ack:
            st.error("Downtime acknowledgement: tick the box to approve a change that requires downtime.", icon=":material/error:")
            return
        body = {"plan_hash": d["plan_hash"], "trial_id": t["id"], "trial_hash": t["trial_hash"],
                "acknowledge_downtime": bool(ack), "approved_recovery_scope": d.get("recovery_scope")}
        r = mutate(ctx, f"approve:{p['id']}:{d['plan_hash']}:{t['id']}:{bool(ack)}", f"/v1/plans/{p['id']}/approve", body)
        if r.ok:
            flash("success", f"Approval {r.body.get('approval_id')} recorded ({r.body.get('status')}); expires "
                  f"{P.fmt_ts(r.body.get('expires_at'))}. Nothing has executed yet — use 'Execute approved change'.")
            st.rerun()
        show_error(r, mutation=True)


def evidence_tab(ctx: Ctx, d: dict, inv_id: str) -> None:
    st.markdown("#### Federation receipt")
    fed = d.get("federation")
    if not fed:
        st.info("No cross-source receipt recorded yet for this investigation.")
    else:
        cross = fed.get("cross_source")
        st.markdown(f"{'✔ Cross-source query' if cross else '✖ Single-source query'} via **{fed.get('source_system')}** · "
                    f"sources: {', '.join(fed.get('sources') or []) or 'none'} · evidence `{fed.get('evidence_id')}`")
        if fed.get("evidence_id"):
            fe = ctx.api.get(f"/v1/evidence/{fed['evidence_id']}")
            if fe.ok:
                for flag in fe.body["data"].get("quality_flags") or []:
                    st.warning(flag, icon=":material/warning:")
        table(fed.get("rows") or [])
    st.markdown("#### Evidence")
    ev = d.get("evidence") or []
    if not ev:
        st.info("No evidence retrieved yet.")
        return
    table([{"Kind": e.get("kind"), "Subject": e.get("subject") or "—", "Evidence ID": e["id"],
            "API record": f"/v1/evidence/{e['id']}"} for e in ev])
    by = {e["id"]: e for e in ev}
    eid = picker("Open evidence record", list(by), f"sel_ev_{inv_id}", f"ev_pick_{inv_id}",
                 lambda i: f"{by[i]['kind']} · {by[i].get('subject') or 'service-wide'} · {P.short_id(i)}")
    if eid:
        evidence_detail(ctx, eid)
    fc = d.get("forecast") or {}
    if fc:
        with st.expander("Forecast stress envelopes (not calibrated confidence intervals)"):
            table([{"Resource": k, "Method": v.get("method"), "Stress peak CPU %": v.get("stress_peak_cpu_pct") or "—",
                    "Residual q95 %": v.get("residual_q95_pct") or "—", "Observations": v.get("observations"),
                    "Unavailable": v.get("unavailable_reason") or "—", "Label": v.get("label")} for k, v in fc.items()])


def evidence_detail(ctx: Ctx, eid: str) -> None:
    r = ctx.api.get(f"/v1/evidence/{eid}")
    if not r.ok:
        show_error(r)
        return
    e = r.body
    d = e["data"]
    rc = d.get("receipt") or {}
    with st.container(border=True):
        row = st.container(horizontal=True, gap="small")
        with row:
            badge(f"Completeness: {e['status']}", e["status"])
            st.badge(f"Result: {e.get('result_kind')}", icon=":material/straighten:", color="gray")
            st.badge(f"Origin: {e.get('data_origin')}", icon=":material/dataset:", color="orange")
            st.badge(f"Retrieval: {P.mode_label(e.get('runtime_mode'))}", icon=":material/science:", color="blue")
        for flag in d.get("quality_flags") or []:
            st.warning(flag, icon=":material/warning:")
        kv_table([("Source system", d.get("source_system")), ("Kind / subject", f"{d.get('kind')} / {d.get('subject') or 'service-wide'}"),
                  ("Observed", f"{P.fmt_ts(d.get('observed_from'))} → {P.fmt_ts(d.get('observed_to'))}"),
                  ("Retrieved", P.fmt_ts(d.get("retrieved_at"))), ("Template", f"{rc.get('template_id')} v{rc.get('template_version')}"),
                  ("Sources", ", ".join(rc.get("sources") or [])), ("Rows / pages", f"{d.get('row_count')} rows / {rc.get('page_count')} pages"),
                  ("Duration", f"{rc.get('duration_ms')} ms"), ("Parameter hash", rc.get("parameter_hash")),
                  ("Result hash", rc.get("result_hash")), ("Receipt ID", rc.get("receipt_id")),
                  ("Warnings", "; ".join(rc.get("warnings") or []) or "none"),
                  ("Source request IDs", ", ".join(rc.get("request_ids") or []) or "none")])
        rows = d.get("rows") or []
        with st.expander(f"First rows ({min(len(rows), 20)} of {d.get('row_count')})"):
            table(rows[:20])
            if d.get("rows_truncated"):
                st.caption("The API truncated this record to 500 rows.")


def memory_tab(d: dict) -> None:
    mem = d.get("memory")
    st.markdown("#### Prior experiment used")
    if not mem:
        st.info("No memory record for this investigation (memory off, or recall not reached yet).")
        return
    status = mem.get("status")
    eng = mem.get("engine") or {}
    emb = mem.get("embedding_profile") or {}
    st.markdown(f"Recall status: {'✔ used' if status == 'used' else P.glyph(status)} · engine {eng.get('package')} "
                f"{eng.get('version')} (upstream {P.short_id(eng.get('upstream_sha'))})")
    if emb and not emb.get("semantic"):
        st.warning(f"Embedding profile {emb.get('model_id')} ({emb.get('kind')}) is not semantic; recall here is "
                   "a conformance path, not semantic-recall evidence.", icon=":material/warning:")
    if mem.get("queries"):
        st.caption("Queries: " + " | ".join(mem["queries"]))
    rows = [(m, "✔ Applicable") for m in mem.get("applicable") or []] + \
           [(m, "⚠ Historical — retest required") for m in mem.get("historical") or []]
    if not rows:
        st.caption("No prior experiment was recalled for this question. This is not proof that no prior failures exist.")
        return
    table([{"Applicability": label, "Memory ID": m.get("memory_id"), "Kind": m.get("kind"), "Signature": m.get("signature"),
            "Finding": m.get("finding"), "Original run": m.get("source_ref"), "Supporting receipts": len(m.get("evidence_refs") or []),
            "Versions": ", ".join(f"{k}={v}" for k, v in (m.get("applicability") or {}).items() if v),
            "Why not applicable": "; ".join(m.get("inapplicable_reasons") or []) or "—", "Score": m.get("score")}
           for m, label in rows])
    st.caption("Memory informs the investigation; it never authorizes an action. Applicability is re-checked by the server.")


def activity_tab(ctx: Ctx, inv_id: str) -> None:
    items, after = [], 0
    for _ in range(10):  # bounded paging: at most 5000 events
        r = ctx.api.get(f"/v1/investigations/{inv_id}/events", {"after_sequence": after, "limit": 500})
        if not r.ok:
            show_error(r)
            return
        page = r.body.get("items") or []
        items += page
        if len(page) < 500:
            break
        after = r.body.get("next_sequence", after)
    if not items:
        st.info("No activity recorded yet.")
        return
    table([{"Seq": e.get("seq"), "Time": P.fmt_ts(e.get("at")), "Kind": e.get("kind"), "Actor": e.get("actor"),
            "Payload": P.cell(e.get("payload"), 200)} for e in items])


# ---- AI Lab --------------------------------------------------------------------------------------

def page_ai_lab(ctx: Ctx) -> None:
    st.title("AI Lab")
    st.info("Development-suite results only (support-dev-v1). Held-out (holdout) results are evaluator-only and are not "
            "shown here; the API refuses trials on held-out suites.", icon=":material/lock:")
    items, lst = list_investigations(ctx)
    if not lst.ok:
        show_error(lst)
        return
    if not items:
        st.info("No investigations yet. Start one on the Investigations page.")
        return
    inv_id = investigation_picker(ctx, items, "ai")
    r = ctx.api.get(f"/v1/investigations/{inv_id}")
    if not r.ok:
        show_error(r)
        return
    d = r.body["data"]
    st.caption(f"Investigation {inv_id} · service {d['investigation']['service_id']} · policy {d['investigation']['policy_version']} "
               f"· status {P.glyph(r.body['status'])} · refreshed {P.now_utc()}")
    ai_plans = {p["id"]: p for p in d.get("plans") or [] if p["path"] == "ai"}
    if not ai_plans:
        st.info("No AI plans in this investigation yet." + (" It is still running — refresh later." if r.body["status"] in ("QUEUED", "RUNNING") else ""))
        return
    trials = [t for t in d.get("trials") or [] if t["plan_id"] in ai_plans]
    latest = {t["plan_id"]: t for t in trials}
    st.subheader("AI plans")
    table([{"Path#": f"ai#{p['candidate_no']}", "Signature": (p.get("screening") or {}).get("signature"), "Plan status": P.glyph(p["status"]),
            "Latest trial": P.glyph(latest[pid]["status"]) if pid in latest else "no trial", "Plan ID": pid}
           for pid, p in ai_plans.items()])
    if not trials:
        st.info("No AI trials yet. Trials run only when the investigation uses the approved trial profile.")
        return
    by = {t["id"]: t for t in trials}
    tid = picker("Trial", list(by), f"sel_trial_{inv_id}", f"trial_pick_{inv_id}",
                 lambda i: f"ai#{ai_plans[by[i]['plan_id']]['candidate_no']} · {by[i]['status']} · trial {i}")
    if tid:
        ai_trial(ctx, tid)


def ai_trial(ctx: Ctx, tid: str) -> None:
    r = ctx.api.get(f"/v1/trials/{tid}")
    if not r.ok:
        show_error(r)
        return
    t = r.body
    td = t["data"]
    res = td.get("result") or {}
    with st.container(border=True):
        st.subheader(f"Trial {tid}")
        row = st.container(horizontal=True, gap="small")
        with row:
            badge(f"Outcome: {t['status']}", t["status"])
            st.badge(f"Result: {t.get('result_kind') or 'unknown'}", icon=":material/straighten:", color="gray")
            st.badge(f"Origin: {t.get('data_origin') or 'unknown'}", icon=":material/dataset:", color="orange")
            st.badge(f"Mode: {P.mode_label(t.get('runtime_mode'))}", icon=":material/science:", color="blue")
        kv_table([("Suite / verifier", f"{td.get('suite_id')} / {res.get('verifier') or '—'}"), ("Plan hash", td.get("plan_hash")),
                  ("Trial hash", td.get("trial_hash")), ("Trial profile", f"{td.get('trial_profile_id')} ({res.get('profile_hash') or '—'})"),
                  ("Run time", f"{P.fmt_ts(td.get('started_at'))} → {P.fmt_ts(td.get('finished_at'))}"),
                  ("Versions", ", ".join(f"{k}={v}" for k, v in (res.get("versions") or {}).items()))])
        base, cand = res.get("baseline") or {}, res.get("candidate") or {}
        if not base and not cand:
            st.warning("This trial produced no measured comparison.", icon=":material/warning:")
        else:
            basis = cand.get("usage_basis") or base.get("usage_basis")
            st.markdown(f"**Usage basis:** {P.usage_basis_label(basis)} (`{basis}`)")

            def metric_rows(label, fn):
                return {"Metric": label, "Baseline": fn(base) if base else "—", "Candidate": fn(cand) if cand else "—"}

            table([
                metric_rows("Accepted tasks", lambda s: f"{s.get('accepted')}/{s.get('cases')}"),
                metric_rows("Critical failures", lambda s: s.get("critical_failures")),
                metric_rows("Errors", lambda s: s.get("errors")),
                metric_rows("Wilson 95% interval (accept rate)", lambda s: " – ".join(P.fmt_num(x) for x in s.get("wilson_95") or []) or "—"),
                metric_rows("Model requests", lambda s: s.get("model_requests")),
                metric_rows("Input tokens", lambda s: s.get("input_tokens")),
                metric_rows("Output tokens", lambda s: s.get("output_tokens")),
                metric_rows("Tool calls", lambda s: s.get("tool_calls")),
                metric_rows("Deduplicated lookups", lambda s: s.get("deduped_lookups")),
                metric_rows("Total cost (USD)", lambda s: P.fmt_num(s.get("total_cost_usd"), 8)),
                metric_rows("Cost per accepted task", lambda s: P.cost_per_accepted(s.get("cost_per_accepted_usd"))),
                metric_rows("Latency p50 / max (ms)", lambda s: f"{P.fmt_num(s.get('latency_ms_p50'), 1)} / {P.fmt_num(s.get('latency_ms_max'), 1)}"),
                metric_rows("Model", lambda s: s.get("model_id")),
                metric_rows("Usage basis", lambda s: s.get("usage_basis")),
            ])
            if res.get("cost_basis"):
                st.caption(f"Cost basis: {res['cost_basis']}")
            st.markdown("**Configuration (before → after)**")
            table(P.before_after_rows({"before": base.get("config"), "after": cand.get("config")}))
            cats = sorted(set(base.get("by_category") or {}) | set(cand.get("by_category") or {}))
            st.markdown("**Per-category accepted**")
            table([{"Category": c,
                    "Baseline": "{accepted}/{total}".format(**(base.get("by_category") or {}).get(c, {"accepted": "—", "total": "—"})),
                    "Candidate": "{accepted}/{total}".format(**(cand.get("by_category") or {}).get(c, {"accepted": "—", "total": "—"}))}
                   for c in cats])
        pdisc = res.get("paired_discordance")
        if pdisc:
            st.markdown("**Paired discordance** (same cases, baseline vs candidate)")
            table([{"Both pass": pdisc.get("both_pass"), "Baseline only": pdisc.get("baseline_only"),
                    "Candidate only": pdisc.get("candidate_only"), "Neither": pdisc.get("neither")}])
        st.markdown("**Trial checks**")
        table([{"Check": c.get("check_id"), "Result": P.glyph(c.get("status")), "Detail": c.get("detail")} for c in res.get("checks") or []])
        if res.get("cost_per_accepted_reduction") is not None:
            st.caption(f"Cost-per-accepted reduction: {P.fmt_num(res['cost_per_accepted_reduction'])} (fraction) · "
                       f"efficiency aspiration met: {P.cell(res.get('efficiency_aspiration_met'))}")
        for lim in res.get("limitations") or []:
            st.caption(f"Limitation: {lim}")
        fails = [(side, c) for side, s in (("baseline", base), ("candidate", cand)) for c in s.get("per_case") or [] if not c.get("accepted")]
        if fails:
            with st.expander(f"Development-case diagnostics: {len(fails)} non-accepted case results"):
                table([{"Side": side, "Case": c.get("case_id"), "Category": c.get("category"), "Critical": c.get("critical"),
                        "Expected": c.get("expected"), "Observed": c.get("observed"),
                        "Failed checks": ", ".join(k for k, v in (c.get("checks") or {}).items() if not v) or "—"} for side, c in fails])


# ---- Actions & reports ----------------------------------------------------------------------------

def page_actions(ctx: Ctx) -> None:
    st.title("Actions & reports")
    items, lst = list_investigations(ctx)
    if not lst.ok:
        show_error(lst)
        return
    if not items:
        st.info("No investigations yet. Start one on the Investigations page.")
        return
    inv_id = investigation_picker(ctx, items, "act")
    r = ctx.api.get(f"/v1/investigations/{inv_id}")
    if not r.ok:
        show_error(r)
        return
    d = r.body["data"]
    st.caption(f"Investigation {inv_id} · service {d['investigation']['service_id']} · policy {d['investigation']['policy_version']} "
               f"· status {P.glyph(r.body['status'])} · refreshed {P.now_utc()}")
    st.subheader("Action status")
    actions = d.get("actions") or []
    if not actions:
        st.info("No action has been requested for this investigation. Execution needs an active human approval in a "
                "Connected demo run with server writes enabled; Sample and Recorded replay runs cannot execute.",
                icon=":material/inbox:")
    else:
        by = {a["id"]: a for a in actions}
        aid = picker("Action", list(by), "sel_action", f"act_pick_{inv_id}", lambda i: f"{by[i]['status']} · action {i}")
        st.button("Refresh action", key=f"refresh_act_{aid}", icon=":material/refresh:")
        action_detail(ctx, aid)
    st.subheader("Evidence report")
    report_section(ctx, inv_id)


def action_detail(ctx: Ctx, aid: str) -> None:
    r = ctx.api.get(f"/v1/actions/{aid}")
    if not r.ok:
        show_error(r)
        return
    a = r.body
    d = a["data"]
    s = a["status"]
    with st.container(border=True):
        badge(f"Action status: {s}", s)
        if s == "EXECUTING":
            st.info("EXECUTING — the change is being applied and is not yet verified. Do not retry; refresh to follow.",
                    icon=":material/hourglass_top:")
        elif s == "PENDING_VERIFICATION":
            st.warning("PENDING_VERIFICATION — the write was made but its effect is not yet verified. An accepted request "
                       "or a running instance is not success. Do not retry.", icon=":material/pending:")
        elif s == "VERIFIED":
            st.success("VERIFIED — intended state and required health checks confirmed.", icon=":material/verified:")
        elif s in ("FAILED", "RECOVERY_REQUIRED"):
            st.error(f"{s} — {P.STATUS_MEANING.get(s)}.", icon=":material/error:")
        elif P.STATUS_MEANING.get(s):
            st.info(f"{s} — {P.STATUS_MEANING[s]}.")
        st.caption(f"Executor: {d.get('executor_label')}")
        kv_table([("Target", d.get("target_key")), ("Plan", d.get("plan_id")), ("Approval", d.get("approval_id")),
                  ("Requested by", d.get("actor_id")), ("Created", P.fmt_ts(d.get("created_at"))),
                  ("Updated", P.fmt_ts(d.get("updated_at"))), ("Verified at", P.fmt_ts(d.get("verified_at"))),
                  ("Provider operation IDs", ", ".join(d.get("operation_ids") or []) or "none recorded"),
                  ("Memory sync", P.glyph(d.get("memory_sync_status")))])
        if d.get("before_state") or d.get("after_state"):
            with st.expander("Configuration read-back (before / after)"):
                st.json({"before_state": d.get("before_state"), "after_state": d.get("after_state")}, expanded=False)
        ver = d.get("verification") or {}
        st.markdown("**Verification**")
        if not ver:
            st.caption("No verification recorded yet.")
        else:
            if ver.get("summary"):
                st.markdown(ver["summary"])
            if ver.get("error"):
                st.error(f"Error: {ver['error']}" + (f" — {ver['reason']}" if ver.get("reason") else ""), icon=":material/error:")
            inner = ver.get("verification") if isinstance(ver.get("verification"), dict) else ver
            checks = inner.get("checks")
            if isinstance(checks, dict):
                table([{"Check": k, "Result": P.glyph("PASS" if v else "FAIL")} for k, v in checks.items()])
            elif isinstance(checks, list):
                table([{"Check": c.get("check_id"), "Result": P.glyph(c.get("status")), "Detail": c.get("detail")} for c in checks])
            if inner.get("readback"):
                st.caption(f"Read-back: {P.cell(inner['readback'])}")
            if inner.get("smoke"):
                table([{"Smoke case": c.get("case_id"), "Result": P.glyph("PASS" if c.get("accepted") else "FAIL")} for c in inner["smoke"]])
        rec = d.get("recovery") or ver.get("recovery")
        st.markdown("**Recovery**")
        if not rec:
            st.caption("No recovery attempted. Recovery, when needed, is limited to restoring the exact prior configuration "
                       "if nothing changed in between; it is not automatic for every failure.")
        else:
            kv_table([(k, v) for k, v in rec.items()])
            if s == "RECOVERY_REQUIRED" or rec.get("attempted") is False:
                st.error("Human step required: inspect the target and restore it using the documented procedure.", icon=":material/engineering:")
        if d.get("error"):
            st.error(f"Action error: {P.cell(d['error'])}", icon=":material/error:")
        journal = d.get("journal") or []
        st.markdown("**Journal**")
        if journal:
            table([{"Seq": j.get("seq"), "Time": P.fmt_ts(j.get("at")), "Stage": P.glyph(j.get("stage")),
                    "Detail": P.cell(j.get("detail"), 220)} for j in journal])
        else:
            st.caption("No journal entries yet.")


def report_section(ctx: Ctx, inv_id: str) -> None:
    st.caption("The report is built by the API from committed state. The workbench fetches it with your session token in "
               "the Authorization header; the download never puts the token in a URL.")
    if st.button("Prepare report downloads", key=f"prep_report_{inv_id}", icon=":material/description:"):
        got = False
        for fmt, mime in (("html", "text/html"), ("json", "application/json")):
            r = ctx.api.download(f"/v1/reports/{inv_id}", {"format": fmt})
            if r.ok:
                got = True
                st.download_button(f"Download {fmt.upper()} report", data=r.body, file_name=f"greenops-report-{inv_id}.{fmt}",
                                   mime=mime, key=f"dl_{fmt}_{inv_id}", on_click="ignore", icon=":material/download:")
            else:
                st.markdown(f"{fmt.upper()} report could not be prepared:")
                show_error(r)
        if got:
            st.caption(f"Prepared {P.now_utc()}.")


# ---- Operations ---------------------------------------------------------------------------------

def page_operations(ctx: Ctx) -> None:
    st.title("Operations")
    r = ctx.api.get("/v1/operations")
    if r.status == 403:
        st.info(f"Operations is available to the admin role only. Your role: {ctx.role}. "
                f"(FORBIDDEN, request ID `{r.error.get('request_id')}`)", icon=":material/lock:")
        return
    if not r.ok:
        show_error(r)
        return
    o = r.body
    d = o["data"]
    st.caption(f"Read-only. Configuration changes follow the documented operator procedure, not this screen. Refreshed {P.now_utc()}.")
    row = st.container(horizontal=True, gap="small")
    with row:
        badge(f"Readiness: {o['status']}", o["status"])
        st.badge(f"Mode: {P.mode_label(d.get('runtime_mode'))}", icon=":material/science:", color="blue")
        w = d.get("sandbox_writes_enabled")
        st.badge("Sandbox writes: ENABLED" if w else "Sandbox writes: disabled", icon=":material/edit:" if w else ":material/edit_off:",
                 color="orange" if w else "gray")
    st.markdown("**Dependencies**")
    table([{"Dependency": k, "State": P.dep_glyph(v)} for k, v in (d.get("dependencies") or {}).items()])
    kv_table([("Policy version", d.get("policy_version")), ("Data manifest", d.get("data_manifest_id")),
              ("Executor", f"{d.get('executor')} — {P.EXECUTOR_LABEL}"), ("GCP executor", d.get("gcp_executor")),
              ("Allowed target IDs", ", ".join(d.get("allowed_target_ids") or []) or "none"),
              ("Zetaris sources", ", ".join(d.get("zetaris_sources") or []) if d.get("zetaris_sources") else "not used in this mode"),
              ("Model ID", d.get("model_id") or "not configured (scripted in sample mode)")])
    slot = d.get("execution_slot") or {}
    st.markdown("**Execution slot** (one active mutation at a time)")
    st.markdown("○ Free" if not slot.get("holder_id") else
                f"⚠ Held by {slot.get('holder_kind')} `{slot.get('holder_id')}` since {P.fmt_ts(slot.get('acquired_at'))}")
    for title, key, cols in (("Active actions", "active_actions", None), ("Jobs (queued / running)", "jobs", None),
                             ("Memory outbox", "memory_outbox", None), ("Budget profiles", "budget_profiles", None),
                             ("Trial profiles", "trial_profiles", None)):
        st.markdown(f"**{title}**")
        rows = d.get(key) or []
        if rows:
            table([{k: (P.fmt_ts(v) if k.endswith("_at") or k == "oldest" else P.glyph(v) if k == "status" else v)
                    for k, v in x.items()} for x in rows])
        else:
            st.caption("None.")


# ---- entry point --------------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="GreenOps Verify", page_icon=":material/fact_check:", layout="wide")
    token = st.session_state.get("token")
    if not token:
        st.navigation([st.Page(login_page, title="Sign in", icon=":material/login:", url_path="signin")], position="hidden").run()
        return
    ctx = build_ctx(token)
    pages = [
        st.Page(lambda: guarded(page_investigations, ctx), title="Investigations", icon=":material/search:",
                url_path="investigations", default=True),
        st.Page(lambda: guarded(page_ai_lab, ctx), title="AI Lab", icon=":material/science:", url_path="ai-lab"),
        st.Page(lambda: guarded(page_actions, ctx), title="Actions & reports", icon=":material/task_alt:", url_path="actions"),
        st.Page(lambda: guarded(page_operations, ctx), title="Operations", icon=":material/monitor_heart:", url_path="operations"),
    ]
    page = st.navigation(pages, position="sidebar")
    sidebar(ctx)
    guarded(banner, ctx)
    page.run()


if __name__ == "__main__":  # streamlit runs the script as __main__; importing it (tests) does not render
    main()
