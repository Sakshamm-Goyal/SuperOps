"""Deterministic synthetic source data for the support-demo scenario (data_origin=synthetic).

Writes CSVs under data/generated/{cloud,ai,ref}/ and data/manifests/support-demo-data-v1.json.
Six resources × 21 days × 96 quarter-hours = 12,096 telemetry rows (R4 deliberately truncated/missing).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "generated"
SEED = 20261022
START = datetime(2026, 9, 30, tzinfo=timezone.utc)
DAYS = 21
END = START + timedelta(days=DAYS)  # scenario as_of
GIB = 1024**3
MANIFEST_ID = "support-demo-data-v1"

MACHINES = [  # type, family, vcpu, mem_gib, arch
    ("e2-standard-2", "e2", 2, 8, "x86_64"), ("e2-standard-4", "e2", 4, 16, "x86_64"),
    ("e2-standard-8", "e2", 8, 32, "x86_64"), ("e2-highmem-2", "e2", 2, 16, "x86_64"),
    ("n2-standard-2", "n2", 2, 8, "x86_64"), ("n2-standard-4", "n2", 4, 16, "x86_64"),
    ("n2-standard-8", "n2", 8, 32, "x86_64"), ("n2-highmem-2", "n2", 2, 16, "x86_64"),
    ("t2a-standard-4", "t2a", 4, 16, "arm64"),
]
# Synthetic scenario rates (USD/hour). Not provider list prices.
PRICES = {"e2-standard-2": "0.067", "e2-standard-8": "0.268", "e2-highmem-2": "0.090",
          "n2-standard-2": "0.097", "n2-standard-4": "0.194", "n2-standard-8": "0.388", "n2-highmem-2": "0.131",
          "t2a-standard-4": "0.154"}
RATE_CHANGE = START + timedelta(days=10)  # e2-standard-4: 0.140 before, 0.134 from day 11 (D-19)

RESOURCES = [
    # key parts, display, env, machine, region, stateful, local_ssd, gpu, role
    ("greenops-sbx-staging", "worker-stg-01", "support-worker", "staging", "e2-standard-8", False, False, "R1 safely rightsizeable"),
    ("greenops-sbx-prod", "worker-prod-01", "support-worker", "production", "e2-standard-8", False, False, "R2 low average, high peak"),
    ("greenops-sbx-staging", "worker-mem-01", "support-indexer", "staging", "n2-standard-4", False, False, "R3 memory constrained"),
    ("greenops-sbx-staging", "worker-stale-01", "support-exporter", "staging", "e2-standard-4", False, False, "R4 missing/stale evidence"),
    ("greenops-sbx-staging", "db-stateful-01", "support-db", "staging", "n2-standard-8", True, True, "R5 unsupported stateful"),
    ("greenops-sbx-staging", "worker-freeze-01", "support-notifier", "staging", "e2-standard-4", False, False, "R6 change freeze"),
]


def mtype(name):
    return next(m for m in MACHINES if m[0] == name)


def cpu_mem(role: str, i: int, rng: random.Random):
    """Return (cpu_percent, memory_gib|None) for quarter-hour index i."""
    day, q = divmod(i, 96)
    hour = q / 4
    diurnal = max(0.0, math.sin(math.pi * (hour - 6) / 12))  # 06:00-18:00 hump
    if role.startswith("R1"):
        cpu = 6 + 26 * diurnal + rng.uniform(-1, 1.5)
        mem = 6 + 2.5 * diurnal + rng.uniform(0, 0.4)
    elif role.startswith("R2"):
        spike = 2 * 4 <= q < 2 * 4 + 2  # 02:00-02:30 batch
        cpu = (78 + rng.uniform(0, 2)) if spike else (8 + 3 * diurnal + rng.uniform(-1, 1))
        mem = 10 + 1.5 * diurnal + (1.5 if spike else 0) + rng.uniform(0, 0.3)
    elif role.startswith("R3"):
        cpu = 10 + 18 * diurnal + rng.uniform(-1, 1)
        mem = 7.5 + 2.4 * diurnal + rng.uniform(0, 0.1)
    elif role.startswith("R4"):
        cpu = 5 + 8 * diurnal + rng.uniform(-1, 1)
        mem = None if day >= DAYS - 2 else 3 + rng.uniform(0, 0.5)
    elif role.startswith("R5"):
        cpu = 7 + 6 * diurnal + rng.uniform(-1, 1)
        mem = 20 + rng.uniform(0, 1)
    else:
        cpu = 4 + 5 * diurnal + rng.uniform(-1, 1)
        mem = 2.5 + rng.uniform(0, 0.4)
    return max(0.5, min(99.0, cpu)), mem


def write_csv(path: Path, header: list[str], rows: list[list]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return {"path": str(path.relative_to(ROOT)), "rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def hourly_rate(machine: str, at: datetime) -> D:
    if machine == "e2-standard-4":
        return D("0.140") if at < RATE_CHANGE else D("0.134")
    return D(PRICES[machine])


def main() -> None:
    rng = random.Random(SEED)
    files = {}
    inv, tel, bill = [], [], []
    for project, rid, display, env, machine, stateful, ssd, role in RESOURCES:
        m = mtype(machine)
        inv.append(["gcp", project, rid, "support-demo", display, env, machine, m[2], m[3], "us-central1", m[4], stateful, ssd, False, 1, role,
                    iso(START), ""])
        for i in range(DAYS * 96):
            at = START + timedelta(minutes=15 * i)
            if role.startswith("R4") and at >= END - timedelta(hours=3):
                continue  # stale: last sample 3h before as_of
            cpu, mem = cpu_mem(role, i, rng)
            reqs = rng.randint(800, 1200)
            tel.append(["gcp", project, rid, iso(at), f"{cpu:.2f}", "" if mem is None else str(int(mem * GIB)),
                        f"{rng.uniform(80, 140):.1f}", rng.randint(0, 2), reqs])
        for d in range(DAYS):
            day0 = START + timedelta(days=d)
            # Effective-interval split for the rate change day boundary is handled at hour grain here.
            cost = sum(hourly_rate(machine, day0 + timedelta(hours=h)) for h in range(24))
            bill.append([f"bill-{project}-{rid}-{d:02d}", "gcp", project, rid, machine, iso(day0), iso(day0 + timedelta(days=1)),
                         "24", "hour", f"{cost:.6f}", "USD", "synthetic-rates-v1"])
    files["cloud.inventory"] = write_csv(OUT / "cloud" / "inventory.csv",
        ["provider", "project_id", "resource_id", "service_id", "display_name", "environment", "machine_type", "vcpu", "memory_gib", "region",
         "architecture", "stateful", "local_ssd", "gpu", "config_version", "scenario_role", "effective_from", "effective_to"], inv)
    files["cloud.telemetry"] = write_csv(OUT / "cloud" / "telemetry.csv",
        ["provider", "project_id", "resource_id", "observed_at", "cpu_percent", "memory_bytes", "latency_ms", "error_count", "request_count"], tel)
    files["cloud.billing"] = write_csv(OUT / "cloud" / "billing.csv",
        ["billing_record_id", "provider", "project_id", "resource_id", "sku", "usage_start", "usage_end", "usage_quantity", "usage_unit",
         "cost", "currency", "rate_version"], bill)
    files["cloud.pagination_probe"] = write_csv(OUT / "cloud" / "pagination_probe.csv", ["probe_id", "label"],
                                                [[i, f"probe-{i:03d}"] for i in range(1, 206)])

    prices = []
    for name, *_ in MACHINES:
        if name == "e2-standard-4":
            prices.append(["gcp", "us-central1", name, "hour", "USD", "0.140", iso(START - timedelta(days=30)), iso(RATE_CHANGE), "synthetic-rates-v1", "synthetic_scenario"])
            prices.append(["gcp", "us-central1", name, "hour", "USD", "0.134", iso(RATE_CHANGE), "", "synthetic-rates-v2", "synthetic_scenario"])
        else:
            prices.append(["gcp", "us-central1", name, "hour", "USD", PRICES[name], iso(START - timedelta(days=30)), "", "synthetic-rates-v1", "synthetic_scenario"])
    files["ref.prices"] = write_csv(OUT / "ref" / "prices.csv",
        ["provider", "region", "sku", "unit", "currency", "price", "effective_from", "effective_to", "rate_version", "price_basis"], prices)
    files["ref.machine_types"] = write_csv(OUT / "ref" / "machine_types.csv", ["machine_type", "family", "vcpu", "memory_gib", "architecture"],
                                           [list(m) for m in MACHINES])
    files["ref.model_prices"] = write_csv(OUT / "ref" / "model_prices.csv",
        ["model_family", "input_per_million", "output_per_million", "currency", "effective_from", "effective_to", "price_basis"],
        [["default", "0.60", "1.20", "USD", iso(START - timedelta(days=30)), "", "synthetic_catalogue_equivalent"]])
    files["ref.carbon_factors"] = write_csv(OUT / "ref" / "carbon_factors.csv",
        ["region", "kg_co2e_per_kwh", "kwh_per_vcpu_hour", "kwh_per_gib_hour", "pue_included", "method_version", "effective_from", "effective_to", "factor_source"],
        [["us-central1", "0.43", "0.0035", "0.0004", "true", "greenops-synthetic-ops-v1", iso(START - timedelta(days=30)), "", "synthetic_illustrative"]])

    base_policy = json.loads((ROOT / "config" / "policies" / "support-demo-pol-v1.json").read_text())
    v2 = dict(base_policy, version="pol-v2", effective_from=iso(END + timedelta(days=1)), workload=dict(base_policy["workload"], slo_p95_ms=600))
    files["ref.policies"] = write_csv(OUT / "ref" / "policies.csv",
        ["service_id", "policy_id", "version", "effective_from", "document"],
        [[base_policy["service_id"], base_policy["policy_id"], "pol-v1", base_policy["effective_from"], json.dumps(base_policy, sort_keys=True)],
         [v2["service_id"], v2["policy_id"], "pol-v2", v2["effective_from"], json.dumps(v2, sort_keys=True)]])

    # AI source: historical development-partition traces of the baseline support workflow.
    calls, runs = [], []
    for r in range(6):
        run_id = f"run-hist-{r:02d}"
        t = START + timedelta(days=2 * r, hours=10)
        runs.append([run_id, "support-demo", "support-workflow", "wf-v1", json.dumps({"policy_context": "full", "dedupe_lookups": False, "max_tool_calls": 8}),
                     "development", "agent_readable", iso(t), 40])
        n = 0
        for case in range(40):
            for attempt in (1, 2) if case % 13 == 0 else (1,):
                n += 1
                calls.append([run_id, f"{run_id}-c{n:04d}", attempt, "model", "", "", rng.randint(5200, 6400), rng.randint(140, 260), "0", "ok" if attempt == 2 or case % 13 else "retry", "development", "agent_readable", iso(t)])
            lookups = ["lookup_order", "lookup_customer", "lookup_order"]  # duplicate side-effect-free lookup
            for k, tool in enumerate(lookups):
                n += 1
                calls.append([run_id, f"{run_id}-c{n:04d}", 1, "tool", tool, hashlib.sha256(f"{case}-{tool}".encode()).hexdigest()[:16],
                              "", "", "0.0001", "ok", "development", "agent_readable", iso(t)])
    files["ai.runs"] = write_csv(OUT / "ai" / "ai_runs.csv",
        ["run_id", "service_id", "workflow_id", "workflow_version", "config_json", "evaluation_partition", "access_class", "started_at", "cases"], runs)
    files["ai.calls"] = write_csv(OUT / "ai" / "ai_calls.csv",
        ["run_id", "call_id", "attempt", "call_kind", "tool_name", "args_hash", "input_tokens", "output_tokens", "tool_cost", "status",
         "evaluation_partition", "access_class", "started_at"], calls)

    manifest = {"manifest_id": MANIFEST_ID, "data_origin": "synthetic", "seed": SEED, "generator": "scripts/generate_data.py",
                "interval": {"start": iso(START), "end": iso(END)}, "scenario_as_of": iso(END),
                "expected_telemetry_rows_full": 6 * DAYS * 96, "actual_telemetry_rows": len(tel),
                "designed_anomalies": ["R4: last 3h missing and memory null for final 2 days", "R2: 02:00-02:30 daily 78-80% CPU spike",
                                       "R1/R2 share display name 'support-worker' in different projects", "e2-standard-4 rate change at day 11"],
                "license": "Synthetic; generated by this repository", "files": files}
    (ROOT / "data" / "manifests" / f"{MANIFEST_ID}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v["rows"] for k, v in files.items()}, indent=1))


if __name__ == "__main__":
    main()
