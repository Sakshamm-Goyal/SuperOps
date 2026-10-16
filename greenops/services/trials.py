"""Trials: matched local workload pairs on disposable fixtures, and AI development-suite paired runs.

A trial may only mutate fixtures named in an operator-approved trial profile; it never touches the final
action target. Holdout suites are not reachable from here (only `support-dev-v1` maps to a directory).
"""
from __future__ import annotations

import json
import math
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from statistics import median

from greenops.adapters.model import BudgetExceeded
from greenops.adapters.sandbox import LocalWorker, VersionConflict, load_workload, run_workload
from experiments.support.workflow import CancelledRun
from greenops.agents.roles import CriticReview
from greenops.config import ROOT
from greenops.db import J, connect
from greenops.domain import accounting as acc
from greenops.domain.models import AiWorkflowConfig, ServicePolicy
from greenops.domain.quantities import canonical_hash
from greenops.services import investigation as I, memory_service, plans as P
from greenops.services.common import AppError, Runtime, acquire_slot, append_event, enqueue, event, now, release_slot

DEV_SUITES = {"support-dev-v1": ROOT / "experiments" / "support" / "dev"}
MAX_SCHEDULE_LAG_MS = 10  # p95 send lag: ~2× the manifest's 5 ms jitter bound
MAX_BURST_LAG_MS = 25  # max send lag; beyond this, delayed requests bunch into bursts the manifest does not contain
MAX_PAIR_REMEASURES = 4


def load_profile(conn, profile_id: str, tenant_id: str) -> dict:
    p = conn.execute("SELECT * FROM trial_profiles WHERE id=%s AND tenant_id=%s", (profile_id, tenant_id)).fetchone()
    if p is None:
        raise AppError("NOT_FOUND", 404, "trial profile not found")
    if p["status"] != "ACTIVE" or p["expires_at"] <= now():
        raise AppError("INVALID_STATE", 409, "trial profile is not active or has expired")
    if canonical_hash(p["document"]) != p["profile_hash"]:
        raise AppError("INVALID_STATE", 409, "trial profile document changed after approval; re-approve it")
    return p


def create_trial(conn, rt: Runtime, plan: dict, profile_id: str, actor_id: str, suite_id: str) -> uuid.UUID:
    prof = load_profile(conn, profile_id, plan["tenant_id"])
    doc = prof["document"]
    if plan["target_key"] in doc["local_worker_pair"]["fixtures"]:
        raise AppError("FORBIDDEN", 403, "a trial fixture can never be the plan's action target")
    if plan["path"] == "ai":
        if suite_id not in doc["ai_dev_suite"]["allowed_suites"] or suite_id not in DEV_SUITES:
            raise AppError("VALIDATION_ERROR", 422, "only allowlisted development suites can be trialled")
    elif plan["core"]["action"]["action_type"] != "LOCAL_WORKER_CONFIG_UPDATE":
        raise AppError("UNSUPPORTED_ACTION", 422, "no trial fixture exists for this action type")
    tid = uuid.uuid4()
    conn.execute("INSERT INTO trials (id, plan_id, tenant_id, service_id, actor_id, plan_hash, trial_profile_id, suite_id, status) "
                 "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'QUEUED')",
                 (tid, plan["id"], plan["tenant_id"], plan["service_id"], actor_id, plan["plan_hash"], profile_id, suite_id))
    enqueue(conn, "trial", tid)
    I.append_event(conn, plan["investigation_id"], "trial.queued", actor_id, {"trial_id": str(tid), "plan_id": str(plan["id"]), "suite_id": suite_id})
    return tid


def cancelled(rt: Runtime, trial: dict) -> bool:
    with connect(rt.db) as c:
        r = c.execute("SELECT i.cancel_requested, i.status FROM plans p JOIN investigations i ON i.id=p.investigation_id WHERE p.id=%s",
                      (trial["plan_id"],)).fetchone()
    return bool(r["cancel_requested"]) or r["status"] == "CANCELLED"


