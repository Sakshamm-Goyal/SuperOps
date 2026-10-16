"""Independent numerical oracles from EVALUATION_SPEC §3 (expected values computed by hand, not by production code)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from greenops.domain import accounting as acc
from greenops.domain.approval import approval_expired, trial_expired
from greenops.domain.capacity import FutureAccess, Point, residual_quantile, screen_capacity, seasonal_naive, stress_peak, vcpu_demand
from greenops.domain.quantities import GIB, DomainError, canonical_hash, dec, to_bytes

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


# D-04 F-CAP-CPU
def test_cpu_peak_rejects_small_target():
    assert vcpu_demand(10, 8) == D("0.8")
    peak = vcpu_demand(80, 8)
    assert peak == D("6.4")
    two = screen_capacity("c", peak, 2, D("0.80"), "vCPU")
    assert not two.passed and two.allowed == D("1.6") and two.utilization == D("3.2")
    eight = screen_capacity("c", peak, 8, D("0.80"), "vCPU")
    assert eight.passed  # equality passes the CPU screen only
    assert not screen_capacity("c", D("7.2"), 8, D("0.80"), "vCPU").passed


# D-05 F-CAP-MEM, D-03 missing memory stays unknown
def test_memory_screen_and_unknown():
    peak = D(10 * GIB) / GIB
    assert to_bytes(10, "GiB") == D(10_737_418_240)
    assert not screen_capacity("m", peak, 8, D("0.8"), "GiB").passed
    assert screen_capacity("m", peak, 16, D("0.8"), "GiB").utilization == D("0.625")
    unknown = screen_capacity("m", None, 16, D("0.8"), "GiB")
    assert not unknown.passed and unknown.demand is None


# D-17 invalid values and unit mismatch
@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", float("inf"), True])
def test_rejects_non_finite_and_negative(bad):
    with pytest.raises(DomainError):
        dec(bad)


def test_gb_vs_gib_and_currency_mismatch():
    assert to_bytes(1, "GB") != to_bytes(1, "GiB")
    r = acc.Rate("s", "hour", "EUR", D("1"), T0, None, "v")
    with pytest.raises(DomainError):
        acc.interval_cost(T0, T0 + timedelta(hours=1), [r], "USD")


# D-16 F-COST
def test_cost_projection_oracle():
    p = acc.project_saving(D("0.20"), D("0.12"), 720, experiment_cost=D("3.00"), transition_cost=D("1.20"))
    assert (p.baseline_cost, p.candidate_cost, p.gross_saving, p.net_saving) == (D("144.00"), D("86.40"), D("57.60"), D("53.40"))
    q = acc.project_saving(D(20) / 24, D(16) / 24, 7 * 24, experiment_cost=6)
    assert q.gross_saving.quantize(D("0.01")) == D("28.00") and q.net_saving.quantize(D("0.01")) == D("22.00")
    assert q.break_even_days.quantize(D("0.01")) == D("1.50")


# D-19 rate boundary
def test_rate_split_across_effective_intervals():
    rates = [acc.Rate("s", "hour", "USD", D("0.20"), T0, T0 + timedelta(hours=4), "v1"),
             acc.Rate("s", "hour", "USD", D("0.10"), T0 + timedelta(hours=4), None, "v2")]
    assert acc.interval_cost(T0, T0 + timedelta(hours=10), rates, "USD") == D("1.40")
    with pytest.raises(DomainError):
        acc.interval_cost(T0 - timedelta(hours=1), T0 + timedelta(hours=1), rates, "USD")


# D-16 F-AI-COST
def test_ai_cost_per_accepted_task():
    rates = acc.TokenRates(D(1), D(2))
    total, completeness = acc.ai_run_cost([{"input_tokens": 100_000, "output_tokens": 20_000, "tool_cost": "0.01"}], rates)
    assert total == D("0.15") and completeness == 1
    assert acc.cost_per_accepted(total, 38).quantize(D("1e-12")) == D("0.003947368421")
    cand, _ = acc.ai_run_cost([{"input_tokens": 70_000, "output_tokens": 15_000, "tool_cost": "0.01"}], rates)
    assert cand == D("0.11") and total - cand - D("0.03") == D("0.01")
    assert acc.cost_per_accepted(total, 0) is None
    incomplete, c = acc.ai_run_cost([{"input_tokens": None, "output_tokens": None}, {"input_tokens": 1, "output_tokens": 1}], rates)
    assert incomplete is None and c == D("0.5")


# D-02 F-JOIN
def test_billing_aggregated_at_own_grain():
    bills = [{"billing_record_id": "b1", "provider": "gcp", "project_id": "project-a", "resource_id": "worker-01", "cost": "10", "currency": "USD"},
             {"billing_record_id": "b2", "provider": "gcp", "project_id": "project-a", "resource_id": "worker-01", "cost": "20", "currency": "USD"},
             {"billing_record_id": "b3", "provider": "gcp", "project_id": "project-b", "resource_id": "worker-01", "cost": "10", "currency": "USD"},
             {"billing_record_id": "b4", "provider": "gcp", "project_id": "project-b", "resource_id": "worker-01", "cost": "10", "currency": "USD"},
             {"billing_record_id": "b4", "provider": "gcp", "project_id": "project-b", "resource_id": "worker-01", "cost": "10", "currency": "USD"}]
    raw_cross_join = 2 * 3 * sum(D(b["cost"]) for b in bills[:2])
    assert raw_cross_join == D(180)
    totals = acc.resource_billing_totals(bills)
    assert totals[("gcp", "project-a", "worker-01")] == D(30)
    assert totals[("gcp", "project-b", "worker-01")] == D(20)  # legit equal bills kept; exact duplicate dropped (D-01 too)


# D-07, D-08, D-09 F-CARBON
def test_carbon_oracles():
    e = acc.operational_carbon(2, D("0.4"), region="a", interval_hours=24, method_version="m", pue_included=True, pue=D("1.1"))
    assert e.kg_co2e == D("0.8")
    a = acc.operational_carbon(2, D("0.4"), region="region-a", interval_hours=24, method_version="m", pue_included=True)
    b = acc.operational_carbon(2, D("0.2"), region="region-b", interval_hours=24, method_version="m", pue_included=True)
    assert (a.kg_co2e, b.kg_co2e, a.region != b.region) == (D("0.8"), D("0.4"), True)
    assert acc.operational_carbon(24, D("0.4"), region="a", interval_hours=24, method_version="m", pue_included=True).kg_co2e == D("9.6")
    u = acc.operational_carbon(2, None, region="a", interval_hours=24, method_version="m", pue_included=True)
    assert u.kg_co2e is None and u.result_kind == "unknown"


# D-20 forecast cannot read the future
def _series(days, value=lambda i: D(i % 96)):
    return [Point(T0 + timedelta(minutes=15 * i), value(i)) for i in range(days * 96)]


def test_seasonal_naive_and_future_guard():
    s = _series(3)
    origin = T0 + timedelta(days=2)
    f = seasonal_naive([p for p in s if p.at < origin], origin)
    assert len(f) == 96 and f[5].value == D(5)
    with pytest.raises(FutureAccess):
        seasonal_naive(s, origin)


def test_residual_envelope_and_stress():
    s = _series(4, lambda i: D(10) + (D(5) if i // 96 == 2 and i % 96 == 10 else 0))
    q = residual_quantile(s, T0 + timedelta(days=1), T0 + timedelta(days=4), D("1"))
    assert q == D(5)
    assert stress_peak(s, T0 + timedelta(days=4), q) == D(15)


# ACT-02 boundary and 24h trial validity
def test_expiry_boundaries():
    exp = T0 + timedelta(minutes=10)
    assert approval_expired(exp, exp) and not approval_expired(exp - timedelta(microseconds=1), exp)
    assert trial_expired(T0 + timedelta(hours=24), T0, 24)


def test_canonical_hash_stable_and_float_rejected():
    assert canonical_hash({"b": D("1.50"), "a": T0}) == canonical_hash({"a": T0, "b": D("1.5")})
    with pytest.raises(DomainError):
        canonical_hash({"x": 1.5})
