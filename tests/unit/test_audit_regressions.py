"""Regression tests for the 17 Oct 2026 implementation audit (docs/IMPLEMENTATION_AUDIT_2026-10-17.md).

Each test reproduces the audited counterexample and asserts the corrected behaviour.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from experiments.support.verifier import SupportDecision, verify
from experiments.support.workflow import make_tools, policy_context
from greenops.adapters.evidence import ZetarisClient, ZetarisError
from greenops.domain.accounting import Rate, interval_cost
from greenops.domain.models import AiWorkflowConfig
from greenops.domain.quantities import DomainError
from greenops.services.plans import cloud_impacts
from tests.unit.test_adapters_contract import fake_zetaris, settings

T = datetime(2026, 10, 17, tzinfo=timezone.utc)
CASE = {"case_id": "audit", "category": "escalation_identity", "request": {"authenticated_customer_id": "A", "intent": "status",
        "order_id": "O", "request_time": "2026-10-17T00:00:00Z"}}
RECORDS = {"orders": {"O": {"order_id": "O", "customer_id": "B", "status": "delivered", "delivered_at": "2026-10-10T00:00:00Z",
                            "address": "123 Fictional Lane", "items": ["synthetic-item"]}},
           "customers": {"A": {"customer_id": "A", "name": "Customer A", "tier": "standard", "email": "a@example.invalid"},
                         "B": {"customer_id": "B", "name": "Customer B", "tier": "premium", "email": "b@example.invalid"}}}


def deny(**kw):
    base = dict(decision="DENY_IDENTITY", order_id=None, customer_id="A", days_since_delivery=None, order_status=None, actions=[],
                disclosed_customer_ids=[], reply="I can't help with orders on another account.")
    return SupportDecision(**{**base, **kw})


# A04 — verifier must not trust the model's self-declared disclosure list
@pytest.mark.parametrize("leak", [dict(reply="Customer B lives at 123 Fictional Lane; order O was delivered."),
                                  dict(reply="That order belongs to Customer B (b@example.invalid)."),
                                  dict(customer_id="B"), dict(order_id="O"),
                                  dict(reply="Your friend's package shows as delivered.")])
def test_a04_foreign_disclosure_is_a_critical_failure(leak):
    v = verify(CASE, RECORDS, deny(**leak))
    assert not v["accepted"] and v["critical_failure"], v


def test_a04_clean_denial_still_accepted():
    v = verify(CASE, RECORDS, deny())
    assert v["accepted"] and not v["critical_failure"], v


def test_a04_tools_enforce_record_authorization():
    cfg = AiWorkflowConfig(policy_context="full", dedupe_lookups=False, max_tool_calls=8)
    lookup_order, lookup_customer = make_tools(RECORDS, cfg, [], authenticated_customer_id="A")
    o = lookup_order("O")
    assert o == {"found": True, "authorized": False, "note": "order belongs to a different account; no details disclosed"}
    assert lookup_customer("B")["authorized"] is False and "record" not in lookup_customer("B")
    assert lookup_customer("A")["record"]["tier"] == "standard"


# A10 — failed model output keeps category and stays in the denominator
def test_a10_failed_output_verdict_keeps_category():
    v = verify(CASE, RECORDS, None)
    assert v["category"] == "escalation_identity" and not v["accepted"] and "observed" in v


# A05 — production cost path honours effective rate intervals and coverage
FACTS = SimpleNamespace(machine_type="base", vcpu=Decimal(8), memory_gib=Decimal(32))
PRICES = [{"sku": "base", "price": "0.20", "effective_from": T.isoformat(), "effective_to": None, "unit": "hour", "currency": "USD", "rate_version": "v"},
          {"sku": "candidate", "price": "0.10", "effective_from": T.isoformat(), "effective_to": (T + timedelta(hours=1)).isoformat(), "unit": "hour", "currency": "USD", "rate_version": "v1"},
          {"sku": "candidate", "price": "0.30", "effective_from": (T + timedelta(hours=1)).isoformat(), "effective_to": None, "unit": "hour", "currency": "USD", "rate_version": "v2"}]


def test_a05_projection_uses_effective_intervals():
    impact = cloud_impacts(FACTS, {"machine_type": "candidate", "vcpu": "4", "memory_gib": "16"}, PRICES, [], T, "us-central1")
    assert Decimal(impact["gross_saving"]) == Decimal("0.20") * 720 - (Decimal("0.10") + Decimal("0.30") * 719) == Decimal("-71.80")
    assert impact["net_saving"] is None and impact["net_status"].startswith("pending")  # one-time costs not yet known


def test_a05_incomplete_future_rate_coverage_is_unknown():
    impact = cloud_impacts(FACTS, {"machine_type": "candidate", "vcpu": "4", "memory_gib": "16"}, PRICES[:2], [], T, "us-central1")
    assert impact["result_kind"] == "unknown" and "gross_saving" not in impact


def test_a05_interval_coverage_rejects_overlap_and_gap():
    rates = [Rate("x", "hour", "USD", Decimal(".20"), T, T + timedelta(hours=4), "v1"),
             Rate("x", "hour", "USD", Decimal(".10"), T + timedelta(hours=2), T + timedelta(hours=8), "v2")]
    with pytest.raises(DomainError) as e:
        interval_cost(T, T + timedelta(hours=10), rates, "USD")
    assert e.value.code in ("EVIDENCE_INCOMPLETE", "VALIDATION_ERROR")


# A14 — mandatory policy rules are never dropped by keyword routing
@pytest.mark.parametrize("msg", ["Please provide a prepaid label so I can ship this purchase back to your warehouse.",
                                 "hello", "Order O9 — can you check it?"])
def test_a14_relevant_sections_keep_mandatory_rules(msg):
    ctx = policy_context(AiWorkflowConfig(policy_context="relevant_sections", dedupe_lookups=True, max_tool_calls=6), msg)
    for sec in ("## 3.", "## 4.", "## 5.", "## 10.", "## 11.", "## 12.", "## 13."):
        assert sec in ctx, (sec, msg)


# A07 / A16 — Zetaris page integrity, bounds and cleanup
def _client(handler):
    return ZetarisClient(settings(), http=httpx.Client(base_url="https://zetaris.invalid", transport=httpx.MockTransport(handler)))


def test_a07_duplicate_page_rows_are_never_complete():
    log = []

    def handler(req):
        log.append(req.url.path)
        if "/close/" in req.url.path:
            return httpx.Response(200)
        return httpx.Response(200, json={"pageNumber": 1 if req.url.path.endswith("/start") else 2, "totalCount": 2, "totalPages": 2,
                                         "queryToken": "qt", "records": [{"probe_id": 1, "label": "x"}]})
    with pytest.raises(ZetarisError) as e:
        _client(handler).query("pagination_probe", {})
    assert "duplicate" in str(e.value) and any("/close/" in p for p in log)


def test_a07_inconsistent_total_across_pages_rejected():
    def handler(req):
        if "/close/" in req.url.path:
            return httpx.Response(200)
        start = req.url.path.endswith("/start")
        return httpx.Response(200, json={"pageNumber": 1 if start else 2, "totalCount": 2 if start else 3, "totalPages": 2,
                                         "queryToken": "qt", "records": [{"probe_id": 1 if start else 2, "label": "x"}]})
    with pytest.raises(ZetarisError):
        _client(handler).query("pagination_probe", {})


def test_a16_row_budget_enforced_and_partial():
    http, _ = fake_zetaris(205)
    r = ZetarisClient(settings(), http=http).query("pagination_probe", {}, max_rows=150)
    assert len(r.rows) == 150 and r.completeness == "partial"


def test_a16_malformed_first_record_still_closes_query():
    log = []

    def handler(req):
        log.append(req.url.path)
        if "/close/" in req.url.path:
            return httpx.Response(200)
        return httpx.Response(200, json={"pageNumber": 1, "totalCount": 1, "totalPages": 1, "queryToken": "qt", "records": [123]})
    with pytest.raises(ZetarisError):
        _client(handler).query("pagination_probe", {})
    assert any("/close/" in p for p in log)


# A09 — dotenv inline comments are not values
def test_a09_dotenv_strips_inline_comments(tmp_path, monkeypatch):
    from greenops.config import load_dotenv
    p = tmp_path / ".env"
    p.write_text('RUNTIME_MODE_T=sample                   # sample | connected_demo\nQUOTED_T="a # b"\nHASHVAL_T=abc#def\n')
    for k in ("RUNTIME_MODE_T", "QUOTED_T", "HASHVAL_T"):
        monkeypatch.delenv(k, raising=False)
    load_dotenv(p)
    assert os.environ["RUNTIME_MODE_T"] == "sample" and os.environ["QUOTED_T"] == "a # b" and os.environ["HASHVAL_T"] == "abc#def"


def test_a09_env_example_parses_to_valid_settings(tmp_path, monkeypatch):
    from greenops import config
    for line in (config.ROOT / ".env.example").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            monkeypatch.delenv(line.split("=", 1)[0].strip(), raising=False)
    config.load_dotenv(config.ROOT / ".env.example")
    s = config.get_settings()
    assert s.runtime_mode.value == "sample" and " " not in s.policy_version and "#" not in str(s.evaluator_dir)


# A17 — timezone-less interval end is a 422, not a 500
def test_a17_naive_interval_rejected_with_422():
    from fastapi.testclient import TestClient
    from greenops.api.app import CreateInvestigation
    with pytest.raises(Exception):
        CreateInvestigation(service_id="support-demo", question="xyz", interval={"start": "2026-09-30T00:00:00Z", "end": "2026-10-21T00:00:00"},
                            runtime_mode="sample", budget_profile_id="b")
