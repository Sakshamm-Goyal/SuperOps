"""Capacity screening and the daily seasonal-naive forecast (EVALUATION_SPEC §2, DATA_AND_DOMAIN)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .quantities import DomainError, dec

LAG = 96  # quarter-hours per day
STEP = timedelta(minutes=15)


def vcpu_demand(cpu_percent, source_vcpu) -> Decimal:
    """observed_vcpu = cpu_percent / 100 × source_vcpu. cpu_percent is on the 0–100 scale."""
    pct = dec(cpu_percent, field="cpu_percent")
    if pct > 100:
        raise DomainError("VALIDATION_ERROR", "cpu_percent is on the 0-100 scale; >100 rejected")
    return pct / Decimal(100) * dec(source_vcpu, field="source_vcpu")


@dataclass(frozen=True)
class CapacityCheck:
    check_id: str
    passed: bool
    demand: Decimal | None
    capacity: Decimal
    allowed: Decimal
    utilization: Decimal | None  # demand / capacity
    unit: str
    reason: str


def screen_capacity(check_id: str, demand, capacity, max_utilization, unit: str) -> CapacityCheck:
    """Pass iff demand <= max_utilization × capacity. Unknown demand never passes."""
    cap = dec(capacity, field="capacity")
    limit = dec(max_utilization, field="max_utilization")
    allowed = cap * limit
    if demand is None:
        return CapacityCheck(check_id, False, None, cap, allowed, None, unit, f"{unit} demand unknown; evidence required")
    d = dec(demand, field="demand")
    util = d / cap if cap else None
    ok = d <= allowed
    shown = d.quantize(Decimal("0.0001")).normalize() if abs(d) < 10**12 else d  # display only; the decision uses exact d
    if (shown <= allowed) != ok:
        shown = d.normalize()  # rounding would make the text contradict the decision at the boundary
    reason = (f"peak {shown:f} {unit} ≤ {allowed.normalize():f} {unit} allowed ({limit:%} of {cap.normalize():f})"
              if ok else f"peak {shown:f} {unit} exceeds {allowed.normalize():f} {unit} allowed ({limit:%} of {cap.normalize():f})")
    return CapacityCheck(check_id, ok, d, cap, allowed, util, unit, reason)


@dataclass(frozen=True)
class Point:
    at: datetime
    value: Decimal


class FutureAccess(AssertionError):
    pass


def seasonal_naive(history: list[Point], origin: datetime) -> list[Point]:
    """Predict the next 96 quarter-hours after `origin` from the previous day's same slot.

    Uses only observations with at < origin; raises FutureAccess otherwise (D-20).
    """
    by_time = {p.at: p.value for p in history}
    if any(p.at >= origin for p in history):
        raise FutureAccess("forecast history contains observations at or after the origin")
    out = []
    for h in range(LAG):
        t = origin + STEP * h
        src = t - STEP * LAG
        if src not in by_time:
            raise DomainError("EVIDENCE_INCOMPLETE", f"missing lag observation at {src.isoformat()}")
        out.append(Point(t, by_time[src]))
    return out


def residual_quantile(series: list[Point], start: datetime, end: datetime, q: Decimal = Decimal("0.95")) -> Decimal:
    """Empirical positive-residual quantile of the seasonal-naive forecast over daily origins in [start, end).

    A stress envelope, not a calibrated confidence interval.
    """
    residuals: list[Decimal] = []
    origin = start
    while origin < end:
        hist = [p for p in series if p.at < origin]
        actual = {p.at: p.value for p in series if origin <= p.at < origin + STEP * LAG}
        for f in seasonal_naive(hist, origin):
            if f.at in actual:
                residuals.append(max(Decimal(0), actual[f.at] - f.value))
        origin += STEP * LAG
    if not residuals:
        raise DomainError("EVIDENCE_INCOMPLETE", "no residuals in calibration window")
    residuals.sort()
    idx = min(len(residuals) - 1, int((Decimal(len(residuals)) * q).to_integral_value()) )
    return residuals[idx]


def stress_peak(series: list[Point], origin: datetime, residual_q: Decimal) -> Decimal:
    """Max of (next-day seasonal-naive forecast + frozen residual quantile)."""
    hist = [p for p in series if p.at < origin]
    return max(f.value + residual_q for f in seasonal_naive(hist, origin))
