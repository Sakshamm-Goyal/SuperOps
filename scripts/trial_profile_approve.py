"""Operator command: approve a reviewed trial profile (OPERATIONS.md). Not callable by any model or agent tool.

    PYTHONPATH=. uv run python scripts/trial_profile_approve.py config/trial-profiles/sandbox-trials-v1.json --actor lead
Authenticates the named operator with OPERATOR_TOKEN (env) or var/actors.local.json, checks that every fixture is a
registered disposable trial fixture distinct from all action targets, and stores the profile hash, scope and expiry.
Editing the profile file afterwards invalidates it (hash mismatch at trial time).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import timedelta

from greenops.adapters.sandbox import REGISTRY
from greenops.config import ROOT, get_settings
from greenops.db import J, connect
from greenops.domain.quantities import canonical_hash
from greenops.services.common import now


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--actor", required=True)
    a = ap.parse_args()
    s = get_settings()
    doc = json.loads((ROOT / a.profile).read_text() if not os.path.isabs(a.profile) else open(a.profile).read())
    token = os.environ.get("OPERATOR_TOKEN") or json.loads((ROOT / "var" / "actors.local.json").read_text())[a.actor]["token"]
    action_targets = {t for t, v in REGISTRY["workers"].items() if v["role"] == "action_target"} | set(REGISTRY["ai_workflows"])
    for f in doc["local_worker_pair"]["fixtures"]:
        spec = REGISTRY["workers"].get(f)
        if spec is None or spec["role"] != "trial_fixture" or f in action_targets:
            raise SystemExit(f"refused: {f} is not a registered disposable trial fixture")
    if not set(doc["forbidden_targets"]) >= action_targets:
        raise SystemExit("refused: profile must forbid every action target")
    with connect(s.database_url) as c:
        actor = c.execute("SELECT * FROM actors WHERE actor_id=%s AND token_sha256=%s AND NOT disabled", (a.actor, hashlib.sha256(token.encode()).hexdigest())).fetchone()
        if actor is None or actor["role"] not in ("operator", "admin"):
            raise SystemExit("refused: operator authentication failed")
        h = canonical_hash(doc)
        c.execute("INSERT INTO trial_profiles (id, tenant_id, service_id, document, profile_hash, approved_by, approved_at, expires_at, status) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE') ON CONFLICT (id) DO UPDATE SET document=EXCLUDED.document, profile_hash=EXCLUDED.profile_hash, "
                  "approved_by=EXCLUDED.approved_by, approved_at=EXCLUDED.approved_at, expires_at=EXCLUDED.expires_at, status='ACTIVE'",
                  (doc["id"], actor["tenant_id"], doc["service_id"], J(doc), h, actor["actor_id"], now(), now() + timedelta(days=doc["valid_days"])))
    print(f"approved trial profile {doc['id']} hash {h} by {a.actor}")


if __name__ == "__main__":
    main()
