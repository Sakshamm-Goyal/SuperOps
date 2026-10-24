// GreenOps private H-MEM memory sidecar (node:http, zero runtime dependencies).
// These routes are GreenOps' own private contract, not a Meterless API. Run on a private
// network only; every route requires the service bearer token.

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ConfigError, loadConfig } from "./config.ts";
import { EmbeddingClient } from "./embedding.ts";
import { MemoryService, ServiceError } from "./memoryService.ts";
import { SerialQueue, tokenMatches } from "./util.ts";
import { ValidationError, parseEmptyBody, parseRecall, parseRemember, scopeId, uuid } from "./validation.ts";

const BODY_LIMIT = 64 * 1024;
const here = path.dirname(fileURLToPath(import.meta.url));

function log(event: string, fields: Record<string, unknown> = {}): void {
  process.stdout.write(JSON.stringify({ ts: new Date().toISOString(), event, ...fields }) + "\n");
}

function readManifestSha(): string | null {
  try {
    const m = JSON.parse(fs.readFileSync(path.join(here, "..", "reference-manifest.json"), "utf-8")) as { sha?: string };
    return typeof m.sha === "string" ? m.sha : null;
  } catch {
    return null;
  }
}

class HttpError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

function send(res: http.ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  res.end(payload);
}

function sendError(res: http.ServerResponse, status: number, code: string, message: string): void {
  send(res, status, { error: { code, message } });
}

function readJson(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const declared = Number(req.headers["content-length"] ?? "0");
    if (declared > BODY_LIMIT) {
      reject(new HttpError(413, "PAYLOAD_TOO_LARGE", `body exceeds ${BODY_LIMIT} bytes`));
      req.resume();
      return;
    }
    const chunks: Buffer[] = [];
    let size = 0;
    let failed = false;
    req.on("data", (chunk: Buffer) => {
      if (failed) return;
      size += chunk.length;
      if (size > BODY_LIMIT) {
        failed = true;
        reject(new HttpError(413, "PAYLOAD_TOO_LARGE", `body exceeds ${BODY_LIMIT} bytes`));
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      if (failed) return;
      const ctype = String(req.headers["content-type"] ?? "");
      if (!/^application\/json\b/i.test(ctype)) {
        reject(new HttpError(415, "UNSUPPORTED_MEDIA_TYPE", "content-type must be application/json"));
        return;
      }
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf-8")));
      } catch {
        reject(new HttpError(400, "MALFORMED_JSON", "request body is not valid JSON"));
      }
    });
    req.on("error", (err) => {
      if (!failed) reject(err);
    });
  });
}

