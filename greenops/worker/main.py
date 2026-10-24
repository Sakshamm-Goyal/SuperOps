"""Single durable workflow worker: claims jobs with DB leases, reconciles interrupted actions, dispatches the memory outbox."""
from __future__ import annotations

import logging
import os
import socket
import threading
import time
import traceback
from datetime import timedelta

from greenops.config import get_settings
from greenops.db import connect
from greenops.services import execution, investigation, memory_service, trials
from greenops.services.common import Runtime, claim, enqueue, finish, now, renew, requeue_expired

log = logging.getLogger("greenops.worker")
KINDS = ("investigation", "trial", "action")


def reconcile_on_start(rt: Runtime) -> int:
    """Actions left mid-flight get a reconciliation job; nothing is re-executed blindly."""
    n = 0
    with connect(rt.db) as c:
        rows = c.execute("SELECT a.id FROM actions a WHERE a.status IN ('EXECUTING','PENDING_VERIFICATION','RECOVERING','QUEUED') "
                         "AND NOT EXISTS (SELECT 1 FROM jobs j WHERE j.ref_id=a.id AND j.status IN ('QUEUED','RUNNING'))").fetchall()
        for r in rows:
            enqueue(c, "action", r["id"])
            n += 1
    return n


def run_job(rt: Runtime, job: dict) -> str:
    if job["kind"] == "investigation":
        return investigation.advance(rt, job["ref_id"])
    if job["kind"] == "trial":
        return trials.run(rt, job["ref_id"])
    return execution.run(rt, job["ref_id"])


MAX_ACTION_ATTEMPTS = 50


def reschedule(rt: Runtime, job: dict, reason: str) -> None:
    """Bounded backoff. Action jobs past the limit stay visible as FAILED jobs while the action keeps its factual
    non-terminal status and slot (startup reconciliation and operators see it); nothing is marked successful."""
    # Waiting for the global slot is normal contention: retry promptly. Unresolved outcomes/crashes back off.
    delay = 2 if reason == "WAITING_FOR_SLOT" else min(300, 5 * job["attempts"])
    with connect(rt.db) as c:
        if job["kind"] == "action" and job["attempts"] >= MAX_ACTION_ATTEMPTS:
            c.execute("UPDATE jobs SET status='FAILED', last_error=%s, lease_owner=NULL, updated_at=now() WHERE id=%s",
                      (f"reconciliation unresolved after {job['attempts']} attempts: {reason}", job["id"]))
            return
        c.execute("UPDATE jobs SET status='QUEUED', lease_owner=NULL, lease_expires_at=NULL, last_error=%s, "
                  "run_after=now() + make_interval(secs => %s), updated_at=now() WHERE id=%s", (reason, delay, job["id"]))


def step(rt: Runtime, owner: str) -> bool:
    for r in requeue_expired(rt.db):
        log.warning("lease expired; requeued %s %s for %s", r["kind"], r["ref_id"], "reconciliation" if r["kind"] == "action" else "resume")
    job = claim(rt.db, owner, KINDS)
    if job is None:
        memory_service.dispatch(rt)
        return False
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(20):
            renew(rt.db, job["id"], owner)

    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        result = run_job(rt, job)
        if result in ("WAITING_FOR_SLOT", "RECONCILE_PENDING"):
            reschedule(rt, job, result)
        else:
            finish(rt.db, job["id"], True)
        log.info("%s %s -> %s", job["kind"], job["ref_id"], result)
    except Exception as e:
        log.error("job %s failed: %s\n%s", job["id"], e, traceback.format_exc())
        if job["kind"] == "action":
            # An action is never abandoned by a crashed handler (audit A03): it is retried as reconciliation.
            reschedule(rt, job, f"{type(e).__name__}: {str(e)[:300]}")
        else:
            finish(rt.db, job["id"], False, f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        stop.set()
    memory_service.dispatch(rt)
    return True


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    rt = Runtime.from_settings(get_settings())
    owner = f"{socket.gethostname()}:{os.getpid()}"
    log.info("worker %s started; runtime_mode=%s; reconciliation jobs=%d", owner, rt.settings.runtime_mode.value, reconcile_on_start(rt))
    while True:
        if not step(rt, owner):
            time.sleep(1.0)


if __name__ == "__main__":
    main()
