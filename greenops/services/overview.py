"""Dashboard read model: one tenant-scoped summary of committed state. No agent run, no provider call except memory health."""
from __future__ import annotations

import os
from decimal import Decimal

from greenops.db import connect
from greenops.services.common import Runtime, now

LIVE = ("DRAFT", "AWAITING_APPROVAL", "APPROVED", "VALIDATED", "NEEDS_EVIDENCE")


def _d(v) -> Decimal | None:
    try:
        return Decimal(str(v)) if v is not None else None
    except ArithmeticError:
        return None


def _sum(vals) -> str | None:
    vals = [v for v in vals if v is not None]
    return format(sum(vals, Decimal(0)).quantize(Decimal("0.001")), "f") if vals else None


def build(rt: Runtime, tenant_id: str) -> dict:
    s = rt.settings
    with connect(rt.db) as c:
        inv_by = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM investigations WHERE tenant_id=%s GROUP BY status", (tenant_id,))}
        plan_by = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM plans WHERE tenant_id=%s GROUP BY status", (tenant_id,))}
        # Latest investigation that produced plans: its live candidates are the current proposal; earlier runs would double count.
        latest = c.execute("SELECT i.id FROM investigations i WHERE i.tenant_id=%s AND EXISTS (SELECT 1 FROM plans p WHERE p.investigation_id=i.id) "
                           "ORDER BY i.created_at DESC LIMIT 1", (tenant_id,)).fetchone()
        plans = c.execute("SELECT status, impacts, screening FROM plans WHERE investigation_id=%s", (latest["id"],)).fetchall() if latest else []
        verified = c.execute("SELECT p.impacts FROM actions a JOIN plans p ON p.id=a.plan_id WHERE a.tenant_id=%s AND a.status='VERIFIED'", (tenant_id,)).fetchall()
        rej = c.execute("SELECT chk->>'check_id' AS check_id, COUNT(*) AS n FROM plans p, jsonb_array_elements(p.screening->'checks') chk "
                        "WHERE p.tenant_id=%s AND p.status='REJECTED' AND chk->>'status' = 'FAIL' GROUP BY 1 ORDER BY 2 DESC", (tenant_id,)).fetchall()
        receipts = c.execute("SELECT COUNT(*) AS n, MAX(created_at) AS last FROM query_receipts WHERE tenant_id=%s AND source_system='zetaris'", (tenant_id,)).fetchone()
        outbox = c.execute("SELECT COUNT(*) FILTER (WHERE status='SENT') AS sent, COUNT(*) AS total FROM memory_outbox WHERE tenant_id=%s", (tenant_id,)).fetchone()
        mem_use = c.execute("SELECT COALESCE(SUM(jsonb_array_length(COALESCE(summary->'memory'->'queries','[]'))),0) AS recalls, "
                            "COALESCE(SUM(jsonb_array_length(COALESCE(summary->'memory'->'applicable','[]'))),0) AS hits FROM investigations WHERE tenant_id=%s",
                            (tenant_id,)).fetchone()
        recent = c.execute("SELECT e.at, e.kind, e.investigation_id, e.actor, e.payload FROM investigation_events e JOIN investigations i ON i.id=e.investigation_id "
                           "WHERE i.tenant_id=%s ORDER BY e.at DESC LIMIT 12", (tenant_id,)).fetchall()
    live = [p for p in plans if p["status"] in LIVE]
    blocked = [p for p in plans if p["status"] == "REJECTED"]
    gross = lambda p: _d((p["impacts"] or {}).get("gross_saving"))
    carbon = lambda p: (lambda cb: (_d(cb.get("baseline_kg_co2e")) or 0) - (_d(cb.get("candidate_kg_co2e")) or 0) if cb else None)((p["impacts"] or {}).get("carbon"))
    try:
        h = rt.memory_factory().health()
        mem = {"status": h.get("status"), "semantic": (h.get("embedding_profile") or {}).get("semantic"),
               "embedding_model": (h.get("embedding_profile") or {}).get("model_id") or (h.get("embedding_profile") or {}).get("kind"),
               "engine_sha": ((h.get("engine") or {}).get("upstream_sha") or "")[:12] or None}
    except Exception as e:
        mem = {"status": f"unavailable:{getattr(e, 'code', type(e).__name__)}", "semantic": None, "embedding_model": None, "engine_sha": None}
    connected = s.runtime_mode.value == "connected_demo"
    summarise = lambda e: (e["payload"] or {}).get("reason") or (e["payload"] or {}).get("signature") or (e["payload"] or {}).get("status") or e["kind"]
    return {
        "runtime_mode": s.runtime_mode.value, "service_id": "support-demo", "generated_at": now(),
        "investigations": {"total": sum(inv_by.values()), "by_status": inv_by},
        "plans": {"total": sum(plan_by.values()), "by_status": plan_by},
        "savings": {"proposed_monthly_usd": _sum(gross(p) for p in live), "blocked_monthly_usd": _sum(gross(p) for p in blocked),
                    "verified_monthly_usd": _sum(_d((v["impacts"] or {}).get("gross_saving")) for v in verified),
                    "latest_investigation_id": latest and str(latest["id"]),
                    "basis": "projected gross saving over a 720 h horizon at dated synthetic rates for the latest investigation's live candidates; "
                             "blocked = tempting candidates the evidence rejected; verified = projections of changes verified in the local sandbox analogue "
                             "(not invoice savings)"},
        "carbon": {"proposed_monthly_kgco2e": _sum(carbon(p) for p in live), "basis": "estimated operational energy at a synthetic grid factor; embodied excluded"},
        "rejections_by_check": rej,
        "memory": {**mem, "engine": "Meterless H-MEM", "records": outbox["sent"], "pending": outbox["total"] - outbox["sent"],
                   "recalls": mem_use["recalls"], "applicable_hits": mem_use["hits"]},
        "federation": {"mode": "zetaris" if connected else "sample_local_db (not federation)",
                       "sources": [{"group": g, "name": n} for g, n in s.source_names.items()] if connected else [],
                       "receipts": receipts["n"], "last_receipt_at": receipts["last"]},
        "model": {"agent_model_id": s.model_id if (connected or os.environ.get("SAMPLE_MODEL") == "nvidia") else "scripted-sample-roles",
                  "copilot_model_id": os.environ.get("COPILOT_MODEL_ID", "claude-haiku-4-5-20251001") if os.environ.get("ANTHROPIC_API_KEY") else None},
        "recent": [{"at": e["at"], "kind": e["kind"], "investigation_id": e["investigation_id"], "actor": e["actor"], "summary": str(summarise(e))[:160]}
                   for e in recent],
    }
