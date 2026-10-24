"""Developer driver: create an investigation through the real API app and run worker steps in-process until idle.

    PYTHONPATH=. uv run python scripts/drive.py [--memory off] [--no-trials]
Prints the resulting queue. Uses the same Runtime/config as the server; no shortcuts around the API or worker.
"""
from __future__ import annotations

import argparse
import json
import uuid

from fastapi.testclient import TestClient

from greenops.api.app import create_app
from greenops.config import ROOT, get_settings
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory", default="on")
    ap.add_argument("--no-trials", action="store_true")
    ap.add_argument("--question", default="Find a testable saving while preserving service and support policy")
    a = ap.parse_args()
    s = get_settings()
    rt = Runtime.from_settings(s)
    client = TestClient(create_app(rt))
    tok = json.loads((ROOT / "var" / "actors.local.json").read_text())["lead"]["token"]
    h = {"Authorization": f"Bearer {tok}", "Idempotency-Key": str(uuid.uuid4())}
    body = {"service_id": "support-demo", "question": a.question, "interval": {"start": "2026-09-30T00:00:00Z", "end": "2026-10-21T00:00:00Z"},
            "runtime_mode": s.runtime_mode.value, "budget_profile_id": "sandbox-approved-budget-v1", "memory_mode": a.memory}
    if not a.no_trials:
        body["approved_trial_profile_id"] = "sandbox-trials-v1"
    r = client.post("/v1/investigations", json=body, headers=h)
    print(r.status_code, r.json())
    iid = r.json()["investigation_id"]
    wait_done(rt, iid)
    d = client.get(f"/v1/investigations/{iid}", headers={"Authorization": f"Bearer {tok}"}).json()
    print("STATUS", d["status"], d["data"]["outcome"])
    for p in d["data"]["plans"]:
        fails = [c["check_id"] for c in p["screening"]["checks"] if c["status"] != "PASS"]
        print(f"  {p['path']}#{p['candidate_no']} r{p['revision']} {p['status']:<18} {p['screening'].get('signature')} {fails} mem={p['memory_refs']}")
    print("memory:", {k: len(v) if isinstance(v, list) else v for k, v in (d["data"]["memory"] or {}).items()})
    print("INVESTIGATION", iid)


if __name__ == "__main__":
    main()
