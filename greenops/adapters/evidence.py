"""Evidence access: reviewed SQL templates executed through Zetaris (connected) or a labelled local sample DB.

No arbitrary SQL: callers name a template and pass typed parameters; values are validated by strict
patterns before being rendered as literals (the Zetaris REST API exposes a SQL string, not bind parameters).
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import httpx

from greenops.config import ROOT, Settings
from greenops.domain.quantities import DomainError, canonical_hash, rfc3339

SQL_DIR = ROOT / "sql"
_PATTERNS = {
    "service_id": re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$"),
    "identifier": re.compile(r"^[A-Za-z0-9._-]{1,64}$"),
    "resource_key": re.compile(r"^(gcp)/([a-z0-9-]{1,63})/([a-z0-9-]{1,63})$"),
}
_SOURCE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")


@dataclass(frozen=True)
class Template:
    id: str
    version: str
    key: tuple[str, ...]
    sources: tuple[str, ...]
    params: dict[str, str]
    sql: str


def load_templates(sql_dir: Path = SQL_DIR) -> dict[str, Template]:
    out = {}
    for path in sorted(sql_dir.glob("*.sql")):
        meta, body = {}, []
        for line in path.read_text().splitlines():
            m = re.match(r"^--\s*(id|version|key|sources|params):\s*(.*)$", line)
            if m:
                meta[m.group(1)] = m.group(2).strip()
            elif not line.startswith("--"):
                body.append(line)
        params = {}
        for p in filter(None, (x.strip() for x in meta.get("params", "").split(","))):
            name, typ = p.split(":")
            params[name] = typ
        t = Template(meta["id"], meta["version"], tuple(k.strip() for k in meta["key"].split(",")),
                     tuple(s.strip() for s in meta["sources"].split(",")), params, "\n".join(body).strip())
        out[t.id] = t
    return out


TEMPLATES = load_templates()


def render(template: Template, params: dict[str, Any], source_names: dict[str, str]) -> str:
    if set(params) != set(template.params):
        raise DomainError("VALIDATION_ERROR", f"template {template.id} expects params {sorted(template.params)}")
    sql = template.sql
    for src in template.sources:
        name = source_names.get(src, "")
        if not _SOURCE_NAME.match(name):
            raise DomainError("VALIDATION_ERROR", f"source name for {src} not configured safely")
        sql = sql.replace("{" + src + "}", name)
    for name, typ in sorted(template.params.items(), key=lambda kv: -len(kv[0])):
        v = params[name]
        if typ == "timestamp":
            if not isinstance(v, datetime) or v.tzinfo is None:
                raise DomainError("VALIDATION_ERROR", f"{name} must be an aware datetime")
            lit = "TIMESTAMP '" + v.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + "'"
            sql = re.sub(rf":{name}\b", lit, sql)
        elif typ == "resource_key":
            m = _PATTERNS["resource_key"].match(str(v))
            if not m:
                raise DomainError("VALIDATION_ERROR", f"{name} is not a canonical resource key")
            for part, val in zip(("provider", "project", "resource"), m.groups()):
                sql = sql.replace(f":{name}.{part}", f"'{val}'")
        else:
            if not _PATTERNS[typ].match(str(v)):
                raise DomainError("VALIDATION_ERROR", f"{name} failed {typ} validation")
            sql = re.sub(rf":{name}\b", f"'{v}'", sql)
    if re.search(r"(?<![:\w]):[a-z_]", sql):
        raise DomainError("VALIDATION_ERROR", "unrendered placeholder")
    return sql


def duplicate_keys(t: Template, rows: list[dict]) -> list[tuple]:
    """Rows sharing the template's declared unique key (audit A07). Missing key columns count as a violation."""
    seen, dupes = set(), []
    for r in rows:
        k = tuple(r.get(c) for c in t.key)
        if None in k or k in seen:
            dupes.append(k)
        seen.add(k)
    return dupes


def norm(v: Any) -> Any:
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float, Decimal)):
        return format(Decimal(str(v)).normalize(), "f")
    if isinstance(v, datetime):
        return rfc3339(v if v.tzinfo else v.replace(tzinfo=timezone.utc))
    return str(v)


@dataclass
class EvidenceResult:
    rows: list[dict]
    receipt: dict
    source_system: str
    completeness: str
    warnings: list[str] = field(default_factory=list)


class EvidenceClient(Protocol):
    source_system: str
    runtime_label: str

    def query(self, template_id: str, params: dict, max_rows: int = 5000) -> EvidenceResult: ...


