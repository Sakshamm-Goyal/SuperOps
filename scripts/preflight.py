"""Redacted readiness check for the configured runtime mode. Exit 1 with actionable missing inputs."""
import json
import sys

import httpx

from greenops.config import get_settings
from greenops.db import connect

s = get_settings()
checks, missing = {}, []
try:
    with connect(s.database_url) as c:
        checks["database"] = "ok, migrations=" + ",".join(r["version"] for r in c.execute("SELECT version FROM schema_migrations"))
        checks["budget_profile"] = "ok" if c.execute("SELECT 1 FROM budget_profiles").fetchone() else "missing (set MAX_RUN_COST_USD, rerun bootstrap)"
        checks["trial_profile"] = "ok" if c.execute("SELECT 1 FROM trial_profiles WHERE status='ACTIVE' AND expires_at > now()").fetchone() else "missing/expired"
except Exception as e:
    checks["database"] = f"unavailable ({type(e).__name__})"
try:
    h = httpx.get(s.memory_base_url + "/health", headers={"Authorization": f"Bearer {s.memory_auth_token}"}, timeout=10).json()
    checks["memory"] = f"{h['status']} semantic={h['embedding_profile'].get('semantic')} engine={h['engine']['upstream_sha'][:12]}"
except Exception as e:
    checks["memory"] = f"unavailable ({type(e).__name__})"
if s.runtime_mode.value == "connected_demo":
    for name, ok in (("ZETARIS_ORG_ID/auth", s.zetaris_configured), ("MODEL_ID/MODEL_API_KEY", s.model_configured),
                     ("MAX_RUN_COST_USD", s.max_run_cost_usd is not None)):
        if not ok:
            missing.append(name)
    if "semantic=True" not in checks["memory"]:
        missing.append("memory sidecar with EMBEDDING_MODE=nvidia (semantic embeddings)")
    if s.source_names["cloud"].split(".")[0] == s.source_names["ai"].split(".")[0]:
        missing.append("ZETARIS_SOURCE_CLOUD and ZETARIS_SOURCE_AI must be different physical datasources")
checks["runtime_mode"] = s.runtime_mode.value
checks["sandbox_writes_enabled"] = s.sandbox_writes_enabled
print(json.dumps({"checks": checks, "missing": missing}, indent=1))
sys.exit(1 if missing or "unavailable" in json.dumps(checks) else 0)
