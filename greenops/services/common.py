"""Shared service plumbing: runtime dependencies, errors, events and durable jobs."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from greenops.config import Settings
from greenops.db import J, connect


def now() -> datetime:
    return datetime.now(timezone.utc)


class AppError(Exception):
    """Maps to the API error envelope (docs/API_REFERENCE.md)."""

    def __init__(self, code: str, status: int, message: str, details: dict | None = None, retryable: bool = False):
        super().__init__(message)
        self.code, self.status, self.message, self.details, self.retryable = code, status, message, details or {}, retryable


@dataclass
class Runtime:
    """Dependencies resolved from server configuration. Tests inject fakes; production never swaps modes silently."""
    settings: Settings
    evidence_factory: Callable
    model_factory: Callable
    memory_factory: Callable
    clock: Callable[[], datetime] = now

    @property
    def db(self) -> str:
        return self.settings.database_url

    @classmethod
    def from_settings(cls, settings: Settings) -> "Runtime":
        from greenops.adapters.evidence import evidence_client
        from greenops.adapters.memory import MemoryClient
        from greenops.adapters.model import AdkGateway, ScriptedGateway
        from greenops.agents.roles import SCRIPTS

        def model():
            if settings.runtime_mode.value == "connected_demo":
                return AdkGateway(settings)
            from experiments.support.workflow import scripted_support
            return ScriptedGateway({**SCRIPTS, "support": scripted_support})

        return cls(settings, lambda: evidence_client(settings), model, lambda: MemoryClient(settings))


def append_event(conn, investigation_id, kind: str, actor: str, payload: dict) -> int:
    conn.execute("SELECT 1 FROM investigations WHERE id = %s FOR UPDATE", (investigation_id,))
    row = conn.execute(
        "INSERT INTO investigation_events (investigation_id, seq, kind, actor, payload) "
        "SELECT %s, COALESCE(MAX(seq), 0) + 1, %s, %s, %s FROM investigation_events WHERE investigation_id = %s RETURNING seq",
        (investigation_id, kind, actor, J(payload), investigation_id)).fetchone()
    return row["seq"]


def event(rt: Runtime, investigation_id, kind: str, actor: str, payload: dict) -> None:
    with connect(rt.db) as c:
        append_event(c, investigation_id, kind, actor, payload)


# ---- durable jobs -----------------------------------------------------------------

LEASE = timedelta(seconds=60)


def enqueue(conn, kind: str, ref_id, run_after: datetime | None = None) -> uuid.UUID:
    jid = uuid.uuid4()
    conn.execute("INSERT INTO jobs (id, kind, ref_id, status, run_after) VALUES (%s, %s, %s, 'QUEUED', COALESCE(%s, now()))",
                 (jid, kind, ref_id, run_after))
    return jid


def claim(db: str, owner: str, kinds: tuple[str, ...]) -> dict | None:
    with connect(db) as c:
        row = c.execute(
            "SELECT * FROM jobs WHERE status = 'QUEUED' AND run_after <= now() AND kind = ANY(%s) "
            "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED", (list(kinds),)).fetchone()
        if not row:
            return None
        c.execute("UPDATE jobs SET status='RUNNING', attempts=attempts+1, lease_owner=%s, lease_expires_at=now()+%s, updated_at=now() WHERE id=%s",
                  (owner, LEASE, row["id"]))
        return {**row, "attempts": row["attempts"] + 1}


def renew(db: str, job_id, owner: str) -> None:
    with connect(db) as c:
        c.execute("UPDATE jobs SET lease_expires_at=now()+%s WHERE id=%s AND lease_owner=%s AND status='RUNNING'", (LEASE, job_id, owner))


def finish(db: str, job_id, ok: bool, error: str | None = None) -> None:
    with connect(db) as c:
        c.execute("UPDATE jobs SET status=%s, last_error=%s, lease_owner=NULL, lease_expires_at=NULL, updated_at=now() WHERE id=%s",
                  ("SUCCEEDED" if ok else "FAILED", error, job_id))


def requeue_expired(db: str) -> list[dict]:
    """Expired leases: read jobs are requeued; action jobs are requeued for *reconciliation*, never blind repeat."""
    with connect(db) as c:
        rows = c.execute("UPDATE jobs SET status='QUEUED', lease_owner=NULL, lease_expires_at=NULL, updated_at=now() "
                         "WHERE status='RUNNING' AND lease_expires_at < now() RETURNING id, kind, ref_id").fetchall()
    return rows


# ---- global mutation slot ------------------------------------------------------------

def acquire_slot(conn, kind: str, holder_id) -> bool:
    row = conn.execute("UPDATE execution_slot SET holder_kind=%s, holder_id=%s, acquired_at=now() "
                       "WHERE id=1 AND (holder_id IS NULL OR holder_id=%s) RETURNING id", (kind, holder_id, holder_id)).fetchone()
    return row is not None


def release_slot(conn, holder_id) -> None:
    conn.execute("UPDATE execution_slot SET holder_kind=NULL, holder_id=NULL, acquired_at=NULL WHERE id=1 AND holder_id=%s", (holder_id,))
