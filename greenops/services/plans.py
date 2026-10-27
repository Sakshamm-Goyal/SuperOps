"""Plan construction, hashing, AI screening, impacts and memory signatures."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from greenops.adapters.sandbox import REGISTRY, ConfigStore, LocalWorker, TargetUnavailable, file_hash, WORKLOAD_PATH
from greenops.db import J
from greenops.domain import accounting as acc
from greenops.domain.models import (AiConfigUpdate, AiWorkflowConfig, AwsInstanceTypeUpdate, CloudProjection, GcpMachineTypeUpdate, LocalWorkerConfigUpdate,
                                    PlanCore, PlanVersions, WorkerConfig)
from greenops.domain.quantities import DomainError, canonical_bytes, canonical_hash
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


def _artifact_hash(*rel: str) -> str:
    import hashlib
    from greenops.config import ROOT
    h = hashlib.sha256()
    for r in rel:
        h.update(r.encode() + b"\0" + (ROOT / r).read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def ai_artifact_versions(model_id: str | None) -> dict:
    """Versions bound into AI plans/memories (audit A06): actual artifact hashes, not hand-maintained strings.
    workload = workflow code + its prompt + the policy text it reads; test = verifier + development cases/records + manifest."""
    return {"model_version": model_id,
            "workload_version": _artifact_hash("experiments/support/workflow.py", "experiments/support/policy.md"),
            "test_version": _artifact_hash("experiments/support/verifier.py", "experiments/support/dev/cases.jsonl",
                                           "experiments/support/dev/records.json", "experiments/support/manifest.json")}


def ai_current(rt: Runtime) -> tuple[int, AiWorkflowConfig]:
    cur = ConfigStore(rt.settings.sandbox_dir, AI_TARGET).read()
    return cur["version"], AiWorkflowConfig(**cur["config"])


def cloud_workload_version(executor: str) -> str:
    """What the trial's offered load is defined by: the AWS sandbox workload script, or the local workload manifest."""
    from greenops.config import ROOT
    return file_hash(ROOT / "scripts" / "aws_sandbox.py") if executor == "aws" else file_hash(WORKLOAD_PATH)


def build_core(rt: Runtime, inv: dict, path: str, candidate_no: int, revision: int, cand, facts=None, evidence_ids=()) -> PlanCore:
    s = rt.settings
    if path == "cloud":
        target = analogue_for(cand.resource_key)
        projection = CloudProjection(resource_key=cand.resource_key, from_machine_type=facts.machine_type, to_machine_type=cand.to_machine_type)
        if cand.resource_key.startswith("aws/"):
            from greenops.adapters.aws import AwsInstanceStore
            region, instance_id = cand.resource_key.split("/")[1:]
            try:
                version = AwsInstanceStore(cand.resource_key).read()["version"]
            except TargetUnavailable:
                version = 0
            action = AwsInstanceTypeUpdate(region=region, instance_id=instance_id, expected_config_version=version,
                                           expected_instance_type=facts.machine_type, new_instance_type=cand.to_machine_type)
            executor, target_key, cfg_version, downtime = "aws", cand.resource_key, str(version), True
        elif target:
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
        versions = PlanVersions(policy_version=inv["policy_version"], workload_version=cloud_workload_version(executor),
                                config_version=cfg_version, model_version=None, test_version=SCREENING_VERSION,
                                data_manifest_id=inv["data_manifest_id"])
    else:
        version, before = ai_current(rt)
        action = AiConfigUpdate(workflow_id="support-workflow", expected_config_version=version, before=before, after=cand.workflow_config)
        projection, executor, target_key, downtime = None, "local_analogue", AI_TARGET, False
        art = ai_artifact_versions(inv["_model_id"])
        versions = PlanVersions(policy_version=inv["policy_version"], workload_version=art["workload_version"], config_version=str(version),
                                model_version=art["model_version"], test_version=art["test_version"], data_manifest_id=inv["data_manifest_id"])
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


