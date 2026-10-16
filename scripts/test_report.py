"""Print PASS/FAIL/BLOCKED/NOT_RUN counts from the last pytest session (var/test-results/latest.json).

--release-gate: exit 1 unless every recorded check PASSed (BLOCKED sponsor checks block a release; they are never PASS).
"""
import json
import sys

from greenops.config import ROOT

d = json.loads((ROOT / "var" / "test-results" / "latest.json").read_text())
print(json.dumps(d["counts"]), "at", d["finished_at"])
for k, v in sorted(d["results"].items()):
    if v != "PASS":
        print(f"  {v:8} {k}")
if "--release-gate" in sys.argv:
    bad = {k: v for k, v in d["counts"].items() if k != "PASS" and v}
    if bad or not d["counts"].get("PASS"):
        print("RELEASE GATE: FAIL", bad)
        sys.exit(1)
    print("RELEASE GATE: PASS")
