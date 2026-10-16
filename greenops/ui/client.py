"""HTTP client for the GreenOps Verify API. The workbench talks to the API only through this module.

The bearer token is passed per call from Streamlit session state; it is never put in URLs,
query strings or log lines. Mutating calls carry a caller-supplied Idempotency-Key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_API_URL = "http://127.0.0.1:8000"
TIMEOUT = httpx.Timeout(20.0, connect=5.0)


def api_base_url() -> str:
    return os.environ.get("GREENOPS_API_URL", DEFAULT_API_URL).rstrip("/")


@dataclass
class ApiResponse:
    """Outcome of one API call. status == 0 means the request did not complete (outcome unknown)."""
    status: int
    body: Any = None
    text: str = ""
    request_id: str | None = None
    replayed: bool = False

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def outcome_unknown(self) -> bool:
        """Transport failure, timeout or server error: a mutation may or may not have been applied."""
        return self.status == 0 or self.status >= 500

    @property
    def error(self) -> dict:
        if isinstance(self.body, dict) and isinstance(self.body.get("error"), dict):
            e = self.body["error"]
            return {"code": e.get("code", "ERROR"), "message": e.get("message", ""), "details": e.get("details") or {},
                    "retryable": bool(e.get("retryable")), "request_id": e.get("request_id") or self.request_id}
        if self.status == 0:
            return {"code": "API_UNREACHABLE", "message": self.text or "the API did not respond", "details": {},
                    "retryable": True, "request_id": None}
        return {"code": f"HTTP_{self.status}", "message": "unexpected response from the API", "details": {},
                "retryable": self.status >= 500, "request_id": self.request_id}


@dataclass
class ApiClient:
    token: str | None
    base_url: str = field(default_factory=api_base_url)
    _memo: dict = field(default_factory=dict)  # per-script-run read memo; a new client is built on every rerun

    def _headers(self, idempotency_key: str | None = None) -> dict:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        return h

    def request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None,
                idempotency_key: str | None = None, raw: bool = False) -> ApiResponse:
        try:
            with httpx.Client(base_url=self.base_url, timeout=TIMEOUT) as c:
                r = c.request(method, path, params=params, json=json, headers=self._headers(idempotency_key))
        except httpx.TimeoutException:
            return ApiResponse(status=0, text="request timed out; the outcome is unknown")
        except httpx.HTTPError as e:
            return ApiResponse(status=0, text=f"could not reach the API at {self.base_url} ({type(e).__name__})")
        rid = r.headers.get("X-Request-ID")
        replayed = r.headers.get("Idempotent-Replay") == "true"
        ctype = r.headers.get("content-type", "")
        if raw and r.status_code < 400:
            return ApiResponse(status=r.status_code, body=r.content, text=r.text, request_id=rid, replayed=replayed)
        body: Any = None
        if "json" in ctype:
            try:
                body = r.json()
            except ValueError:
                body = None
        return ApiResponse(status=r.status_code, body=body, text="" if body is not None else r.text[:500],
                           request_id=rid, replayed=replayed)

    def get(self, path: str, params: dict | None = None, *, fresh: bool = False) -> ApiResponse:
        key = (path, tuple(sorted((params or {}).items())))
        if not fresh and key in self._memo:
            return self._memo[key]
        resp = self.request("GET", path, params=params)
        self._memo[key] = resp
        return resp

    def post(self, path: str, body: dict, idempotency_key: str) -> ApiResponse:
        self._memo.clear()  # reads after a mutation must see the new state
        return self.request("POST", path, json=body, idempotency_key=idempotency_key)

    def download(self, path: str, params: dict | None = None) -> ApiResponse:
        """Fetch a report body server-side with the bearer header; the token never enters a URL."""
        return self.request("GET", path, params=params, raw=True)