def _ts(v):
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def rates_for(prices: list[dict], sku: str) -> list[acc.Rate]:
    return [acc.Rate(p["sku"], p.get("unit", "hour"), p.get("currency", "USD"), Decimal(p["price"]), _ts(p["effective_from"]),
                     _ts(p.get("effective_to")), p.get("rate_version", "")) for p in prices if p["sku"] == sku]


def cloud_impacts(facts, target_mt: dict | None, prices: list[dict], carbon: list[dict], as_of: datetime, region: str) -> dict:
    """Projected cost over [as_of, as_of + horizon) using every effective rate interval (audit A05).

    Net saving is deliberately not computed here: experiment, transition and optimizer costs are attributed after the
    trial (plans.finalize_cloud_net). Incomplete or ambiguous rate coverage makes the projection UNKNOWN.
    """
    end = as_of + timedelta(hours=int(HORIZON_HOURS))
    out: dict = {"basis": "Projected at dated rates", "result_kind": "projected", "horizon_hours": str(HORIZON_HOURS),
                 "horizon": [as_of.isoformat(), end.isoformat()], "currency": "USD", "price_basis": "synthetic_scenario",
                 "commitment_assumption": "on-demand; no committed-use discount modelled"}
    try:
        if target_mt is None:
            raise DomainError("EVIDENCE_INCOMPLETE", "candidate machine type unknown")
        base = acc.interval_cost(as_of, end, rates_for(prices, facts.machine_type), "USD")
        cand = acc.interval_cost(as_of, end, rates_for(prices, target_mt["machine_type"]), "USD")
    except DomainError as e:
        out.update({"result_kind": "unknown", "reason": f"rate evidence does not cover the horizon: {e}"})
    else:
        out.update({"baseline_cost": str(base), "candidate_cost": str(cand), "gross_saving": str(base - cand),
                    "baseline_usd_per_hour_at_as_of": str(current_rate(prices, facts.machine_type, as_of)),
                    "candidate_usd_per_hour_at_as_of": str(current_rate(prices, target_mt["machine_type"], as_of)),
                    "net_saving": None, "net_status": "pending: experiment, transition and optimizer costs are attributed after the trial",
                    "note": "projection only; not an invoice saving"})
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


def finalize_cloud_net(impacts: dict | None, *, experiment_cost: Decimal | None, transition_cost: Decimal | None,
                       optimizer_overhead: Decimal | None, overhead_reason: str | None) -> dict | None:
    """net = gross − experiment − transition − optimizer overhead, each counted once; any unknown term → net unknown."""
    if not impacts or impacts.get("gross_saving") is None:
        return impacts
    parts = {"experiment_cost": experiment_cost, "transition_cost": transition_cost, "optimizer_overhead": optimizer_overhead}
    out = {**impacts, **{k: (None if v is None else str(v)) for k, v in parts.items()}}
    missing = [k for k, v in parts.items() if v is None]
    if missing:
        out.update({"net_saving": None, "net_status": f"unknown: {', '.join(missing)} not measurable" + (f" ({overhead_reason})" if overhead_reason else "")})
    else:
        net = Decimal(impacts["gross_saving"]) - sum(parts.values())
        out.update({"net_saving": str(net), "net_status": "computed: gross minus one-time costs, each counted once"})
    return out


