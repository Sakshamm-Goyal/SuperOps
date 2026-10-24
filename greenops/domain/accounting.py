"""Decimal cost and carbon accounting (DATA_AND_DOMAIN §Accounting/Carbon, EVALUATION_SPEC §3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .quantities import DomainError, dec, require_same, utc

HOUR_SECONDS = Decimal(3600)


@dataclass(frozen=True)
class Rate:
    sku: str
    unit: str  # "hour"
    currency: str
    price: Decimal
    effective_from: datetime
    effective_to: datetime | None  # half-open [from, to)
    rate_version: str


def interval_cost(start: datetime, end: datetime, rates: list[Rate], currency: str) -> Decimal:
    """Hourly usage over [start, end) split across effective rate intervals (D-19).

    Raises EVIDENCE_INCOMPLETE if any part of the interval has no effective rate.
    """
    start, end = utc(start), utc(end)
    if end <= start:
        raise DomainError("VALIDATION_ERROR", "empty or inverted interval")
    segments = []
    for r in rates:
        require_same("currency", r.currency, currency)
        if r.unit != "hour":
            raise DomainError("VALIDATION_ERROR", f"unsupported rate unit {r.unit!r}")
        lo = max(start, utc(r.effective_from))
        hi = min(end, utc(r.effective_to)) if r.effective_to else end
        if hi > lo:
            segments.append((lo, hi, dec(r.price, field="price")))
    # Coverage is the union of intervals: overlaps are ambiguous and gaps are missing evidence (audit A05).
    total, cursor = Decimal(0), start
    for lo, hi, price in sorted(segments, key=lambda s: s[0]):
        if lo < cursor:
            raise DomainError("VALIDATION_ERROR", f"overlapping effective rates at {lo.isoformat()}")
        if lo > cursor:
            raise DomainError("EVIDENCE_INCOMPLETE", f"no effective rate for [{cursor.isoformat()}, {lo.isoformat()})")
        total += Decimal((hi - lo).total_seconds()) / HOUR_SECONDS * price
        cursor = hi
    if cursor < end:
        raise DomainError("EVIDENCE_INCOMPLETE", f"no effective rate for [{cursor.isoformat()}, {end.isoformat()})")
    return total


@dataclass(frozen=True)
class Projection:
    baseline_cost: Decimal
    candidate_cost: Decimal
    gross_saving: Decimal
    one_time_costs: Decimal
    net_saving: Decimal
    break_even_days: Decimal | None
    currency: str
    horizon_hours: Decimal
    result_kind: str = "projected"


def project_saving(baseline_hourly, candidate_hourly, horizon_hours, *, experiment_cost=0,
                   transition_cost=0, optimizer_overhead=0, currency: str = "USD") -> Projection:
    """gross = baseline − candidate over the horizon; net subtracts one-time costs exactly once."""
    b, c, h = dec(baseline_hourly), dec(candidate_hourly), dec(horizon_hours)
    one_time = dec(experiment_cost) + dec(transition_cost) + dec(optimizer_overhead)
    base, cand = b * h, c * h
    gross = base - cand
    per_day = (b - c) * 24
    break_even = (one_time / per_day) if per_day > 0 else None
    return Projection(base, cand, gross, one_time, gross - one_time, break_even, currency, h)


@dataclass(frozen=True)
class TokenRates:
    input_per_million: Decimal
    output_per_million: Decimal
    currency: str = "USD"


def ai_run_cost(calls: list[dict], rates: TokenRates) -> tuple[Decimal | None, Decimal]:
    """Sum every attempt exactly once. Returns (total or None if usage incomplete, usage completeness 0..1)."""
    if not calls:
        return Decimal(0), Decimal(1)
    total = Decimal(0)
    known = 0
    for c in calls:
        tool = dec(c.get("tool_cost", 0), field="tool_cost")
        if c.get("input_tokens") is None or c.get("output_tokens") is None:
            total += tool
            continue
        known += 1
        total += (dec(c["input_tokens"]) * rates.input_per_million + dec(c["output_tokens"]) * rates.output_per_million) / Decimal(1_000_000) + tool
    completeness = Decimal(known) / Decimal(len(calls))
    return (total if known == len(calls) else None), completeness


def cost_per_accepted(total: Decimal | None, accepted: int) -> Decimal | None:
    """Undefined (None) when no task is accepted or cost is incomplete — never zero."""
    if total is None or accepted <= 0:
        return None
    return total / Decimal(accepted)


def resource_billing_totals(billing_rows: list[dict]) -> dict[tuple[str, str, str], Decimal]:
    """Aggregate billing at its own grain (provider, project, resource) — never after a raw join (F-JOIN).

    Exact duplicate source records (same billing_record_id) are dropped; equal amounts are not.
    """
    seen: set[str] = set()
    totals: dict[tuple[str, str, str], Decimal] = {}
    currency = None
    for r in billing_rows:
        if r["billing_record_id"] in seen:
            continue
        seen.add(r["billing_record_id"])
        currency = currency or r["currency"]
        require_same("currency", r["currency"], currency)
        key = (r["provider"], r["project_id"], r["resource_id"])
        totals[key] = totals.get(key, Decimal(0)) + dec(r["cost"], field="cost")
    return totals


# ---- carbon -------------------------------------------------------------------

@dataclass(frozen=True)
class CarbonEstimate:
    kg_co2e: Decimal | None
    method_version: str | None
    region: str
    interval_hours: Decimal
    factor_kg_per_kwh: Decimal | None
    energy_kwh: Decimal | None
    coverage: str  # full | partial | none
    result_kind: str  # estimated | unknown
    reason: str | None = None


def operational_carbon(energy_kwh, factor_kg_per_kwh, *, region: str, interval_hours, method_version: str | None,
                       pue_included: bool, pue=None) -> CarbonEstimate:
    """kWh × kgCO2e/kWh; PUE applied only when the energy figure excludes overhead. Missing → UNKNOWN."""
    hours = dec(interval_hours)
    if energy_kwh is None or factor_kg_per_kwh is None or method_version is None:
        return CarbonEstimate(None, method_version, region, hours, factor_kg_per_kwh, energy_kwh, "none", "unknown",
                              "emission factor, energy estimate or method unavailable")
    e = dec(energy_kwh)
    if not pue_included and pue is not None:
        e = e * dec(pue)
    f = dec(factor_kg_per_kwh)
    return CarbonEstimate(e * f, method_version, region, hours, f, e, "full", "estimated")