def _receipt(t: Template, params: dict, sources: list[str], started: float, rows: list[dict], pages: int, completeness: str,
             warnings: list[str], request_ids: list[str], extra: dict | None = None) -> dict:
    return {"receipt_id": str(uuid.uuid4()), "template_id": t.id, "template_version": t.version,
            "parameter_hash": canonical_hash({k: (rfc3339(v) if isinstance(v, datetime) else v) for k, v in params.items()}),
            "sources": sources, "request_ids": request_ids, "started_at": rfc3339(datetime.fromtimestamp(started, timezone.utc)),
            "finished_at": rfc3339(datetime.now(timezone.utc)), "duration_ms": int((time.time() - started) * 1000),
            "row_count": len(rows), "page_count": pages, "completeness": completeness,
            "result_hash": canonical_hash(rows), "warnings": warnings, **(extra or {})}


class SampleSqlClient:
    """Local sample-mode evidence from ONE local database. Not Zetaris, not federation."""
    source_system = "local_sample_postgres"
    runtime_label = "sample"

    def __init__(self, url: str, source_names: dict[str, str] | None = None):
        self.url = url
        self.source_names = source_names or {"cloud": "cloud", "ai": "ai", "ref": "ref"}

    def query(self, template_id: str, params: dict, max_rows: int = 5000) -> EvidenceResult:
        import psycopg
        from psycopg.rows import dict_row

        t = TEMPLATES.get(template_id)
        if t is None:
            raise DomainError("VALIDATION_ERROR", f"unknown evidence template {template_id}")
        sql = render(t, params, self.source_names)
        started = time.time()
        with psycopg.connect(self.url, row_factory=dict_row, options="-c default_transaction_read_only=on -c TimeZone=UTC") as c:
            raw = c.execute(sql).fetchmany(max_rows + 1)
        rows = [{k: norm(v) for k, v in r.items()} for r in raw[:max_rows]]
        if dupes := duplicate_keys(t, rows):
            raise DomainError("EVIDENCE_QUERY_FAILED", f"{t.id}: {len(dupes)} rows violate declared unique key {t.key}")
        completeness, warnings = "complete", ["runtime_mode=sample: local fixture database, not Zetaris federation"]
        if len(raw) > max_rows:
            completeness = "partial"
            warnings.append(f"row budget {max_rows} reached")
        sources = [f"sample:{self.source_names[s]}" for s in t.sources]
        return EvidenceResult(rows, _receipt(t, params, sources, started, rows, 1, completeness, warnings, []), self.source_system,
                              completeness, warnings)


