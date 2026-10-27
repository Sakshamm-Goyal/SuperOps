"""Operator command: a dedicated, self-expiring AWS sandbox for the SuperOps live demo (never touches existing resources).

    make aws-up        # create (idempotent): VPC, subnet, IGW, SG (no inbound), IAM role, 3 Graviton EC2 with workloads
    make aws-status    # list sandbox instances
    make aws-down      # terminate instances and delete everything tagged Project=SuperOps

Every resource is created new and tagged Project=SuperOps. Cost guard by construction: each instance schedules its own
shutdown at a fixed deadline (re-armed after every reboot or resize), instance-initiated shutdown = stop, so compute
spend is bounded (~3 instances × 30 h). An account budget of 30 USD is created for visibility.

Workloads use absolute vCPU (not percent), so the same load can be measured before and after a resize:
  superops-api-01     c7g.xlarge  prod     spiky: ~0.4 vCPU, 3-minute spikes to ~3.4 vCPU every 20 minutes
  superops-worker-01  c7g.xlarge  staging  steady: ~1.0-1.25 vCPU  (the safe downsize to c7g.large)
  superops-batch-01   c7g.large   prod     steady ~0.3 vCPU, under a change freeze (policy refusal)
"""
from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import boto3

REGION = "ap-south-1"
TAG = {"Key": "Project", "Value": "SuperOps"}
ROLE = "SuperOpsSandboxEc2Role"
DEADLINE_HOURS = 30
INSTANCES = [
    {"name": "superops-api-01", "type": "c7g.xlarge", "env": "prod", "role": "api", "freeze": "false", "profile": "spiky", "mem_mb": 2500},
    {"name": "superops-worker-01", "type": "c7g.xlarge", "env": "staging", "role": "worker", "freeze": "false", "profile": "steady", "mem_mb": 2200},
    {"name": "superops-batch-01", "type": "c7g.large", "env": "prod", "role": "batch", "freeze": "true", "profile": "low", "mem_mb": 1200},
]

WORKLOAD = r'''#!/usr/bin/env python3
"""SuperOps sandbox workload: burns an absolute number of vCPUs on a schedule and holds a fixed amount of memory."""
import math, multiprocessing as mp, os, sys, time
profile, mem_mb = sys.argv[1], int(sys.argv[2])
hold = bytearray(mem_mb * 1024 * 1024)
for i in range(0, len(hold), 4096):
    hold[i] = 1
def target(t):
    m = (t / 60.0) % 20
    if profile == "spiky":
        return 3.4 if m < 3 else 0.4
    if profile == "steady":
        return 1.0 + 0.25 * (0.5 + 0.5 * math.sin(t / 900.0))
    return 0.3
def worker(idx, shared):
    while True:
        frac = max(0.0, min(1.0, shared.value - idx))
        start = time.time()
        while time.time() - start < 0.1 * frac:
            pass
        time.sleep(0.1 * (1 - frac) + 0.0001)
if __name__ == "__main__":
    shared = mp.Value("d", 0.0, lock=False)
    for i in range(int(math.ceil(3.5))):
        mp.Process(target=worker, args=(i, shared), daemon=True).start()
    while True:
        shared.value = target(time.time())
        time.sleep(5)
'''


def user_data(spec: dict, deadline: datetime) -> str:
    cw = {"agent": {"metrics_collection_interval": 60},
          "metrics": {"namespace": "CWAgent", "append_dimensions": {"InstanceId": "${aws:InstanceId}"},
                      "metrics_collected": {"mem": {"measurement": ["mem_used_percent", "mem_used"]}}}}
    return f"""#!/bin/bash
set -eux
mkdir -p /etc/superops
echo '{deadline.isoformat()}' > /etc/superops/deadline
cat > /usr/local/bin/superops-workload.py <<'PY'
{WORKLOAD}
PY
chmod +x /usr/local/bin/superops-workload.py
cat > /usr/local/bin/superops-expire.sh <<'SH'
#!/bin/bash
# re-arm the self-shutdown at the fixed deadline on every boot (survives resizes)
left=$(( ($(date -d "$(cat /etc/superops/deadline)" +%s) - $(date +%s)) / 60 ))
if [ "$left" -le 1 ]; then shutdown -h now; else shutdown -h +$left; fi
SH
chmod +x /usr/local/bin/superops-expire.sh
cat > /etc/systemd/system/superops-workload.service <<UNIT
[Unit]
Description=SuperOps sandbox workload
[Service]
ExecStartPre=/usr/local/bin/superops-expire.sh
ExecStart=/usr/bin/python3 /usr/local/bin/superops-workload.py {spec['profile']} {spec['mem_mb']}
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now superops-workload.service
dnf install -y amazon-cloudwatch-agent || true
cat > /opt/aws/amazon-cloudwatch-agent/etc/superops.json <<'CW'
{json.dumps(cw)}
CW
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/superops.json || true
"""


