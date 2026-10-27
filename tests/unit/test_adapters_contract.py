"""Adapter CONTRACT tests (mocked transport). They prove request/response handling, not live Zetaris access (ZET-* in tests/connected)."""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import httpx
import pytest

from greenops.adapters.evidence import TEMPLATES, ZetarisClient, ZetarisError, render
from greenops.config import get_settings
from greenops.domain.quantities import DomainError

S = datetime(2026, 9, 30, tzinfo=timezone.utc)
E = datetime(2026, 10, 21, tzinfo=timezone.utc)
NAMES = {"cloud": "cloud_pg.public", "ai": "ai_pg.public", "ref": "cloud_pg.ref"}


def settings(**kw):
    return dataclasses.replace(get_settings(), zetaris_base_url="https://zetaris.invalid", zetaris_org_id="42", zetaris_auth_mode="api_key",
                               zetaris_api_key="sk-secret-canary", zetaris_page_limit=100, source_names=NAMES, **kw)


def fake_zetaris(total: int, base: int = 1, fail_page: int | None = None, drop: int = 0, as_strings: bool = False):
    log = {"closed": 0, "calls": []}
    rows = [{"PROBE_ID": i, "LABEL": f"probe-{i:03d}"} for i in range(1, total + 1 - drop)]

    def page(n):
        chunk = rows[(n - base) * 100:(n - base + 1) * 100]
        return [json.dumps(r) for r in chunk] if as_strings else chunk

    def handler(req: httpx.Request):
        log["calls"].append((req.method, req.url.path, dict(req.headers)))
        assert req.headers["X-Org-ID"] == "42" and req.headers["Authorization"] == "Bearer sk-secret-canary"
        assert len(req.headers["X-Request-ID"]) == 36
        pages = -(-total // 100)
        if req.url.path.endswith("/sql/start"):
            body = json.loads(req.content)
            assert "select" in body and 1 <= body["pageLimit"] <= 100
            return httpx.Response(200, json={"pageNumber": base, "pageLimit": 100, "totalCount": total, "totalPages": pages,
                                             "queryToken": "qt-1", "records": page(base)})
        if req.url.path.endswith("/sql/page"):
            n = int(req.url.params["pageNumber"])
            if n == fail_page:
                return httpx.Response(500, text="boom sk-secret-canary")
            return httpx.Response(200, json={"pageNumber": n, "totalCount": total, "totalPages": pages, "queryToken": "qt-1", "records": page(n)})
        if "/sql/close/" in req.url.path:
            log["closed"] += 1
            return httpx.Response(200)
        return httpx.Response(404)
    return httpx.Client(base_url="https://zetaris.invalid", transport=httpx.MockTransport(handler)), log


@pytest.mark.parametrize("base", [0, 1])
@pytest.mark.parametrize("as_strings", [False, True])
def test_zet02_contract_pagination_205_rows_exactly_once(base, as_strings):
    http, log = fake_zetaris(205, base=base, as_strings=as_strings)
    r = ZetarisClient(settings(), http=http).query("pagination_probe", {})
    ids = [row["probe_id"] for row in r.rows]
    assert len(ids) == 205 == len(set(ids)) and r.completeness == "complete"
    assert r.receipt["page_count"] == 3 and r.receipt["query_close"] == "closed" and log["closed"] == 1
    assert r.receipt["sources"] == ["zetaris:cloud_pg.public"]
    assert "sk-secret-canary" not in json.dumps(r.receipt)


def test_zet_contract_count_mismatch_is_partial_not_complete():
    http, _ = fake_zetaris(205, drop=5)
    r = ZetarisClient(settings(), http=http).query("pagination_probe", {})
    assert r.completeness == "partial" and "totalCount=205" in r.warnings[0]


def test_zet04_contract_failure_closes_query_and_redacts_secret():
    http, log = fake_zetaris(205, fail_page=2)
    with pytest.raises(ZetarisError) as e:
        ZetarisClient(settings(), http=http).query("pagination_probe", {})
    assert log["closed"] == 1 and "sk-secret-canary" not in str(e.value)


def test_zet_contract_rejected_credentials_and_unconfigured():
    http = httpx.Client(base_url="https://zetaris.invalid", transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    with pytest.raises(ZetarisError) as e:
        ZetarisClient(settings(), http=http).query("pagination_probe", {})
    assert e.value.code == "DEPENDENCY_UNAVAILABLE"
    with pytest.raises(ZetarisError):
        ZetarisClient(dataclasses.replace(get_settings(), zetaris_org_id=None))


def test_sec03_templates_reject_injection_and_unknown_params():
    t = TEMPLATES["telemetry_series"]
    with pytest.raises(DomainError):
        render(t, {"resource_key": "gcp/x'; DROP TABLE telemetry;--/y", "start": S, "end": E}, NAMES)
    with pytest.raises(DomainError):
        render(TEMPLATES["policy"], {"service_id": "support-demo' OR '1'='1", "version": "pol-v1"}, NAMES)
    with pytest.raises(DomainError):
        render(TEMPLATES["inventory"], {"service_id": "support-demo", "as_of": E, "extra": 1}, NAMES)
    with pytest.raises(DomainError):
        render(TEMPLATES["inventory"], {"service_id": "support-demo", "as_of": E}, {**NAMES, "cloud": "x; DROP"})
    sql = render(TEMPLATES["service_cost_rollup"], {"service_id": "support-demo", "start": S, "end": E}, NAMES)
    assert "cloud_pg.public.billing" in sql and "ai_pg.public.ai_calls" in sql and "TIMESTAMP '2026-09-30 00:00:00'" in sql
    assert all(t.sql.lstrip().upper().startswith(("SELECT", "WITH")) for t in TEMPLATES.values())  # read-only templates only


def test_holdout_never_in_agent_readable_templates():
    for t in TEMPLATES.values():
        if "ai_calls" in t.sql or "ai_runs" in t.sql:
            assert "evaluation_partition = 'development'" in t.sql and "access_class = 'agent_readable'" in t.sql, t.id


def test_model_gateway_retries_one_transient_failure_only():
    from greenops.adapters.model import AdkGateway, ModelError
    calls = []

    async def flaky(*a):
        calls.append(1)
        if len(calls) == 1:
            raise ModelError("DEPENDENCY_UNAVAILABLE", "investigator: model call exceeded 90.0s")
        return "ok"

    g = object.__new__(AdkGateway)  # no provider construction: this checks the retry policy only
    g._run = flaky
    assert g.run("investigator", "", {}, None, timeout_s=1) == "ok" and len(calls) == 2

    async def always(*a):
        calls.append(1)
        raise ModelError("DEPENDENCY_UNAVAILABLE", "down")
    g._run, calls[:] = always, []
    with pytest.raises(ModelError):
        g.run("investigator", "", {}, None, timeout_s=1)
    assert len(calls) == 2

    async def invalid(*a):
        calls.append(1)
        raise ModelError("MODEL_OUTPUT_INVALID", "schema")
    g._run, calls[:] = invalid, []
    with pytest.raises(ModelError):
        g.run("investigator", "", {}, None, timeout_s=1)
    assert len(calls) == 1  # schema violations are not retried


def _ts_zetaris(tz: str):
    """Spark renders timestamptz as zone-less strings in the session time zone (observed on local Zetaris, 26 Oct)."""
    def handler(req: httpx.Request):
        if req.url.path.endswith("/sql/start"):
            sql = json.loads(req.content)["select"]
            recs = [{"tz": tz}] if "current_timezone" in sql else [{"SKU": "e2-standard-2", "EFFECTIVE_FROM": "2026-08-31 00:00:00.0", "EFFECTIVE_TO": None,
                                                                    "PRICE": "0.067", "NOTE": "2026-08-31 00:00:00 is not a time"}]
            return httpx.Response(200, json={"pageNumber": 1, "pageLimit": 100, "totalCount": len(recs), "totalPages": 1, "queryToken": "qt", "records": recs})
        if "/sql/close/" in req.url.path:
            return httpx.Response(200)
        return httpx.Response(404)
    return httpx.Client(base_url="https://zetaris.invalid", transport=httpx.MockTransport(handler))


def test_zetaris_spark_timestamps_become_rfc3339_utc_only_in_a_utc_session():
    rows = ZetarisClient(settings(), http=_ts_zetaris("GMT")).query("prices", {"region": "us-central1"}).rows
    assert rows[0]["effective_from"] == "2026-08-31T00:00:00Z" and rows[0]["effective_to"] is None
    assert rows[0]["note"] == "2026-08-31 00:00:00 is not a time"
    with pytest.raises(ZetarisError) as e:
        ZetarisClient(settings(), http=_ts_zetaris("Australia/Sydney")).query("prices", {"region": "us-central1"})
    assert e.value.code == "EVIDENCE_QUERY_FAILED" and "Australia/Sydney" in str(e.value)
