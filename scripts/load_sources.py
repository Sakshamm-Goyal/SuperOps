"""Load the generated synthetic CSVs into source databases.

Connected demo: load `cloud`+`ref` into physical source A and `ai` into physical source B, both reachable by
your Zetaris workspace, then register them there (see docs/OPERATIONS.md). Sample mode: all groups go into
one local database under separate schemas — that is NOT federation and is labelled runtime_mode=sample.

    uv run python scripts/load_sources.py --group cloud=postgresql://.../src_a#public \
        --group ref=postgresql://.../src_a#ref --group ai=postgresql://.../src_b#public
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "data" / "generated"

DDL = {
    "cloud": {
        "inventory": """provider text not null, project_id text not null, resource_id text not null, service_id text not null,
            display_name text not null, environment text not null, machine_type text not null, vcpu numeric not null,
            memory_gib numeric not null, region text not null, architecture text not null, stateful boolean not null,
            local_ssd boolean not null, gpu boolean not null, config_version integer not null, scenario_role text not null,
            effective_from timestamptz not null, effective_to timestamptz, primary key (provider, project_id, resource_id, effective_from)""",
        "telemetry": """provider text not null, project_id text not null, resource_id text not null, observed_at timestamptz not null,
            cpu_percent numeric, memory_bytes bigint, latency_ms numeric, error_count integer, request_count integer,
            primary key (provider, project_id, resource_id, observed_at)""",
        "billing": """billing_record_id text primary key, provider text not null, project_id text not null, resource_id text not null,
            sku text not null, usage_start timestamptz not null, usage_end timestamptz not null, usage_quantity numeric not null,
            usage_unit text not null, cost numeric not null, currency text not null, rate_version text not null""",
        "pagination_probe": "probe_id integer primary key, label text not null",
    },
    "ref": {
        "prices": """provider text, region text, sku text, unit text, currency text, price numeric, effective_from timestamptz,
            effective_to timestamptz, rate_version text, price_basis text""",
        "machine_types": "machine_type text primary key, family text, vcpu numeric, memory_gib numeric, architecture text",
        "model_prices": """model_family text, input_per_million numeric, output_per_million numeric, currency text,
            effective_from timestamptz, effective_to timestamptz, price_basis text""",
        "carbon_factors": """region text, kg_co2e_per_kwh numeric, kwh_per_vcpu_hour numeric, kwh_per_gib_hour numeric,
            pue_included boolean, method_version text, effective_from timestamptz, effective_to timestamptz, factor_source text""",
        "policies": "service_id text, policy_id text, version text, effective_from timestamptz, document text, primary key (service_id, version)",
    },
    "ai": {
        "ai_runs": """run_id text primary key, service_id text, workflow_id text, workflow_version text, config_json text,
            evaluation_partition text, access_class text, started_at timestamptz, cases integer""",
        "ai_calls": """run_id text, call_id text primary key, attempt integer, call_kind text, tool_name text, args_hash text,
            input_tokens integer, output_tokens integer, tool_cost numeric, status text, evaluation_partition text,
            access_class text, started_at timestamptz""",
    },
}
FILES = {"inventory": "cloud/inventory.csv", "telemetry": "cloud/telemetry.csv", "billing": "cloud/billing.csv",
         "pagination_probe": "cloud/pagination_probe.csv", "prices": "ref/prices.csv", "machine_types": "ref/machine_types.csv",
         "model_prices": "ref/model_prices.csv", "carbon_factors": "ref/carbon_factors.csv", "policies": "ref/policies.csv",
         "ai_runs": "ai/ai_runs.csv", "ai_calls": "ai/ai_calls.csv"}
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def load(group: str, url: str, schema: str) -> None:
    if not IDENT.match(schema):
        raise SystemExit(f"bad schema name {schema!r}")
    with psycopg.connect(url, autocommit=False) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for table, cols in DDL[group].items():
            conn.execute(f"DROP TABLE IF EXISTS {schema}.{table}")
            conn.execute(f"CREATE TABLE {schema}.{table} ({cols})")
            path = GEN / FILES[table]
            with conn.cursor().copy(f"COPY {schema}.{table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')") as cp:
                cp.write(path.read_bytes())
            n = conn.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
            print(f"{group}:{schema}.{table} rows={n}")
        conn.commit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", required=True, help="group=postgresql_url#schema (group: cloud|ref|ai)")
    for spec in ap.parse_args().group:
        group, rest = spec.split("=", 1)
        url, _, schema = rest.partition("#")
        load(group, url, schema or "public")


if __name__ == "__main__":
    main()
