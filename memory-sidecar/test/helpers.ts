// Test helpers: a deterministic fake OpenAI-compatible embedding server (CONTRACT testing
// only; bag-of-words vectors are not semantic evidence) and a real sidecar child process.

import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const TOKEN = "test-token-0123456789abcdef";

export interface FakeEmbedder {
  url: string;
  requests: Array<Record<string, unknown>>;
  setFailing(failing: boolean): void;
  /** Malformed-response modes for validation tests. */
  setMode(mode: "ok" | "nan" | "short" | "zero" | "misorder" | "dims" | "notjson"): void;
  close(): Promise<void>;
}

function fnv(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export function bagOfWords(text: string, dims: number): number[] {
  const v = new Array<number>(dims).fill(0);
  for (const tok of text.toLowerCase().match(/[a-z0-9]+/g) ?? []) v[fnv(tok) % dims] += 1;
  if (v.every((x) => x === 0)) v[0] = 1;
  return v;
}

export async function startFakeEmbedder(dims = 32): Promise<FakeEmbedder> {
  const requests: Array<Record<string, unknown>> = [];
  let failing = false;
  let mode = "ok";
  const server = http.createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf-8")) as { input: string[]; model: string };
      requests.push({ ...body, authorization: req.headers.authorization ?? null, path: req.url });
      if (failing || req.url !== "/v1/embeddings") {
        res.writeHead(failing ? 503 : 404, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "unavailable" }));
        return;
      }
      res.writeHead(200, { "content-type": "application/json" });
      if (mode === "notjson") { res.end("<html>"); return; }
      if (mode !== "ok") {
        const vec = (t: string): unknown[] =>
          mode === "nan" ? [Number.NaN, ...bagOfWords(t, dims - 1)].map((x) => (Number.isNaN(x) ? "NaN" : x))
          : mode === "zero" ? new Array(dims).fill(0)
          : mode === "dims" ? bagOfWords(t, dims + 8)
          : bagOfWords(t, dims);
        const data = mode === "short" ? [] : body.input.map((t, index) => ({ index: mode === "misorder" ? index + 1 : index, embedding: vec(t) }));
        res.end(JSON.stringify({ data }));
        return;
      }
      res.end(JSON.stringify({
        object: "list",
        model: body.model,
        data: body.input.map((t, index) => ({ object: "embedding", index, embedding: bagOfWords(t, dims) })),
        usage: { prompt_tokens: 1, total_tokens: 1 },
      }));
    });
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const addr = server.address() as { port: number };
  return {
    url: `http://127.0.0.1:${addr.port}/v1`,
    requests,
    setFailing: (f) => { failing = f; },
    setMode: (m) => { mode = m; },
    close: () => new Promise<void>((r) => { server.closeAllConnections(); server.close(() => r()); }),
  };
}

export function tempDataDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "greenops-hmem-test-"));
}

export interface Sidecar {
  url: string;
  proc: ChildProcess;
  stdout: () => string;
  stop(): Promise<number | null>;
  req(method: string, p: string, body?: unknown, opts?: { token?: string | null; raw?: string; contentType?: string }): Promise<{ status: number; body: any }>;
}

export async function startSidecar(env: Record<string, string>): Promise<Sidecar> {
  const proc = spawn(process.execPath, ["--experimental-transform-types", "--no-warnings", "src/server.ts"], {
    cwd: root,
    env: { PATH: process.env.PATH ?? "", MEMORY_AUTH_TOKEN: TOKEN, PORT: "0", HOST: "127.0.0.1", ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let out = "";
  let err = "";
  proc.stdout!.on("data", (d: Buffer) => { out += d.toString(); });
  proc.stderr!.on("data", (d: Buffer) => { err += d.toString(); });
  const port = await new Promise<number>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`sidecar did not start: ${err}`)), 15000);
    const check = () => {
      for (const line of out.split("\n")) {
        if (!line.trim()) continue;
        try {
          const j = JSON.parse(line) as { event?: string; port?: number };
          if (j.event === "listening" && j.port) {
            clearTimeout(timer);
            resolve(j.port);
            return;
          }
        } catch { /* partial line */ }
      }
    };
    proc.stdout!.on("data", check);
    proc.on("exit", (code) => { clearTimeout(timer); reject(new Error(`sidecar exited ${code}: ${err}`)); });
  });
  const url = `http://127.0.0.1:${port}`;
  return {
    url,
    proc,
    stdout: () => out,
    stop: () => new Promise<number | null>((resolve) => {
      if (proc.exitCode !== null) return resolve(proc.exitCode);
      proc.removeAllListeners("exit");
      proc.on("exit", (code) => resolve(code));
      proc.kill("SIGTERM");
    }),
    async req(method, p, body, opts = {}) {
      const headers: Record<string, string> = {};
      const token = opts.token === undefined ? TOKEN : opts.token;
      if (token !== null) headers.authorization = `Bearer ${token}`;
      let payload: string | undefined;
      if (opts.raw !== undefined) payload = opts.raw;
      else if (body !== undefined) payload = JSON.stringify(body);
      if (payload !== undefined) headers["content-type"] = opts.contentType ?? "application/json";
      const res = await fetch(url + p, { method, headers, body: payload });
      const text = await res.text();
      return { status: res.status, body: text ? JSON.parse(text) : null };
    },
  };
}

export function contractEnv(dataDir: string, fake: FakeEmbedder, model = "fake-bow-32"): Record<string, string> {
  return {
    HMEM_DATA_DIR: dataDir,
    EMBEDDING_MODE: "openai_compatible",
    EMBEDDING_BASE_URL: fake.url,
    EMBEDDING_MODEL_ID: model,
    EMBEDDING_API_KEY: "fake-key",
    EMBEDDING_TIMEOUT_MS: "3000",
  };
}

export const APPLICABILITY = {
  policy_version: "policy-v1",
  workload_version: "workload-v1",
  config_version: "config-v1",
  model_version: null,
  test_version: null,
};

export function rememberBody(over: Record<string, unknown> = {}): Record<string, any> {
  const finding = (over.finding as string) ?? "Rightsizing checkout-api from m5.xlarge to m5.large failed the p95 latency trial under peak load";
  const id = (over.application_receipt_id as string) ?? crypto.randomUUID();
  return {
    application_receipt_id: id,
    kind: "rejected_trial",
    scope: { tenant_id: "tenant-a", service_id: "checkout", target_id: "i-0abc" },
    finding,
    evidence_refs: ["trial:run-17", "metric:p95"],
    applicability: { ...APPLICABILITY },
    content_hash: `sha256:${crypto.createHash("sha256").update(id + finding).digest("hex")}`,
    ...over,
  };
}

export function recallBody(over: Record<string, unknown> = {}): Record<string, any> {
  return {
    scope: { tenant_id: "tenant-a", service_id: "checkout" },
    query: "did rightsizing checkout-api to m5.large fail the latency trial",
    applicability: { ...APPLICABILITY },
    top_k: 5,
    threshold: 0,
    ...over,
  };
}

export function snapshotFiles(dir: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of fs.readdirSync(dir)) out[f] = fs.readFileSync(path.join(dir, f), "utf-8");
  return out;
}
