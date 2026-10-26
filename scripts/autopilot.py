"""Autopilot: drift-triggered investigations. It watches evidence, never touches infrastructure.

    make autopilot                 # poll every AUTOPILOT_INTERVAL_S (default 900 s)
    make autopilot ONCE=1          # one check, then exit

Each cycle fingerprints the evidence that decides rightsizing (inventory, telemetry summary, billing, prices,
policy) through the configured evidence path — Zetaris federation in connected_demo — using each query
receipt's result hash. When the fingerprint differs from the last one it started a run for, and no investigation
is queued or running, it starts an investigation through the public API as the `autopilot` actor (role
`automation`: may start investigations; the API refuses it every trial, approval, revocation, cancellation and
execution). Results wait for a human in the queue, with memory recall on, so known failures are not re-proposed.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from greenops.config import ROOT, get_settings
from greenops.domain.quantities import canonical_hash
from greenops.services.common import Runtime

STATE = ROOT / "var" / "autopilot.json"
API = os.environ.get("GREENOPS_API_URL", "http://127.0.0.1:8000")
WATCH = ("inventory", "telemetry_summary", "billing_rows", "prices", "policy")
INTERVAL_DAYS = 21


def fingerprint(rt: Runtime, as_of: datetime) -> dict:
    s = rt.settings
    start = as_of - timedelta(days=INTERVAL_DAYS)
    params = {"inventory": {"service_id": "support-demo", "as_of": as_of}, "telemetry_summary": {"start": start, "end": as_of},
              "billing_rows": {"start": start, "end": as_of}, "prices": {"region": "us-central1"},
              "policy": {"service_id": "support-demo", "version": s.policy_version}}
    client = rt.evidence_factory()
    hashes = {t: client.query(t, params[t], max_rows=20000).receipt["result_hash"] for t in WATCH}
    return {"hash": canonical_hash(hashes), "templates": hashes, "source_system": client.source_system}


def log(event: str, **kw) -> None:
    print(json.dumps({"at": datetime.now(timezone.utc).isoformat()[:19] + "Z", "event": event, **kw}), flush=True)


def cycle(rt: Runtime, token: str, as_of: datetime) -> None:
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    fp = fingerprint(rt, as_of)
    changed = sorted(t for t, h in fp["templates"].items() if state.get("templates", {}).get(t) != h)
    if fp["hash"] == state.get("hash"):
        log("no_drift", source=fp["source_system"], fingerprint=fp["hash"][:19])
        return
    h = {"Authorization": f"Bearer {token}"}
    busy = httpx.get(f"{API}/v1/investigations", headers=h, params={"limit": 20}, timeout=30).json()["items"]
    if any(i["status"] in ("QUEUED", "RUNNING") for i in busy):
        log("drift_deferred", reason="an investigation is already queued or running", changed=changed)
        return
    mode = httpx.get(f"{API}/v1/me", headers=h, timeout=30).json()["data"]["runtime_mode"]
    why = "first baseline" if not state else "evidence drift in " + ", ".join(changed)
    body = {"service_id": "support-demo", "question": f"Autopilot ({why}): find a testable saving while preserving service and support policy",
            "interval": {"start": (as_of - timedelta(days=INTERVAL_DAYS)).isoformat().replace("+00:00", "Z"),
                         "end": as_of.isoformat().replace("+00:00", "Z")},
            "runtime_mode": mode, "budget_profile_id": "sandbox-approved-budget-v1", "approved_trial_profile_id": "sandbox-trials-v1",
            "memory_mode": "on"}
    r = httpx.post(f"{API}/v1/investigations", headers={**h, "Idempotency-Key": str(uuid.uuid4())}, json=body, timeout=30)
    if r.status_code != 202:
        log("start_failed", status=r.status_code, error=r.json().get("error", {}).get("code"))
        return
    STATE.write_text(json.dumps({"hash": fp["hash"], "templates": fp["templates"], "investigation_id": r.json()["investigation_id"],
                                 "started_at": datetime.now(timezone.utc).isoformat()}, indent=1))
    log("investigation_started", investigation_id=r.json()["investigation_id"], reason=why, changed=changed)


def main() -> None:
    s = get_settings()
    rt = Runtime.from_settings(s)
    token = json.loads((ROOT / "var" / "actors.local.json").read_text())["autopilot"]["token"]
    # The scenario's data ends at AUTOPILOT_AS_OF (synthetic, dated); a production deployment would use now().
    as_of = datetime.fromisoformat(os.environ.get("AUTOPILOT_AS_OF", "2026-10-21T00:00:00+00:00"))
    once = os.environ.get("ONCE") == "1"
    every = int(os.environ.get("AUTOPILOT_INTERVAL_S", "900"))
    while True:
        try:
            cycle(rt, token, as_of)
        except Exception as e:  # a failed check is logged and retried next cycle; it never starts anything
            log("check_failed", error=f"{type(e).__name__}: {str(e)[:200]}")
            if once:
                sys.exit(1)
        if once:
            return
        time.sleep(every)


if __name__ == "__main__":
    main()