def tags(name: str, extra: dict | None = None) -> list:
    return [TAG, {"Key": "Name", "Value": name}] + [{"Key": k, "Value": v} for k, v in (extra or {}).items()]


def find(ec2, kind: str, name: str):
    f = [{"Name": "tag:Project", "Values": ["SuperOps"]}, {"Name": "tag:Name", "Values": [name]}]
    return {"vpc": lambda: ec2.describe_vpcs(Filters=f)["Vpcs"], "subnet": lambda: ec2.describe_subnets(Filters=f)["Subnets"],
            "igw": lambda: ec2.describe_internet_gateways(Filters=f)["InternetGateways"],
            "rt": lambda: ec2.describe_route_tables(Filters=f)["RouteTables"],
            "sg": lambda: ec2.describe_security_groups(Filters=f)["SecurityGroups"]}[kind]()


def ensure_role(iam) -> str:
    try:
        iam.get_role(RoleName=ROLE)
    except iam.exceptions.NoSuchEntityException:
        iam.create_role(RoleName=ROLE, Tags=[TAG], AssumeRolePolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}))
        for arn in ("arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy", "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"):
            iam.attach_role_policy(RoleName=ROLE, PolicyArn=arn)
    try:
        iam.get_instance_profile(InstanceProfileName=ROLE)
    except iam.exceptions.NoSuchEntityException:
        iam.create_instance_profile(InstanceProfileName=ROLE, Tags=[TAG])
        iam.add_role_to_instance_profile(InstanceProfileName=ROLE, RoleName=ROLE)
        time.sleep(12)  # instance profile propagation
    return ROLE


def up() -> None:
    ec2, iam, ssm = (boto3.client(s, region_name=REGION) for s in ("ec2", "iam", "ssm"))
    vpc = (find(ec2, "vpc", "superops-sandbox") or [None])[0]
    if not vpc:
        vpc = ec2.create_vpc(CidrBlock="10.42.0.0/16", TagSpecifications=[{"ResourceType": "vpc", "Tags": tags("superops-sandbox")}])["Vpc"]
        ec2.modify_vpc_attribute(VpcId=vpc["VpcId"], EnableDnsHostnames={"Value": True})
    vid = vpc["VpcId"]
    igw = (find(ec2, "igw", "superops-sandbox") or [None])[0]
    if not igw:
        igw = ec2.create_internet_gateway(TagSpecifications=[{"ResourceType": "internet-gateway", "Tags": tags("superops-sandbox")}])["InternetGateway"]
        ec2.attach_internet_gateway(InternetGatewayId=igw["InternetGatewayId"], VpcId=vid)
    sub = (find(ec2, "subnet", "superops-sandbox-a") or [None])[0]
    if not sub:
        sub = ec2.create_subnet(VpcId=vid, CidrBlock="10.42.1.0/24", AvailabilityZone=f"{REGION}a",
                                TagSpecifications=[{"ResourceType": "subnet", "Tags": tags("superops-sandbox-a")}])["Subnet"]
        ec2.modify_subnet_attribute(SubnetId=sub["SubnetId"], MapPublicIpOnLaunch={"Value": True})
    if not find(ec2, "rt", "superops-sandbox"):
        rt = ec2.create_route_table(VpcId=vid, TagSpecifications=[{"ResourceType": "route-table", "Tags": tags("superops-sandbox")}])["RouteTable"]
        ec2.create_route(RouteTableId=rt["RouteTableId"], DestinationCidrBlock="0.0.0.0/0", GatewayId=igw["InternetGatewayId"])
        ec2.associate_route_table(RouteTableId=rt["RouteTableId"], SubnetId=sub["SubnetId"])
    sg = (find(ec2, "sg", "superops-sandbox") or [None])[0]
    if not sg:  # no ingress rules at all; egress default (package install, CloudWatch, SSM)
        sg = {"GroupId": ec2.create_security_group(GroupName="superops-sandbox", Description="SuperOps sandbox: no inbound", VpcId=vid,
                                                   TagSpecifications=[{"ResourceType": "security-group", "Tags": tags("superops-sandbox")}])["GroupId"]}
    profile = ensure_role(iam)
    ami = ssm.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64")["Parameter"]["Value"]
    deadline = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=DEADLINE_HOURS)
    existing = {t["Value"] for r in ec2.describe_instances(Filters=[{"Name": "tag:Project", "Values": ["SuperOps"]},
                {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}])["Reservations"]
                for i in r["Instances"] for t in i.get("Tags", []) if t["Key"] == "Name"}
    for spec in INSTANCES:
        if spec["name"] in existing:
            print("exists", spec["name"]); continue
        for attempt in range(3):
            try:
                r = ec2.run_instances(ImageId=ami, InstanceType=spec["type"], MinCount=1, MaxCount=1, SubnetId=sub["SubnetId"],
                                      SecurityGroupIds=[sg["GroupId"]], IamInstanceProfile={"Name": profile}, Monitoring={"Enabled": True},
                                      InstanceInitiatedShutdownBehavior="stop", MetadataOptions={"HttpTokens": "required"},
                                      UserData=user_data(spec, deadline),
                                      BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 8, "VolumeType": "gp3", "DeleteOnTermination": True}}],
                                      TagSpecifications=[{"ResourceType": rt_, "Tags": tags(spec["name"], {
                                          "Service": "superops-aws", "Environment": spec["env"], "Role": spec["role"], "ChangeFreeze": spec["freeze"],
                                          "ExpiresAt": deadline.isoformat()})} for rt_ in ("instance", "volume")])
                print("launched", spec["name"], r["Instances"][0]["InstanceId"], spec["type"]); break
            except ec2.exceptions.ClientError as e:
                if "InvalidParameterValue" in str(e) and "iamInstanceProfile" in str(e) and attempt < 2:
                    time.sleep(10); continue
                raise
    try:
        acct = boto3.client("sts").get_caller_identity()["Account"]
        boto3.client("budgets", region_name="us-east-1").create_budget(AccountId=acct, Budget={
            "BudgetName": "SuperOps-sandbox-30usd", "BudgetLimit": {"Amount": "30", "Unit": "USD"}, "TimeUnit": "MONTHLY", "BudgetType": "COST"})
        print("budget SuperOps-sandbox-30usd created")
    except Exception as e:
        print("budget:", type(e).__name__)
    print("deadline", deadline.isoformat())