def runbook(conn, plan: dict) -> dict:
    """A deterministic change runbook from the plan's immutable core: what changes, expected downtime, the automated path
    (only after a human approves the exact hash) and the equivalent manual commands, plus rollback. No model writes this."""
    core, a = plan["core"], plan["core"]["action"]
    if a["action_type"] == "AWS_INSTANCE_TYPE_UPDATE":
        r, i, old, new = a["region"], a["instance_id"], a["expected_instance_type"], a["new_instance_type"]
        last = conn.execute(
            "SELECT (j.detail->>'downtime_seconds')::int AS s, j.at FROM action_journal j JOIN actions x ON x.id=j.action_id "
            "JOIN plans p ON p.id=x.plan_id WHERE j.stage='WRITE_APPLIED' AND j.detail ? 'downtime_seconds' AND p.tenant_id=%s "
            "ORDER BY j.at DESC LIMIT 1", (plan["tenant_id"],)).fetchone()
        downtime = ({"expected": True, "estimate_seconds": last["s"], "basis": f"measured on the last AWS stop/start ({last['at']:%d %b %H:%M} UTC)"}
                    if last else {"expected": True, "estimate_seconds": 120, "basis": "estimate: one EC2 stop/start cycle; replaced by a measurement after the first run"})
        aws = f"aws ec2 --region {r}"
        return {
            "title": f"Resize {i} from {old} to {new}",
            "downtime": downtime,
            "preconditions": [f"instance is still {old} at config version {a['expected_config_version']}",
                              f"policy {core['versions']['policy_version']} still current; target in ALLOWED_TARGET_IDS",
                              "a matched canary trial on the candidate type passed"],
            "automated": {"who": "SuperOps executor, after a human approves the exact plan hash and trial hash",
                          "steps": ["Re-check approval, authority, policy, trial and target versions", "Take the target lock and record intent",
                                    f"Stop {i}", f"Change instance type to {new}", "Tag the new config version and this operation's identity",
                                    f"Start {i}", "Read back the type and wait for EC2 status checks",
                                    "Measure 5+ minutes of CloudWatch CPU against the policy limit on the new capacity",
                                    f"If verification fails and nothing else changed, restore {old} the same way"]},
            "manual": {"note": "Doing this by hand makes the plan stale (its version tag no longer matches); the next investigation records the new state.",
                       "steps": [{"title": "Stop the instance", "command": f"{aws} stop-instances --instance-ids {i}"},
                                 {"title": "Wait until stopped", "command": f"{aws} wait instance-stopped --instance-ids {i}"},
                                 {"title": "Change the type", "command": f"{aws} modify-instance-attribute --instance-id {i} --instance-type Value={new}"},
                                 {"title": "Start it", "command": f"{aws} start-instances --instance-ids {i}"},
                                 {"title": "Read back", "command": f"{aws} describe-instances --instance-ids {i} --query 'Reservations[].Instances[].[InstanceType,State.Name]'"},
                                 {"title": "Check status", "command": f"{aws} describe-instance-status --instance-ids {i}"}]},
            "rollback": {"steps": [{"title": "Restore the previous type", "command":
                                    f"{aws} stop-instances --instance-ids {i} && {aws} wait instance-stopped --instance-ids {i} && "
                                    f"{aws} modify-instance-attribute --instance-id {i} --instance-type Value={old} && {aws} start-instances --instance-ids {i}"}]}}
    if a["action_type"] == "LOCAL_WORKER_CONFIG_UPDATE":
        return {"title": f"Set {a['worker_id']} max_concurrency {a['before']['max_concurrency']} → {a['after']['max_concurrency']} (local analogue)",
                "downtime": {"expected": False, "estimate_seconds": 0, "basis": "hot reload of the worker configuration"},
                "automated": {"who": "SuperOps executor, after a human approves the exact plan hash and trial hash",
                              "steps": ["Re-check approval and versions", "Compare-and-set the config", "Reload and read back", "Run a fresh workload against the SLO"]},
                "manual": {"note": "Local sandbox analogue of a machine-type change; manual edits make the plan stale.", "steps": []},
                "rollback": {"steps": [{"title": "Restore", "command": f"previous max_concurrency {a['before']['max_concurrency']} (automatic when verification fails)"}]}}
    if a["action_type"] == "AI_CONFIG_UPDATE":
        return {"title": "Update the support workflow configuration", "downtime": {"expected": False, "estimate_seconds": 0, "basis": "new runs load the new config"},
                "automated": {"who": "SuperOps executor, after a ROLLOUT_ELIGIBLE holdout verdict and a human approval",
                              "steps": ["Re-check model, workflow and test versions", "Write the config", "Run smoke cases"]},
                "manual": {"note": "Manual edits make the plan stale.", "steps": []}, "rollback": {"steps": []}}
    return {"title": "Projection only", "downtime": {"expected": True, "estimate_seconds": None, "basis": "no executor configured"},
            "automated": {"who": "not available: no executor for this action type", "steps": []},
            "manual": {"note": "Projection only; no executor is configured for this target.", "steps": []}, "rollback": {"steps": []}}
