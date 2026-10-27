"""Live AWS service: screening waiver semantics, runbooks, per-service evidence routing, suites and live drift."""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from greenops.adapters.evidence import TEMPLATES, ZetarisClient, evidence_client, render
from greenops.config import ROOT, RuntimeMode, get_settings, service_config
from greenops.domain.models import ServicePolicy
from greenops.domain.quantities import DomainError
from greenops.domain.screening import MachineType, ResourceFacts, screen_cloud
from greenops.services.investigation import suite_for
from greenops.services.plans import runbook

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
KEY = "aws/ap-south-1/i-0e90f66f292190c4e"
POLICY = ServicePolicy.model_validate_json((ROOT / "config/policies/superops-aws-pol-v1.json").read_text())


def facts(peak="31.3", stress=None, key=KEY, env="staging"):
    return ResourceFacts(resource_key=key, environment=env, machine_type="c7g.xlarge", vcpu=Decimal(4), memory_gib=Decimal(8),
                         architecture="arm64", region="ap-south-1", stateful=False, local_ssd=False, gpu=False, expected_rows=24,
                         cpu_rows=360, memory_rows=360, last_observed_at=NOW - timedelta(minutes=2), avg_cpu_pct=Decimal("27"),
                         peak_cpu_pct=Decimal(peak), peak_memory_bytes=Decimal(2_500_000_000), stress_peak_cpu_pct=stress)


LARGE = MachineType("c7g.large", Decimal(2), Decimal(4), "arm64")


def test_policy_waiver_is_waived_never_pass_and_does_not_block():
    r = screen_cloud(facts(), LARGE, POLICY, NOW, "AWS_INSTANCE_TYPE_UPDATE", Decimal("0.0491"), Decimal("0.0982"))
    stress = next(c for c in r.checks if c.check_id == "CHK-CPU-STRESS")
    assert stress.status == "WAIVED" and "waived by policy pol-v1" in stress.detail
    assert r.outcome == "ELIGIBLE_FOR_TRIAL"
    no_waiver = POLICY.model_copy(update={"stress_forecast_waiver": None})
    r2 = screen_cloud(facts(), LARGE, no_waiver, NOW, "AWS_INSTANCE_TYPE_UPDATE", Decimal("0.0491"), Decimal("0.0982"))
    assert next(c for c in r2.checks if c.check_id == "CHK-CPU-STRESS").status == "UNKNOWN" and r2.outcome == "NEEDS_EVIDENCE"


def test_waiver_never_rescues_a_peak_or_a_frozen_resource():
    spiky = screen_cloud(facts(peak="85"), LARGE, POLICY, NOW, "AWS_INSTANCE_TYPE_UPDATE", Decimal("0.0491"), Decimal("0.0982"))
    assert spiky.outcome == "REJECTED" and any(c.check_id == "CHK-CPU-PEAK" and c.status == "FAIL" for c in spiky.checks)
    frozen = screen_cloud(facts(key="aws/ap-south-1/i-05a6f032525dd0cf9", env="prod"), LARGE, POLICY, NOW, "AWS_INSTANCE_TYPE_UPDATE",
                          Decimal("0.0491"), Decimal("0.0982"))
    assert frozen.outcome == "REJECTED" and "change freeze" in next(c for c in frozen.checks if c.check_id == "CHK-POLICY").detail


class FakeConn:
    def __init__(self, row):
        self.row = row

    def execute(self, *a):
        return self

    def fetchone(self):
        return self.row


PLAN = {"tenant_id": "t", "core": {"versions": {"policy_version": "pol-v1"}, "action": {
    "action_type": "AWS_INSTANCE_TYPE_UPDATE", "region": "ap-south-1", "instance_id": "i-0e90f66f292190c4e", "expected_config_version": 1,
    "expected_instance_type": "c7g.xlarge", "new_instance_type": "c7g.large"}}}


