"""AWS adapter: a real EC2 instance as a versioned change target, CloudWatch measurement and canary trials.

The instance carries its own change ledger in tags, so the executor's existing contract holds on real AWS:
  SuperOpsConfigVersion  integer, +1 per applied change (compare-and-set precondition)
  SuperOpsWriter         operation identity of the last write (action:<id> or recovery:<id>)
compare_and_set = check version → stop → wait stopped → modify instance type → tag version+1/writer → start → wait running.
A failure part-way raises TargetUnavailable; the executor then reconciles from the instance's actual state and never
repeats the write blindly. Credentials come from the operator's environment, never from a request or an agent.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from greenops.adapters.sandbox import TargetUnavailable, VersionConflict

VERSION_TAG, WRITER_TAG = "SuperOpsConfigVersion", "SuperOpsWriter"


def parse_key(resource_key: str) -> tuple[str, str]:
    provider, region, instance_id = resource_key.split("/")
    if provider != "aws":
        raise ValueError(f"not an AWS resource key: {resource_key}")
    return region, instance_id


def _ec2(region: str):
    return boto3.client("ec2", region_name=region)


class AwsInstanceStore:
    """Same read/compare_and_set contract as the local ConfigStore, backed by a real EC2 instance."""

    def __init__(self, resource_key: str, wait_s: int = 600):
        self.key = resource_key
        self.region, self.instance_id = parse_key(resource_key)
        self.wait_s = wait_s

    def read(self) -> dict:
        try:
            i = _ec2(self.region).describe_instances(InstanceIds=[self.instance_id])["Reservations"][0]["Instances"][0]
        except (ClientError, BotoCoreError, IndexError) as e:
            raise TargetUnavailable(f"{self.key} unreadable: {type(e).__name__}")
        tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
        return {"version": int(tags.get(VERSION_TAG, "1")), "instance_type": i["InstanceType"], "writer": tags.get(WRITER_TAG),
                "state": i["State"]["Name"], "instance_id": self.instance_id, "region": self.region}

    def _wait(self, waiter: str) -> None:
        _ec2(self.region).get_waiter(waiter).wait(InstanceIds=[self.instance_id],
                                                  WaiterConfig={"Delay": 5, "MaxAttempts": max(1, self.wait_s // 5)})

    def compare_and_set(self, expected_version: int, change: dict, writer: str) -> dict:
        cur = self.read()
        if cur["version"] != expected_version:
            raise VersionConflict(f"{self.key} is at config version {cur['version']}, expected {expected_version}")
        ec2 = _ec2(self.region)
        t0 = time.time()
        try:
            if cur["state"] != "stopped":
                ec2.stop_instances(InstanceIds=[self.instance_id])
                self._wait("instance_stopped")
            ec2.modify_instance_attribute(InstanceId=self.instance_id, InstanceType={"Value": change["instance_type"]})
            ec2.create_tags(Resources=[self.instance_id], Tags=[{"Key": VERSION_TAG, "Value": str(expected_version + 1)},
                                                                 {"Key": WRITER_TAG, "Value": writer}])
            ec2.start_instances(InstanceIds=[self.instance_id])
            self._wait("instance_running")
        except (ClientError, BotoCoreError) as e:
            raise TargetUnavailable(f"{self.key} change interrupted: {type(e).__name__}: {str(e)[:160]}")
        return {**self.read(), "downtime_seconds": round(time.time() - t0)}  # stop → running, as measured by this write


# ---- measurement --------------------------------------------------------------------------

def metric_series(region: str, instance_id: str, start: datetime, end: datetime, period: int = 60) -> dict[str, list]:
    """1-minute CPUUtilization (AWS/EC2, detailed monitoring) and mem_used / mem_used_percent (CWAgent)."""
    cw = boto3.client("cloudwatch", region_name=region)
    dims = [{"Name": "InstanceId", "Value": instance_id}]
    q = lambda qid, ns, name, stat: {"Id": qid, "MetricStat": {"Metric": {"Namespace": ns, "MetricName": name, "Dimensions": dims},
                                                                "Period": period, "Stat": stat}, "ReturnData": True}
    out: dict[str, list] = {"cpu": [], "cpu_max": [], "mem_bytes": [], "mem_pct": []}
    token = None
    while True:
        kw = {"MetricDataQueries": [q("cpu", "AWS/EC2", "CPUUtilization", "Average"), q("cpu_max", "AWS/EC2", "CPUUtilization", "Maximum"),
                                    q("mem_bytes", "CWAgent", "mem_used", "Average"), q("mem_pct", "CWAgent", "mem_used_percent", "Average")],
              "StartTime": start, "EndTime": end, "ScanBy": "TimestampAscending"}
        if token:
            kw["NextToken"] = token
        r = cw.get_metric_data(**kw)
        for res in r["MetricDataResults"]:
            out[res["Id"]] += list(zip(res["Timestamps"], res["Values"]))
        token = r.get("NextToken")
        if not token:
            return out


def status_ok(region: str, instance_id: str) -> bool:
    s = _ec2(region).describe_instance_status(InstanceIds=[instance_id])["InstanceStatuses"]
    return bool(s) and s[0]["InstanceStatus"]["Status"] == "ok" and s[0]["SystemStatus"]["Status"] == "ok"


def wait_measured(region: str, instance_id: str, since: datetime, min_points: int, max_wait_s: int) -> dict[str, list]:
    """Poll CloudWatch until `min_points` CPU datapoints after `since` exist (or the wait expires)."""
    end = time.time() + max_wait_s
    while datetime.now(timezone.utc) < since + timedelta(minutes=1):  # the window may open in the future (boot exclusion)
        time.sleep(15)
    while True:
        m = metric_series(region, instance_id, since, datetime.now(timezone.utc) + timedelta(minutes=1))
        if len(m["cpu"]) >= min_points or time.time() > end:
            return m
        time.sleep(30)


# ---- canary trial -------------------------------------------------------------------------

def launch_canary(target_key: str, candidate_type: str, minutes: int) -> str:
    """A disposable clone of the target's workload on the candidate type, in the same subnet and role.
    It stops itself after `minutes` + 20 even if this process dies."""
    from scripts.aws_sandbox import INSTANCES, user_data  # the sandbox workload definitions are the single source
    region, instance_id = parse_key(target_key)
    ec2 = _ec2(region)
    src = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0]
    tags = {t["Key"]: t["Value"] for t in src.get("Tags", [])}
    spec = next(s for s in INSTANCES if s["name"] == tags.get("Name"))
    deadline = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=minutes + 20)
    r = ec2.run_instances(ImageId=src["ImageId"], InstanceType=candidate_type, MinCount=1, MaxCount=1, SubnetId=src["SubnetId"],
                          SecurityGroupIds=[g["GroupId"] for g in src["SecurityGroups"]],
                          IamInstanceProfile={"Arn": src["IamInstanceProfile"]["Arn"]}, Monitoring={"Enabled": True},
                          InstanceInitiatedShutdownBehavior="terminate", MetadataOptions={"HttpTokens": "required"},
                          UserData=user_data(spec, deadline),
                          TagSpecifications=[{"ResourceType": "instance", "Tags": [
                              {"Key": "Project", "Value": "SuperOps"}, {"Key": "Name", "Value": f"{spec['name']}-canary"},
                              {"Key": "Canary", "Value": "true"}, {"Key": "CanaryOf", "Value": instance_id},
                              {"Key": "ExpiresAt", "Value": deadline.isoformat()}]}])
    return r["Instances"][0]["InstanceId"]


def terminate(region: str, instance_id: str) -> None:
    try:
        _ec2(region).terminate_instances(InstanceIds=[instance_id])
    except (ClientError, BotoCoreError):
        pass
