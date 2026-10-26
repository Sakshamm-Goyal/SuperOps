"""Memory outbox (PostgreSQL → H-MEM sidecar) and scoped recall with application-side applicability re-checks."""
from __future__ import annotations

import uuid

from greenops.adapters.memory import MemoryUnavailable
from greenops.db import J, connect
from greenops.domain.quantities import canonical_hash
from greenops.services.common import Runtime, now


def enqueue(conn, *, tenant_id: str, service_id: str, kind: str, source_ref: str, finding: str, evidence_refs: list[str],
            applicability: dict, signature: str | None, target_id: str | None,
            supersedes_receipt_id: str | None = None, correction_review_id: str | None = None) -> uuid.UUID:
    """Commit the envelope with the receipt it describes (same transaction as the caller's status change)."""
    rid = uuid.uuid4()
    env = {"application_receipt_id": str(rid), "kind": kind, "scope": {"tenant_id": tenant_id, "service_id": service_id, "target_id": target_id},
           "finding": finding[:2000], "evidence_refs": [str(e) for e in evidence_refs][:50], "applicability": applicability,
           "tags": [f"kind:{kind}"]}
    if supersedes_receipt_id:  # reviewed correction: the sidecar links lineage and recall marks the predecessor SUPERSEDED
        env["supersedes_receipt_id"], env["correction_review_id"] = str(supersedes_receipt_id), correction_review_id
    env["content_hash"] = canonical_hash({k: env[k] for k in ("kind", "scope", "finding", "evidence_refs", "applicability")})
    conn.execute("INSERT INTO memory_outbox (id, tenant_id, service_id, receipt_kind, application_receipt_id, source_ref, signature, envelope, "
                 "content_hash, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING')",
                 (uuid.uuid4(), tenant_id, service_id, kind, rid, source_ref, signature, J(env), env["content_hash"]))
    return rid


def dispatch(rt: Runtime, limit: int = 20) -> dict:
    """Serial, idempotent delivery. A duplicate delivery returns the same engine id (sidecar dedupes by receipt)."""
    sent = failed = 0
    with connect(rt.db) as c:
        rows = c.execute("SELECT * FROM memory_outbox WHERE status IN ('PENDING','FAILED') AND attempts < 20 ORDER BY created_at LIMIT %s",
                         (limit,)).fetchall()
    if not rows:
        return {"sent": 0, "failed": 0}
    try:
        client = rt.memory_factory()
    except MemoryUnavailable as e:
        return {"sent": 0, "failed": len(rows), "error": e.code}
    for r in rows:
        try:
            ack = client.remember(r["envelope"])
            with connect(rt.db) as c:
                c.execute("UPDATE memory_outbox SET status='SENT', engine_memory_id=%s, sent_at=now(), attempts=attempts+1, last_error=NULL WHERE id=%s",
                          (ack["engine_memory_id"], r["id"]))
                c.execute("UPDATE actions SET memory_sync_status='SENT' WHERE id::text = %s", (r["source_ref"].removeprefix("action:"),))
            sent += 1
        except MemoryUnavailable as e:
            with connect(rt.db) as c:
                c.execute("UPDATE memory_outbox SET status='FAILED', attempts=attempts+1, last_error=%s WHERE id=%s", (e.code, r["id"]))
                c.execute("UPDATE actions SET memory_sync_status='FAILED' WHERE id::text = %s", (r["source_ref"].removeprefix("action:"),))
            failed += 1
    return {"sent": sent, "failed": failed}


def applicable(envelope_app: dict, current: dict) -> list[str]:
    """Second, application-side applicability check (the sidecar already filtered). Returns inapplicable reasons."""
    reasons = []
    for k in ("policy_version", "workload_version", "config_version", "model_version", "test_version"):
        if envelope_app.get(k) is not None and envelope_app.get(k) != current.get(k):
            reasons.append(f"{k.upper()}_CHANGED")
    return reasons


def recall(rt: Runtime, inv: dict, query: str, current_by_path: dict[str, dict]) -> dict:
    """Recall across both paths' applicability profiles; join outbox signatures; re-validate scope + versions."""
    client = rt.memory_factory()
    out = {"applicable": [], "historical": [], "query": query, "retrieved_at": now().isoformat()}
    seen = set()
    for path, cur in current_by_path.items():
        res = client.recall(inv["tenant_id"], inv["service_id"], query, cur, top_k=8)
        ids = [i["application_receipt_id"] for i in res["items"] + res["historical"]]
        with connect(rt.db) as c:
            rows = {str(r["application_receipt_id"]): r for r in c.execute(
                "SELECT * FROM memory_outbox WHERE application_receipt_id::text = ANY(%s) AND tenant_id=%s AND service_id=%s",
                (ids, inv["tenant_id"], inv["service_id"])).fetchall()}
        for bucket, items in (("applicable", res["items"]), ("historical", res["historical"])):
            for i in items:
                rid = i["application_receipt_id"]
                row = rows.get(rid)
                if row is None or rid in seen:
                    continue  # unknown to our authority store → never injected
                if (row["signature"] or "cloud:").split(":", 1)[0] != path:
                    continue  # each memory is judged only under its own path's applicability profile
                env = row["envelope"]
                reasons = applicable(env["applicability"], cur) + list(i.get("inapplicable_reasons", []))
                b = "applicable" if bucket == "applicable" and not reasons else "historical"
                seen.add(rid)
                out[b].append({"memory_id": rid, "engine_memory_id": i["engine_memory_id"], "kind": env["kind"], "finding": env["finding"],
                               "signature": row["signature"], "score": i.get("score"), "evidence_refs": env["evidence_refs"],
                               "applicability": env["applicability"], "inapplicable_reasons": sorted(set(reasons)), "source_ref": row["source_ref"],
                               "applicable": b == "applicable"})
    return out