def optimizer_overhead(conn, inv: dict) -> tuple[Decimal | None, str | None]:
    """Role-model cost of this investigation at the evidenced model rate, counted once; unknown if any usage is missing."""
    rows = conn.execute("SELECT input_tokens, output_tokens FROM model_calls WHERE investigation_id=%s", (inv["id"],)).fetchall()
    if any(r["input_tokens"] is None or r["output_tokens"] is None for r in rows):
        return None, "role-model usage not reported (scripted sample or provider omitted usage)"
    mp = conn.execute("SELECT data FROM evidence WHERE id::text=%s", (inv["summary"]["evidence"]["model_prices"],)).fetchone()["data"]["rows"][0]
    total, _ = acc.ai_run_cost([{"input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"]} for r in rows],
                               acc.TokenRates(Decimal(mp["input_per_million"]), Decimal(mp["output_per_million"]), mp["currency"]))
    return total, None


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 4), round(c + h, 4)


def _set_fixture(rt, fixture_id: str, mc: int, allowed: dict, writer: str = "trial") -> dict:
    if not allowed["min"] <= mc <= allowed["max"]:
        raise AppError("FORBIDDEN", 403, f"max_concurrency {mc} outside the trial profile range")
    w = LocalWorker(rt.settings.sandbox_dir, fixture_id)
    cur = w.store.read()
    if cur["max_concurrency"] != mc:
        w.store.compare_and_set(cur["version"], {"max_concurrency": mc}, writer=writer)
    st = w.reload()
    if st["loaded_config"]["max_concurrency"] != mc:
        raise AppError("TRIAL_NOT_ACCEPTED", 422, "fixture did not load the trial configuration")
    return st