def status() -> list:
    ec2 = boto3.client("ec2", region_name=REGION)
    out = []
    for r in ec2.describe_instances(Filters=[{"Name": "tag:Project", "Values": ["SuperOps"]}])["Reservations"]:
        for i in r["Instances"]:
            t = {x["Key"]: x["Value"] for x in i.get("Tags", [])}
            out.append({"name": t.get("Name"), "id": i["InstanceId"], "type": i["InstanceType"], "state": i["State"]["Name"],
                        "env": t.get("Environment"), "expires": t.get("ExpiresAt")})
    return out


def down() -> None:
    ec2, iam = boto3.client("ec2", region_name=REGION), boto3.client("iam")
    ids = [i["id"] for i in status() if i["state"] != "terminated"]
    if ids:
        ec2.terminate_instances(InstanceIds=ids)
        ec2.get_waiter("instance_terminated").wait(InstanceIds=ids)
    for sg in find(ec2, "sg", "superops-sandbox"):
        ec2.delete_security_group(GroupId=sg["GroupId"])
    for sub in find(ec2, "subnet", "superops-sandbox-a"):
        ec2.delete_subnet(SubnetId=sub["SubnetId"])
    for rt in find(ec2, "rt", "superops-sandbox"):
        for a in rt.get("Associations", []):
            if not a.get("Main"):
                ec2.disassociate_route_table(AssociationId=a["RouteTableAssociationId"])
        ec2.delete_route_table(RouteTableId=rt["RouteTableId"])
    for vpc in find(ec2, "vpc", "superops-sandbox"):
        for igw in find(ec2, "igw", "superops-sandbox"):
            ec2.detach_internet_gateway(InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc["VpcId"])
            ec2.delete_internet_gateway(InternetGatewayId=igw["InternetGatewayId"])
        ec2.delete_vpc(VpcId=vpc["VpcId"])
    try:
        iam.remove_role_from_instance_profile(InstanceProfileName=ROLE, RoleName=ROLE)
        iam.delete_instance_profile(InstanceProfileName=ROLE)
        for p in iam.list_attached_role_policies(RoleName=ROLE)["AttachedPolicies"]:
            iam.detach_role_policy(RoleName=ROLE, PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=ROLE)
    except iam.exceptions.NoSuchEntityException:
        pass
    print("sandbox removed")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"up": up, "down": down, "status": lambda: print(json.dumps(status(), indent=1))}[cmd]()
