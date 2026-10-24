"""Minimal secret scan over tracked/untracked repo files (not a substitute for a dedicated scanner)."""
import re
import subprocess
import sys
from pathlib import Path

PAT = re.compile(r"(nvapi-[A-Za-z0-9_-]{20,}|gov_[A-Za-z0-9_-]{30,}|sk-[A-Za-z0-9]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16})")
files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.split()
hits = []
for f in files:
    p = Path(f)
    if p.suffix in (".pdf", ".docx", ".png") or not p.is_file():
        continue
    for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
        if PAT.search(line):
            hits.append(f"{f}:{i}")
print("secret scan:", "clean" if not hits else hits)
sys.exit(1 if hits else 0)
