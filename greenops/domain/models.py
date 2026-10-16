"""Typed domain records, lifecycles and the discriminated action union (DATA_AND_DOMAIN, ARCHITECTURE)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---- lifecycles: separate typed enums ------------------------------------------

class InvestigationStatus(StrEnum):
    QUEUED = "QUEUED"; RUNNING = "RUNNING"; AWAITING_APPROVAL = "AWAITING_APPROVAL"; COMPLETED = "COMPLETED"
    NO_CHANGE = "NO_CHANGE"; NEEDS_REVIEW = "NEEDS_REVIEW"; FAILED = "FAILED"; CANCELLED = "CANCELLED"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"; NEEDS_EVIDENCE = "NEEDS_EVIDENCE"; REJECTED = "REJECTED"; VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"; APPROVED = "APPROVED"; STALE = "STALE"


class TrialStatus(StrEnum):
    QUEUED = "QUEUED"; RUNNING = "RUNNING"; PASSED = "PASSED"; FAILED = "FAILED"; INCOMPLETE = "INCOMPLETE"; CANCELLED = "CANCELLED"


class ApprovalStatus(StrEnum):
    ACTIVE = "ACTIVE"; CONSUMED = "CONSUMED"; EXPIRED = "EXPIRED"; REVOKED = "REVOKED"; STALE = "STALE"


class ActionStatus(StrEnum):
    QUEUED = "QUEUED"; EXECUTING = "EXECUTING"; PENDING_VERIFICATION = "PENDING_VERIFICATION"; VERIFIED = "VERIFIED"
    FAILED = "FAILED"; RECOVERY_REQUIRED = "RECOVERY_REQUIRED"; RECOVERING = "RECOVERING"; RECOVERED = "RECOVERED"


ACTIVE_ACTION_STATES = ("QUEUED", "EXECUTING", "PENDING_VERIFICATION", "RECOVERING", "RECOVERY_REQUIRED")


class ResultKind(StrEnum):
    MEASURED = "measured"; PROJECTED = "projected"; ESTIMATED = "estimated"; UNKNOWN = "unknown"


class DataOrigin(StrEnum):
    SYNTHETIC = "synthetic"; REAL_PERMITTED = "real_permitted"


class Path(StrEnum):
    CLOUD = "cloud"; AI = "ai"


# ---- policy --------------------------------------------------------------------

class WorkloadPolicy(Strict):
    p95_regression_max: Decimal
    slo_p95_ms: int
    max_error_rate: Decimal


class AiPolicy(Strict):
    min_accepted: int
    total_cases: int
    efficiency_aspiration: Decimal


class ServicePolicy(Strict):
    policy_id: str
    version: str
    service_id: str
    effective_from: datetime
    cpu_max_utilization: Decimal
    memory_max_utilization: Decimal
    telemetry_max_age_minutes: int
    required_critical_coverage: Decimal
    allowed_action_types: list[str]
    executable_environments: list[str]
    frozen_resources: list[str]
    unsupported_features: list[str]
    workload: WorkloadPolicy
    ai: AiPolicy
    approval_ttl_minutes: int = 15
    trial_validity_hours: int = 24
    max_candidates_per_path: int = 3


# ---- evidence ------------------------------------------------------------------

class Completeness(StrEnum):
    COMPLETE = "complete"; PARTIAL = "partial"; FAILED = "failed"


class EvidenceSummary(Strict):
    """What a model/critic sees: a redacted, typed summary bound to persisted evidence IDs."""
    evidence_id: str
    template_id: str
    source_system: str
    completeness: Completeness
    row_count: int
    observed_from: datetime | None = None
    observed_to: datetime | None = None
    warnings: list[str] = []
    data: dict


# ---- actions: discriminated union --------------------------------------------

class WorkerConfig(Strict):
    max_concurrency: int = Field(ge=1, le=16)


class AiWorkflowConfig(Strict):
    policy_context: Literal["full", "relevant_sections", "truncated"]
    policy_char_limit: int | None = Field(default=None, ge=200, le=20000)
    dedupe_lookups: bool
    max_tool_calls: int = Field(ge=1, le=12)

    @field_validator("policy_char_limit")
    @classmethod
    def _limit_only_for_truncated(cls, v, info):
        if info.data.get("policy_context") == "truncated" and v is None:
            raise ValueError("truncated policy_context requires policy_char_limit")
        return v


class LocalWorkerConfigUpdate(Strict):
    action_type: Literal["LOCAL_WORKER_CONFIG_UPDATE"] = "LOCAL_WORKER_CONFIG_UPDATE"
    worker_id: str
    expected_config_version: int
    before: WorkerConfig
    after: WorkerConfig


class AiConfigUpdate(Strict):
    action_type: Literal["AI_CONFIG_UPDATE"] = "AI_CONFIG_UPDATE"
    workflow_id: str
    expected_config_version: int
    before: AiWorkflowConfig
    after: AiWorkflowConfig


class GcpMachineTypeUpdate(Strict):
    action_type: Literal["GCP_MACHINE_TYPE_UPDATE"] = "GCP_MACHINE_TYPE_UPDATE"
    project_id: str
    zone: str
    instance_id: str
    expected_machine_type: str
    new_machine_type: str


Action = Annotated[Union[LocalWorkerConfigUpdate, AiConfigUpdate, GcpMachineTypeUpdate], Field(discriminator="action_type")]

RECOVERY_SCOPE = "restore_exact_pre_change_config_if_no_intervening_change"


class PlanVersions(Strict):
    policy_version: str
    workload_version: str
    config_version: str
    model_version: str | None
    test_version: str | None
    data_manifest_id: str


class CloudProjection(Strict):
    """Projected-only screening of the GCP machine type change behind a local analogue."""
    resource_key: str
    from_machine_type: str
    to_machine_type: str
    result_kind: Literal["projected"] = "projected"


class PlanCore(Strict):
    """Everything bound by the plan hash. No free-form prose."""
    schema_version: str = SCHEMA_VERSION
    tenant_id: str
    service_id: str
    investigation_id: str
    path: Path
    revision: int
    target_key: str
    action: Action
    recovery_scope: str = RECOVERY_SCOPE
    requires_downtime: bool
    executor: Literal["local_analogue", "gcp", "none"]
    versions: PlanVersions
    projection: CloudProjection | None
    evidence_ids: list[str]
    calculation_versions: dict[str, str]
