"""Migrate the authority DB, seed the sandbox tenant/service/budget and create actors.

Tokens are printed once and written to var/actors.local.json (git-ignored). They are sandbox credentials only.
    PYTHONPATH=. uv run python scripts/bootstrap.py [--reset-actors]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from decimal import Decimal

from greenops.config import ROOT, get_settings
from greenops.db import connect, migrate

ACTORS = [("lead", "Engineering lead", "operator"), ("teammate", "Read-only teammate", "viewer"),
          ("admin", "Sandbox operator admin", "admin"), ("judge", "Public judge (read-only)", "viewer"),
          ("operator2", "Second operator", "operator")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset-actors", action="store_true")
    args = ap.parse_args()
    s = get_settings()
    print("migrations applied:", migrate(s.database_url))
    cap = s.max_run_cost_usd if s.max_run_cost_usd is not None else (Decimal("0") if s.runtime_mode.value == "connected_demo" else Decimal("1"))
    with connect(s.database_url) as c:
        c.execute("INSERT INTO services (tenant_id, service_id, display_name, runtime_modes) VALUES (%s,'support-demo','Support demo service',%s) "
                  "ON CONFLICT DO NOTHING", (s.tenant_id, ["sample", "connected_demo", "replay"]))
        if s.runtime_mode.value == "connected_demo" and s.max_run_cost_usd is None:
            print("WARNING: MAX_RUN_COST_USD not set; connected budget profile not created (charged runs blocked: BUDGET_NOT_CONFIGURED)")
        else:
            c.execute("INSERT INTO budget_profiles (id, tenant_id, max_run_cost_usd, max_model_calls, max_conservative_cost_per_call_usd) "
                      "VALUES ('sandbox-approved-budget-v1', %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET max_run_cost_usd=EXCLUDED.max_run_cost_usd, "
                      "max_model_calls=EXCLUDED.max_model_calls, max_conservative_cost_per_call_usd=EXCLUDED.max_conservative_cost_per_call_usd",
                      (s.tenant_id, cap, s.max_model_calls_per_run, Decimal("0.002")))
        path = ROOT / "var" / "actors.local.json"
        existing = json.loads(path.read_text()) if path.exists() and not args.reset_actors else {}
        out = {}
        for aid, name, role in ACTORS:
            tok = existing.get(aid, {}).get("token") or "gov_" + secrets.token_urlsafe(32)
            c.execute("INSERT INTO actors (actor_id, tenant_id, display_name, role, token_sha256) VALUES (%s,%s,%s,%s,%s) "
                      "ON CONFLICT (actor_id) DO UPDATE SET token_sha256=EXCLUDED.token_sha256, role=EXCLUDED.role, disabled=false",
                      (aid, s.tenant_id, name, role, hashlib.sha256(tok.encode()).hexdigest()))
            out[aid] = {"role": role, "token": tok}
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    path.chmod(0o600)
    print(f"actors: {', '.join(f'{k} ({v['role']})' for k, v in out.items())}; tokens in {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
