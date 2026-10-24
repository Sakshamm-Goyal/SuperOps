"""Start/stop/inspect the local sandbox workers. Usage: python scripts/sandbox.py up|down|status"""
import json
import sys

from greenops.adapters.sandbox import REGISTRY, LocalWorker, TargetUnavailable, start_workers, stop_workers
from greenops.config import get_settings

s = get_settings()
cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
if cmd == "up":
    print("started:", start_workers(s.sandbox_dir))
elif cmd == "down":
    print("stopped:", stop_workers(s.sandbox_dir))
for tid in REGISTRY["workers"]:
    try:
        st = LocalWorker(s.sandbox_dir, tid).status()
        print(tid, "version", st["loaded_version"], "max_concurrency", st["loaded_config"]["max_concurrency"], st["loaded_config_hash"][:19])
    except TargetUnavailable as e:
        print(tid, "DOWN", e)
