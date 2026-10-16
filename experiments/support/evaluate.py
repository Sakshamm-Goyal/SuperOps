"""Evaluator-only holdout evaluation (role D). Not reachable from the API, agents, Zetaris views or memory.

1) Freeze:   PYTHONPATH=. uv run python -m experiments.support.evaluate freeze --plan <plan_id>
             records the candidate config, model, prompt/workflow/verifier versions and hashes (experiments/support/freeze.json).
2) Evaluate: PYTHONPATH=. uv run python -m experiments.support.evaluate run
             runs baseline + frozen candidate once on the 40 holdout cases from $EVALUATOR_DIR, interleaved with a recorded seed.
Public output: evidence/eval/<run_id>/metrics.json (aggregates only). Per-case results stay in $EVALUATOR_DIR/results/.
Credentials: connected mode requires EVALUATOR_MODEL_API_KEY (separate from the agent's MODEL_API_KEY).
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from greenops.config import ROOT, get_settings
from greenops.domain import accounting as acc

FREEZE = ROOT / "experiments" / "support" / "freeze.json"
MANIFEST = ROOT / "experiments" / "support" / "manifest.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze(plan_id: str) -> None:
    from greenops.db import connect
    from experiments.support.verifier import VERIFIER_VERSION
    from experiments.support.workflow import WORKFLOW_VERSION, config_hash
    from greenops.agents.roles import PROMPT_VERSION
    from greenops.domain.models import AiWorkflowConfig
    s = get_settings()
    with connect(s.database_url) as c:
        p = c.execute("SELECT * FROM plans WHERE id=%s AND path='ai'", (plan_id,)).fetchone()
        t = c.execute("SELECT * FROM trials WHERE plan_id=%s AND status='PASSED' ORDER BY finished_at DESC LIMIT 1", (plan_id,)).fetchone()
    if not p or not t:
        raise SystemExit("freeze requires an AI plan with a PASSED development trial")
    cand = p["core"]["action"]["after"]
    doc = {"frozen_at": datetime.now(timezone.utc).isoformat(), "plan_id": plan_id, "plan_hash": p["plan_hash"], "trial_id": str(t["id"]),
           "trial_hash": t["trial_hash"], "baseline_config": p["core"]["action"]["before"], "candidate_config": cand,
           "candidate_config_hash": config_hash(AiWorkflowConfig(**cand)), "model_id": t["result"]["candidate"]["model_id"],
           "workflow_version": WORKFLOW_VERSION, "prompt_version": PROMPT_VERSION, "verifier_version": VERIFIER_VERSION,
           "code_hashes": {f: _sha(ROOT / f) for f in ("experiments/support/workflow.py", "experiments/support/verifier.py", "experiments/support/policy.md")},
           "selection_gate": "≥38/40 accepted, zero critical failures, no baseline-pass→candidate-fail, lower cost per accepted task"}
    FREEZE.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"frozen candidate {doc['candidate_config_hash']} from plan {plan_id}")


def run() -> None:
    from experiments.support.verifier import SupportDecision, verify
    from experiments.support.workflow import config_hash, load_suite, run_case
    from greenops.adapters.model import AdkGateway, ScriptedGateway
    from greenops.domain.models import AiWorkflowConfig
    from greenops.services.trials import wilson
    s = get_settings()
    if not FREEZE.exists():
        raise SystemExit("refused: no frozen candidate (run `freeze` first)")
    fz = json.loads(FREEZE.read_text())
    for f, h in fz["code_hashes"].items():
        if _sha(ROOT / f) != h:
            raise SystemExit(f"refused: {f} changed after freeze; a new freeze/evaluation protocol is required")
    man = json.loads(MANIFEST.read_text())["holdout"]
    hdir = s.evaluator_dir / "support-holdout-v1"
    if {f: _sha(hdir / f) for f in ("cases.jsonl", "records.json")} != man["sha256"]:
        raise SystemExit("refused: holdout files do not match the committed manifest hashes")
    cases, records = load_suite(hdir)
    if s.runtime_mode.value == "connected_demo":
        key = os.environ.get("EVALUATOR_MODEL_API_KEY")
        if not key:
            raise SystemExit("BLOCKED: EVALUATOR_MODEL_API_KEY (separate evaluator credential) not set")
        gw = AdkGateway(dataclasses.replace(s, model_api_key=key, model_id=fz["model_id"]))
    else:
        from experiments.support.workflow import scripted_support
        gw = ScriptedGateway({"support": scripted_support})
    seed = int(os.environ.get("EVAL_ORDER_SEED", "20261025"))
    order = [(c, lab) for c in cases for lab in ("baseline", "candidate")]
    random.Random(seed).shuffle(order)
    cfgs = {"baseline": AiWorkflowConfig(**fz["baseline_config"]), "candidate": AiWorkflowConfig(**fz["candidate_config"])}
    out = {"baseline": {}, "candidate": {}}
    for case, lab in order:
        r = run_case(gw, case, records, cfgs[lab], None)
        v = verify(case, records, SupportDecision(**r["output"]) if r["output"] else None)
        out[lab][case["case_id"]] = {**r, "verdict": v}
    rates = acc.TokenRates(Decimal("0.60"), Decimal("1.20"))  # synthetic catalogue-equivalent (ref/model_prices.csv)
    metrics = {}
    for lab, res in out.items():
        acc_n = sum(x["verdict"]["accepted"] for x in res.values())
        total, comp = acc.ai_run_cost([{"input_tokens": x["input_tokens"], "output_tokens": x["output_tokens"],
                                        "tool_cost": Decimal("0.0001") * x["tool_calls"]} for x in res.values()], rates)
        cats = sorted({x["verdict"]["category"] for x in res.values()})
        metrics[lab] = {"config_hash": config_hash(cfgs[lab]), "cases": len(res), "accepted": acc_n, "wilson_95": wilson(acc_n, len(res)),
                        "critical_failures": sum(x["verdict"]["critical_failure"] for x in res.values()),
                        "by_category": {k: sum(1 for x in res.values() if x["verdict"]["category"] == k and x["verdict"]["accepted"]) for k in cats},
                        "input_tokens": sum(x["input_tokens"] or 0 for x in res.values()), "output_tokens": sum(x["output_tokens"] or 0 for x in res.values()),
                        "tool_calls": sum(x["tool_calls"] for x in res.values()), "errors": sum(1 for x in res.values() if x["error"]),
                        "total_cost_usd": None if total is None else str(total), "usage_completeness": str(comp),
                        "cost_per_accepted_usd": None if (cpa := acc.cost_per_accepted(total, acc_n)) is None else str(cpa)}
    bp = {k for k, x in out["baseline"].items() if x["verdict"]["accepted"]}
    cp = {k for k, x in out["candidate"].items() if x["verdict"]["accepted"]}
    b, c = metrics["baseline"], metrics["candidate"]
    gate = {"accepted_ge_38": c["accepted"] >= 38, "zero_critical": c["critical_failures"] == 0, "no_regression": not (bp - cp),
            "cost_per_accepted_lower": b["cost_per_accepted_usd"] is not None and c["cost_per_accepted_usd"] is not None
            and Decimal(c["cost_per_accepted_usd"]) < Decimal(b["cost_per_accepted_usd"])}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    public = {"run_id": run_id, "suite": man["suite_id"], "cases": len(cases), "runtime_mode": s.runtime_mode.value, "data_origin": "synthetic",
              "model_id": gw.model_id, "freeze": {k: fz[k] for k in ("plan_hash", "trial_hash", "candidate_config_hash", "verifier_version", "frozen_at")},
              "order_seed": seed, "metrics": metrics, "paired_discordance": {"both_pass": len(bp & cp), "baseline_only": len(bp - cp),
              "candidate_only": len(cp - bp), "neither": len(cases) - len(bp | cp)}, "selection_gate": gate, "selected": all(gate.values()),
              "decision": "ROLLOUT_ELIGIBLE" if all(gate.values()) else "NO_CHANGE",
              "limitations": ["40 holdout cases: Wilson lower bound at 40/40 is ~0.912; not a broad reliability claim",
                              "holdout authored by the same agent as the dev set in pre-event work; role D should re-author/re-seed it",
                              "cost uses synthetic catalogue-equivalent rates; provider billing not observed"]}
    pub = ROOT / "evidence" / "eval" / run_id
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "metrics.json").write_text(json.dumps(public, indent=2) + "\n")
    priv = s.evaluator_dir / "results" / run_id
    priv.mkdir(parents=True, exist_ok=True)
    (priv / "cases.jsonl").write_text("".join(json.dumps({"label": lab, **x}, default=str) + "\n" for lab, res in out.items() for x in res.values()))
    print(json.dumps({k: public[k] for k in ("run_id", "decision", "selection_gate")}, indent=1))
    print(f"public aggregates: {pub.relative_to(ROOT)}/metrics.json; per-case results evaluator-only")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--plan", required=True)
    sub.add_parser("run")
    a = ap.parse_args()
    freeze(a.plan) if a.cmd == "freeze" else run()
