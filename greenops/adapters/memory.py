"""Client for our private H-MEM sidecar (memory-sidecar/). Errors are explicit; never an empty 'no memories'."""
from __future__ import annotations

import httpx

from greenops.config import Settings


class MemoryUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MemoryClient:
    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        if not settings.memory_auth_token:
            raise MemoryUnavailable("MEMORY_NOT_READY", "MEMORY_AUTH_TOKEN not configured")
        self.http = http or httpx.Client(base_url=settings.memory_base_url, timeout=30,
                                         headers={"Authorization": f"Bearer {settings.memory_auth_token}"})

    def _req(self, method: str, path: str, **kw) -> dict:
        try:
            r = self.http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise MemoryUnavailable("MEMORY_NOT_READY", f"memory sidecar unreachable: {type(e).__name__}")
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code >= 400:
            err = body.get("error", {})
            raise MemoryUnavailable(err.get("code", f"HTTP_{r.status_code}"), err.get("message", r.text[:200]))
        return body

    def health(self) -> dict:
        try:
            r = self.http.get("/health")
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise MemoryUnavailable("MEMORY_NOT_READY", f"memory sidecar unreachable: {type(e).__name__}")

    def remember(self, envelope: dict) -> dict:
        return self._req("POST", "/memory/remember", json=envelope)

    def recall(self, tenant_id: str, service_id: str, query: str, applicability: dict, top_k: int = 5) -> dict:
        return self._req("POST", "/memory/recall", json={"scope": {"tenant_id": tenant_id, "service_id": service_id},
                                                          "query": query, "applicability": applicability, "top_k": top_k})

    def audit(self, receipt_id: str, tenant_id: str, service_id: str) -> dict:
        return self._req("GET", f"/memory/audit/{receipt_id}", params={"tenant_id": tenant_id, "service_id": service_id})
