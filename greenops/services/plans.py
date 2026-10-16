"""Plan construction, hashing, AI screening, impacts and memory signatures."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from greenops.adapters.sandbox import REGISTRY, ConfigStore, LocalWorker, TargetUnavailable, file_hash, WORKLOAD_PATH
from greenops.db import J
from greenops.domain import accounting as acc
from greenops.domain.models import (AiConfigUpdate, AiWorkflowConfig, CloudProjection, GcpMachineTypeUpdate, LocalWorkerConfigUpdate,
                                    PlanCore, PlanVersions, WorkerConfig)
from greenops.domain.quantities import canonical_bytes, canonical_hash
from greenops.domain.screening import SCREENING_VERSION, Check, ScreeningResult
from greenops.services.common import Runtime

AI_TARGET = "local/sandbox/support-ai-workflow"
CALC_VERSIONS = {"screening": SCREENING_VERSION, "accounting": "decimal-v1", "carbon": "greenops-synthetic-ops-v1",
                 "forecast": "seasonal-naive-lag96-resq95-v1"}
HORIZON_HOURS = Decimal(720)


def cloud_signature(resource_key: str, to_type: str) -> str:
    return f"cloud:{resource_key}:{to_type}"


def ai_signature(cfg: AiWorkflowConfig) -> str:
    d = cfg.model_dump(mode="json")
    return "ai:" + ",".join(f"{k}={d[k] if d[k] is not None else 'None'}" for k in sorted(d))


def analogue_for(resource_key: str) -> str | None:
    for tid, spec in REGISTRY["workers"].items():
        if spec.get("analogue_of") == resource_key:
            return tid
    return None


def current_rate(prices: list[dict], sku: str, at: datetime) -> Decimal | None:
    for p in prices:
        start = datetime.fromisoformat(p["effective_from"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(p["effective_to"].replace("Z", "+00:00")) if p.get("effective_to") else None
        if p["sku"] == sku and start <= at and (end is None or at < end):
            return Decimal(p["price"])
    return None


def ai_current(rt: Runtime) -> tuple[int, AiWorkflowConfig]:
    cur = ConfigStore(rt.settings.sandbox_dir, AI_TARGET).read()
    return cur["version"], AiWorkflowConfig(**cur["config"])


def build_core(rt: Runtime, inv: dict, path: str, candidate_no: int, revision: int, cand, facts=None, evidence_ids=()) -> PlanCore:
    s = rt.settings
    if path == "cloud":
        target = analogue_for(cand.resource_key)
        projection = CloudProjection(resource_key=cand.resource_key, from_machine_type=facts.machine_type, to_machine_type=cand.to_machine_type)
        if target:
            catalog = {m["machine_type"]: m for m in inv["_catalog"]}
            try:
                cur = LocalWorker(s.sandbox_dir, target).store.read()
                version, before = cur["version"], cur["max_concurrency"]
            except TargetUnavailable:
                version, before = 0, int(facts.vcpu)
            after = int(Decimal(catalog[cand.to_machine_type]["vcpu"])) if cand.to_machine_type in catalog else before
            action = LocalWorkerConfigUpdate(worker_id=target, expected_config_version=version,
                                             before=WorkerConfig(max_concurrency=before), after=WorkerConfig(max_concurrency=max(1, min(16, after))))
            executor, target_key, cfg_version, downtime = "local_analogue", target, str(version), False
        else:
            p, proj, res = cand.resource_key.split("/")
            action = GcpMachineTypeUpdate(project_id=proj, zone="us-central1-a", instance_id=res,
                                          expected_machine_type=facts.machine_type, new_machine_type=cand.to_machine_type)
            executor, target_key, cfg_version, downtime = "none", cand.resource_key, "inventory-1", True
        versions = PlanVersions(policy_version=inv["policy_version"], workload_version=file_hash(WORKLOAD_PATH),
                                config_version=cfg_version, model_version=None, test_version=SCREENING_VERSION,
                                data_manifest_id=inv["data_manifest_id"])
    else:
        version, before = ai_current(rt)
        action = AiConfigUpdate(workflow_id="support-workflow", expected_config_version=version, before=before, after=cand.workflow_config)
        projection, executor, target_key, downtime = None, "local_analogue", AI_TARGET, False
        from experiments.support.workflow import WORKFLOW_VERSION
        manifest = json.loads(_support_manifest())
        versions = PlanVersions(policy_version=inv["policy_version"], workload_version=WORKFLOW_VERSION, config_version=str(version),
                                model_version=inv["_model_id"], test_version="support-dev-v1:" + manifest["development"]["sha256"]["cases.jsonl"][:16],
                                data_manifest_id=inv["data_manifest_id"])
    return PlanCore(tenant_id=inv["tenant_id"], service_id=inv["service_id"], investigation_id=str(inv["id"]), path=path,
                    revision=revision, target_key=target_key, action=action, requires_downtime=downtime, executor=executor,
                    versions=versions, projection=projection, evidence_ids=sorted(evidence_ids), calculation_versions=CALC_VERSIONS)


def _support_manifest() -> str:
    from greenops.config import ROOT
    return (ROOT / "experiments" / "support" / "manifest.json").read_text()


def insert_plan(conn, core: PlanCore, *, candidate_no: int, status: str, screening: dict, impacts: dict | None,
                rationale: str, memory_refs: list, signature: str, parent_plan_id=None, plan_id=None) -> dict:
    canon = canonical_bytes(core).decode()
    h = canonical_hash(core)
    pid = plan_id or uuid.uuid4()
    if plan_id:  # evidence-driven revision of the same candidate before validation: new immutable hash recorded
        conn.execute("UPDATE plans SET revision=%s, core=%s, canonical_json=%s, plan_hash=%s, status=%s, screening=%s, impacts=%s, "
                     "updated_at=now() WHERE id=%s", (core.revision, J(json.loads(canon)), canon, h, status, J(screening), J(impacts), plan_id))
    else:
        conn.execute("INSERT INTO plans (id, investigation_id, tenant_id, service_id, path, candidate_no, revision, parent_plan_id, target_key, "
                     "action_type, core, canonical_json, plan_hash, status, screening, impacts, rationale, memory_refs) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (pid, core.investigation_id, core.tenant_id, core.service_id, core.path.value, candidate_no, core.revision, parent_plan_id,
                      core.target_key, core.action.action_type, J(json.loads(canon)), canon, h, status, J({**screening, "signature": signature}),
                      J(impacts), rationale, J(memory_refs)))
    return {"id": pid, "plan_hash": h}


def screen_ai(inv: dict, cfg: AiWorkflowConfig, current: AiWorkflowConfig, policy, usage_rows: list, dup_rows: list) -> ScreeningResult:
    checks = [Check("AI-POLICY", "PASS" if "AI_CONFIG_UPDATE" in policy.allowed_action_types else "FAIL", "AI_CONFIG_UPDATE allowlisted"),
              Check("AI-CHANGED", "PASS" if cfg != current else "FAIL", "candidate differs from current workflow config"),
              Check("AI-USAGE-EVIDENCE", "PASS" if usage_rows else "UNKNOWN", f"{len(usage_rows)} development runs with usage")]
    if cfg.dedupe_lookups:
        dups = sum(int(r["duplicate_calls"]) for r in dup_rows)
        checks.append(Check("AI-DEDUPE-BASIS", "PASS" if dups else "UNKNOWN", f"{dups} duplicate side-effect-free lookups observed"))
    checks.append(Check("AI-TRIAL-REQUIRED", "PASS", "quality and cost must be measured on the development suite before approval"))
    outcome = "REJECTED" if any(c.status == "FAIL" for c in checks) else "NEEDS_EVIDENCE" if any(c.status == "UNKNOWN" for c in checks) else "ELIGIBLE_FOR_TRIAL"
    return ScreeningResult(outcome, checks)


def cloud_impacts(facts, target_mt: dict | None, prices: list[dict], carbon: list[dict], as_of: datetime, region: str) -> dict:
    base = current_rate(prices, facts.machine_type, as_of)
    cand = current_rate(prices, target_mt["machine_type"], as_of) if target_mt else None
    out: dict = {"basis": "Projected at dated rate", "result_kind": "projected", "horizon_hours": str(HORIZON_HOURS),
                 "currency": "USD", "price_basis": "synthetic_scenario", "commitment_assumption": "on-demand; no committed-use discount modelled"}
    if base is None or cand is None:
        out.update({"result_kind": "unknown", "reason": "effective rate missing"})
    else:
        p = acc.project_saving(base, cand, HORIZON_HOURS, experiment_cost=0, transition_cost=0)
        out.update({"baseline_usd_per_hour": str(base), "candidate_usd_per_hour": str(cand), "baseline_cost": str(p.baseline_cost),
                    "candidate_cost": str(p.candidate_cost), "gross_saving": str(p.gross_saving), "net_saving": str(p.net_saving),
                    "one_time_costs": str(p.one_time_costs), "note": "projection only; not an invoice saving"})
    f = next((c for c in carbon if c["region"] == region), None)
    def energy(vcpu, mem):
        return (Decimal(vcpu) * Decimal(f["kwh_per_vcpu_hour"]) + Decimal(mem) * Decimal(f["kwh_per_gib_hour"])) * HORIZON_HOURS
    if f and target_mt:
        b = acc.operational_carbon(energy(facts.vcpu, facts.memory_gib), Decimal(f["kg_co2e_per_kwh"]), region=region, interval_hours=HORIZON_HOURS,
                                   method_version=f["method_version"], pue_included=str(f["pue_included"]).lower() == "true")
        c = acc.operational_carbon(energy(target_mt["vcpu"], target_mt["memory_gib"]), Decimal(f["kg_co2e_per_kwh"]), region=region,
                                   interval_hours=HORIZON_HOURS, method_version=f["method_version"], pue_included=str(f["pue_included"]).lower() == "true")
        out["carbon"] = {"basis": "Estimated carbon", "result_kind": "estimated", "method_version": b.method_version, "region": region,
                         "factor_kg_per_kwh": str(b.factor_kg_per_kwh), "factor_source": f["factor_source"], "baseline_kg_co2e": str(b.kg_co2e),
                         "candidate_kg_co2e": str(c.kg_co2e), "coverage": "operational energy only; embodied excluded",
                         "note": "estimated lower allocation, not measured avoided emissions"}
    else:
        out["carbon"] = {"basis": "Unknown", "result_kind": "unknown", "reason": "emission factors unavailable"}
    return out