class ZetarisError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ZetarisClient:
    """Zetaris SaaS REST adapter per public OpenAPI v1 (sha256 4ec254d6…): login, sql/start, sql/page, sql/close."""
    source_system = "zetaris"
    runtime_label = "connected_demo"

    def __init__(self, settings: Settings, http: httpx.Client | None = None, timeout_s: float = 15.0, max_retries: int = 2):
        if not settings.zetaris_configured:
            raise ZetarisError("DEPENDENCY_UNAVAILABLE", "Zetaris is not configured (ZETARIS_* settings)")
        self.s = settings
        self.http = http or httpx.Client(base_url=settings.zetaris_base_url.rstrip("/"), timeout=timeout_s)
        self.max_retries = max_retries
        self._token: str | None = None

    def _headers(self, request_id: str) -> dict:
        return {"X-Request-ID": request_id, "X-Org-ID": str(int(self.s.zetaris_org_id)), "Accept": "application/json"}

    def _bearer(self) -> str:
        if self.s.zetaris_auth_mode == "api_key":
            return self.s.zetaris_api_key
        if self._token is None:
            rid = str(uuid.uuid4())
            r = self.http.get("/api/v1.0/auth/login", headers=self._headers(rid),
                              auth=(self.s.zetaris_username, self.s.zetaris_password))
            if r.status_code != 200:
                raise ZetarisError("DEPENDENCY_UNAVAILABLE", f"Zetaris login failed with HTTP {r.status_code}")
            self._token = r.json()["idToken"]
        return self._token

    def _call(self, method: str, path: str, request_ids: list[str], **kw) -> httpx.Response:
        last = None
        for attempt in range(self.max_retries + 1):  # bounded retries are safe: these are read operations
            rid = str(uuid.uuid4())
            request_ids.append(rid)
            try:
                r = self.http.request(method, path, headers={**self._headers(rid), "Authorization": f"Bearer {self._bearer()}"}, **kw)
            except httpx.TimeoutException as e:
                last = ZetarisError("DEPENDENCY_UNAVAILABLE", f"Zetaris {path} timed out")
                continue
            except httpx.HTTPError as e:
                last = ZetarisError("DEPENDENCY_UNAVAILABLE", f"Zetaris transport error: {type(e).__name__}")
                continue
            if r.status_code in (429, 502, 503, 504):
                last = ZetarisError("DEPENDENCY_UNAVAILABLE", f"Zetaris HTTP {r.status_code}")
                time.sleep(min(2.0, 0.5 * (attempt + 1)))
                continue
            if r.status_code in (401, 403):
                raise ZetarisError("DEPENDENCY_UNAVAILABLE", f"Zetaris rejected credentials (HTTP {r.status_code})")
            if r.status_code != 200:
                msg = r.text[:200].replace(self.s.zetaris_api_key or "\x00", "[REDACTED]")
                raise ZetarisError("EVIDENCE_QUERY_FAILED", f"Zetaris HTTP {r.status_code}: {msg}")
            return r
        raise last

    @staticmethod
    def _records(payload: dict) -> list[dict]:
        recs = payload.get("records")
        if recs is None:
            return []
        out = []
        for r in recs:
            if isinstance(r, str):
                r = json.loads(r, parse_float=Decimal)
            if not isinstance(r, dict):
                raise ZetarisError("EVIDENCE_QUERY_FAILED", "Zetaris record is not a JSON object; column names unknown")
            out.append({k.lower(): norm(v) for k, v in r.items()})
        return out

    MAX_PAGE_BYTES = 5 * 1024 * 1024

    def _page(self, r: httpx.Response) -> dict:
        if len(r.content) > self.MAX_PAGE_BYTES:
            raise ZetarisError("EVIDENCE_QUERY_FAILED", f"Zetaris page exceeds {self.MAX_PAGE_BYTES} bytes")
        try:
            body = json.loads(r.text, parse_float=Decimal)
            int(body["totalCount"]), int(body["totalPages"]), int(body["pageNumber"])
        except (ValueError, KeyError, TypeError):
            raise ZetarisError("EVIDENCE_QUERY_FAILED", "Zetaris page is not a valid paging response")
        return body

    def query(self, template_id: str, params: dict, max_rows: int = 5000, max_seconds: float = 120.0) -> EvidenceResult:
        t = TEMPLATES.get(template_id)
        if t is None:
            raise DomainError("VALIDATION_ERROR", f"unknown evidence template {template_id}")
        sql = render(t, params, self.s.source_names)
        started, request_ids, warnings = time.time(), [], []
        limit = max(1, min(100, self.s.zetaris_page_limit))
        r = self._call("POST", "/api/v1.0/query/sql/start", request_ids, json={"select": sql, "pageLimit": limit})
        try:
            token = json.loads(r.text)["queryToken"]
        except (ValueError, KeyError, TypeError):
            raise ZetarisError("EVIDENCE_QUERY_FAILED", "Zetaris start response has no queryToken")
        rows, pages, completeness, close = [], 0, "complete", "not_attempted"
        try:  # everything after the token is inside cleanup (audit A16)
            first = self._page(r)
            total, total_pages, base = int(first["totalCount"]), int(first["totalPages"]), int(first["pageNumber"])
            rows, pages = self._records(first), 1
            page = base
            while page - base + 1 < total_pages:
                if len(rows) >= max_rows or time.time() - started > max_seconds:
                    break
                page += 1
                body = self._page(self._call("GET", "/api/v1.0/query/sql/page", request_ids,
                                              params={"queryToken": token, "pageLimit": limit, "pageNumber": page}))
                if int(body["pageNumber"]) != page:
                    raise ZetarisError("EVIDENCE_QUERY_FAILED", f"Zetaris returned page {body['pageNumber']} for {page}")
                if int(body["totalCount"]) != total or int(body["totalPages"]) != total_pages or body.get("queryToken", token) != token:
                    raise ZetarisError("EVIDENCE_QUERY_FAILED", "Zetaris paging metadata changed between pages (unstable result set)")
                rows.extend(self._records(body))
                pages += 1
            if dupes := duplicate_keys(t, rows):
                raise ZetarisError("EVIDENCE_QUERY_FAILED", f"{t.id}: {len(dupes)} duplicate or keyless rows across pages for key {t.key}")
            if len(rows) > max_rows or (len(rows) == max_rows and total > max_rows):
                rows = rows[:max_rows]
                completeness = "partial"
                warnings.append(f"row budget {max_rows} reached of totalCount={total}")
            elif time.time() - started > max_seconds and len(rows) < total:
                completeness = "partial"
                warnings.append("time budget reached before final page")
            elif len(rows) != total:
                completeness = "partial"
                warnings.append(f"retrieved {len(rows)} rows but totalCount={total}")
        finally:
            try:
                self._call("DELETE", f"/api/v1.0/query/sql/close/{token}", request_ids)
                close = "closed"
            except Exception as e:  # cleanup failure is recorded, never hides the result state
                close = f"close_failed:{getattr(e, 'code', type(e).__name__)}"
        sources = [f"zetaris:{self.s.source_names[s]}" for s in t.sources]
        receipt = _receipt(t, params, sources, started, rows, pages, completeness, warnings, request_ids,
                           {"query_close": close, "page_limit": limit, "page_base": base, "total_count": total, "key": list(t.key)})
        return EvidenceResult(rows, receipt, self.source_system, completeness, warnings)


def evidence_client(settings: Settings) -> EvidenceClient:
    """Mode is server configuration. connected_demo never silently falls back to the sample DB."""
    if settings.runtime_mode.value == "connected_demo":
        return ZetarisClient(settings)
    return SampleSqlClient(settings.sample_source_url)