def _cloud_trial(rt: Runtime, trial: dict, plan: dict, doc: dict, policy: ServicePolicy) -> dict:
    lp = doc["local_worker_pair"]
    a_id, b_id = lp["fixtures"]
    act = plan["core"]["action"]
    allowed = lp["allowed_operations"][0]
    workload, wl_hash = load_workload()
    started = time.time()
    tw = f"trial:{trial['id']}"
    a_st = _set_fixture(rt, a_id, act["before"]["max_concurrency"], allowed, tw)
    b_st = _set_fixture(rt, b_id, act["after"]["max_concurrency"], allowed, tw)
    A, B = LocalWorker(rt.settings.sandbox_dir, a_id), LocalWorker(rt.settings.sandbox_dir, b_id)
    runs, discarded = [], []
    pair_complete = True
    try:
        run_workload(A, lp["warmup_s"], "warmup-a")
        run_workload(B, lp["warmup_s"], "warmup-b")
        for i, order in enumerate(["AB", "BA", "AB"][: lp["pairs"]]):
            for attempt in range(1 + MAX_PAIR_REMEASURES):
                pair = []
                for side in order:
                    if time.time() - started > min(lp["max_seconds"], rt.settings.max_trial_seconds):
                        raise TimeoutError("trial wall-clock cap reached")
                    if cancelled(rt, trial):
                        raise CancelledRun("investigation cancelled at a safe boundary")
                    r = run_workload(A if side == "A" else B, lp["measure_s"], f"pair{i}-{side}-{attempt}")
                    pair.append({"pair": i, "attempt": attempt, "side": "baseline" if side == "A" else "candidate", **r})
                # Offered-load fidelity: a window whose load generator fell behind schedule did not deliver the manifest's
                # workload, so the pair is non-comparable and re-measured (bounded, recorded) — never judged.
                if all((w["schedule_lag_p95_ms"] or 0) <= MAX_SCHEDULE_LAG_MS and (w["schedule_lag_max_ms"] or 0) <= MAX_BURST_LAG_MS for w in pair):
                    runs.extend(pair)
                    break
                discarded.extend({k: v for k, v in w.items() if k not in ("latencies_ms", "server_latencies_ms")} for w in pair)
            else:
                pair_complete = False
    finally:
        for f in (a_id, b_id):
            try:
                _set_fixture(rt, f, lp["reset"]["max_concurrency"], allowed, f"{tw}:reset")
            except Exception:
                pass  # reset failure is visible via fixture status; the trial result below remains authoritative
    base = [r for r in runs if r["side"] == "baseline"]
    cand = [r for r in runs if r["side"] == "candidate"]
    if not base or not cand:  # no comparable pair at all: the instrument failed; never judge the candidate
        return {"kind": "local_worker_pair", "executor": "local_analogue", "result_kind": "measured", "data_origin": "synthetic",
                "outcome": "INCOMPLETE", "summary": {"discarded_windows": discarded},
                "checks": [{"check_id": "TRIAL-COMPARABLE", "status": "FAIL", "detail": "no window delivered the manifest's offered load"}],
                "experiment_cost": {"amount": "0", "currency": "USD", "basis": "local compute, not billed"}}
    # Pooled p95 over every completed request per side, plus per-pair consistency (protocol amendment 17 Oct 2026):
    # one noisy short window can neither pass nor fail the gate on its own.
    # Gate metric: server-side latency (queue wait + delivered service) — what a concurrency limit changes. Client-observed
    # latency includes the in-process load generator's own scheduling noise; it is reported but does not decide.
    pooled = lambda rs: sorted(x for r in rs for x in r["server_latencies_ms"])
    pooled_client = lambda rs: sorted(x for r in rs for x in r["latencies_ms"])
    pb, pc = pooled(base), pooled(cand)
    q = lambda xs: xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))] if xs else None
    bp95, cp95 = q(pb), q(pc)
    bfail, cfail = sum(r["failures"] for r in base), sum(r["failures"] for r in cand)
    comparable = (pair_complete and len({r["offered"] for r in runs}) == 1
                  and all(r["config_hashes_seen"] == [b_st["loaded_config_hash"]] for r in cand))
    limit = Decimal(str(bp95)) * (1 + policy.workload.p95_regression_max)
    pair_ratios = []
    for i in sorted({r["pair"] for r in runs}):
        bpp = next(r["server_p95_ms"] for r in base if r["pair"] == i)
        cpp = next(r["server_p95_ms"] for r in cand if r["pair"] == i)
        pair_ratios.append(None if not bpp or cpp is None else round(cpp / bpp, 4))
    pairs_over = sum(1 for x in pair_ratios if x is None or Decimal(str(x)) > 1 + policy.workload.p95_regression_max)
    regression = cp95 is None or (Decimal(str(cp95)) > limit and pairs_over * 2 > len(pair_ratios))
    client_b, client_c = q(pooled_client(base)), q(pooled_client(cand))
    for r in runs:
        r.pop("latencies_ms", None)
        r.pop("server_latencies_ms", None)
    checks = [
        {"check_id": "TRIAL-COMPARABLE", "status": "PASS" if comparable else "FAIL",
         "detail": f"identical offered load (schedule lag p95 ≤ {MAX_SCHEDULE_LAG_MS} ms in every judged window; {len(discarded)} non-comparable "
                   f"windows re-measured); candidate fixture served the candidate config hash"},
        {"check_id": "TRIAL-NO-NEW-FAILURES", "status": "PASS" if cfail <= bfail else "FAIL", "detail": f"candidate failures {cfail} vs baseline {bfail}"},
        {"check_id": "TRIAL-P95-REGRESSION", "status": "FAIL" if regression else "PASS",
         "detail": f"pooled server-side candidate p95 {cp95 and round(cp95, 1)} ms vs limit {round(limit, 1)} ms (baseline {round(bp95, 1)} ms "
                   f"+{policy.workload.p95_regression_max:%}, n={len(pc)}/{len(pb)}); pairs over limit {pairs_over}/{len(pair_ratios)}, ratios {pair_ratios}"},
        {"check_id": "TRIAL-P95-SLO", "status": "PASS" if client_c is not None and client_c <= policy.workload.slo_p95_ms else "FAIL",
         "detail": f"client-observed candidate p95 {client_c and round(client_c, 1)} ms vs SLO {policy.workload.slo_p95_ms} ms (SLO judged end-to-end)"}]
    outcome = "PASSED" if all(c["status"] == "PASS" for c in checks) else ("INCOMPLETE" if not comparable else "FAILED")
    return {"kind": "local_worker_pair", "executor": "local_analogue", "result_kind": "measured", "data_origin": "synthetic",
            "workload": {"id": workload["workload_id"], "version": workload["version"], "hash": wl_hash},
            "fixtures": {"baseline": {"id": a_id, "config_hash": a_st["loaded_config_hash"]}, "candidate": {"id": b_id, "config_hash": b_st["loaded_config_hash"]}},
            "runs": runs, "summary": {"baseline_p95_ms": bp95, "candidate_p95_ms": cp95, "baseline_failures": bfail, "candidate_failures": cfail,
                        "pooled_samples": {"baseline": len(pb), "candidate": len(pc)}, "pair_p95_ratios": pair_ratios,
                        "client_p95_ms": {"baseline": client_b, "candidate": client_c},
                        "method": "pooled p95 + majority of paired windows; windows with load-generator lag re-measured (amendment 2026-10-17)",
                        "discarded_windows": discarded},
            "checks": checks, "outcome": outcome, "limitations": ["local analogue: proves a local concurrency change, not a GCP VM resize",
            "short matched trial; not a long-term SLA"], "experiment_cost": {"amount": "0", "currency": "USD", "basis": "local compute, not billed"}}


