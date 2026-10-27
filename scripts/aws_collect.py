"""Operator command: collect the live AWS sandbox into its own evidence source and register it in Zetaris.

    make aws-collect              # one collection (and create/register the source on first run)
    make aws-collect WATCH=120    # collect every 120 s (keeps telemetry fresh for investigations)

Source C (`superops_src_aws`, a separate database) receives, from AWS APIs only:
  public.inventory   EC2 DescribeInstances (Project=SuperOps, not canaries): type, vCPU, memory, tags, config version tag
  public.telemetry   CloudWatch 1-minute CPUUtilization (AWS/EC2) + mem_used (CWAgent), since launch
  public.billing     ESTIMATED hourly rows = observed running hours × Price List on-demand rate (rate_version says so)
  ref.prices         AWS Price List API, on-demand Linux, Asia Pacific (Mumbai), with the term's effective date
  ref.machine_types  EC2 DescribeInstanceTypes for the c7g family
  ref.carbon_factors an illustrative grid factor (labelled; not a measured emission)
  ref.policies       config/policies/superops-aws-pol-v1.json
Zetaris datasources `aws_pg` (public) and `aws_ref` (views over ref) point at it through the read-only role.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
import psycopg

from greenops.config import ROOT
from scripts.aws_sandbox import REGION
from scripts.load_sources import DDL
from scripts.zetaris_setup import Zetaris, local_env

SRC = os.environ.get("AWS_SOURCE_URL", "postgresql://greenops@127.0.0.1:55432/superops_src_aws")
SERVICE = "superops-aws"
FAMILY = ("c7g.medium", "c7g.large", "c7g.xlarge", "c7g.2xlarge")
LOCATION = "Asia Pacific (Mumbai)"


def ensure_db() -> None:
    admin = SRC.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname='superops_src_aws'").fetchone():
            c.execute("CREATE DATABASE superops_src_aws")
    with psycopg.connect(SRC) as c:
        c.execute("CREATE SCHEMA IF NOT EXISTS ref")
        for group, schema in (("cloud", "public"), ("ref", "ref")):
            for table, cols in DDL[group].items():
                if table == "pagination_probe":
                    continue
                c.execute(f"CREATE TABLE IF NOT EXISTS {schema}.{table} ({cols})")
        pw = local_env()["SRC_RO_PW"]
        c.execute(f"ALTER ROLE zetaris_ro PASSWORD '{pw}'")
        c.execute("GRANT CONNECT ON DATABASE superops_src_aws TO zetaris_ro")
        for schema in ("public", "ref"):
            c.execute(f"GRANT USAGE ON SCHEMA {schema} TO zetaris_ro")
            c.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO zetaris_ro")


def prices() -> list[tuple]:
    p = boto3.client("pricing", region_name="us-east-1")
    out = []
    for t in FAMILY:
        flt = {"instanceType": t, "location": LOCATION, "operatingSystem": "Linux", "tenancy": "Shared", "preInstalledSw": "NA", "capacitystatus": "Used"}
        for item in p.get_products(ServiceCode="AmazonEC2", Filters=[{"Type": "TERM_MATCH", "Field": k, "Value": v} for k, v in flt.items()])["PriceList"]:
            d = json.loads(item)
            for term in d["terms"]["OnDemand"].values():
                for dim in term["priceDimensions"].values():
                    out.append(("aws", REGION, t, "hour", "USD", Decimal(dim["pricePerUnit"]["USD"]), term["effectiveDate"], None,
                                f"aws-price-list-{str(d.get('publicationDate', ''))[:10] or 'current'}", "aws_price_list_on_demand"))
    return out


def collect() -> dict:
    ec2, cw = boto3.client("ec2", region_name=REGION), boto3.client("cloudwatch", region_name=REGION)
    from greenops.adapters.aws import metric_series
    types = {t["InstanceType"]: t for t in ec2.describe_instance_types(InstanceTypes=list(FAMILY))["InstanceTypes"]}
    inst = [i for r in ec2.describe_instances(Filters=[{"Name": "tag:Project", "Values": ["SuperOps"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}])["Reservations"] for i in r["Instances"]]
    inst = [i for i in inst if {t["Key"]: t["Value"] for t in i.get("Tags", [])}.get("Canary") != "true"]
    price_rows = prices()
    rate = {r[2]: r[5] for r in price_rows}
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    inv_rows, tel_rows, bill_rows = [], [], []
    for i in inst:
        tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
        it = types.get(i["InstanceType"]) or ec2.describe_instance_types(InstanceTypes=[i["InstanceType"]])["InstanceTypes"][0]
        mem_gib = Decimal(it["MemoryInfo"]["SizeInMiB"]) / 1024
        launched = i["LaunchTime"].astimezone(timezone.utc)
        inv_rows.append(("aws", REGION, i["InstanceId"], SERVICE, tags.get("Name", i["InstanceId"]), tags.get("Environment", "unknown"),
                         i["InstanceType"], it["VCpuInfo"]["DefaultVCpus"], mem_gib, REGION, "arm64" if i["Architecture"] == "arm64" else "x86_64",
                         False, False, False, int(tags.get("SuperOpsConfigVersion", "1")), tags.get("Role", ""), launched, None))
        start = max(launched, now - timedelta(hours=24))
        m = metric_series(REGION, i["InstanceId"], start, now)
        mem = {t.replace(second=0, microsecond=0): v for t, v in m["mem_bytes"]}
        hours: dict[datetime, int] = {}
        for t, cpu in m["cpu"]:
            t = t.replace(second=0, microsecond=0)
            mb = mem.get(t)
            tel_rows.append(("aws", REGION, i["InstanceId"], t, Decimal(str(round(cpu, 4))), int(mb) if mb is not None else None, None, None, None))
            h = t.replace(minute=0)
            hours[h] = hours.get(h, 0) + 1
        for h, n in sorted(hours.items()):
            frac = Decimal(min(n, 60)) / 60
            bill_rows.append((f"est-{i['InstanceId']}-{h:%Y%m%d%H}", "aws", REGION, i["InstanceId"], i["InstanceType"], h, h + timedelta(hours=1),
                              frac, "hour", (rate.get(i["InstanceType"], Decimal(0)) * frac).quantize(Decimal("0.000001")), "USD",
                              "estimated: observed running minutes × AWS Price List on-demand rate"))
    policy = (ROOT / "config" / "policies" / "superops-aws-pol-v1.json").read_text()
    with psycopg.connect(SRC) as c:
        c.execute("DELETE FROM public.inventory")
        c.cursor().executemany("INSERT INTO public.inventory VALUES (" + ",".join(["%s"] * 18) + ")", inv_rows)
        c.cursor().executemany("INSERT INTO public.telemetry VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (provider, project_id, resource_id, observed_at) "
                               "DO UPDATE SET cpu_percent=EXCLUDED.cpu_percent, memory_bytes=COALESCE(EXCLUDED.memory_bytes, public.telemetry.memory_bytes)", tel_rows)
        c.cursor().executemany("INSERT INTO public.billing VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (billing_record_id) "
                               "DO UPDATE SET usage_quantity=EXCLUDED.usage_quantity, cost=EXCLUDED.cost, sku=EXCLUDED.sku", bill_rows)
        c.execute("DELETE FROM ref.prices")
        c.cursor().executemany("INSERT INTO ref.prices VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", price_rows)
        c.execute("DELETE FROM ref.machine_types")
        c.cursor().executemany("INSERT INTO ref.machine_types VALUES (%s,%s,%s,%s,%s)",
                               [(t, "c7g", v["VCpuInfo"]["DefaultVCpus"], Decimal(v["MemoryInfo"]["SizeInMiB"]) / 1024, "arm64") for t, v in types.items()])
        c.execute("DELETE FROM ref.carbon_factors")
        c.execute("INSERT INTO ref.carbon_factors VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (REGION, Decimal("0.70"), Decimal("0.0035"), Decimal("0.0004"), True, "greenops-synthetic-ops-v1", "2026-10-01T00:00:00Z", None,
                   "illustrative_grid_average"))
        c.execute("DELETE FROM ref.model_prices")
        c.execute("INSERT INTO ref.policies VALUES (%s,%s,%s,%s,%s) ON CONFLICT (service_id, version) DO UPDATE SET document=EXCLUDED.document",
                  (SERVICE, "superops-aws-ops-policy", "pol-v1", "2026-10-27T00:00:00Z", policy))
    with psycopg.connect("postgresql://greenops@127.0.0.1:55432/greenops_src_cloud") as a, psycopg.connect(SRC) as c:
        rows = a.execute("SELECT * FROM ref.model_prices").fetchall()  # shared model rate card, copied so the AWS ref source is self-contained
        c.cursor().executemany("INSERT INTO ref.model_prices VALUES (%s,%s,%s,%s,%s,%s,%s)", rows)
    return {"instances": len(inv_rows), "telemetry_rows": len(tel_rows), "billing_rows": len(bill_rows), "prices": len(price_rows), "at": now.isoformat()}


def register() -> None:
    z = Zetaris()
    existing = {row[0] for row in z.run("SHOW DATASOURCES")["data"]}
    pw = local_env()["SRC_RO_PW"]
    for name, desc in (("aws_pg", "Source C host PostgreSQL - live AWS sandbox inventory, CloudWatch telemetry, estimated billing"),
                       ("aws_ref", "Source C host PostgreSQL - AWS Price List rates, instance types, policy, schema ref")):
        if name in existing:
            z.run(f"DROP DATASOURCE {name}")
        z.run(f'CREATE DATASOURCE {name} DESCRIBE BY "{desc}" OPTIONS (jdbcdriver "org.postgresql.Driver", '
              f'jdbcurl "jdbc:postgresql://host.docker.internal:55432/superops_src_aws", username "zetaris_ro", password "{pw}", fetchsize "1000")')
    z.run("REGISTER DATASOURCE TABLES FROM aws_pg")
    for t in ("prices", "machine_types", "model_prices", "carbon_factors", "policies"):
        z.run(f"CREATE DATASOURCE VIEW {t} FROM aws_ref AS SELECT * FROM ref.{t}")
    n = z.select("SELECT COUNT(*) AS n FROM aws_pg.inventory")[0]["n"]
    print(f"Zetaris: aws_pg.inventory {n} rows; aws_ref registered")


if __name__ == "__main__":
    ensure_db()
    print(json.dumps(collect()))
    if "--register" in sys.argv:
        register()
    every = int(os.environ.get("WATCH") or 0)
    while every:
        time.sleep(every)
        try:
            print(json.dumps(collect()), flush=True)
        except Exception as e:  # a failed collection leaves the last good data; investigations see its age via freshness
            print(json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"}), flush=True)
