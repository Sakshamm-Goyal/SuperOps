"""Investigation workflow: durable, re-entrant stage machine over persisted state.

SCOPE → PROPOSE (≤3 rounds: optimizer → deterministic screening → critic → evidence requests) → TRIALS → FINALIZE.
Every candidate consumes the per-path cap (3 cloud + 3 AI), including rejected ones. Deterministic checks and
policy are authoritative; the critic cannot validate a failed check; memory can only *block* a repeat of an
applicable prior failure or inform proposals — it never authorizes anything.
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
from decimal import Decimal

from greenops.adapters.memory import MemoryUnavailable
from greenops.adapters.model import BudgetExceeded, ModelError
from greenops.agents.roles import (INSTRUCTIONS, PROMPT_VERSION, AiCandidate, CloudCandidate, CoordinatorScope, CriticReview,
                                   InvestigatorReport, OptimizerProposal)
from greenops.config import service_config
from greenops.db import J, connect
from greenops.domain.models import AiWorkflowConfig, ServicePolicy
from greenops.domain.quantities import GIB, DomainError, canonical_hash
from greenops.domain.screening import Check, MachineType, ScreeningResult, screen_cloud
from greenops.services import memory_service, plans as P
from greenops.services.common import AppError, Runtime, append_event, enqueue, event, now
from greenops.services.evidence_service import build_facts, collect, forecast_stress, resource_key

TERMINAL = {"COMPLETED", "NO_CHANGE", "FAILED", "CANCELLED"}
MAX_ROUNDS = 3
FAILURE_KINDS = {"screening_rejection", "rejected_trial"}


def load(conn, inv_id) -> dict:
    inv = conn.execute("SELECT * FROM investigations WHERE id=%s", (inv_id,)).fetchone()
    if inv is None:
        raise AppError("NOT_FOUND", 404, "investigation not found")
    return inv


def save_summary(rt: Runtime, inv_id, summary: dict, **fields) -> None:
    sets = ", ".join(f"{k}=%s" for k in fields)
    with connect(rt.db) as c:
        c.execute(f"UPDATE investigations SET summary=%s{', ' + sets if sets else ''}, updated_at=now() WHERE id=%s",
                  (J(summary), *fields.values(), inv_id))


def record_model_call(rt: Runtime, inv_id, trial_id, role: str, res=None, error: str | None = None, duration_ms: int = 0, model_id: str = "") -> None:
    with connect(rt.db) as c:
        c.execute("INSERT INTO model_calls (id, investigation_id, trial_id, role, model_id, runtime_mode, status, input_tokens, output_tokens, "
                  "tool_calls, requests, duration_ms, error_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (uuid.uuid4(), inv_id, trial_id, role, res.model_id if res else model_id, rt.settings.runtime_mode.value,
                   "ok" if res else "error", res.input_tokens if res else None, res.output_tokens if res else None,
                   res.tool_calls if res else 0, max(1, res.model_requests) if res else 1, res.duration_ms if res else duration_ms, error))


def budget_for(rt: Runtime, inv: dict):
    """Durable per-investigation reservations (audit A08): counted from budget_reservations, not usage metadata."""
    from greenops.services.budget import DurableBudget, investigation_limits
    return DurableBudget(rt.db, investigation_id=inv["id"], limits=investigation_limits(inv), daily_cap_usd=rt.settings.max_daily_cost_usd)


def call_role(rt: Runtime, inv: dict, gateway, role: str, payload: dict, out_model, budget: Budget, tools=None):
    try:
        res = gateway.run(role, INSTRUCTIONS[role], payload, out_model, tools=tools, budget=budget)
    except ModelError as e:
        record_model_call(rt, inv["id"], None, role, error=e.code, model_id=gateway.model_id)
        raise
    record_model_call(rt, inv["id"], None, role, res)
    event(rt, inv["id"], f"model.{role}", f"agent:{role}", {"model_id": res.model_id, "prompt_version": PROMPT_VERSION,
          "output": json.loads(res.output.model_dump_json()), "tool_calls": res.tool_log, "input_tokens": res.input_tokens,
          "output_tokens": res.output_tokens, "duration_ms": res.duration_ms, "corrective_attempts": res.corrective_attempts})
    return res.output


# ---- context reconstructed from persisted evidence --------------------------------

BASE_TEMPLATES = ["policy", "inventory", "telemetry_summary", "billing_rows", "prices", "machine_types", "carbon_factors",
                  "model_prices", "ai_usage_by_run", "ai_duplicate_lookups", "service_cost_rollup"]


def _params(inv: dict, t: str) -> dict:
    s, e = inv["interval_start"], inv["interval_end"]
    return {"policy": {"service_id": inv["service_id"], "version": inv["policy_version"]},
            "inventory": {"service_id": inv["service_id"], "as_of": inv["as_of"]}, "telemetry_summary": {"start": s, "end": e},
            "billing_rows": {"start": s, "end": e}, "prices": {"region": service_config(inv["service_id"])["region"]}, "machine_types": {},
            "carbon_factors": {"region": service_config(inv["service_id"])["region"]}, "model_prices": {}, "ai_usage_by_run": {"service_id": inv["service_id"]},
            "ai_duplicate_lookups": {"service_id": inv["service_id"]},
            "service_cost_rollup": {"service_id": inv["service_id"], "start": s, "end": e}}[t]


def context(rt: Runtime, inv: dict) -> dict:
    summ = inv["summary"]
    ids = summ["evidence"]
    with connect(rt.db) as c:
        rows = {str(r["id"]): r["data"]["rows"] for r in c.execute("SELECT id, data FROM evidence WHERE id::text = ANY(%s)",
                                                                   (list(ids.values()) + list(summ.get("series", {}).values()),)).fetchall()}
    get = lambda t: rows[ids[t]]
    policy = ServicePolicy.model_validate_json(get("policy")[0]["document"])
    stress = {k: (Decimal(v) if v is not None else None) for k, v in summ.get("stress", {}).items()}
    facts = build_facts(get("inventory"), get("telemetry_summary"), inv["interval_start"], inv["interval_end"], stress)
    catalog = get("machine_types")
    inv["_catalog"] = catalog
    inv["_model_id"] = summ.get("model_id")
    return {"policy": policy, "facts": facts, "inventory": {resource_key(r): r for r in get("inventory")}, "catalog": catalog,
            "prices": get("prices"), "carbon": [] if summ.get("carbon_incomplete") else get("carbon_factors"), "ai_usage": get("ai_usage_by_run"), "ai_dups": get("ai_duplicate_lookups"),
            "ids": ids, "series_ids": summ.get("series", {}), "as_of": inv["as_of"]}


def current_versions(rt: Runtime, inv: dict, ctx: dict | None = None) -> dict:
    """Applicability profile per path, shared by plans, memory envelopes and recall (audit A06)."""
    ai_ver, _ = P.ai_current(rt)
    art = P.ai_artifact_versions(inv["summary"].get("model_id"))
    return {"cloud": {"policy_version": inv["policy_version"], "workload_version": inv["data_manifest_id"],
                      "config_version": inv["summary"].get("inventory_version", "inventory-unknown"),
                      "model_version": None, "test_version": "screen-v1"},
            "ai": {"policy_version": inv["policy_version"], "workload_version": art["workload_version"], "config_version": str(ai_ver),
                   "model_version": art["model_version"], "test_version": art["test_version"]}}


# ---- stages -----------------------------------------------------------------------------

def _collect_series(rt: Runtime, inv: dict, summ: dict, key: str, client=None) -> None:
    if key in summ.setdefault("series", {}):
        return
    eid, res = collect(rt, inv, "telemetry_series", {"resource_key": key, "start": inv["interval_start"], "end": inv["interval_end"]},
                       subject=key, client=client, max_rows=5000)
    peak, meta = forecast_stress(res.rows, inv["interval_start"], inv["as_of"]) if res.completeness == "complete" else (None, {"unavailable_reason": "partial series"})
    summ["series"][key] = eid
    summ.setdefault("stress", {})[key] = None if peak is None else format(peak, "f")
    summ.setdefault("forecast", {})[key] = {**meta, "evidence_id": eid}


def _scope(rt: Runtime, inv: dict, gateway, budget: Budget) -> None:
    from greenops.services.evidence_service import _client
    client = _client(rt, inv["service_id"])
    summ = inv["summary"]
    summ["model_id"] = gateway.model_id
    summ["evidence"] = {}
    for t in BASE_TEMPLATES:
        eid, res = collect(rt, inv, t, _params(inv, t), client=client)
        # Every decision input must be complete (audit A07); only carbon may degrade, to an explicit UNKNOWN.
        if res.completeness != "complete":
            if t != "carbon_factors":
                raise AppError("EVIDENCE_INCOMPLETE", 422, f"decision evidence {t} is {res.completeness}: {res.warnings}")
            summ["carbon_incomplete"] = True
        summ["evidence"][t] = eid
        if t == "service_cost_rollup":
            summ["federation"] = {"sources": res.receipt["sources"], "source_system": res.source_system, "evidence_id": eid,
                                  "cross_source": len(res.receipt["sources"]) >= 2, "rows": res.rows}
    with connect(rt.db) as c:
        inv_rows = c.execute("SELECT data FROM evidence WHERE id::text=%s", (summ["evidence"]["inventory"],)).fetchone()["data"]["rows"]
    summ["inventory_version"] = "inv:" + canonical_hash([[resource_key(r), r["machine_type"], r["config_version"]] for r in inv_rows])[7:23]
    save_summary(rt, inv["id"], summ)
    inv["summary"] = summ
    ctx = context(rt, inv)
    if ctx["policy"].version != inv["policy_version"]:
        raise AppError("EVIDENCE_INCOMPLETE", 422, "policy version from source does not match the server policy")

    scope = call_role(rt, inv, gateway, "coordinator", {"question": inv["question"], "service_id": inv["service_id"],
                      "available_paths": service_config(inv["service_id"])["paths"], "resources": len(ctx["facts"])}, CoordinatorScope, budget)
    summ["paths"] = sorted(set(scope.paths) & set(service_config(inv["service_id"])["paths"]))  # model choice bounded by service config
    summ["focus"] = scope.focus

    summ["memory"] = {"status": "off" if inv["memory_mode"] == "off" else "pending", "applicable": [], "historical": [], "queries": []}
    versions = current_versions(rt, inv, ctx)

    def recall_prior_experiments(query: str) -> dict:
        """Semantic search over persisted prior experiment results for this service. Returns applicable and historical findings."""
        if inv["memory_mode"] == "off":
            return {"memory": "disabled for this run (ablation)", "applicable": [], "historical": []}
        r = memory_service.recall(rt, inv, query[:1000], versions)
        summ["memory"]["queries"].append(query[:1000])
        for b in ("applicable", "historical"):
            known = {m["memory_id"] for m in summ["memory"][b]}
            summ["memory"][b] += [m for m in r[b] if m["memory_id"] not in known]
        return {"applicable": [{k: m[k] for k in ("memory_id", "kind", "finding", "signature")} for m in r["applicable"]],
                "historical": [{k: m[k] for k in ("memory_id", "kind", "finding", "inapplicable_reasons")} for m in r["historical"]]}

    if inv["memory_mode"] == "on":
        try:
            h = rt.memory_factory().health()
            if h.get("status") != "ready":
                raise MemoryUnavailable("MEMORY_NOT_READY", f"memory sidecar {h.get('status')}: {h.get('reasons')}")
            if rt.settings.runtime_mode.value == "connected_demo" and not h.get("embedding_profile", {}).get("semantic"):
                raise MemoryUnavailable("MEMORY_NOT_READY", "connected_demo requires a real (semantic) embedding profile")
            summ["memory"]["engine"] = h.get("engine")
            summ["memory"]["embedding_profile"] = h.get("embedding_profile")
        except MemoryUnavailable as e:
            raise AppError(e.code, 503, f"memory-aware investigation blocked: {e}")
    payload = {"question": inv["question"], "focus": scope.focus, "resources": _resource_payload(ctx),
               "ai_usage": ctx["ai_usage"], "ai_duplicate_lookups": ctx["ai_dups"], "federated_rollup": summ["federation"]["rows"]}
    report = call_role(rt, inv, gateway, "investigator", payload, InvestigatorReport, budget,
                       tools=[recall_prior_experiments] if inv["memory_mode"] == "on" else None)
    if inv["memory_mode"] == "on":
        if not summ["memory"]["queries"]:
            recall_prior_experiments(f"prior rejected or failed changes for {inv['service_id']} workers and AI workflow")
        summ["memory"]["status"] = "used"
    summ["investigator"] = json.loads(report.model_dump_json())
    for key in report.series_requests:
        if key in ctx["facts"]:
            _collect_series(rt, inv, summ, key, client)
    summ["rounds"], summ["feedback"] = 0, []


def _resource_payload(ctx: dict) -> list[dict]:
    out = []
    ids = ctx["ids"]
    for k, f in sorted(ctx["facts"].items()):
        out.append({"resource_key": k, "display_name": ctx["inventory"][k]["display_name"], "environment": f.environment,
                    "machine_type": f.machine_type, "family": f.machine_type.split("-")[0], "architecture": f.architecture,
                    "vcpu": str(f.vcpu), "memory_gib": str(f.memory_gib), "stateful": f.stateful or f.local_ssd,
                    "avg_cpu_pct": None if f.avg_cpu_pct is None else str(round(f.avg_cpu_pct, 2)),
                    "peak_cpu_pct": None if f.peak_cpu_pct is None else str(f.peak_cpu_pct),
                    "peak_memory_gib": None if f.peak_memory_bytes is None else str(round(f.peak_memory_bytes / GIB, 2)),
                    "stress_peak_cpu_pct": None if f.stress_peak_cpu_pct is None else str(round(f.stress_peak_cpu_pct, 2)),
                    "cpu_observations": f"{f.cpu_rows}/{f.expected_rows}", "memory_observations": f"{f.memory_rows}/{f.expected_rows}",
                    "last_observed_at": None if f.last_observed_at is None else f.last_observed_at.isoformat(),
                    "usd_per_hour": None if (r := P.current_rate(ctx["prices"], f.machine_type, ctx["as_of"])) is None else str(r),
                    "evidence_ids": [ids["inventory"], ids["telemetry_summary"]] + ([ctx["series_ids"][k]] if k in ctx["series_ids"] else [])})
    return out


def _plans(conn, inv_id) -> list[dict]:
    return conn.execute("SELECT * FROM plans WHERE investigation_id=%s ORDER BY path, candidate_no", (inv_id,)).fetchall()


def _screen_plan(rt, inv, ctx, cand, path):
    if path == "cloud":
        facts = ctx["facts"].get(cand.resource_key)
        mt = next((m for m in ctx["catalog"] if m["machine_type"] == cand.to_machine_type), None)
        target = MachineType(mt["machine_type"], Decimal(mt["vcpu"]), Decimal(mt["memory_gib"]), mt["architecture"]) if mt else None
        action_type = ("AWS_INSTANCE_TYPE_UPDATE" if cand.resource_key.startswith("aws/") else
                       "LOCAL_WORKER_CONFIG_UPDATE" if P.analogue_for(cand.resource_key) else "GCP_MACHINE_TYPE_UPDATE")
        impacts = P.cloud_impacts(facts, mt, ctx["prices"], ctx["carbon"], inv["as_of"], facts.region) if facts and mt else None
        # Economics compares horizon cost over every effective rate interval (audit A05); unknown coverage stays UNKNOWN.
        known = impacts is not None and impacts.get("gross_saving") is not None
        base = Decimal(impacts["baseline_cost"]) / P.HORIZON_HOURS if known else None
        new = Decimal(impacts["candidate_cost"]) / P.HORIZON_HOURS if known else None
        res = screen_cloud(facts, target, ctx["policy"], inv["as_of"], action_type, new, base)
        ev = [ctx["ids"]["inventory"], ctx["ids"]["telemetry_summary"], ctx["ids"]["prices"], ctx["ids"]["policy"]]
        if cand.resource_key in ctx["series_ids"]:
            ev.append(ctx["series_ids"][cand.resource_key])
        return res, impacts, facts, ev
    _, current = P.ai_current(rt)
    res = P.screen_ai(inv, cand.workflow_config, current, ctx["policy"], ctx["ai_usage"], ctx["ai_dups"])
    return res, {"basis": "Measured workload pending", "result_kind": "unknown", "reason": "requires development-suite trial"}, None, \
        [ctx["ids"]["ai_usage_by_run"], ctx["ids"]["ai_duplicate_lookups"], ctx["ids"]["policy"], ctx["ids"]["model_prices"]]


def _memory_failures(summ: dict) -> dict[str, dict]:
    return {m["signature"]: m for m in summ.get("memory", {}).get("applicable", []) if m["kind"] in FAILURE_KINDS and m.get("signature")}


def _remember_rejection(conn, inv, plan_row_id, sig, path, reason, ev, versions, target):
    memory_service.enqueue(conn, tenant_id=inv["tenant_id"], service_id=inv["service_id"], kind="screening_rejection",
                           source_ref=f"plan:{plan_row_id}", finding=reason, evidence_refs=ev, applicability=versions[path],
                           signature=sig, target_id=target)


def _propose_round(rt: Runtime, inv: dict, gateway, budget: Budget) -> bool:
    summ = inv["summary"]
    ctx = context(rt, inv)
    pol = ctx["policy"]
    with connect(rt.db) as c:
        existing = _plans(c, inv["id"])
    used = {p: sum(1 for x in existing if x["path"] == p) for p in ("cloud", "ai")}
    slots = {p: (pol.max_candidates_per_path - used[p]) if p in summ["paths"] else 0 for p in ("cloud", "ai")}
    if not any(v > 0 for v in slots.values()) or summ["rounds"] >= MAX_ROUNDS:
        return False
    summ["rounds"] += 1
    _, ai_cfg = P.ai_current(rt)
    proposed = {x["screening"].get("signature") for x in existing}
    versions = current_versions(rt, inv, ctx)
    mem_fail = _memory_failures(summ)
    payload = {"round": summ["rounds"], "question": inv["question"], "remaining_slots": slots,
               "policy": {"version": pol.version, "cpu_max_utilization": str(pol.cpu_max_utilization),
                          "memory_max_utilization": str(pol.memory_max_utilization), "executable_environments": pol.executable_environments,
                          "frozen_resources": pol.frozen_resources, "unsupported_features": pol.unsupported_features},
               "resources": _resource_payload(ctx),
               "machine_catalog": [{**m, "usd_per_hour": str(P.current_rate(ctx["prices"], m["machine_type"], inv["as_of"]) or "")}
                                   for m in ctx["catalog"] if P.current_rate(ctx["prices"], m["machine_type"], inv["as_of"]) is not None],
               "ai_current_config": ai_cfg.model_dump(mode="json") if "ai" in summ["paths"] else None,
               "ai_usage": ctx["ai_usage"], "ai_duplicate_lookups": ctx["ai_dups"], "ai_evidence_ids": [ctx["ids"]["ai_usage_by_run"]],
               "memory": [{k: m[k] for k in ("memory_id", "kind", "finding", "signature", "applicable")} for m in summ["memory"]["applicable"]]
                         + [{**{k: m[k] for k in ("memory_id", "kind", "finding", "signature")}, "applicable": False,
                             "inapplicable_reasons": m["inapplicable_reasons"]} for m in summ["memory"]["historical"]],
               "feedback": summ["feedback"], "proposed_signatures": sorted(s for s in proposed if s)}
    proposal = call_role(rt, inv, gateway, "optimizer", payload, OptimizerProposal, budget)
    new_ids = []
    for cand in proposal.candidates:
        path = cand.path
        sig = P.cloud_signature(cand.resource_key, cand.to_machine_type) if path == "cloud" else P.ai_signature(cand.workflow_config)
        if slots[path] <= 0 or sig in proposed:
            event(rt, inv["id"], "candidate.discarded", "application", {"signature": sig, "reason": "over cap" if slots[path] <= 0 else "duplicate"})
            continue
        slots[path] -= 1
        proposed.add(sig)
        cno = used[path] + 1
        used[path] += 1
        res, impacts, facts, ev = _screen_plan(rt, inv, ctx, cand, path)
        if path == "cloud" and facts is None:
            res, impacts = ScreeningResult("REJECTED", [Check("CHK-IDENTITY", "FAIL", f"{cand.resource_key} not in inventory")]), None
        memory_refs = []
        if sig in mem_fail:  # deterministic memory guard: an applicable prior failure under identical versions
            m = mem_fail[sig]
            res = ScreeningResult("REJECTED", [Check("MEM-PRIOR-FAILURE", "FAIL",
                  f"skipped repeating candidate: memory {m['memory_id']} ({m['kind']}) already failed under the same policy/workload/config versions")] + res.checks)
            memory_refs = [m["memory_id"]]
        if facts is None and path == "cloud":  # unknown target: consumes the slot, never becomes a plan
            event(rt, inv["id"], "candidate.rejected", "application", {"signature": sig, "reason": "CHK-IDENTITY: target not in inventory"})
            summ["feedback"].append({"signature": sig, "outcome": "REJECTED", "reasons": "CHK-IDENTITY: target not in inventory"})
            continue
        core = P.build_core(rt, inv, path, cno, 1, cand, facts, ev)
        with connect(rt.db) as c:
            row = P.insert_plan(c, core, candidate_no=cno, status="REJECTED" if res.outcome == "REJECTED" else "DRAFT",
                                screening=res.as_dict(), impacts=impacts, rationale=cand.rationale, memory_refs=memory_refs, signature=sig)
            append_event(c, inv["id"], "plan.proposed", "agent:optimizer", {"plan_id": str(row["id"]), "signature": sig, "screening": res.outcome,
                         "plan_hash": row["plan_hash"], "memory_refs": memory_refs})
        new_ids.append(row["id"])
    revise = _critic_pass(rt, inv, gateway, budget, ctx, new_ids, versions)
    return revise


def _critic_pass(rt, inv, gateway, budget, ctx, plan_ids, versions, depth: int = 0) -> bool:
    if not plan_ids:
        return False
    summ = inv["summary"]
    with connect(rt.db) as c:
        rows = [c.execute("SELECT * FROM plans WHERE id=%s", (pid,)).fetchone() for pid in plan_ids]
    payload = {"candidates": [{"candidate_ref": str(r["id"]), "path": r["path"], "signature": r["screening"].get("signature"),
                               "resource_key": (r["core"].get("projection") or {}).get("resource_key"), "checks": r["screening"]["checks"],
                               "screening_outcome": r["screening"]["outcome"], "evidence_ids": r["core"]["evidence_ids"],
                               "impacts": r["impacts"]} for r in rows]}
    review = call_role(rt, inv, gateway, "critic", payload, CriticReview, budget)
    verdicts = {rv.candidate_ref: rv for rv in review.reviews}
    revise, rescreen = False, []
    for r in rows:
        rv = verdicts.get(str(r["id"]))
        sig, outcome = r["screening"].get("signature"), r["screening"]["outcome"]
        real_checks = {k["check_id"] for k in r["screening"]["checks"]}
        critic = json.loads(rv.model_dump_json()) if rv else {"verdict": "MISSING", "note": "critic returned no review"}
        if rv and rv.verdict == "VALIDATED" and (outcome != "ELIGIBLE_FOR_TRIAL" or not set(rv.check_ids) & real_checks):
            critic["enforcement"] = "critic VALIDATED overridden: deterministic checks did not all pass or no real check cited"
        status, reason = r["status"], None
        if outcome == "REJECTED":
            status = "REJECTED"
            reason = "; ".join(f"{k['check_id']}: {k['detail']}" for k in r["screening"]["checks"] if k["status"] == "FAIL")
            if rv and rv.verdict == "REVISE":
                revise = True
        elif outcome == "NEEDS_EVIDENCE":
            key = (r["core"].get("projection") or {}).get("resource_key")
            asks_series = rv and any(e.template_id == "telemetry_series" for e in rv.evidence_requests)
            stress_unknown = any(k["check_id"] == "CHK-CPU-STRESS" and k["status"] == "UNKNOWN" for k in r["screening"]["checks"])
            if depth == 0 and key and (asks_series or stress_unknown) and key not in ctx["series_ids"]:
                _collect_series(rt, inv, summ, key)
                rescreen.append(r)
                continue
            status = "NEEDS_EVIDENCE"
            reason = "; ".join(f"{k['check_id']}: {k['detail']}" for k in r["screening"]["checks"] if k["status"] == "UNKNOWN")
        else:  # eligible for trial
            if rv and rv.verdict == "VALIDATED" and set(rv.check_ids) & real_checks:
                status = "DRAFT"
            elif rv and rv.verdict == "NEEDS_EVIDENCE" and not [e for e in rv.evidence_requests
                                                                 if r["path"] == "cloud" and e.resource_key in ctx["facts"]
                                                                 and e.resource_key not in ctx["series_ids"]]:
                # Every deterministic check passed and the critic named no fetchable data (live critics also ask for
                # telemetry_series of resource "ai", which does not exist): the evidence it wants is the matched trial.
                status = "DRAFT"
                critic["enforcement"] = "NEEDS_EVIDENCE without a data request on a screened-eligible candidate: the trial is that evidence"
            else:
                status, reason = "REJECTED", f"critic {critic['verdict']}: {critic.get('note', '')}"
                if rv and rv.verdict == "REVISE":
                    revise = True
        with connect(rt.db) as c:
            c.execute("UPDATE plans SET status=%s, critic=%s, updated_at=now() WHERE id=%s", (status, J(critic), r["id"]))
            append_event(c, inv["id"], "plan.reviewed", "agent:critic", {"plan_id": str(r["id"]), "status": status, "critic": critic, "reason": reason})
            if status == "REJECTED" and outcome == "REJECTED" and inv["memory_mode"] == "on" and not r["memory_refs"]:
                _remember_rejection(c, inv, r["id"], sig, r["path"], f"Rejected candidate {sig} under policy {inv['policy_version']}: {reason}",
                                    r["core"]["evidence_ids"], versions, r["target_key"])
        if status in ("REJECTED", "NEEDS_EVIDENCE"):
            summ["feedback"].append({"signature": sig, "outcome": status, "reasons": reason})
    save_summary(rt, inv["id"], summ)
    if rescreen:
        inv["summary"] = summ
        ctx2 = context(rt, inv)
        ids = []
        for r in rescreen:
            proj = r["core"]["projection"]
            cand = CloudCandidate(resource_key=proj["resource_key"], to_machine_type=proj["to_machine_type"], rationale=r["rationale"] or "", evidence_ids=[])
            res, impacts, facts, ev = _screen_plan(rt, inv, ctx2, cand, "cloud")
            core = P.build_core(rt, inv, "cloud", r["candidate_no"], r["revision"] + 1, cand, facts, ev)
            with connect(rt.db) as c:
                row = P.insert_plan(c, core, candidate_no=r["candidate_no"], status="REJECTED" if res.outcome == "REJECTED" else "DRAFT",
                                    screening={**res.as_dict(), "signature": r["screening"]["signature"]}, impacts=impacts,
                                    rationale=r["rationale"], memory_refs=[], signature=r["screening"]["signature"], plan_id=r["id"])
                append_event(c, inv["id"], "plan.rescreened", "application", {"plan_id": str(r["id"]), "reason": "evidence request: telemetry_series",
                             "screening": res.outcome, "plan_hash": row["plan_hash"], "revision": r["revision"] + 1})
            ids.append(r["id"])
        revise = _critic_pass(rt, inv, gateway, budget, ctx2, ids, versions, depth=1) or revise
    return revise


def suite_for(plan: dict) -> str:
    return "support-dev-v1" if plan["path"] == "ai" else "aws-canary-v1" if plan["core"]["executor"] == "aws" else "workload-wl-v1"


def _dispatch_trials(rt: Runtime, inv: dict) -> int:
    if not inv["trial_profile_id"]:
        return 0
    n = 0
    with connect(rt.db) as c:
        for p in _plans(c, inv["id"]):
            if p["status"] != "DRAFT" or p["core"]["executor"] == "none":
                continue
            if c.execute("SELECT 1 FROM trials WHERE plan_id=%s AND plan_hash=%s", (p["id"], p["plan_hash"])).fetchone():
                continue
            from greenops.services.trials import create_trial
            create_trial(c, rt, p, inv["trial_profile_id"], inv["actor_id"], suite_for(p))
            n += 1
    return n


def finalize(rt: Runtime, inv_id) -> str:
    with connect(rt.db) as c:
        inv = load(c, inv_id)
        ps = _plans(c, inv_id)
        st = [p["status"] for p in ps]
        if any(s in ("AWAITING_APPROVAL", "APPROVED") for s in st):
            status = "AWAITING_APPROVAL"
        elif any(s in ("DRAFT", "NEEDS_EVIDENCE", "VALIDATED") for s in st):
            status = "NEEDS_REVIEW"
        else:
            status = "NO_CHANGE"
        reasons = [{"plan_id": str(p["id"]), "signature": p["screening"].get("signature"), "status": p["status"],
                    "executable": p["core"]["executor"] != "none"} for p in ps]
        summ = {**inv["summary"], "outcome": {"status": status, "plans": reasons, "decided_at": now().isoformat()}}
        c.execute("UPDATE investigations SET status=%s, stage='DONE', summary=%s, updated_at=now() WHERE id=%s", (status, J(summ), inv_id))
        append_event(c, inv_id, "investigation.finalized", "application", {"status": status, "plans": reasons})
    return status


def advance(rt: Runtime, inv_id) -> str:
    with connect(rt.db) as c:
        inv = load(c, inv_id)
        if inv["status"] in TERMINAL:
            return inv["status"]
        if inv["cancel_requested"]:
            c.execute("UPDATE investigations SET status='CANCELLED', updated_at=now() WHERE id=%s", (inv_id,))
            append_event(c, inv_id, "investigation.cancelled", "application", {"note": "stopped at a safe stage boundary"})
            return "CANCELLED"
        c.execute("UPDATE investigations SET status='RUNNING', updated_at=now() WHERE id=%s", (inv_id,))
    inv["status"] = "RUNNING"
    gateway = rt.model_factory()
    budget = budget_for(rt, inv)
    try:
        if inv["stage"] == "SCOPE":
            event(rt, inv_id, "stage.entered", "application", {"stage": "SCOPE"})
            _scope(rt, inv, gateway, budget)
            save_summary(rt, inv_id, inv["summary"], stage="PROPOSE")
            inv["stage"] = "PROPOSE"
        if inv["stage"] == "PROPOSE":
            event(rt, inv_id, "stage.entered", "application", {"stage": "PROPOSE"})
            while _propose_round(rt, inv, gateway, budget):
                with connect(rt.db) as c:
                    if load(c, inv_id)["cancel_requested"]:
                        break
            with connect(rt.db) as c:
                inv["summary"] = load(c, inv_id)["summary"]
            dispatched = _dispatch_trials(rt, inv)
            save_summary(rt, inv_id, inv["summary"], stage="TRIALS" if dispatched else "FINALIZE")
            inv["stage"] = "TRIALS" if dispatched else "FINALIZE"
            if dispatched:
                event(rt, inv_id, "stage.entered", "application", {"stage": "TRIALS", "trials": dispatched})
                return "RUNNING"
        if inv["stage"] == "TRIALS":
            with connect(rt.db) as c:
                pending = c.execute("SELECT COUNT(*) AS n FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s "
                                    "AND t.status IN ('QUEUED','RUNNING')", (inv_id,)).fetchone()["n"]
                failed_since = c.execute("SELECT COUNT(*) AS n FROM plans WHERE investigation_id=%s AND status='REJECTED' AND critic ? 'trial'",
                                         (inv_id,)).fetchone()["n"]
            if pending:
                return "RUNNING"
            if failed_since > inv["summary"].get("trial_failures_seen", 0) and inv["summary"]["rounds"] < MAX_ROUNDS:
                inv["summary"]["trial_failures_seen"] = failed_since
                save_summary(rt, inv_id, inv["summary"], stage="PROPOSE")
                inv["stage"] = "PROPOSE"
                return advance(rt, inv_id)
            inv["stage"] = "FINALIZE"
        return finalize(rt, inv_id)
    except BudgetExceeded as e:
        event(rt, inv_id, "budget.exhausted", "application", {"reason": str(e)})
        return finalize_with(rt, inv_id, "NEEDS_REVIEW", "BUDGET_EXCEEDED", str(e))
    except (AppError, ModelError, DomainError, MemoryUnavailable) as e:
        code = getattr(e, "code", "INTERNAL_ERROR")
        event(rt, inv_id, "investigation.failed", "application", {"code": code, "message": str(e)[:500]})
        return finalize_with(rt, inv_id, "FAILED", code, str(e))
    except Exception as e:  # never leave an investigation silently RUNNING; the job log keeps the traceback
        code = "INTERNAL_ERROR"
        import logging, traceback
        logging.getLogger("greenops.investigation").error("investigation %s crashed:\n%s", inv_id, traceback.format_exc())
        event(rt, inv_id, "investigation.failed", "application", {"code": code, "message": str(e)[:500]})
        return finalize_with(rt, inv_id, "FAILED", code, str(e))


def finalize_with(rt: Runtime, inv_id, status: str, code: str, message: str) -> str:
    with connect(rt.db) as c:
        inv = load(c, inv_id)
        summ = {**inv["summary"], "outcome": {"status": status, "error": {"code": code, "message": message[:500]}, "decided_at": now().isoformat()}}
        c.execute("UPDATE investigations SET status=%s, stage='DONE', summary=%s, updated_at=now() WHERE id=%s", (status, J(summ), inv_id))
    return status
