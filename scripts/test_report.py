"""Print PASS/FAIL/BLOCKED/NOT_RUN counts from the last pytest session (var/test-results/latest.json)."""
import json

from greenops.config import ROOT

d = json.loads((ROOT / "var" / "test-results" / "latest.json").read_text())
print(json.dumps(d["counts"]), "at", d["finished_at"])
for k, v in sorted(d["results"].items()):
    if v != "PASS":
        print(f"  {v:8} {k}")
