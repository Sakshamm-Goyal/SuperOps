"""Docs consistency: local markdown links resolve, OpenAPI snapshot matches the app, every route is in API_REFERENCE."""
import json
import re
import sys
from pathlib import Path

from greenops.api.app import create_app
from greenops.config import ROOT

errors = []
for md in [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md"), *ROOT.glob("memory-sidecar/*.md")]:
    for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", md.read_text()):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (md.parent / target.replace("%20", " ").replace("%28", "(").replace("%29", ")")).exists():
            errors.append(f"{md.relative_to(ROOT)}: broken link {target}")
spec = create_app().openapi()
snap = ROOT / "docs" / "openapi.json"
if not snap.exists() or json.loads(snap.read_text()) != json.loads(json.dumps(spec, sort_keys=True)):
    errors.append("docs/openapi.json is stale: run `make openapi`")
ref = (ROOT / "docs" / "API_REFERENCE.md").read_text()
for path, ops in spec["paths"].items():
    for method in ops:
        norm = re.sub(r"\{[a-z_]+\}", "{id}", path)
        if f"{method.upper()} {norm}" not in ref and f"{method.upper()} {path}" not in ref:
            errors.append(f"API_REFERENCE.md missing {method.upper()} {path}")
print("\n".join(errors) or "docs consistent")
sys.exit(1 if errors else 0)
