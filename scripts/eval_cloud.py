"""Cloud evaluation (EVALUATION_SPEC §2/§4) on the synthetic dataset:

1. Forecast temporal evaluation: frozen seasonal-naive + residual envelope (fit on days 2–17) evaluated on days 18–21.
2. Decision benchmark: frozen naive baseline B0 (avg CPU < 20% → next smaller permitted size) vs GreenOps screening B1,
   scored against the independent constraint ledger below (written from the scenario design, not from production code).
Output: evidence/eval/cloud-<ts>.json. Uses the labelled local sample source DB (data_origin=synthetic).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from greenops.adapters.evidence import SampleSqlClient
from greenops.config import ROOT, get_settings
from greenops.domain.capacity import LAG, STEP, Point, residual_quantile, seasonal_naive
from greenops.domain.models import ServicePolicy
from greenops.domain.screening import MachineType, screen_cloud
from greenops.services.evidence_service import build_facts, forecast_stress, ts

S, E = datetime(2026, 9, 30, tzinfo=timezone.utc), datetime(2026, 10, 21, tzinfo=timezone.utc)
# Independent constraint ledger: is ANY cheaper same-family downsizing safe for this resource? (scenario design)
LEDGER = {"gcp/greenops-sbx-staging/worker-stg-01": {"safe_targets": {"e2-standard-4"}, "role": "R1 rightsizeable"},
          "gcp/greenops-sbx-prod/worker-prod-01": {"safe_targets": set(), "role": "R2 peak + production"},
          "gcp/greenops-sbx-staging/worker-mem-01": {"safe_targets": set(), "role": "R3 memory (n2-highmem-2 fits but no allowed executor)"},
          "gcp/greenops-sbx-staging/worker-stale-01": {"safe_targets": set(), "role": "R4 evidence incomplete"},
          "gcp/greenops-sbx-staging/db-stateful-01": {"safe_targets": set(), "role": "R5 stateful"},
          "gcp/greenops-sbx-staging/worker-freeze-01": {"safe_targets": set(), "role": "R6 change freeze"}}


def main() -> None:
    c = SampleSqlClient(get_settings().sample_source_url)
    inv = c.query("inventory", {"service_id": "support-demo", "as_of": E}).rows
    summ = c.query("telemetry_summary", {"start": S, "end": E}).rows
    cat = c.query("machine_types", {}).rows
    prices = c.query("prices", {"region": "us-central1"}).rows
    policy = ServicePolicy.model_validate_json((ROOT / "config/policies/support-demo-pol-v1.json").read_text())
    forecast, stress = {}, {}
    for r in inv:
        key = f"{r['provider']}/{r['project_id']}/{r['resource_id']}"
        rows = c.query("telemetry_series", {"resource_key": key, "start": S, "end": E}).rows
        pts = [Point(ts(x["observed_at"]), Decimal(x["cpu_percent"])) for x in rows]
        stress[key], meta = forecast_stress(rows, S, E)
        try:
            q = residual_quantile(pts, S + timedelta(days=1), S + timedelta(days=17))
            errs, covered, n = [], 0, 0
            for d in range(17, 21):
                origin = S + timedelta(days=d)
                actual = {p.at: p.value for p in pts if origin <= p.at < origin + STEP * LAG}
                for f in seasonal_naive([p for p in pts if p.at < origin], origin):
                    if f.at in actual:
                        errs.append(abs(actual[f.at] - f.value)); n += 1
                        covered += actual[f.at] <= f.value + q
            forecast[key] = {"mae_cpu_pct": str(round(sum(errs) / len(errs), 3)), "envelope_coverage": f"{covered}/{n}", "residual_q95": str(q),
                             "origins": "days 18-21", "no_future_data": True}
        except Exception as e:
            forecast[key] = {"unavailable": str(e)}
    facts = build_facts(inv, summ, S, E, stress)
    rate = lambda sku: next((Decimal(p["price"]) for p in prices if p["sku"] == sku and not p["effective_to"]), None)
    rows, b0_unsafe, b1_unsafe, b1_kept, b0_kept = [], 0, 0, 0, 0
    for key, f in sorted(facts.items()):
        same = sorted((m for m in cat if m["family"] == f.machine_type.split("-")[0] and Decimal(m["vcpu"]) < f.vcpu and m["architecture"] == f.architecture),
                      key=lambda m: -Decimal(m["vcpu"]))
        b0 = same[0]["machine_type"] if same and f.avg_cpu_pct is not None and f.avg_cpu_pct < 20 else None  # next smaller size
        b1 = []
        for m in same:
            mt = MachineType(m["machine_type"], Decimal(m["vcpu"]), Decimal(m["memory_gib"]), m["architecture"])
            action = "LOCAL_WORKER_CONFIG_UPDATE" if key.endswith("worker-stg-01") else "GCP_MACHINE_TYPE_UPDATE"
            if screen_cloud(f, mt, policy, E, action, rate(m["machine_type"]), rate(f.machine_type)).outcome == "ELIGIBLE_FOR_TRIAL":
                b1.append(m["machine_type"])
        safe = LEDGER[key]["safe_targets"]
        b0_unsafe += bool(b0 and b0 not in safe); b0_kept += bool(b0 and b0 in safe)
        b1_unsafe += sum(1 for t in b1 if t not in safe); b1_kept += sum(1 for t in b1 if t in safe)
        rows.append({"resource": key, "role": LEDGER[key]["role"], "b0_recommendation": b0, "b1_eligible_for_trial": b1, "ledger_safe": sorted(safe)})
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "data_origin": "synthetic", "runtime_mode": "sample",
           "forecast_temporal_evaluation": forecast,
           "decision_benchmark": {"rows": rows, "B0_unsafe_recommendations": b0_unsafe, "B0_safe_recommendations": b0_kept,
                                  "B1_unsafe_eligible": b1_unsafe, "B1_safe_eligible": b1_kept,
                                  "note": "B0 is a deliberately simple frozen heuristic, not an industry optimizer; six synthetic resources only"}}
    p = ROOT / "evidence" / "eval" / f"cloud-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out["decision_benchmark"], indent=1, default=str))
    print({k: v.get("envelope_coverage", v.get("unavailable")) for k, v in forecast.items()})
    print("wrote", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
