"""Deterministic evidence report built only from committed state (no agent run)."""
from __future__ import annotations

import html
import json
from decimal import Decimal

from greenops.db import connect
from greenops.domain.quantities import canonical_hash
from greenops.services.common import AppError, now

REPORT_VERSION = "report-v1"


def build(db: str, tenant_id: str, inv_id) -> dict:
    with connect(db) as c:
        inv = c.execute("SELECT * FROM investigations WHERE id=%s AND tenant_id=%s", (inv_id, tenant_id)).fetchone()
        if inv is None:
            raise AppError("NOT_FOUND", 404, "investigation not found")
        plans = c.execute("SELECT * FROM plans WHERE investigation_id=%s ORDER BY path, candidate_no", (inv_id,)).fetchall()
        pids = [p["id"] for p in plans]
        trials = c.execute("SELECT id, plan_id, status, trial_hash, suite_id, result, started_at, finished_at FROM trials WHERE plan_id = ANY(%s) ORDER BY created_at", (pids,)).fetchall()
        approvals = c.execute("SELECT id, plan_id, actor_id, plan_hash, trial_id, trial_hash, status, created_at, expires_at, recovery_scope FROM approvals WHERE plan_id = ANY(%s)", (pids,)).fetchall()
        actions = c.execute("SELECT * FROM actions WHERE plan_id = ANY(%s)", (pids,)).fetchall()
        journal = c.execute("SELECT * FROM action_journal WHERE action_id = ANY(%s) ORDER BY action_id, seq", ([a["id"] for a in actions],)).fetchall()
        receipts = c.execute("SELECT id, template_id, template_version, source_system, runtime_mode, completeness, row_count, result_hash, receipt, created_at "
                             "FROM query_receipts WHERE investigation_id=%s ORDER BY created_at", (inv_id,)).fetchall()
        evidence = c.execute("SELECT id, receipt_id, kind, subject, observed_from, observed_to, retrieved_at, result_kind, data_origin, quality_flags "
                             "FROM evidence WHERE investigation_id=%s", (inv_id,)).fetchall()
        calls = c.execute("SELECT role, model_id, status, input_tokens, output_tokens, requests, tool_calls, duration_ms FROM model_calls m "
                          "WHERE investigation_id=%s OR trial_id = ANY(%s) ORDER BY created_at", (inv_id, [t["id"] for t in trials])).fetchall()
        outbox = c.execute("SELECT application_receipt_id, receipt_kind, source_ref, status, engine_memory_id, signature FROM memory_outbox "
                           "WHERE source_ref = ANY(%s)", ([f"plan:{p}" for p in pids] + [f"trial:{t['id']}" for t in trials] + [f"action:{a['id']}" for a in actions],)).fetchall()
    summ = inv["summary"]
    for t in trials:  # per-case development diagnostics stay in the trial record, out of the summary report
        if t["result"]:
            for side in ("baseline", "candidate"):
                if side in t["result"]:
                    t["result"][side] = {k: v for k, v in t["result"][side].items() if k != "per_case"}
            t["result"].pop("runs", None)
    report = {
        "report_version": REPORT_VERSION, "generated_at": now().isoformat(),
        "labels": {"runtime_mode": inv["runtime_mode"], "data_origin": inv["data_origin"],
                   "executor": "local_analogue (real local configuration change; not a GCP resize)",
                   "model_id": summ.get("model_id"), "memory_mode": inv["memory_mode"]},
        "question": inv["question"], "investigation": {k: inv[k] for k in ("id", "service_id", "status", "stage", "actor_id", "policy_version",
                                                                            "data_manifest_id", "interval_start", "interval_end", "as_of", "created_at", "updated_at")},
        "outcome": summ.get("outcome"), "federation": summ.get("federation"), "forecast": summ.get("forecast"),
        "memory": {k: summ.get("memory", {}).get(k) for k in ("status", "queries", "applicable", "historical", "embedding_profile", "engine")},
        "plans": [{"id": p["id"], "path": p["path"], "candidate_no": p["candidate_no"], "revision": p["revision"], "status": p["status"],
                   "signature": (p["screening"] or {}).get("signature"), "plan_hash": p["plan_hash"], "target_key": p["target_key"],
                   "action": p["core"]["action"], "executor": p["core"]["executor"], "projection": p["core"].get("projection"),
                   "versions": p["core"]["versions"], "screening": p["screening"], "critic": p["critic"], "impacts": p["impacts"],
                   "memory_refs": p["memory_refs"], "stale_reason": p["stale_reason"], "evidence_ids": p["core"]["evidence_ids"],
                   "rationale_untrusted_model_text": p["rationale"]} for p in plans],
        "trials": trials, "approvals": approvals, "actions": actions, "action_journal": journal,
        "evidence_receipts": [{**{k: r[k] for k in ("id", "template_id", "template_version", "source_system", "runtime_mode", "completeness",
                                                    "row_count", "result_hash", "created_at")},
                               "sources": r["receipt"].get("sources"), "page_count": r["receipt"].get("page_count"),
                               "warnings": r["receipt"].get("warnings"), "query_close": r["receipt"].get("query_close"),
                               "request_ids": r["receipt"].get("request_ids")} for r in receipts],
        "evidence": evidence, "model_calls": calls, "memory_outbox": outbox,
        "limitations": ["Synthetic data (data_origin=synthetic); not a customer fleet.",
                        "Cloud savings are projections at synthetic dated rates, not invoice savings.",
                        "The executed change is a local analogue (worker max_concurrency), not a GCP VM resize.",
                        "Carbon is an estimate with a named synthetic method, or UNKNOWN.",
                        "AI results on 40 development cases are a small local evaluation; holdout evaluation is separate."],
    }
    report["content_hash"] = canonical_hash(json.loads(json.dumps(report, default=str), parse_float=Decimal))
    return report


