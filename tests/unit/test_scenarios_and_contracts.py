"""Scenario screening over the generated synthetic data (D-01/03/04/05/06, policy) and API/OpenAPI/doc consistency."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from greenops.adapters.evidence import SampleSqlClient
from greenops.config import ROOT, get_settings
from greenops.domain.models import ServicePolicy
from greenops.domain.screening import MachineType, screen_cloud
from greenops.services.evidence_service import build_facts, forecast_stress

S, E = datetime(2026, 9, 30, tzinfo=timezone.utc), datetime(2026, 10, 21, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def facts():
    try:
        c = SampleSqlClient(get_settings().sample_source_url)
        inv = c.query("inventory", {"service_id": "support-demo", "as_of": E}).rows
    except Exception:
        pytest.skip("BLOCKED: sample source DB not loaded (make sample-data)")
    summ = c.query("telemetry_summary", {"start": S, "end": E}).rows
    stress = {}
    for key in ("gcp/greenops-sbx-staging/worker-stg-01", "gcp/greenops-sbx-staging/worker-stale-01"):
        series = c.query("telemetry_series", {"resource_key": key, "start": S, "end": E}).rows
        stress[key] = forecast_stress(series, S, E)[0]
    return build_facts(inv, summ, S, E, stress)


POLICY = ServicePolicy.model_validate_json((ROOT / "config/policies/support-demo-pol-v1.json").read_text())
MT = {"e2-standard-2": MachineType("e2-standard-2", Decimal(2), Decimal(8), "x86_64"), "e2-standard-4": MachineType("e2-standard-4", Decimal(4), Decimal(16), "x86_64"),
      "n2-standard-2": MachineType("n2-standard-2", Decimal(2), Decimal(8), "x86_64"), "t2a-standard-4": MachineType("t2a-standard-4", Decimal(4), Decimal(16), "arm64")}


def screen(facts, key, mt, action="LOCAL_WORKER_CONFIG_UPDATE"):
    return screen_cloud(facts[key], MT[mt], POLICY, E, action, Decimal("0.1"), Decimal("0.2"))


def failed(r):
    return {c.check_id for c in r.checks if c.status == "FAIL"}


def test_d01_colliding_display_names_stay_distinct(facts):
    assert len(facts) == 6
    assert {"gcp/greenops-sbx-prod/worker-prod-01", "gcp/greenops-sbx-staging/worker-stg-01"} <= set(facts)


def test_d04_low_average_high_peak_rejected(facts):
    f = facts["gcp/greenops-sbx-prod/worker-prod-01"]
    assert f.avg_cpu_pct < 11 and f.peak_cpu_pct > 79
    r = screen(facts, "gcp/greenops-sbx-prod/worker-prod-01", "e2-standard-2")
    assert r.outcome == "REJECTED" and {"CHK-CPU-PEAK", "CHK-POLICY"} <= failed(r)


def test_r1_rightsize_passes_only_at_safe_size(facts):
    k = "gcp/greenops-sbx-staging/worker-stg-01"
    assert screen(facts, k, "e2-standard-4").outcome == "ELIGIBLE_FOR_TRIAL"
    assert "CHK-CPU-PEAK" in failed(screen(facts, k, "e2-standard-2"))
    assert "CHK-COMPAT" in failed(screen(facts, k, "t2a-standard-4"))  # architecture change unsupported


def test_d05_memory_constrained(facts):
    r = screen(facts, "gcp/greenops-sbx-staging/worker-mem-01", "n2-standard-2", "GCP_MACHINE_TYPE_UPDATE")
    assert "CHK-MEM-PEAK" in failed(r)


def test_d03_d18_missing_and_stale_evidence_needs_evidence(facts):
    f = facts["gcp/greenops-sbx-staging/worker-stale-01"]
    assert f.stress_peak_cpu_pct is None and f.memory_rows < f.expected_rows
    r = screen(facts, "gcp/greenops-sbx-staging/worker-stale-01", "e2-standard-2")
    unknown = {c.check_id for c in r.checks if c.status == "UNKNOWN"}
    assert r.outcome in ("NEEDS_EVIDENCE", "REJECTED") and {"CHK-FRESHNESS", "CHK-COVERAGE-MEM"} <= unknown


def test_d06_stateful_and_frozen_rejected(facts):
    assert "CHK-COMPAT" in failed(screen(facts, "gcp/greenops-sbx-staging/db-stateful-01", "e2-standard-4"))
    assert "CHK-POLICY" in failed(screen(facts, "gcp/greenops-sbx-staging/worker-freeze-01", "e2-standard-2"))


def test_openapi_matches_runtime_routes_and_api_reference():
    from greenops.api.app import create_app
    app = create_app()
    spec = app.openapi()
    runtime = {(m, r.path) for r in app.routes if hasattr(r, "methods") and r.include_in_schema for m in r.methods if m not in ("HEAD", "OPTIONS")}
    documented = {(m.upper(), p) for p, ops in spec["paths"].items() for m in ops}
    assert runtime == documented
    ref = (ROOT / "docs/API_REFERENCE.md").read_text()
    for method, path in documented:
        norm = re.sub(r"\{[a-z_]+\}", "{id}", path).replace("{id}/events", "{id}/events")
        assert f"{method} {norm}" in ref or f"{method} {path}" in ref, f"{method} {path} missing from docs/API_REFERENCE.md"
    for name in ("ErrorEnvelope", "Resource", "Page", "EventPage", "Accepted", "CreateInvestigation", "ApproveRequest", "ExecuteRequest"):
        assert name in spec["components"]["schemas"]
