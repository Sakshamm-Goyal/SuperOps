"""Operator command: record the human resolution of a RECOVERY_REQUIRED action (docs/OPERATIONS.md).

    PYTHONPATH=. uv run python scripts/resolve_action.py <action_id> --actor lead --note "inspected; kept on-call value 6"
Authenticates the named operator (OPERATOR_TOKEN or var/actors.local.json), reads back the target and releases it.
"""
import argparse
import hashlib
import json
import os

from greenops.config import ROOT, get_settings
from greenops.db import connect
from greenops.services.common import Runtime
from greenops.services.execution import resolve_manually

ap = argparse.ArgumentParser()
ap.add_argument("action_id")
ap.add_argument("--actor", required=True)
ap.add_argument("--note", required=True)
a = ap.parse_args()
s = get_settings()
tok = os.environ.get("OPERATOR_TOKEN") or json.loads((ROOT / "var" / "actors.local.json").read_text())[a.actor]["token"]
with connect(s.database_url) as c:
    if not c.execute("SELECT 1 FROM actors WHERE actor_id=%s AND token_sha256=%s", (a.actor, hashlib.sha256(tok.encode()).hexdigest())).fetchone():
        raise SystemExit("refused: operator authentication failed")
print(json.dumps(resolve_manually(Runtime.from_settings(s), a.action_id, a.actor, a.note), indent=1, default=str))