def to_html(r: dict) -> str:
    e = lambda v: html.escape(str(v))
    rows = "".join(f"<tr><td>{e(p['path'])}#{p['candidate_no']}</td><td>{e(p['signature'])}</td><td><b>{e(p['status'])}</b></td>"
                   f"<td>{e((p['screening'] or {}).get('outcome'))}</td><td>{e('; '.join(c['check_id'] + ': ' + c['detail'] for c in (p['screening'] or {}).get('checks', []) if c['status'] != 'PASS') or 'all checks passed')}</td>"
                   f"<td>{e((p['impacts'] or {}).get('net_saving', (p['impacts'] or {}).get('reason', '')))}</td></tr>" for p in r["plans"])
    acts = "".join(f"<li>{e(a['id'])}: <b>{e(a['status'])}</b> on {e(a['target_key'])} ({e(a['executor'])})</li>" for a in r["actions"]) or "<li>No action executed.</li>"
    rec = "".join(f"<li>{e(x['template_id'])} via {e(x['source_system'])} {e(x['sources'])}: {e(x['row_count'])} rows, {e(x['completeness'])}, pages {e(x['page_count'])}</li>" for x in r["evidence_receipts"])
    mem = r["memory"] or {}
    mem_items = "".join(f"<li>[{'applicable' if m.get('applicable') else 'historical — retest required'}] {e(m['finding'])}</li>"
                        for m in (mem.get("applicable") or []) + (mem.get("historical") or [])) or "<li>None recalled.</li>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SuperOps report {e(r['investigation']['id'])}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1b1f23;background:#fff}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.4rem;vertical-align:top}}.lab{{background:#fff4d6;padding:.5rem;border:1px solid #e0c060}}</style></head>
<body><h1>SuperOps — evidence report</h1>
<p class="lab">Runtime mode: <b>{e(r['labels']['runtime_mode'])}</b> · Data origin: <b>{e(r['labels']['data_origin'])}</b> · Executor: {e(r['labels']['executor'])} · Model: {e(r['labels']['model_id'])} · Memory: {e(r['labels']['memory_mode'])}</p>
<p><b>Question:</b> {e(r['question'])}</p><p><b>Outcome:</b> {e((r['outcome'] or {}).get('status'))} · Investigation {e(r['investigation']['id'])} · policy {e(r['investigation']['policy_version'])} · generated {e(r['generated_at'])}</p>
<h2>Candidates (including rejections)</h2><table><tr><th>Candidate</th><th>Signature</th><th>Status</th><th>Screening</th><th>Failed / unknown checks</th><th>Projected net (720 h)</th></tr>{rows}</table>
<h2>Actions</h2><ul>{acts}</ul><h2>Prior experiments (memory)</h2><ul>{mem_items}</ul><h2>Evidence receipts</h2><ul>{rec}</ul>
<h2>Limitations</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in r['limitations'])}</ul><p>Content hash {e(r['content_hash'])}</p></body></html>"""