function main(): void {
  const config = (() => {
    try {
      return loadConfig(process.env);
    } catch (err) {
      process.stderr.write(`config error: ${err instanceof ConfigError ? err.message : String(err)}\n`);
      process.exit(1);
    }
  })();

  const upstreamSha = readManifestSha();
  const embedder = new EmbeddingClient(config.embedding);
  const service = new MemoryService(config.dataDir, embedder);
  service.open();
  const queue = new SerialQueue();
  if (service.corruptionDetail) log("memory_state_corrupt", { detail: service.corruptionDetail });
  else {
    const orphans = service.reconcilableOrphans();
    if (orphans.length > 0) {
      log("memory_reconcilable_orphans", { count: orphans.length, application_receipt_ids: orphans.map((o) => o.receiptId) });
    }
    const missing = service.missingEngineReceipts();
    if (missing.length > 0) {
      log("memory_missing_engine_records", { count: missing.length, application_receipt_ids: missing });
    }
  }

  const health = () => {
    const h = service.health();
    return {
      status: h.status,
      reasons: h.reasons,
      engine: { package: "@meterless/hmem-reference", version: "0.1.0", upstream_sha: upstreamSha },
      embedding_profile: h.embedding_profile,
      ...(h.stored_embedding_profile !== undefined ? { stored_embedding_profile: h.stored_embedding_profile } : {}),
      store: h.store,
    };
  };

  async function route(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const auth = req.headers.authorization ?? "";
    const presented = auth.startsWith("Bearer ") ? auth.slice("Bearer ".length) : "";
    if (!presented || !tokenMatches(presented, config.authToken)) {
      req.resume();
      sendError(res, 401, "AUTH_REQUIRED", "valid bearer token required");
      return;
    }

    const url = new URL(req.url ?? "/", "http://sidecar.invalid");
    const method = req.method ?? "GET";
    const p = url.pathname;

    if (p === "/health") {
      if (method !== "GET") throw new HttpError(405, "METHOD_NOT_ALLOWED", "use GET");
      const h = await queue.run(() => health());
      send(res, h.status === "ready" ? 200 : 503, h);
      return;
    }

    if (p === "/memory/remember") {
      if (method !== "POST") throw new HttpError(405, "METHOD_NOT_ALLOWED", "use POST");
      const body = parseRemember(await readJson(req));
      const out = await queue.run(() => service.remember(body));
      log("memory_remember", {
        application_receipt_id: body.application_receipt_id,
        engine_memory_id: out.body.engine_memory_id,
        duplicate: out.body.duplicate,
        reconciled: out.body.reconciled === true,
      });
      send(res, out.status, out.body);
      return;
    }

    if (p === "/memory/recall") {
      if (method !== "POST") throw new HttpError(405, "METHOD_NOT_ALLOWED", "use POST");
      const body = parseRecall(await readJson(req));
      const out = await queue.run(() => service.recall(body));
      log("memory_recall", {
        items: (out.items as unknown[]).length,
        historical: (out.historical as unknown[]).length,
        excluded_unscoped: out.excluded_unscoped,
      });
      send(res, 200, out);
      return;
    }

    if (p === "/memory/reindex") {
      if (method !== "POST") throw new HttpError(405, "METHOD_NOT_ALLOWED", "use POST");
      parseEmptyBody(await readJson(req));
      const out = await queue.run(() => service.reindex());
      log("memory_reindex", { reindexed: out.reindexed });
      send(res, 200, out);
      return;
    }

    const auditMatch = /^\/memory\/audit\/([^/]+)$/.exec(p);
    if (auditMatch) {
      if (method !== "GET") throw new HttpError(405, "METHOD_NOT_ALLOWED", "use GET");
      req.resume();
      for (const key of url.searchParams.keys()) {
        if (key !== "tenant_id" && key !== "service_id") throw new ValidationError(key, "unknown query parameter");
      }
      const receiptId = uuid(decodeURIComponent(auditMatch[1]), "application_receipt_id");
      const scope = {
        tenant_id: scopeId(url.searchParams.get("tenant_id") ?? undefined, "tenant_id"),
        service_id: scopeId(url.searchParams.get("service_id") ?? undefined, "service_id"),
      };
      const out = await queue.run(() => service.audit(receiptId, scope));
      send(res, 200, out);
      return;
    }

    req.resume();
    throw new HttpError(404, "NOT_FOUND", "no such route");
  }

  const server = http.createServer((req, res) => {
    route(req, res).catch((err: unknown) => {
      if (res.headersSent) {
        res.destroy();
        return;
      }
      if (err instanceof ValidationError) {
        sendError(res, 422, "VALIDATION_ERROR", err.message);
      } else if (err instanceof HttpError || err instanceof ServiceError) {
        if (err.status >= 500) log("request_failed", { code: err.code, message: err.message });
        sendError(res, err.status, err.code, err.message);
      } else {
        log("internal_error", { message: err instanceof Error ? err.message : String(err) });
        sendError(res, 500, "INTERNAL_ERROR", "internal error");
      }
    });
  });
  server.requestTimeout = 60_000;
  server.headersTimeout = 20_000;

  server.listen(config.port, config.host, () => {
    const addr = server.address();
    const port = typeof addr === "object" && addr ? addr.port : config.port;
    log("listening", {
      host: config.host,
      port,
      embedding_mode: config.embedding.mode,
      semantic: config.embedding.mode !== "hash_conformance",
      status: service.health().status,
    });
  });

  let stopping = false;
  const shutdown = (signal: string) => {
    if (stopping) return;
    stopping = true;
    log("shutdown", { signal });
    server.close();
    server.closeIdleConnections();
    const force = setTimeout(() => process.exit(1), 10_000);
    force.unref();
    queue.drain().then(
      () => process.exit(0),
      () => process.exit(1)
    );
  };
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

main();
