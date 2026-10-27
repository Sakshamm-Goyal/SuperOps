"""Ops Copilot safety contract: read-only tools, caller-scoped API access, no mutating route reachable."""
from __future__ import annotations

from greenops import copilot
from greenops.services.common import AppError


class FakeRt:
    settings = None


def toolbox(calls):
    def get(path):
        calls.append(path)
        return 200, {"id": "x", "status": "OK", "data": {}}
    return copilot.Toolbox(FakeRt(), {"tenant_id": "t", "actor_id": "a"}, get)


def test_copilot_tools_are_read_only():
    names = {t["name"] for t in copilot.TOOLS}
    assert names == {"system_status", "list_investigations", "get_investigation", "get_investigation_events", "get_record",
                     "recall_memory", "query_evidence"}
    assert not any(w in n for n in names for w in ("approve", "execute", "revoke", "create", "cancel", "trial"))


def test_copilot_api_allowlist_refuses_mutating_and_unknown_routes():
    calls = []
    tb = toolbox(calls)
    for path in ("/v1/plans/00000000-0000-0000-0000-000000000000/approve", "/v1/plans/00000000-0000-0000-0000-000000000000/execute",
                 "/v1/approvals/00000000-0000-0000-0000-000000000000/revoke", "/docs", "/v1/plans/../operations", "http://evil/v1/me"):
        assert tb._get(path) == {"error": "route not allowed for the copilot"}
    assert calls == []
    tb._get("/v1/plans/00000000-0000-0000-0000-000000000000")
    assert calls == ["/v1/plans/00000000-0000-0000-0000-000000000000"]


def test_copilot_rejects_bad_inputs_without_calling():
    calls = []
    tb = toolbox(calls)
    assert tb.run("get_record", {"kind": "policy", "id": "x"}) == {"error": "unknown kind"}
    assert tb.run("approve_plan", {}) == {"error": "unknown tool approve_plan"}
    assert tb.run("query_evidence", {"template_id": "DROP TABLE"}) == {"error": "unknown template"}
    tb.run("list_investigations", {"status": "x'; DROP", "limit": 999})
    assert calls == ["/v1/investigations?limit=20"]  # bad status ignored, limit clamped
    assert calls and all(p.startswith("/v1/") for p in calls)


def test_copilot_timestamp_requires_timezone():
    try:
        copilot._ts("2026-10-01T00:00:00")
    except AppError as e:
        assert e.code == "VALIDATION_ERROR"
    else:
        raise AssertionError("naive timestamp accepted")


def test_investigation_tool_carries_each_trials_own_measurements():
    """27 Oct: without them the copilot gave trial 15a31577 an earlier canary's 58.4% (cited in the plan rationale)."""
    T = "15a31577-1808-44ac-a0cf-1fa19a602e50"
    I = "9959c31a-5909-47f3-8fb5-7df728fac88e"

    def get(path):
        if path.startswith("/v1/trials/"):
            return 200, {"id": T, "data": {"result": {"checks": [{"check_id": "TRIAL-CPU-HEADROOM", "status": "PASS",
                                                                  "detail": "peak 1-minute CPU 50.7% on c7g.large vs policy limit 80%"}]}}}
        return 200, {"id": I, "status": "COMPLETED", "data": {"plans": [{"id": "p", "rationale": "earlier canary shows peak CPU 58.4%"}],
                                                               "trials": [{"id": T, "status": "PASSED"}]}}
    body = copilot.Toolbox(FakeRt(), {"tenant_id": "t", "actor_id": "a"}, get).t_get_investigation(I)
    assert "50.7%" in body["data"]["trials"][0]["checks"][0]["detail"]