def test_aws_runbook_has_manual_commands_rollback_and_learns_downtime():
    book = runbook(FakeConn(None), PLAN)
    assert book["downtime"]["expected"] and "estimate" in book["downtime"]["basis"]
    cmds = " ".join(s["command"] for s in book["manual"]["steps"])
    assert "stop-instances --instance-ids i-0e90f66f292190c4e" in cmds and "Value=c7g.large" in cmds and "--region ap-south-1" in cmds
    assert "Value=c7g.xlarge" in book["rollback"]["steps"][0]["command"] and "stale" in book["manual"]["note"]
    measured = runbook(FakeConn({"s": 74, "at": NOW}), PLAN)["downtime"]
    assert measured["estimate_seconds"] == 74 and measured["basis"].startswith("measured")


def test_live_service_routes_evidence_to_its_own_zetaris_sources():
    s = dataclasses.replace(get_settings(), runtime_mode=RuntimeMode.CONNECTED_DEMO, zetaris_org_id="1", zetaris_auth_mode="api_key",
                            zetaris_api_key="k", source_names={"cloud": "cloud_pg", "ref": "cloud_ref", "ai": "ai_pg"})
    aws = evidence_client(s, "superops-aws")
    assert isinstance(aws, ZetarisClient) and aws.s.source_names["cloud"] == "aws_pg" and aws.s.source_names["ref"] == "aws_ref"
    assert evidence_client(s, "support-demo").s.source_names["cloud"] == "cloud_pg"
    assert service_config("superops-aws")["paths"] == ["cloud"] and service_config("superops-aws")["data_origin"] == "real_permitted"


def test_resource_keys_accept_aws_and_reject_injection():
    sql = render(TEMPLATES["telemetry_series"], {"resource_key": KEY, "start": NOW - timedelta(hours=1), "end": NOW},
                 {"cloud": "aws_pg", "ref": "aws_ref", "ai": "ai_pg"})
    assert "'aws'" in sql and "'i-0e90f66f292190c4e'" in sql
    with pytest.raises(DomainError):
        render(TEMPLATES["telemetry_series"], {"resource_key": "azure/x/y'--", "start": NOW, "end": NOW}, {"cloud": "aws_pg"})


def test_suite_selection_per_executor():
    assert suite_for({"path": "cloud", "core": {"executor": "aws"}}) == "aws-canary-v1"
    assert suite_for({"path": "cloud", "core": {"executor": "local_analogue"}}) == "workload-wl-v1"
    assert suite_for({"path": "ai", "core": {"executor": "local_analogue"}}) == "support-dev-v1"


def test_live_drift_is_material_not_every_minute():
    import importlib
    ap = importlib.import_module("scripts.autopilot")
    a = ap._bands([{"resource_id": "i-1", "peak_cpu_percent": "81.2", "avg_cpu_percent": "21.0"}])
    b = ap._bands([{"resource_id": "i-1", "peak_cpu_percent": "84.9", "avg_cpu_percent": "23.9"}])  # minute-to-minute noise
    c = ap._bands([{"resource_id": "i-1", "peak_cpu_percent": "95.0", "avg_cpu_percent": "21.0"}])  # a new, higher peak band
    assert a == b and a != c


def test_action_states_for_aws_plans_are_instance_types():
    """Live run 9959c31a: execution 500'd because the action record assumed local before/after configs."""
    from greenops.services.approvals import _state
    plan = {"core": PLAN["core"]}
    assert _state(plan, "before") == {"instance_type": "c7g.xlarge"} and _state(plan, "after") == {"instance_type": "c7g.large"}


def test_only_a_bounded_rejection_loop_earns_a_fresh_session_retry(monkeypatch):
    """Autopilot run 998db355: Nemotron re-sent a schema-rejected set_model_response until the 90 s cap, twice."""
    from greenops.adapters.model import AdkGateway, ModelError
    g = AdkGateway.__new__(AdkGateway)
    calls = []

    async def loop(*a):
        calls.append(1)
        raise ModelError("MODEL_OUTPUT_INVALID", "typed answer rejected 3 times", fresh_retry=True)
    monkeypatch.setattr(g, "_run", loop)
    with pytest.raises(ModelError):
        g.run("investigator", "", {}, None, timeout_s=1)
    assert len(calls) == 2