def _ai_cost(results: list[dict], rates: acc.TokenRates) -> tuple[Decimal | None, Decimal, str]:
    from experiments.support.workflow import TOOL_COST_USD
    calls = [{"input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"], "tool_cost": Decimal(TOOL_COST_USD) * r["tool_calls"]} for r in results]
    total, completeness = acc.ai_run_cost(calls, rates)
    basis = {r["usage_basis"] for r in results}
    return total, completeness, "provider" if basis == {"provider"} else ("scripted_estimate" if "scripted_estimate" in basis else "incomplete")


def _ai_trial(rt: Runtime, trial: dict, plan: dict, doc: dict, policy: ServicePolicy, inv: dict) -> dict:
    from experiments.support.verifier import VERIFIER_VERSION, SupportDecision, verify
    from experiments.support.workflow import config_hash, load_suite, run_suite
    from greenops.services.budget import DurableBudget, investigation_limits
    cases, records = load_suite(DEV_SUITES[trial["suite_id"]])
    gateway = rt.model_factory()
    ai = doc["ai_dev_suite"]
    inv_lim = investigation_limits(inv)
    # Profile limits bind this trial; the investigation cap and daily cap still apply (audit A08).
    budget = DurableBudget(rt.db, investigation_id=inv["id"], trial_id=trial["id"], parent_limits=inv_lim, daily_cap_usd=rt.settings.max_daily_cost_usd,
                           limits={"max_calls": ai["max_model_calls"], "max_cost_usd": ai["max_cost_usd"], "per_call_usd": inv_lim["per_call_usd"]},
                           deadline=now() + timedelta(seconds=min(int(ai["max_seconds"]), rt.settings.max_trial_seconds)))
    with connect(rt.db) as c:
        mp = c.execute("SELECT data FROM evidence WHERE id::text=%s", (inv["summary"]["evidence"]["model_prices"],)).fetchone()["data"]["rows"][0]
    rates = acc.TokenRates(Decimal(mp["input_per_million"]), Decimal(mp["output_per_million"]), mp["currency"])
    act = plan["core"]["action"]
    out = {}
    for label, cfgd in (("baseline", act["before"]), ("candidate", act["after"])):
        cfg = AiWorkflowConfig(**cfgd)
        cached = inv["summary"].get("ai_baseline_cache", {}).get(config_hash(cfg) + "|" + gateway.model_id) if label == "baseline" else None
        if cached:
            out[label] = cached
            continue
        t0 = time.perf_counter()

        def persist_case(r, label=label):  # usage persisted as each case completes, even if a later case breaks the budget
            with connect(rt.db) as c:
                c.execute("INSERT INTO model_calls (id, investigation_id, trial_id, role, model_id, runtime_mode, status, input_tokens, output_tokens, "
                          "tool_calls, requests, duration_ms, error_code) VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (uuid.uuid4(), trial["id"], f"support:{label}", gateway.model_id, rt.settings.runtime_mode.value,
                           "ok" if r["error"] is None else "error", r["input_tokens"], r["output_tokens"], r["tool_calls"],
                           max(1, r["model_requests"]), r["latency_ms"], r["error"]))
        results = run_suite(gateway, cases, records, cfg, budget, on_case=persist_case, should_stop=lambda: cancelled(rt, trial))
        verdicts = [verify(cs, records, SupportDecision(**r["output"]) if r["output"] else None) for cs, r in zip(cases, results)]
        total, completeness, basis = _ai_cost(results, rates)
        accepted = sum(v["accepted"] for v in verdicts)
        out[label] = {"config": cfgd, "config_hash": config_hash(cfg), "model_id": gateway.model_id, "cases": len(cases), "accepted": accepted,
                      "critical_failures": sum(v["critical_failure"] for v in verdicts), "wilson_95": wilson(accepted, len(cases)),
                      "by_category": {k: {"accepted": sum(1 for v in verdicts if v["category"] == k and v["accepted"]),
                                          "total": sum(1 for v in verdicts if v["category"] == k)} for k in sorted({v["category"] for v in verdicts})},
                      "input_tokens": sum(r["input_tokens"] or 0 for r in results), "output_tokens": sum(r["output_tokens"] or 0 for r in results),
                      "model_requests": sum(r["model_requests"] for r in results), "tool_calls": sum(r["tool_calls"] for r in results),
                      "deduped_lookups": sum(r["deduped_lookups"] for r in results), "errors": sum(1 for r in results if r["error"]),
                      "latency_ms_p50": median(r["latency_ms"] for r in results), "latency_ms_max": max(r["latency_ms"] for r in results),
                      "total_cost_usd": None if total is None else str(total), "usage_completeness": str(completeness), "usage_basis": basis,
                      "cost_per_accepted_usd": None if (cpa := acc.cost_per_accepted(total, accepted)) is None else str(cpa),
                      "per_case": [{"case_id": v["case_id"], "category": v["category"], "accepted": v["accepted"], "critical": v["critical_failure"],
                                    "checks": v["checks"], "expected": v["expected"], "observed": v.get("observed")} for v in verdicts],
                      "wall_ms": int((time.perf_counter() - t0) * 1000)}
        if label == "baseline":
            inv["summary"].setdefault("ai_baseline_cache", {})[out[label]["config_hash"] + "|" + gateway.model_id] = out[label]
            I.save_summary(rt, inv["id"], inv["summary"])
    b, cnd = out["baseline"], out["candidate"]
    bpass = {p["case_id"] for p in b["per_case"] if p["accepted"]}
    cpass = {p["case_id"] for p in cnd["per_case"] if p["accepted"]}
    regressions = sorted(bpass - cpass)
    cpa_b, cpa_c = b["cost_per_accepted_usd"], cnd["cost_per_accepted_usd"]
    cost_ok = cpa_b is not None and cpa_c is not None and Decimal(cpa_c) < Decimal(cpa_b) and b["usage_basis"] == cnd["usage_basis"] != "incomplete"
    checks = [
        {"check_id": "AI-QUALITY-GATE", "status": "PASS" if cnd["accepted"] >= policy.ai.min_accepted else "FAIL",
         "detail": f"candidate accepted {cnd['accepted']}/{cnd['cases']} (gate {policy.ai.min_accepted}/{policy.ai.total_cases}); baseline {b['accepted']}/{b['cases']}"},
        {"check_id": "AI-ZERO-CRITICAL", "status": "PASS" if cnd["critical_failures"] == 0 else "FAIL", "detail": f"{cnd['critical_failures']} critical failures"},
        {"check_id": "AI-NO-REGRESSION", "status": "PASS" if not regressions else "FAIL", "detail": f"baseline-pass→candidate-fail: {regressions or 'none'}"},
        {"check_id": "AI-COST-PER-ACCEPTED", "status": "PASS" if cost_ok else "FAIL",
         "detail": f"cost/accepted {cpa_c} vs baseline {cpa_b} USD ({cnd['usage_basis']} usage)"}]
    disc = {"both_pass": len(bpass & cpass), "baseline_only": len(bpass - cpass), "candidate_only": len(cpass - bpass),
            "neither": b["cases"] - len(bpass | cpass)}
    quality_ok = all(c["status"] == "PASS" for c in checks[:3])
    outcome = "PASSED" if quality_ok and cost_ok else "FAILED"
    reduction = None
    if cpa_b and cpa_c and Decimal(cpa_b) > 0:
        reduction = str(((Decimal(cpa_b) - Decimal(cpa_c)) / Decimal(cpa_b)).quantize(Decimal("0.0001")))
    return {"kind": "ai_dev_suite", "suite_id": trial["suite_id"], "verifier": VERIFIER_VERSION, "result_kind": "measured", "data_origin": "synthetic",
            "baseline": b, "candidate": cnd, "paired_discordance": disc, "checks": checks, "outcome": outcome,
            "quality_passed_cost_not_improved": quality_ok and not cost_ok, "cost_per_accepted_reduction": reduction,
            "efficiency_aspiration_met": reduction is not None and Decimal(reduction) >= policy.ai.efficiency_aspiration,
            "cost_basis": f"tokens × synthetic catalogue-equivalent rate ({mp['price_basis']}); provider billing not observed",
            "limitations": ["40 development cases: a small local evaluation, not broad reliability proof",
                            "development suite; final selection requires the locked holdout evaluation"]}


