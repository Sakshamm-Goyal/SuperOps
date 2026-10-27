"""Evidence collection: every query persists an immutable receipt and evidence record before use."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from greenops.adapters.evidence import EvidenceResult, ZetarisError
from greenops.db import J, connect
from greenops.domain.capacity import LAG, Point, residual_quantile, stress_peak
from greenops.domain.quantities import DomainError
from greenops.domain.screening import ResourceFacts
from greenops.services.common import AppError, Runtime, now

RESULT_KIND = {"telemetry_summary": "measured", "telemetry_series": "measured", "billing_rows": "measured",
               "ai_usage_by_run": "measured", "ai_duplicate_lookups": "measured", "service_cost_rollup": "measured"}
FORECAST_VERSION = "seasonal-naive-lag96-resq95-v1"


def ts(v: str | None) -> datetime | None:
    if v is None:
        return None
    return datetime.fromisoformat(v.replace("Z", "+00:00").replace(" ", "T"))


def as_bool(v) -> bool:
    return v is True or str(v).lower() in ("true", "t", "1")


def collect(rt: Runtime, inv: dict, template_id: str, params: dict, *, subject: str | None = None,
            client=None, max_rows: int = 5000) -> tuple[str, EvidenceResult]:
    client = client or _client(rt, inv["service_id"])
    try:
        res = client.query(template_id, params, max_rows=max_rows)
    except (ZetarisError, DomainError) as e:
        raise AppError(getattr(e, "code", "DEPENDENCY_UNAVAILABLE"), 503, f"evidence query {template_id} failed: {e}")
    rid, eid = uuid.uuid4(), uuid.uuid4()
    rec = {**res.receipt, "receipt_id": str(rid)}
    observed = [ts(r.get("observed_at") or r.get("last_observed_at")) for r in res.rows if r.get("observed_at") or r.get("last_observed_at")]
    with connect(rt.db) as c:
        c.execute("INSERT INTO query_receipts (id, investigation_id, tenant_id, service_id, template_id, template_version, source_system, "
                  "runtime_mode, completeness, row_count, result_hash, receipt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (rid, inv["id"], inv["tenant_id"], inv["service_id"], template_id, rec["template_version"], res.source_system,
                   inv["runtime_mode"], res.completeness, len(res.rows), rec["result_hash"], J(rec)))
        c.execute("INSERT INTO evidence (id, receipt_id, investigation_id, tenant_id, service_id, kind, subject, observed_from, observed_to, "
                  "retrieved_at, result_kind, data_origin, quality_flags, data) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (eid, rid, inv["id"], inv["tenant_id"], inv["service_id"], template_id, subject,
                   min(observed) if observed else None, max(observed) if observed else None, now(),
                   RESULT_KIND.get(template_id, "measured"), inv["data_origin"], J(res.warnings), J({"rows": res.rows})))
    return str(eid), res


def _client(rt: Runtime, service_id: str):
    try:
        return rt.evidence_factory(service_id)
    except TypeError:  # test runtimes inject a zero-argument factory
        return rt.evidence_factory()


def resource_key(r: dict) -> str:
    return f"{r['provider']}/{r['project_id']}/{r['resource_id']}"


def build_facts(inventory: list[dict], summary: list[dict], interval_start: datetime, interval_end: datetime,
                stress: dict[str, Decimal | None]) -> dict[str, ResourceFacts]:
    expected = int((interval_end - interval_start).total_seconds() // 900)
    by_key = {resource_key(s): s for s in summary}
    out = {}
    for r in inventory:
        k = resource_key(r)
        s = by_key.get(k, {})
        # duplicates: rows beyond distinct timestamps are not extra observations
        rows = int(s.get("distinct_times") or 0)
        dupes = int(s.get("row_count") or 0) - rows
        out[k] = ResourceFacts(
            resource_key=k, environment=r["environment"], machine_type=r["machine_type"], vcpu=Decimal(r["vcpu"]),
            memory_gib=Decimal(r["memory_gib"]), architecture=r["architecture"], region=r["region"],
            stateful=as_bool(r["stateful"]), local_ssd=as_bool(r["local_ssd"]), gpu=as_bool(r["gpu"]),
            expected_rows=expected, cpu_rows=min(rows, int(s.get("cpu_rows") or 0)) - max(0, dupes),
            memory_rows=min(rows, int(s.get("memory_rows") or 0)) - max(0, dupes),
            last_observed_at=ts(s.get("last_observed_at")),
            avg_cpu_pct=Decimal(s["avg_cpu_percent"]) if s.get("avg_cpu_percent") else None,
            peak_cpu_pct=Decimal(s["peak_cpu_percent"]) if s.get("peak_cpu_percent") else None,
            peak_memory_bytes=Decimal(s["peak_memory_bytes"]) if s.get("peak_memory_bytes") else None,
            stress_peak_cpu_pct=stress.get(k))
    return out


def forecast_stress(series_rows: list[dict], interval_start: datetime, as_of: datetime) -> tuple[Decimal | None, dict]:
    """Frozen protocol: residual envelope fitted on daily origins of days 2–17 (dev+calibration), applied at as_of."""
    pts = [Point(ts(r["observed_at"]), Decimal(r["cpu_percent"])) for r in series_rows if r.get("cpu_percent") is not None]
    meta = {"method": FORECAST_VERSION, "fit_origins": [str(interval_start + timedelta(days=1)), str(interval_start + timedelta(days=17))],
            "observations": len(pts), "label": "stress envelope, not a calibrated confidence interval"}
    try:
        q = residual_quantile(pts, interval_start + timedelta(days=1), interval_start + timedelta(days=17))
        peak = stress_peak(pts, as_of, q)
    except DomainError as e:
        meta["unavailable_reason"] = str(e)
        return None, meta
    meta.update({"residual_q95_pct": format(q, "f"), "stress_peak_cpu_pct": format(peak, "f"), "horizon_quarter_hours": LAG})
    return peak, meta
