"""Local sandbox executor adapter: compare-and-set config writes, reload, read-back and matched workload runs."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

from greenops.config import ROOT

REGISTRY = json.loads((ROOT / "config" / "sandbox.json").read_text())
WORKLOAD_PATH = ROOT / "sandbox" / "workload-v1.json"


class VersionConflict(Exception):
    """Target changed since it was read: never overwrite an intervening change."""


class TargetUnavailable(Exception):
    pass


class SandboxOwnershipError(TargetUnavailable):
    """A responsive worker on the expected port serves a different config file/sandbox (audit A22): never adopt it."""


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def config_hash(cfg: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _slug(target_id: str) -> str:
    return target_id.replace("/", "__")


@dataclass(frozen=True)
class ConfigStore:
    """Versioned JSON config file with an exclusive lock for compare-and-set."""
    sandbox_dir: Path
    target_id: str

    @property
    def path(self) -> Path:
        return self.sandbox_dir / _slug(self.target_id) / "config.json"

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(".lock"), "a+b") as lf:
            if os.name == "posix":
                import fcntl
                fcntl.flock(lf, fcntl.LOCK_EX)
                yield
            else:
                import msvcrt
                if lf.seek(0, os.SEEK_END) == 0:
                    lf.write(b"\0")
                    lf.flush()
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lf.seek(0)
                    msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)

    def read(self) -> dict:
        if not self.path.exists():
            raise TargetUnavailable(f"{self.target_id} has no config")
        return json.loads(self.path.read_text())

    def _write(self, cfg: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            f.write(json.dumps(cfg, sort_keys=True, indent=1))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def init(self, cfg: dict, force: bool = False) -> dict:
        with self._locked():
            if self.path.exists() and not force:
                return self.read()
            self._write(cfg)
            return cfg

    def compare_and_set(self, expected_version: int, changes: dict, writer: str = "unknown") -> dict:
        """Atomic CAS. `writer` is the operation identity stored with the version (audit A01): reconciliation and
        recovery only treat a version as their own when its writer matches; unknown writers are never ours."""
        with self._locked():
            cur = self.read()
            if cur["version"] != expected_version:
                raise VersionConflict(f"{self.target_id} is at version {cur['version']}, expected {expected_version}")
            new = {**cur, **changes, "version": cur["version"] + 1, "writer": writer}
            self._write(new)
            return new


class LocalWorker:
    def __init__(self, sandbox_dir: Path, target_id: str):
        spec = REGISTRY["workers"].get(target_id)
        if spec is None:
            raise TargetUnavailable(f"unknown local worker {target_id}")
        self.target_id, self.port, self.spec = target_id, spec["port"] + int(os.environ.get("SANDBOX_PORT_OFFSET", "0")), spec
        self.store = ConfigStore(sandbox_dir, target_id)
        self.url = f"http://127.0.0.1:{self.port}"

    def _owned(self, st: dict) -> dict:
        served = st.get("config_path")
        if st.get("worker_id") != self.target_id or not served or os.path.realpath(served) != os.path.realpath(self.store.path):
            raise SandboxOwnershipError(f"port {self.port} serves {st.get('worker_id')} from {served}, not {self.store.path}")
        return st

    def status(self) -> dict:
        try:
            r = httpx.get(self.url + "/status", timeout=3)
            r.raise_for_status()
            st = r.json()
        except httpx.HTTPError as e:
            raise TargetUnavailable(f"{self.target_id} status unreachable: {type(e).__name__}")
        return self._owned(st)

    def reload(self) -> dict:
        try:
            r = httpx.post(self.url + "/reload", timeout=5)
        except httpx.HTTPError as e:
            raise TargetUnavailable(f"{self.target_id} reload unreachable: {type(e).__name__}")
        if r.status_code != 200:
            raise TargetUnavailable(f"{self.target_id} rejected reload: {r.text[:200]}")
        return self._owned(r.json())


def load_workload() -> tuple[dict, str]:
    return json.loads(WORKLOAD_PATH.read_text()), file_hash(WORKLOAD_PATH)


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


async def _run(url: str, workload: dict, duration_s: float, label: str) -> dict:
    rng = random.Random(f"{workload['seed']}-{label}")
    interval = 1.0 / workload["rate_per_s"]
    n = int(duration_s * workload["rate_per_s"])
    lat, failures, hashes, lag, svc, queue, server = [], 0, set(), [], [], [], []
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    async with httpx.AsyncClient(timeout=workload["request_timeout_s"], limits=limits) as client:
        t0 = time.perf_counter()

        async def one(i: int):
            nonlocal failures
            due = t0 + i * interval + rng.uniform(0, workload["jitter_ms"]) / 1000
            await asyncio.sleep(max(0.0, due - time.perf_counter()))
            s = time.perf_counter()
            lag.append((s - due) * 1000)  # load-generator schedule lag: offered load fidelity
            try:
                r = await client.post(url + "/work", json={"request_id": f"{label}-{i}", "service_ms": workload["service_ms"]})
                if r.status_code != 200:
                    failures += 1
                    return
                body = r.json()
                hashes.add(body.get("config_hash"))
                lat.append((time.perf_counter() - s) * 1000)
                if body.get("service_ms") is not None:
                    svc.append(body["service_ms"])
                    queue.append(body["queue_ms"])
                    server.append(body["queue_ms"] + body["service_ms"])
            except httpx.HTTPError:
                failures += 1

        await asyncio.gather(*(one(i) for i in range(n)))
    return {"offered": n, "completed": len(lat), "failures": failures, "p50_ms": _pct(lat, 0.50), "p95_ms": _pct(lat, 0.95),
            "max_ms": max(lat) if lat else None, "config_hashes_seen": sorted(h for h in hashes if h), "latencies_ms": lat,
            "schedule_lag_p95_ms": _pct(lag, 0.95), "schedule_lag_max_ms": max(lag) if lag else None,
            "service_p95_ms": _pct(svc, 0.95), "queue_p95_ms": _pct(queue, 0.95), "nominal_service_ms": workload["service_ms"],
            "server_p95_ms": _pct(server, 0.95), "server_latencies_ms": server}


def run_workload(worker: LocalWorker, duration_s: float, label: str) -> dict:
    workload, _ = load_workload()
    return asyncio.run(_run(worker.url, workload, duration_s, label))


# ---- process management (scripts/sandbox.py) ------------------------------------

def pid_file(sandbox_dir: Path, target_id: str) -> Path:
    return sandbox_dir / _slug(target_id) / "worker.pid"


def start_workers(sandbox_dir: Path) -> list[str]:
    started = []
    for tid, spec in REGISTRY["workers"].items():
        w = LocalWorker(sandbox_dir, tid)
        w.store.init({"worker_id": tid, "version": 1, "max_concurrency": spec["initial_max_concurrency"], "writer": "init"})
        try:
            w.status()  # raises SandboxOwnershipError if the port belongs to another sandbox directory
            continue  # already running, and owned by this sandbox
        except SandboxOwnershipError:
            raise
        except TargetUnavailable:
            pass
        log = open(w.store.path.parent / "worker.log", "a")
        p = subprocess.Popen([sys.executable, str(ROOT / "sandbox" / "worker.py"), "--worker-id", tid, "--port", str(w.port),
                              "--config", str(w.store.path)], stdout=log, stderr=log, start_new_session=True)
        pid_file(sandbox_dir, tid).write_text(str(p.pid))
        started.append(tid)
    for tid in REGISTRY["workers"]:
        for _ in range(50):
            try:
                LocalWorker(sandbox_dir, tid).status()
                break
            except SandboxOwnershipError:
                raise
            except TargetUnavailable:
                time.sleep(0.1)
    for tid, spec in REGISTRY["ai_workflows"].items():
        ConfigStore(sandbox_dir, tid).init({"workflow_id": spec["workflow_id"], "version": 1, "config": spec["initial_config"], "writer": "init"})
    return started


def stop_workers(sandbox_dir: Path) -> list[str]:
    stopped = []
    for tid in REGISTRY["workers"]:
        pf = pid_file(sandbox_dir, tid)
        if pf.exists():
            try:
                os.kill(int(pf.read_text()), signal.SIGTERM)
                stopped.append(tid)
            except ProcessLookupError:
                pass
            pf.unlink()
    return stopped
