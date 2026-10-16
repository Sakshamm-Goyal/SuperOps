"""Reset ONLY the demo namespaces: authority run tables, sandbox target configs and the H-MEM data dir (moved to a
timestamped backup, never deleted). Refuses while any action is active or unresolved. Actors, services, budgets and
trial profiles are kept.     PYTHONPATH=. uv run python scripts/reset_demo.py --confirm support-demo
"""
from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from greenops.adapters.sandbox import REGISTRY, ConfigStore, LocalWorker, TargetUnavailable
from greenops.config import ROOT, get_settings
from greenops.db import connect

TABLES = ["memory_corrections", "memory_outbox", "action_journal", "actions", "approvals", "model_calls", "trials", "plans", "evidence",
          "query_receipts", "investigation_events", "investigations", "jobs", "idempotency"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", required=True, help="must equal the service id: support-demo")
    a = ap.parse_args()
    if a.confirm != "support-demo":
        raise SystemExit("refused: --confirm must be support-demo")
    s = get_settings()
    if s.app_env not in ("sandbox", "hosted") or "prod" in s.database_url:
        raise SystemExit("refused: not a sandbox database")
    with connect(s.database_url) as c:
        active = c.execute("SELECT COUNT(*) AS n FROM actions WHERE status IN ('QUEUED','EXECUTING','PENDING_VERIFICATION','RECOVERING','RECOVERY_REQUIRED')").fetchone()["n"]
        if active:
            raise SystemExit(f"refused: {active} active/unresolved action(s); reconcile them first")
        c.execute("TRUNCATE " + ", ".join(TABLES))
        c.execute("UPDATE execution_slot SET holder_kind=NULL, holder_id=NULL, acquired_at=NULL")
    for tid, spec in REGISTRY["workers"].items():
        w = LocalWorker(s.sandbox_dir, tid)
        w.store.init({"worker_id": tid, "version": 1, "max_concurrency": spec["initial_max_concurrency"]}, force=True)
        try:
            w.reload()
        except TargetUnavailable:
            pass
    for tid, spec in REGISTRY["ai_workflows"].items():
        ConfigStore(s.sandbox_dir, tid).init({"workflow_id": spec["workflow_id"], "version": 1, "config": spec["initial_config"]}, force=True)
    hm = Path(os.environ.get("HMEM_DATA_DIR", "var/hmem-sample"))
    hm = hm if hm.is_absolute() else ROOT / hm
    if hm.exists() and any(hm.iterdir()):
        dest = hm.with_name(hm.name + "-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        shutil.move(str(hm), str(dest))
        print(f"memory data moved to {dest.relative_to(ROOT)} (restart the sidecar)")
    hm.mkdir(parents=True, exist_ok=True)
    print("demo namespaces reset")


if __name__ == "__main__":
    main()
