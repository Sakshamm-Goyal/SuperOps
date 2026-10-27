"""Operator command: supersede a wrong memory with a reviewed correction (never a deletion).

    make correct-memory RECEIPT=<application_receipt_id> ACTOR=lead NOTE="why the original is wrong"

Authenticates the operator, writes a `correction` envelope that supersedes the receipt through the transactional
outbox, and delivers it. The sidecar links lineage both ways; recall then reports the original as SUPERSEDED
(historical), so the prior-failure guard no longer applies it. Both records and the audit trail remain.
"""
import argparse
import hashlib
import json
import os
import uuid

from greenops.config import ROOT, get_settings
from greenops.db import connect
from greenops.services import memory_service
from greenops.services.common import Runtime

ap = argparse.ArgumentParser()
ap.add_argument("receipt_id")
ap.add_argument("--actor", required=True)
ap.add_argument("--note", required=True)
a = ap.parse_args()
s = get_settings()
tok = os.environ.get("OPERATOR_TOKEN") or json.loads((ROOT / "var" / "actors.local.json").read_text())[a.actor]["token"]
review = f"operator:{a.actor}:{uuid.uuid4()}"
with connect(s.database_url) as c:
    actor = c.execute("SELECT * FROM actors WHERE actor_id=%s AND token_sha256=%s", (a.actor, hashlib.sha256(tok.encode()).hexdigest())).fetchone()
    if not actor or actor["role"] not in ("operator", "admin"):
        raise SystemExit("refused: operator authentication failed")
    old = c.execute("SELECT * FROM memory_outbox WHERE application_receipt_id=%s AND tenant_id=%s", (a.receipt_id, actor["tenant_id"])).fetchone()
    if old is None or old["status"] != "SENT":
        raise SystemExit("refused: receipt not found or not yet delivered")
    env = old["envelope"]
    rid = memory_service.enqueue(c, tenant_id=old["tenant_id"], service_id=old["service_id"], kind="correction", source_ref=f"correction:{review}",
                                 finding=f"Correction of {a.receipt_id} by {a.actor}: {a.note}"[:2000], evidence_refs=env["evidence_refs"],
                                 applicability=env["applicability"], signature=None, target_id=env["scope"].get("target_id"),
                                 supersedes_receipt_id=a.receipt_id, correction_review_id=review)
print(json.dumps({"correction_receipt_id": str(rid), "supersedes": a.receipt_id, "review": review,
                  "delivery": memory_service.dispatch(Runtime.from_settings(s))}, indent=1))