def run(rt: Runtime, trial_id) -> str:
    with connect(rt.db) as c:
        trial = c.execute("SELECT * FROM trials WHERE id=%s", (trial_id,)).fetchone()
        if trial["status"] not in ("QUEUED", "RUNNING"):
            return trial["status"]
        plan = c.execute("SELECT * FROM plans WHERE id=%s", (trial["plan_id"],)).fetchone()
        inv = I.load(c, plan["investigation_id"])
        prof = load_profile(c, trial["trial_profile_id"], trial["tenant_id"])
        if trial["plan_hash"] != plan["plan_hash"]:
            c.execute("UPDATE trials SET status='CANCELLED', result=%s, finished_at=now() WHERE id=%s", (J({"reason": "PLAN_CHANGED"}), trial_id))
            return "CANCELLED"
        if inv["cancel_requested"] or inv["status"] == "CANCELLED":  # audit A13: no fixture or model work after cancellation
            c.execute("UPDATE trials SET status='CANCELLED', result=%s, finished_at=now() WHERE id=%s",
                      (J({"reason": "INVESTIGATION_CANCELLED", "work_started": False}), trial_id))
            append_event(c, inv["id"], "trial.cancelled", "application", {"trial_id": str(trial_id), "reason": "investigation cancelled"})
            enqueue(c, "investigation", inv["id"])
            return "CANCELLED"
        mutating = plan["path"] == "cloud"
        if mutating and not acquire_slot(c, "trial", trial_id):
            return "WAITING_FOR_SLOT"
        c.execute("UPDATE trials SET status='RUNNING', started_at=COALESCE(started_at, now()) WHERE id=%s", (trial_id,))
    policy = I.context(rt, inv)["policy"]
    try:
        result = _cloud_trial(rt, trial, plan, prof["document"], policy) if mutating else _ai_trial(rt, trial, plan, prof["document"], policy, inv)
    except BudgetExceeded as e:
        result = {"outcome": "INCOMPLETE", "checks": [{"check_id": "BUDGET", "status": "FAIL", "detail": str(e)}]}
    except CancelledRun as e:
        result = {"outcome": "CANCELLED", "checks": [{"check_id": "CANCELLED", "status": "FAIL", "detail": str(e)}]}
    except Exception as e:  # any execution failure is a recorded INCOMPLETE trial, never a silent RUNNING row
        result = {"outcome": "INCOMPLETE", "checks": [{"check_id": "TRIAL-EXECUTION", "status": "FAIL", "detail": f"{type(e).__name__}: {e}"[:300]}]}
    finally:
        if mutating:
            with connect(rt.db) as c:
                release_slot(c, trial_id)
    finished = now()
    result.update({"runtime_mode": inv["runtime_mode"], "profile_hash": prof["profile_hash"], "plan_hash": plan["plan_hash"],
                   "versions": plan["core"]["versions"], "finished_at": finished.isoformat()})
    exact = json.loads(json.dumps(result, default=str), parse_float=Decimal)  # measured floats hashed as exact decimals
    th = canonical_hash(exact)
    status = result["outcome"]
    with connect(rt.db) as c:
        c.execute("UPDATE trials SET status=%s, trial_hash=%s, result=%s, finished_at=%s WHERE id=%s", (status, th, J(result), finished, trial_id))
        append_event(c, inv["id"], "trial.finished", "application", {"trial_id": str(trial_id), "plan_id": str(plan["id"]), "status": status, "trial_hash": th})
    if status != "CANCELLED":
        _post_trial(rt, inv, plan, trial_id, status, result, th)
    with connect(rt.db) as c:
        c.execute("UPDATE investigations SET stage='TRIALS', updated_at=now() WHERE id=%s AND status NOT IN ('COMPLETED','FAILED','CANCELLED')", (inv["id"],))
        enqueue(c, "investigation", inv["id"])
    return status


