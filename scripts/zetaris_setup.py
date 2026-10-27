"""Operator setup (never an agent tool): register the two physical evidence sources in a Zetaris instance.

    make sources-up         # source B: a separate PostgreSQL container on :55434 (source A is the project PostgreSQL on :55432)
    make zetaris-setup      # load both sources, create read-only roles, register datasources in Zetaris, verify

Datasources (names match ZETARIS_SOURCE_* in .env):
  cloud_pg  -> source A public schema (inventory, telemetry, billing, pagination_probe)
  cloud_ref -> source A ref schema, as datasource views (Zetaris imports only the default schema's tables)
  ai_pg     -> source B public schema (ai_runs, ai_calls)
Zetaris reaches the sources at host.docker.internal (Zetaris runs in Docker Desktop). Passwords live in the git-ignored
var/sources.local.env and are never printed.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

import httpx

from greenops.config import ROOT, get_settings

ENV = ROOT / "var" / "sources.local.env"
REF_TABLES = ("prices", "machine_types", "model_prices", "carbon_factors", "policies")
HOST = os.environ.get("ZETARIS_SOURCE_HOST", "host.docker.internal")


def local_env() -> dict:
    if not ENV.exists():
        ENV.write_text(f"SRC_B_ADMIN_PW={secrets.token_hex(16)}\nSRC_RO_PW={secrets.token_hex(16)}\n")
        ENV.chmod(0o600)
    return dict(line.split("=", 1) for line in ENV.read_text().split() if "=" in line)


def psql(url: str, sql: str) -> None:
    subprocess.run(["psql", url, "-q", "-v", "ON_ERROR_STOP=1"], input=sql, text=True, check=True)


def read_only_role(url: str, pw: str, schemas: tuple[str, ...]) -> None:
    grants = "\n".join(f"GRANT USAGE ON SCHEMA {s} TO zetaris_ro; GRANT SELECT ON ALL TABLES IN SCHEMA {s} TO zetaris_ro;" for s in schemas)
    psql(url, f"""DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='zetaris_ro') THEN CREATE ROLE zetaris_ro LOGIN; END IF; END$$;
ALTER ROLE zetaris_ro PASSWORD '{pw}';
SELECT 'GRANT CONNECT ON DATABASE ' || current_database() || ' TO zetaris_ro' \\gexec
{grants}
ALTER ROLE zetaris_ro SET default_transaction_read_only = on;
""")


class Zetaris:
    def __init__(self):
        s = get_settings()
        self.s, self.http = s, httpx.Client(base_url=s.zetaris_base_url.rstrip("/"), timeout=600)
        r = self.http.get("/api/v1.0/auth/login", headers=self._h(), auth=(s.zetaris_username, s.zetaris_password))
        r.raise_for_status()
        self.token = r.json()["idToken"]

    def _h(self) -> dict:
        return {"X-Request-ID": str(uuid.uuid4()), "X-Org-ID": str(self.s.zetaris_org_id)}

    def run(self, sql: str) -> dict:
        r = self.http.post("/api/v1.0/sql-editor/sqls/run", headers={**self._h(), "Authorization": f"Bearer {self.token}"},
                           json={"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": 100})
        if r.status_code != 200:
            raise SystemExit(f"Zetaris refused a setup statement: HTTP {r.status_code} {r.text[:200]}")
        return r.json()

    def select(self, sql: str) -> list:
        r = self.http.post("/api/v1.0/query/sql/start", headers={**self._h(), "Authorization": f"Bearer {self.token}"},
                           json={"select": sql, "pageLimit": 10})
        r.raise_for_status()
        return r.json()["records"]


def main() -> None:
    env = local_env()
    a = "postgresql://greenops@127.0.0.1:55432/greenops_src_cloud"
    b = f"postgresql://greenops:{env['SRC_B_ADMIN_PW']}@127.0.0.1:55434/greenops_src_ai"
    subprocess.run([sys.executable, "scripts/load_sources.py", "--group", f"cloud={a}#public", "--group", f"ref={a}#ref",
                    "--group", f"ai={b}#public"], check=True)
    read_only_role(a, env["SRC_RO_PW"], ("public", "ref"))
    read_only_role(b, env["SRC_RO_PW"], ("public",))
    z = Zetaris()
    names = z.s.source_names
    existing = {row[0] for row in z.run("SHOW DATASOURCES")["data"]}
    specs = [(names["cloud"], "Source A host PostgreSQL - cloud inventory, telemetry, billing", "55432/greenops_src_cloud"),
             (names["ref"], "Source A host PostgreSQL - reference prices, policies, carbon, schema ref", "55432/greenops_src_cloud"),
             (names["ai"], "Source B separate PostgreSQL container - AI runs and calls", "55434/greenops_src_ai")]
    for name, desc, db in specs:
        if name in existing:
            z.run(f"DROP DATASOURCE {name}")
        z.run(f'CREATE DATASOURCE {name} DESCRIBE BY "{desc}" OPTIONS (jdbcdriver "org.postgresql.Driver", '
              f'jdbcurl "jdbc:postgresql://{HOST}:{db}", username "zetaris_ro", password "{env["SRC_RO_PW"]}", fetchsize "1000")')
    z.run(f"REGISTER DATASOURCE TABLES FROM {names['cloud']}")
    z.run(f"REGISTER DATASOURCE TABLES FROM {names['ai']}")
    for t in REF_TABLES:
        z.run(f"CREATE DATASOURCE VIEW {t} FROM {names['ref']} AS SELECT * FROM ref.{t}")
    checks = {f"{names['cloud']}.inventory": 6, f"{names['ref']}.prices": 10, f"{names['ai']}.ai_runs": 6}
    for table, expected in checks.items():
        n = int(z.select(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])
        print(f"{table}: {n} rows {'OK' if n == expected else f'EXPECTED {expected}'}")
        if n != expected:
            raise SystemExit(1)
    print("Zetaris datasources registered:", ", ".join(n for n, _, _ in specs))


if __name__ == "__main__":
    main()
