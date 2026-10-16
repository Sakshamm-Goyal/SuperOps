"""Pure approval/execution precondition checks (DATA_AND_DOMAIN §Plan and approval integrity)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .quantities import DomainError


def approval_expired(now: datetime, expires_at: datetime) -> bool:
    """Expired at the boundary: now >= expiry (ACT-02)."""
    return now >= expires_at


def trial_expired(now: datetime, trial_finished_at: datetime, validity_hours: int) -> bool:
    return now >= trial_finished_at + timedelta(hours=validity_hours)


def require_approvable(*, plan_status: str, plan_hash: str, requested_plan_hash: str, trial_status: str | None,
                       trial_hash: str | None, requested_trial_hash: str, trial_finished_at: datetime | None,
                       trial_validity_hours: int, now: datetime, requires_downtime: bool, acknowledge_downtime: bool,
                       recovery_scope: str, requested_recovery_scope: str, versions_current: bool,
                       runtime_mode: str) -> None:
    if runtime_mode != "connected_demo":
        raise DomainError("INVALID_STATE", f"{runtime_mode} runs cannot be approved")
    if plan_hash != requested_plan_hash:
        raise DomainError("PLAN_CHANGED", "plan hash does not match the current immutable plan")
    if plan_status != "AWAITING_APPROVAL":
        raise DomainError("INVALID_STATE", f"plan is {plan_status}, not AWAITING_APPROVAL")
    if trial_status != "PASSED" or trial_hash != requested_trial_hash:
        raise DomainError("TRIAL_NOT_ACCEPTED", "an accepted trial with the requested hash is required")
    if trial_finished_at is None or trial_expired(now, trial_finished_at, trial_validity_hours):
        raise DomainError("TRIAL_NOT_ACCEPTED", "accepted trial is older than its validity window")
    if not versions_current:
        raise DomainError("APPROVAL_STALE", "policy/workload/config version changed since the trial")
    if requires_downtime and not acknowledge_downtime:
        raise DomainError("VALIDATION_ERROR", "this plan requires explicit downtime acknowledgment")
    if requested_recovery_scope != recovery_scope:
        raise DomainError("VALIDATION_ERROR", "recovery scope must equal the plan's declared recovery scope")