def _post_trial(rt, inv, plan, trial_id, status, result, trial_hash) -> None:
    """Critic reviews the measured trial; deterministic trial outcome stays authoritative."""
    gateway = rt.model_factory()
    critic = {"verdict": "SKIPPED"}
    if status == "PASSED":
        try:
            review = I.call_role(rt, inv, gateway, "critic", {"candidates": [{"candidate_ref": str(plan["id"]), "path": plan["path"], "stage": "post_trial",
                                 "checks": result["checks"], "evidence_ids": plan["core"]["evidence_ids"] + [f"trial:{trial_id}"]}]},
                                 CriticReview, I.budget_for(rt, inv))
            rv = next((r for r in review.reviews if r.candidate_ref == str(plan["id"])), None)
            critic = json.loads(rv.model_dump_json()) if rv else {"verdict": "MISSING"}
        except Exception as e:
            critic = {"verdict": "ERROR", "note": f"{type(e).__name__}"}
    real = {c["check_id"] for c in result["checks"]}
    validated = status == "PASSED" and critic.get("verdict") == "VALIDATED" and bool(set(critic.get("check_ids", [])) & real)
    new_status = "AWAITING_APPROVAL" if validated else "REJECTED"
    sig = plan["screening"].get("signature")
    reason = "; ".join(f"{c['check_id']}: {c['detail']}" for c in result["checks"] if c["status"] != "PASS") or f"critic {critic.get('verdict')}"
    versions = I.current_versions(rt, inv, None)
    with connect(rt.db) as c:
        if plan["path"] == "ai" and result.get("kind") == "ai_dev_suite":
            b, cnd = result["baseline"], result["candidate"]
            basis = "Measured workload" if cnd["usage_basis"] == "provider" else "Estimated (scripted usage estimate)"
            c.execute("UPDATE plans SET impacts=%s WHERE id=%s", (J({
                "basis": basis, "result_kind": "measured" if cnd["usage_basis"] == "provider" else "estimated", "trial_id": str(trial_id),
                "suite": result["suite_id"], "accepted": f"{cnd['accepted']}/{cnd['cases']}", "baseline_accepted": f"{b['accepted']}/{b['cases']}",
                "baseline_cost_per_accepted_usd": b["cost_per_accepted_usd"], "candidate_cost_per_accepted_usd": cnd["cost_per_accepted_usd"],
                "cost_per_accepted_reduction": result.get("cost_per_accepted_reduction"), "currency": "USD", "cost_basis": result.get("cost_basis"),
                "note": "development-suite batch; not a monthly saving; holdout evaluation is separate",
                "carbon": {"basis": "Unknown", "result_kind": "unknown",
                           "reason": "external model carbon cannot be derived from tokens alone; no provider-reported factor"}}), plan["id"]))
        if plan["path"] == "cloud" and result.get("kind") == "local_worker_pair":
            overhead, why = optimizer_overhead(c, inv)
            c.execute("UPDATE plans SET impacts=%s WHERE id=%s", (J(P.finalize_cloud_net(plan["impacts"], experiment_cost=Decimal(result["experiment_cost"]["amount"]),
                      transition_cost=Decimal(0), optimizer_overhead=overhead, overhead_reason=why)), plan["id"]))
        if validated:
            c.execute("UPDATE plans SET status='VALIDATED', updated_at=now() WHERE id=%s", (plan["id"],))
            append_event(c, inv["id"], "plan.validated", "application", {"plan_id": str(plan["id"]), "trial_id": str(trial_id)})
        c.execute("UPDATE plans SET status=%s, critic=%s, updated_at=now() WHERE id=%s",
                  (new_status, J({**(plan["critic"] or {}), "trial": {"trial_id": str(trial_id), "status": status, "critic": critic}}), plan["id"]))
        append_event(c, inv["id"], "plan.post_trial", "agent:critic", {"plan_id": str(plan["id"]), "status": new_status, "critic": critic, "reason": reason})
        if inv["memory_mode"] == "on" and status in ("PASSED", "FAILED"):
            kind = "validated_plan" if validated else "rejected_trial"
            finding = (f"Trial {trial_id} for {sig} {'passed' if validated else 'failed'} under policy {inv['policy_version']}: "
                       + ("; ".join(f"{c['check_id']}: {c['detail']}" for c in result["checks"])))
            memory_service.enqueue(c, tenant_id=inv["tenant_id"], service_id=inv["service_id"], kind=kind, source_ref=f"trial:{trial_id}",
                                   finding=finding, evidence_refs=plan["core"]["evidence_ids"] + [f"trial:{trial_id}"],
                                   applicability=versions[plan["path"]], signature=sig, target_id=plan["target_key"])
    with connect(rt.db) as c:
        inv2 = I.load(c, inv["id"])
    summ = inv2["summary"]
    if not validated:
        summ.setdefault("feedback", []).append({"signature": sig, "outcome": "FAILED", "reasons": reason, "trial_id": str(trial_id)})
        I.save_summary(rt, inv["id"], summ)
