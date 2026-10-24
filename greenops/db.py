"""PostgreSQL access. ponytail: plain psycopg + versioned SQL files; one connection per unit of work."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb, set_json_dumps

from greenops.config import ROOT

MIGRATIONS = ROOT / "migrations"


def _default(o):
    if isinstance(o, Decimal):
        return format(o, "f")
    if isinstance(o, datetime):
        return o.isoformat().replace("+00:00", "Z")
    if isinstance(o, UUID):
        return str(o)
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def dumps(obj) -> str:
    return json.dumps(obj, default=_default, sort_keys=True)


set_json_dumps(dumps)
J = Jsonb


def _url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


@contextmanager
def connect(url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(_url(url), row_factory=dict_row, options="-c TimeZone=UTC") as conn:
        yield conn


def migrate(url: str) -> list[str]:
    applied = []
    with connect(url) as c:
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        c.execute("SELECT pg_advisory_xact_lock(4207)")
        done = {r["version"] for r in c.execute("SELECT version FROM schema_migrations")}
        for path in sorted(Path(MIGRATIONS).glob("*.sql")):
            if path.stem in done:
                continue
            c.execute(path.read_text())
            c.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
            applied.append(path.stem)
    return applied
