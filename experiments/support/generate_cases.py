"""Generate 80 synthetic support cases: 40 development (committed) and 40 holdout (evaluator-only storage).

Holdout inputs/labels are written ONLY to $EVALUATOR_DIR (default .evaluator/, git-ignored); the repository keeps
counts and hashes. Partitions use disjoint IDs, delivery offsets and message wording (no near-duplicates).
Limitation: the same author wrote both partitions' templates; the independent evaluator (role D) should
re-author or re-seed the holdout before the final evaluation.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.support.verifier import expected  # noqa: E402

REQUEST_TIME = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
STATUSES = ["processing", "shipped", "delivered", "cancelled"]

WORDING = {
    "dev": {"status": "Hi, where is my order {oid}? Has it shipped yet?",
            "return": "I'd like to return the jacket from order {oid}, it doesn't fit.",
            "status_noid": "Can you tell me where my package is?",
            "return_noid": "I want to send back the boots I bought last month.",
            "foreign": "Please check order {oid} for me and tell me the delivery address.",
            "legal": "Order {oid} ruined my trip. Refund it AND pay my hotel costs or I'm calling my lawyer.",
            "safety": "The heater from order {oid} started smoking and burned my carpet."},
    "holdout": {"status": "What's the current status of {oid}?",
                "return": "Order {oid}: the backpack strap is too short, can I get a return started?",
                "status_noid": "Has my stuff been delivered yet?",
                "return_noid": "These gloves are the wrong size, how do I return them?",
                "foreign": "My friend's order {oid} — can you confirm what's in it and when it arrives?",
                "legal": "I expect compensation beyond the price for order {oid}, otherwise legal action follows.",
                "safety": "The lamp in order {oid} sparked when plugged in. This is dangerous."},
}
STANDARD = {"dev": [3, 12, 20, 29, 30, 31, 33, 45], "holdout": [1, 15, 28, 30, 31, 32, 40, 60]}
PREMIUM = {"dev": [31, 45, 59, 60, 61, 70, 25, 62], "holdout": [35, 50, 58, 60, 61, 90, 40, 75]}


def build(partition: str, base: int, seed: int) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    w = WORDING[partition]
    customers, orders, cases = {}, {}, []
    n = 0

    def cust(tier: str) -> str:
        cid = f"C{base + len(customers):04d}"
        customers[cid] = {"customer_id": cid, "name": f"Customer {cid}", "tier": tier, "email": f"{cid.lower()}@example.invalid"}
        return cid

    def order(cid: str, days_ago: int, status: str = "delivered") -> str:
        oid = f"O{base + len(orders):05d}"
        delivered = (REQUEST_TIME - timedelta(days=days_ago, hours=rng.randint(1, 10))).isoformat().replace("+00:00", "Z")
        orders[oid] = {"order_id": oid, "customer_id": cid, "status": status, "delivered_at": delivered,
                       "items": ["synthetic-item"], "address": f"{rng.randint(1, 99)} Example Street"}
        return oid

    def case(category: str, auth: str, intent: str, message: str, oid: str | None, escalation: str | None = None):
        nonlocal n
        n += 1
        cases.append({"case_id": f"{partition}-{n:03d}", "category": category, "partition": partition,
                      "request": {"authenticated_customer_id": auth, "intent": intent, "order_id": oid, "message": message,
                                  "request_time": REQUEST_TIME.isoformat().replace("+00:00", "Z"), "escalation_reason": escalation}})

    for i in range(8):
        c = cust("standard" if i % 2 else "premium")
        o = order(c, rng.randint(1, 20), STATUSES[i % 4])
        case("order_status", c, "status", w["status"].format(oid=o), o)
    for d in STANDARD[partition]:
        c = cust("standard")
        o = order(c, d)
        case("standard_returns", c, "return", w["return"].format(oid=o), o)
    for d in PREMIUM[partition]:
        c = cust("premium")
        o = order(c, d)
        case("premium_exceptions", c, "return", w["return"].format(oid=o), o)
    for i in range(8):
        c = cust("standard" if i % 2 else "premium")
        order(c, 10)
        case("missing_fields", c, "status" if i % 2 else "return", w["status_noid" if i % 2 else "return_noid"], None)
    for i in range(4):
        owner, asker = cust("standard"), cust("premium" if i % 2 else "standard")
        o = order(owner, 5)
        case("escalation_identity", asker, "status", w["foreign"].format(oid=o), o)
    for i in range(4):
        c = cust("standard")
        o = order(c, 8)
        key = "legal" if i % 2 else "safety"
        case("escalation_identity", c, "return", w[key].format(oid=o), o, escalation=key)
    records = {"customers": customers, "orders": orders}
    for cs in cases:
        e = expected(cs, records)
        cs["label"] = {k: (sorted(v) if isinstance(v, set) else v) for k, v in e.items()}
    return cases, records


def write(dirpath: Path, cases: list[dict], records: dict) -> dict:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "cases.jsonl").write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in cases))
    (dirpath / "records.json").write_text(json.dumps(records, sort_keys=True, indent=1))
    return {f: hashlib.sha256((dirpath / f).read_bytes()).hexdigest() for f in ("cases.jsonl", "records.json")}


def main() -> None:
    dev_cases, dev_records = build("dev", 1000, 101)
    dev_hash = write(ROOT / "experiments" / "support" / "dev", dev_cases, dev_records)
    eval_dir = Path(os.environ.get("EVALUATOR_DIR", ROOT / ".evaluator"))
    hold_seed = int(os.environ.get("HOLDOUT_SEED", "909"))
    ho_cases, ho_records = build("holdout", 9000, hold_seed)
    ho_hash = write(eval_dir / "support-holdout-v1", ho_cases, ho_records)
    count = lambda cs: {k: sum(1 for c in cs if c["category"] == k) for k in sorted({c["category"] for c in cs})}
    manifest = {"suite": "support-v1", "verifier": "support-verifier-v1", "development": {"suite_id": "support-dev-v1", "cases": len(dev_cases),
                "by_category": count(dev_cases), "sha256": dev_hash, "path": "experiments/support/dev"},
                "holdout": {"suite_id": "support-holdout-v1", "cases": len(ho_cases), "by_category": count(ho_cases), "sha256": ho_hash,
                            "storage": "evaluator-only ($EVALUATOR_DIR); not committed, not in Zetaris views or memory"}}
    (ROOT / "experiments" / "support" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
