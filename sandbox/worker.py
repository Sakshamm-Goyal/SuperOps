"""Synthetic support workload worker: the real local executable analogue (executor=local_analogue).

It loads a versioned `max_concurrency` config file, serves /work requests under that concurrency limit and
reports the exact config hash it actually loaded. It does NOT represent a GCP VM; it proves a real local
configuration change and its measured workload effect only.

    python sandbox/worker.py --worker-id local/sandbox/support-worker-stg --port 7520 --config var/sandbox/x/config.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class State:
    def __init__(self, worker_id: str, config_path: str):
        self.worker_id = worker_id
        self.config_path = config_path
        self.lock = threading.Lock()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.load()

    def load(self) -> None:
        raw = open(self.config_path, "rb").read()
        cfg = json.loads(raw)
        if cfg.get("worker_id") != self.worker_id:
            raise ValueError("config worker_id mismatch")
        mc = cfg["max_concurrency"]
        if not isinstance(mc, int) or not 1 <= mc <= 16:
            raise ValueError("max_concurrency out of range")
        with self.lock:
            self.config = cfg
            self.config_hash = "sha256:" + hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.sem = threading.BoundedSemaphore(mc)

    def status(self) -> dict:
        with self.lock:
            return {"worker_id": self.worker_id, "loaded_config": self.config, "loaded_config_hash": self.config_hash,
                    "loaded_version": self.config["version"], "pid": os.getpid(), "started_at": self.started_at}


def make_handler(state: State):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/status":
                return self._send(200, state.status())
            self._send(404, {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/reload":
                try:
                    state.load()
                except Exception as e:
                    return self._send(422, {"error": f"reload rejected: {e}", **state.status()})
                return self._send(200, state.status())
            if self.path == "/work":
                sem, h = state.sem, state.config_hash
                if not sem.acquire(timeout=1.0):
                    return self._send(503, {"error": "concurrency limit; request timed out waiting"})
                try:
                    time.sleep(max(0, min(2000, int(body.get("service_ms", 60)))) / 1000)
                finally:
                    sem.release()
                return self._send(200, {"request_id": body.get("request_id"), "config_hash": h})
            self._send(404, {"error": "not found"})

    return H


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    state = State(a.worker_id, a.config)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(state))
    srv.daemon_threads = True
    srv.serve_forever()


if __name__ == "__main__":
    main()
