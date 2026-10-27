"""Deterministic cloud candidate screening. Authoritative over any model or critic opinion."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .capacity import screen_capacity, vcpu_demand
from .models import ServicePolicy
from .quantities import GIB, dec

SCREENING_VERSION = "screen-v1"


@dataclass(frozen=True)
class ResourceFacts:
    resource_key: str  # provider/project/resource_id
    environment: str
    machine_type: str
    vcpu: Decimal
    memory_gib: Decimal
    architecture: str
    region: str
    stateful: bool
    local_ssd: bool
    gpu: bool
    expected_rows: int
    cpu_rows: int
    memory_rows: int
    last_observed_at: datetime | None
    avg_cpu_pct: Decimal | None
    peak_cpu_pct: Decimal | None
    peak_memory_bytes: Decimal | None
    stress_peak_cpu_pct: Decimal | None  # seasonal-naive stress envelope; None = not computed


@dataclass(frozen=True)
class MachineType:
    machine_type: str
    vcpu: Decimal
    memory_gib: Decimal
    architecture: str


@dataclass(frozen=True)
class Check:
    check_id: str
    status: str  # PASS | FAIL | UNKNOWN
    detail: str
    measured: str | None = None
    limit: str | None = None


@dataclass(frozen=True)
class ScreeningResult:
    outcome: str  # ELIGIBLE_FOR_TRIAL | REJECTED | NEEDS_EVIDENCE
    checks: list[Check]

    def as_dict(self) -> dict:
        return {"outcome": self.outcome, "version": SCREENING_VERSION, "checks": [asdict(c) for c in self.checks]}


def _fmt(d: Decimal | None) -> str | None:
    return None if d is None else format(d.normalize(), "f")


def screen_cloud(facts: ResourceFacts | None, target: MachineType | None, policy: ServicePolicy, as_of: datetime,
                 action_type: str, candidate_hourly: Decimal | None, baseline_hourly: Decimal | None) -> ScreeningResult:
    checks: list[Check] = []
    if facts is None:
        return ScreeningResult("REJECTED", [Check("CHK-IDENTITY", "FAIL", "target resource key not in inventory")])
    checks.append(Check("CHK-IDENTITY", "PASS", f"resolved {facts.resource_key}"))
    if target is None:
        checks.append(Check("CHK-COMPAT", "FAIL", "unknown candidate machine type"))
        return ScreeningResult("REJECTED", checks)

    # Evidence completeness and freshness
    need = policy.required_critical_coverage
    cov_cpu = Decimal(facts.cpu_rows) / Decimal(facts.expected_rows) if facts.expected_rows else Decimal(0)
    cov_mem = Decimal(facts.memory_rows) / Decimal(facts.expected_rows) if facts.expected_rows else Decimal(0)
    checks.append(Check("CHK-COVERAGE-CPU", "PASS" if cov_cpu >= need else "UNKNOWN",
                        f"{facts.cpu_rows}/{facts.expected_rows} CPU observations", _fmt(cov_cpu), _fmt(need)))
    checks.append(Check("CHK-COVERAGE-MEM", "PASS" if cov_mem >= need else "UNKNOWN",
                        f"{facts.memory_rows}/{facts.expected_rows} memory observations", _fmt(cov_mem), _fmt(need)))
    max_age = timedelta(minutes=policy.telemetry_max_age_minutes)
    if facts.last_observed_at is None:
        checks.append(Check("CHK-FRESHNESS", "UNKNOWN", "no telemetry observed"))
    else:
        age = as_of - facts.last_observed_at
        checks.append(Check("CHK-FRESHNESS", "PASS" if age <= max_age else "UNKNOWN",
                            f"latest observation {facts.last_observed_at.isoformat()} is {age} before as_of",
                            str(age), str(max_age)))

    # Capacity
    peak_vcpu = None if facts.peak_cpu_pct is None else vcpu_demand(facts.peak_cpu_pct, facts.vcpu)
    c = screen_capacity("CHK-CPU-PEAK", peak_vcpu, target.vcpu, policy.cpu_max_utilization, "vCPU")
    checks.append(Check(c.check_id, "UNKNOWN" if c.demand is None else ("PASS" if c.passed else "FAIL"), c.reason,
                        _fmt(c.demand), _fmt(c.allowed)))
    if facts.stress_peak_cpu_pct is None and policy.stress_forecast_waiver:
        checks.append(Check("CHK-CPU-STRESS", "WAIVED", f"waived by policy {policy.version}: {policy.stress_forecast_waiver}"))
    elif facts.stress_peak_cpu_pct is None:
        checks.append(Check("CHK-CPU-STRESS", "UNKNOWN", "forecast stress envelope not computed"))
    else:
        stress = vcpu_demand(min(facts.stress_peak_cpu_pct, Decimal(100)), facts.vcpu)
        s = screen_capacity("CHK-CPU-STRESS", stress, target.vcpu, policy.cpu_max_utilization, "vCPU")
        checks.append(Check(s.check_id, "PASS" if s.passed else "FAIL", "forecast stress " + s.reason,
                            _fmt(s.demand), _fmt(s.allowed)))
    mem_gib = None if facts.peak_memory_bytes is None else dec(facts.peak_memory_bytes) / GIB
    m = screen_capacity("CHK-MEM-PEAK", mem_gib, target.memory_gib, policy.memory_max_utilization, "GiB")
    checks.append(Check(m.check_id, "UNKNOWN" if m.demand is None else ("PASS" if m.passed else "FAIL"), m.reason,
                        _fmt(m.demand), _fmt(m.allowed)))

    # Compatibility and policy
    unsupported = [f for f, on in (("stateful", facts.stateful), ("local_ssd", facts.local_ssd), ("gpu", facts.gpu))
                   if on and f in policy.unsupported_features]
    if target.architecture != facts.architecture:
        unsupported.append(f"architecture change {facts.architecture}->{target.architecture}")
    checks.append(Check("CHK-COMPAT", "FAIL" if unsupported else "PASS",
                        ("unsupported: " + ", ".join(unsupported)) if unsupported else "no unsupported features"))
    policy_fail = []
    if action_type not in policy.allowed_action_types:
        policy_fail.append(f"action {action_type} not allowed")
    if facts.environment not in policy.executable_environments:
        policy_fail.append(f"environment {facts.environment} not executable")
    if facts.resource_key in policy.frozen_resources:
        policy_fail.append("resource under change freeze")
    checks.append(Check("CHK-POLICY", "FAIL" if policy_fail else "PASS",
                        "; ".join(policy_fail) or f"allowed by policy {policy.version}"))
    if candidate_hourly is None or baseline_hourly is None:
        checks.append(Check("CHK-ECONOMICS", "UNKNOWN", "effective rate missing; no quantified benefit"))
    else:
        checks.append(Check("CHK-ECONOMICS", "PASS" if candidate_hourly < baseline_hourly else "FAIL",
                            f"candidate {_fmt(candidate_hourly)} vs baseline {_fmt(baseline_hourly)} USD/hour",
                            _fmt(candidate_hourly), _fmt(baseline_hourly)))

    if any(c.status == "FAIL" for c in checks):
        return ScreeningResult("REJECTED", checks)
    if any(c.status == "UNKNOWN" for c in checks):
        return ScreeningResult("NEEDS_EVIDENCE", checks)
    return ScreeningResult("ELIGIBLE_FOR_TRIAL", checks)
