"""Memory ablation (EVALUATION_SPEC §6, illustrative): the same two-investigation sequence with memory on vs off.

Start from a clean authority DB snapshot and an EMPTY sidecar data dir for a fair run. Counts plans, trials, model
calls and model-trial requests per investigation. Writes evidence/eval/memory-ablation-<ts>.json.
    PYTHONPATH=. uv run python scripts/memory_ablation.py
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from greenops.api.app import create_app
from greenops.config import ROOT, get_settings
from greenops.db import connect
from greenops.services.common import Runtime
from greenops.worker.main import step


def wait_done(rt, iid, timeout_s: float = 1800) -> None:
    """Run worker steps in-process (or let a running worker do it) until the investigation leaves QUEUED/RUNNING."""
    import time
    from greenops.db import connect
    end = time.time() + timeout_s
    while time.time() < end:
        if not step(rt, "driver"):
            with connect(rt.db) as c:
                st = c.execute("SELECT status FROM investigations WHERE id=%s", (iid,)).fetchone()["status"]
                busy = c.execute("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()["n"]
            if st not in ("QUEUED", "RUNNING") and not busy:
                return
            time.sleep(1)


def run(client, rt, tok, memory: str, n: int) -> dict:
    body = {"service_id": "support-demo", "question": f"ablation {memory} #{n}", "interval": {"start": "2026-09-30T00:00:00Z", "end": "2026-10-21T00:00:00Z"},
            "runtime_mode": rt.settings.runtime_mode.value, "budget_profile_id": "sandbox-approved-budget-v1", "memory_mode": memory,
            "approved_trial_profile_id": "sandbox-trials-v1"}
    started = datetime.now(timezone.utc)
    iid = client.post("/v1/investigations", json=body, headers={"Authorization": f"Bearer {tok}", "Idempotency-Key": str(uuid.uuid4())}).json()["investigation_id"]
    wait_done(rt, iid)
    with connect(rt.db) as c:
        inv = c.execute("SELECT status, summary FROM investigations WHERE id=%s", (iid,)).fetchone()
        plans = c.execute("SELECT status, screening->>'signature' AS sig FROM plans WHERE investigation_id=%s", (iid,)).fetchall()
        trials = c.execute("SELECT t.status FROM trials t JOIN plans p ON p.id=t.plan_id WHERE p.investigation_id=%s", (iid,)).fetchall()
        calls = c.execute("SELECT COALESCE(SUM(m.requests),0) AS r, COALESCE(SUM(m.input_tokens),0) AS i FROM model_calls m LEFT JOIN trials t ON t.id=m.trial_id "
                          "LEFT JOIN plans p ON p.id=t.plan_id WHERE m.investigation_id=%s OR p.investigation_id=%s", (iid, iid)).fetchone()
    return {"investigation_id": iid, "status": inv["status"], "plans": len(plans), "trials": len(trials),
            "failed_trials": sum(1 for t in trials if t["status"] == "FAILED"), "repeated_known_failures": None,
            "model_requests": int(calls["r"]), "input_tokens": int(calls["i"]), "elapsed_s": (datetime.now(timezone.utc) - started).total_seconds(),
            "memory_applicable": len((inv["summary"].get("memory") or {}).get("applicable", [])),
            "signatures": sorted(p["sig"] for p in plans), "final_ready": sorted(p["sig"] for p in plans if p["status"] == "AWAITING_APPROVAL")}


def main() -> None:
    s = get_settings()
    rt = Runtime.from_settings(s)
    client = TestClient(create_app(rt))
    tok = json.loads((ROOT / "var" / "actors.local.json").read_text())["lead"]["token"]
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "runtime_mode": s.runtime_mode.value, "data_origin": "synthetic", "conditions": {}}
    for memory in ("off", "on"):
        seq = [run(client, rt, tok, memory, 1), run(client, rt, tok, memory, 2)]
        failed_first = set(seq[0]["signatures"]) - set(seq[0]["final_ready"])
        seq[1]["repeated_known_failures"] = len(set(seq[1]["signatures"]) & failed_first)
        out["conditions"][memory] = seq
    out["note"] = ("Illustrative single sequence; memory-off bypasses recall/remember with all other validation enabled. "
                   "Sample mode uses scripted roles and a hash embedder (semantic=false): it demonstrates the mechanism, not semantic recall quality.")
    p = ROOT / "evidence" / "eval" / f"memory-ablation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2) + "\n")
    for m, seq in out["conditions"].items():
        print(m, [{k: r[k] for k in ("status", "plans", "trials", "failed_trials", "repeated_known_failures", "model_requests")} for r in seq])
    print("wrote", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
