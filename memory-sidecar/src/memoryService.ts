// GreenOps memory service: wraps the vendored Meterless H-MEM reference engine with
// receipt idempotency, tenant/service scope, version applicability, lineage, a real
// embedding boundary and corruption detection. Scope is enforced HERE, not by the engine.
//
// All engine-touching operations must be called through the server's SerialQueue
// (single writer); recall is included because upstream query() mutates access counters.

import fs from "node:fs";
import path from "node:path";
import { HMEM } from "../vendor/hmem/src/index.ts";
import type { LedgerEntry, MemoryRecord } from "../vendor/hmem/src/types.ts";
import {
  EmbeddingClient,
  EmbeddingUnavailableError,
  installFailClosedEmbedder,
  profileConfigMatches,
  withPreparedVectors,
} from "./embedding.ts";
import type { EmbeddingProfile } from "./embedding.ts";
import { atomicWriteFile } from "./util.ts";
import type { Applicability, MemoryKind, RecallRequest, RememberRequest, Scope, TargetScope } from "./validation.ts";

export const INDEX_FILE = "greenops-index.json";
export const RECEIPT_SOURCE_PREFIX = "greenops:receipt:";
export const AUDIT_LIMITATIONS = [
  "JSON state + JSONL ledger: not transactional, not tamper-proof",
  "single-tenant sandbox; scope enforced by this wrapper, not the engine",
];

export interface ReceiptEntry {
  engine_memory_id: string;
  kind: MemoryKind;
  scope: TargetScope;
  applicability: Applicability;
  content_hash: string;
  evidence_refs: string[];
  stored_at: string;
  supersedes_receipt_id: string | null;
  superseded_by_receipt_id: string | null;
  correction_review_id: string | null;
}

export interface IndexFile {
  schema_version: 1;
  embedding_profile: EmbeddingProfile | null;
  receipts: Record<string, ReceiptEntry>;
}

export class ServiceError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

const MISSING_IDS_REPORTED = 50;
const UUID_LOWER_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export type HealthStatus = "ready" | "degraded" | "unavailable";

const INAPPLICABLE_REASON: Record<keyof Applicability, string> = {
  policy_version: "POLICY_VERSION_CHANGED",
  workload_version: "WORKLOAD_VERSION_CHANGED",
  config_version: "CONFIG_VERSION_CHANGED",
  model_version: "MODEL_VERSION_CHANGED",
  test_version: "TEST_VERSION_CHANGED",
};

function isIndexShape(v: unknown): v is IndexFile {
  if (v === null || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  if (o.schema_version !== 1) return false;
  if (o.receipts === null || typeof o.receipts !== "object" || Array.isArray(o.receipts)) return false;
  if (o.embedding_profile !== null && (typeof o.embedding_profile !== "object" || Array.isArray(o.embedding_profile))) return false;
  for (const e of Object.values(o.receipts as Record<string, unknown>)) {
    if (e === null || typeof e !== "object") return false;
    const r = e as Record<string, unknown>;
    if (typeof r.engine_memory_id !== "string" || typeof r.content_hash !== "string") return false;
    if (r.scope === null || typeof r.scope !== "object" || r.applicability === null || typeof r.applicability !== "object") return false;
  }
  return true;
}

/** Read-only integrity probe of engine files. Throws on any parse/shape failure. Never writes. */
function probeEngineFiles(dataDir: string): void {
  const stateFile = path.join(dataDir, "state.json");
  if (fs.existsSync(stateFile)) {
    const saved = JSON.parse(fs.readFileSync(stateFile, "utf-8")) as { seq?: unknown; records?: unknown };
    if (typeof saved?.seq !== "number" || !Array.isArray(saved.records)) throw new Error("state.json has unexpected shape");
    for (const r of saved.records as Array<Record<string, unknown>>) {
      if (typeof r?.id !== "string" || typeof r.content !== "string" || !Array.isArray(r.embedding)) {
        throw new Error("state.json contains a malformed record");
      }
    }
  }
  const ledgerFile = path.join(dataDir, "ledger.jsonl");
  if (fs.existsSync(ledgerFile)) {
    const lines = fs.readFileSync(ledgerFile, "utf-8").split("\n").filter(Boolean);
    for (const line of lines) {
      const e = JSON.parse(line) as Record<string, unknown>;
      if (typeof e?.memoryId !== "string" || typeof e.action !== "string") throw new Error("ledger.jsonl contains a malformed entry");
    }
  }
}

export class MemoryService {
  private hmem: HMEM | null = null;
  private index: IndexFile = { schema_version: 1, embedding_profile: null, receipts: {} };
  private corrupt: string | null = null;
  private profileMismatch = false;
  private readonly indexFile: string;

  constructor(private dataDir: string, private embedder: EmbeddingClient) {
    this.indexFile = path.join(dataDir, INDEX_FILE);
  }

  /** Load engine + index. On corruption, records the fault and leaves every file untouched. */
  open(): void {
    installFailClosedEmbedder();
    fs.mkdirSync(this.dataDir, { recursive: true });
    try {
      probeEngineFiles(this.dataDir);
      if (fs.existsSync(this.indexFile)) {
        const parsed: unknown = JSON.parse(fs.readFileSync(this.indexFile, "utf-8"));
        if (!isIndexShape(parsed)) throw new Error(`${INDEX_FILE} has unexpected shape`);
        this.index = parsed;
      }
      this.hmem = new HMEM({ persistDir: this.dataDir, actor: "greenops-memory-sidecar" });
    } catch (err) {
      this.hmem = null;
      this.corrupt = err instanceof Error ? err.message : String(err);
      return;
    }
    const stored = this.index.embedding_profile;
    this.profileMismatch = stored !== null && !profileConfigMatches(stored, this.embedder.configuredProfile(stored.dimensions));
  }

  get corruptionDetail(): string | null {
    return this.corrupt;
  }

  /** Profile reported to callers: the stored one once learned, else the configured one. */
  currentProfile(): EmbeddingProfile {
    if (this.profileMismatch) return this.embedder.configuredProfile(null);
    return this.index.embedding_profile ?? this.embedder.configuredProfile(null);
  }

  health(): {
    status: HealthStatus;
    reasons: string[];
    embedding_profile: EmbeddingProfile;
    stored_embedding_profile?: EmbeddingProfile | null;
    store: {
      records: number;
      receipts: number;
      data_dir: string;
      unindexed_engine_records?: number;
      missing_engine_records?: number;
      missing_engine_receipt_ids?: string[];
      reconcilable_orphans?: number;
    };
  } {
    if (this.corrupt || !this.hmem) {
      return {
        status: "unavailable",
        reasons: ["MEMORY_STATE_CORRUPT"],
        embedding_profile: this.embedder.configuredProfile(null),
        store: { records: 0, receipts: 0, data_dir: this.dataDir },
      };
    }
    const reasons: string[] = [];
    if (this.profileMismatch) reasons.push("EMBEDDING_PROFILE_MISMATCH");
    const { unindexed, missing } = this.consistency();
    if (unindexed > 0 || missing > 0) reasons.push("INDEX_ENGINE_MISMATCH");
    if (missing > 0) reasons.push("ENGINE_RECORD_MISSING");
    const out: ReturnType<MemoryService["health"]> = {
      status: reasons.length === 0 ? "ready" : "degraded",
      reasons,
      embedding_profile: this.currentProfile(),
      store: {
        records: this.hmem.store.all().length,
        receipts: Object.keys(this.index.receipts).length,
        data_dir: this.dataDir,
        unindexed_engine_records: unindexed,
        missing_engine_records: missing,
        missing_engine_receipt_ids: this.missingEngineReceipts().slice(0, MISSING_IDS_REPORTED),
        reconcilable_orphans: this.reconcilableOrphans().length,
      },
    };
    if (this.profileMismatch) out.stored_embedding_profile = this.index.embedding_profile;
    return out;
  }

  /** The engine record an index entry points at, only if it exists and carries this receipt's source. */
  private recordFor(receiptId: string, entry: ReceiptEntry): MemoryRecord | undefined {
    const rec = this.mustEngine().store.get(entry.engine_memory_id);
    return rec && rec.source === RECEIPT_SOURCE_PREFIX + receiptId ? rec : undefined;
  }

  private consistency(): { unindexed: number; missing: number } {
    const engine = this.mustEngine();
    const mapped = this.engineToReceipt();
    const missing = Object.keys(this.index.receipts).length - mapped.size;
    const unindexed = engine.store.all().filter((r) => !mapped.has(r.id)).length;
    return { unindexed, missing };
  }

  /** Receipts whose index entry exists but whose engine record is gone (or no longer theirs). */
  missingEngineReceipts(): string[] {
    return Object.entries(this.index.receipts)
      .filter(([receiptId, entry]) => !this.recordFor(receiptId, entry))
      .map(([receiptId]) => receiptId)
      .sort();
  }

  /**
   * Engine records left by a crash between the engine write and the index write: source is
   * exactly `greenops:receipt:<uuid>`, no index entry exists for that receipt, no index entry
   * points at the record, and it is the only engine record with that source.
   */
  reconcilableOrphans(): Array<{ receiptId: string; engineId: string }> {
    const engine = this.mustEngine();
    const referenced = this.engineToReceipt();
    const bySource = new Map<string, MemoryRecord[]>();
    for (const r of engine.store.all()) {
      if (!r.source.startsWith(RECEIPT_SOURCE_PREFIX)) continue;
      const list = bySource.get(r.source) ?? [];
      list.push(r);
      bySource.set(r.source, list);
    }
    const out: Array<{ receiptId: string; engineId: string }> = [];
    for (const [source, recs] of bySource) {
      const receiptId = source.slice(RECEIPT_SOURCE_PREFIX.length);
      if (!UUID_LOWER_RE.test(receiptId) || this.index.receipts[receiptId]) continue;
      if (recs.length !== 1 || referenced.has(recs[0].id)) continue;
      out.push({ receiptId, engineId: recs[0].id });
    }
    return out;
  }

  /** Engine records carrying this receipt's source that no index entry references. */
  private orphansFor(receiptId: string): MemoryRecord[] {
    const engine = this.mustEngine();
    const referenced = this.engineToReceipt();
    return engine.store.all().filter((r) => r.source === RECEIPT_SOURCE_PREFIX + receiptId && !referenced.has(r.id));
  }

  private mustEngine(): HMEM {
    if (this.corrupt || !this.hmem) {
      throw new ServiceError(503, "MEMORY_STATE_CORRUPT", "memory state failed integrity checks at startup; files left untouched");
    }
    return this.hmem;
  }

  private requireReady(): HMEM {
    const engine = this.mustEngine();
    if (this.profileMismatch) {
      throw new ServiceError(503, "MEMORY_NOT_READY", "stored embedding profile differs from configuration; POST /memory/reindex required");
    }
    return engine;
  }

  /**
   * Map engine id -> receipt id for index entries that point at a matching engine record.
   * Dangling entries are left out, so a stale pointer can never claim another receipt's record.
   */
  private engineToReceipt(): Map<string, string> {
    const m = new Map<string, string>();
    for (const [receiptId, entry] of Object.entries(this.index.receipts)) {
      if (this.recordFor(receiptId, entry)) m.set(entry.engine_memory_id, receiptId);
    }
    return m;
  }

  /**
   * Read state.json back from disk and require the record to be there with this receipt's
   * source. Every `persisted:true` acknowledgment passes through this check.
   */
  private assertPersisted(engineId: string, receiptId: string): void {
    let found = false;
    try {
      const saved = JSON.parse(fs.readFileSync(path.join(this.dataDir, "state.json"), "utf-8")) as { records?: Array<{ id?: unknown; source?: unknown }> };
      found = Array.isArray(saved.records) &&
        saved.records.some((r) => r?.id === engineId && r.source === RECEIPT_SOURCE_PREFIX + receiptId);
    } catch {
      found = false;
    }
    if (!found) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED",
        `engine record ${engineId} for receipt ${receiptId} is not present in state.json; not acknowledged`);
    }
  }

  /** Orphan checks shared by first writes and missing-record reconciliation. */
  private adoptableOrphan(receiptId: string, finding: string): MemoryRecord | undefined {
    const orphans = this.orphansFor(receiptId);
    if (orphans.length > 1 || (orphans.length === 1 && orphans[0].content !== finding)) {
      throw new ServiceError(409, "ORPHAN_CONFLICT",
        "an unindexed engine record for this receipt exists with different content (or more than one exists); not adopted");
    }
    return orphans[0];
  }

  /** Re-embed an adopted orphan so its vector matches the stored profile. */
  private reembed(engine: HMEM, record: MemoryRecord, v: number[]): void {
    try {
      if (record.embedding.length !== v.length || record.embedding.some((x, i) => x !== v[i])) {
        engine.store.update(record.id, { embedding: v });
      }
    } catch (err) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED", `orphan re-embed failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  private addEngineRecord(engine: HMEM, req: RememberRequest, vector: number[], learnedAt: number, supersedes: string | undefined): MemoryRecord {
    try {
      return withPreparedVectors([[req.finding, vector]], () =>
        engine.add({
          content: req.finding,
          source: RECEIPT_SOURCE_PREFIX + req.application_receipt_id,
          type: "factual",
          layer: "long_term",
          tags: req.tags,
          confidence: 0.9,
          provenance: { origin: "document", learnedAt, label: req.kind, refs: [...req.evidence_refs] },
          supersedes,
        })
      );
    } catch (err) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED", `engine add failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  private writeIndex(next: IndexFile): void {
    atomicWriteFile(this.indexFile, JSON.stringify(next, null, 2) + "\n");
    this.index = next;
  }

  private cloneIndex(): IndexFile {
    return structuredClone(this.index);
  }

  /** Fetch vectors and learn/check dimensions. Nothing is written here. */
  private async prepare(texts: string[], purpose: "passage" | "query"): Promise<{ vectors: number[][]; profile: EmbeddingProfile }> {
    let result;
    try {
      result = await this.embedder.embed(texts, purpose);
    } catch (err) {
      if (err instanceof EmbeddingUnavailableError) {
        throw new ServiceError(503, "MEMORY_EMBEDDING_UNAVAILABLE", err.message);
      }
      throw new ServiceError(503, "MEMORY_EMBEDDING_UNAVAILABLE", "embedding provider failed");
    }
    const stored = this.index.embedding_profile;
    if (stored && stored.dimensions !== null && stored.dimensions !== result.dimensions) {
      throw new ServiceError(503, "MEMORY_EMBEDDING_UNAVAILABLE",
        `provider returned ${result.dimensions} dimensions; stored profile has ${stored.dimensions}`);
    }
    return { vectors: result.vectors, profile: stored ?? this.embedder.configuredProfile(result.dimensions) };
  }

  async remember(req: RememberRequest): Promise<{ status: number; body: Record<string, unknown> }> {
    const engine = this.requireReady();
    const id = req.application_receipt_id;
    const existing = this.index.receipts[id];
    if (existing) {
      const sameScope = existing.scope.tenant_id === req.scope.tenant_id && existing.scope.service_id === req.scope.service_id;
      if (existing.content_hash === req.content_hash && sameScope) {
        if (!this.recordFor(id, existing)) return this.reconcileMissing(engine, req, existing);
        this.assertPersisted(existing.engine_memory_id, id);
        return {
          status: 200,
          body: {
            engine_memory_id: existing.engine_memory_id,
            application_receipt_id: id,
            stored_at: existing.stored_at,
            embedding_profile: this.currentProfile(),
            persisted: true,
            duplicate: true,
          },
        };
      }
      throw new ServiceError(409, "IDEMPOTENCY_CONFLICT", "application_receipt_id already stored with different content");
    }

    let superseded: ReceiptEntry | null = null;
    if (req.supersedes_receipt_id) {
      const old = this.index.receipts[req.supersedes_receipt_id];
      if (!old || old.scope.tenant_id !== req.scope.tenant_id || old.scope.service_id !== req.scope.service_id) {
        throw new ServiceError(404, "MEMORY_NOT_FOUND", "superseded receipt not found in this tenant and service");
      }
      if (old.superseded_by_receipt_id) {
        throw new ServiceError(409, "SUPERSESSION_CONFLICT", "superseded receipt is already superseded");
      }
      if (!this.recordFor(req.supersedes_receipt_id, old)) {
        throw new ServiceError(409, "INDEX_ENGINE_MISMATCH", "superseded receipt has no engine record");
      }
      superseded = old;
    }

    // Crash reconciliation: adopt an orphan engine record for this receipt instead of adding a second one.
    const orphan = this.adoptableOrphan(id, req.finding);

    const { vectors, profile } = await this.prepare([req.finding], "passage");
    const storedAt = orphan ? new Date(orphan.timestamp).toISOString() : new Date().toISOString();

    let record: MemoryRecord;
    if (orphan) {
      record = orphan;
      this.reembed(engine, record, vectors[0]);
    } else {
      record = this.addEngineRecord(engine, req, vectors[0], Date.parse(storedAt), superseded?.engine_memory_id);
    }

    try {
      // Upstream enrichment may auto-set `supersedes` from heuristic similarity (possibly
      // across scopes). Lineage is authoritative only from an approved correction.
      const intended = superseded?.engine_memory_id;
      if (record.supersedes !== intended) engine.store.update(record.id, { supersedes: intended });
      if (superseded && engine.store.get(superseded.engine_memory_id)?.supersededBy !== record.id) {
        engine.store.update(superseded.engine_memory_id, { supersededBy: record.id });
      }
    } catch (err) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED", `engine lineage update failed: ${err instanceof Error ? err.message : String(err)}`);
    }

    const next = this.cloneIndex();
    if (!next.embedding_profile) next.embedding_profile = profile;
    next.receipts[id] = {
      engine_memory_id: record.id,
      kind: req.kind,
      scope: { ...req.scope },
      applicability: { ...req.applicability },
      content_hash: req.content_hash,
      evidence_refs: [...req.evidence_refs],
      stored_at: storedAt,
      supersedes_receipt_id: req.supersedes_receipt_id,
      superseded_by_receipt_id: null,
      correction_review_id: req.correction_review_id,
    };
    if (superseded && req.supersedes_receipt_id) next.receipts[req.supersedes_receipt_id].superseded_by_receipt_id = id;
    try {
      this.writeIndex(next);
    } catch (err) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED",
        `engine persisted but index write failed (health will report INDEX_ENGINE_MISMATCH): ${err instanceof Error ? err.message : String(err)}`);
    }
    this.assertPersisted(record.id, id);

    return {
      status: 201,
      body: {
        engine_memory_id: record.id,
        application_receipt_id: id,
        stored_at: storedAt,
        embedding_profile: this.currentProfile(),
        persisted: true,
        duplicate: orphan !== undefined,
        ...(orphan ? { reconciled: true } : {}),
      },
    };
  }

  /**
   * The index entry exists (same hash and scope already checked) but its engine record is gone.
   * Re-create the record from the request, re-link any supersession the index records, re-point
   * the index, and acknowledge only after the record is confirmed on disk. A crash part-way
   * leaves an orphan with this receipt's source, which the next retry adopts.
   */
  private async reconcileMissing(engine: HMEM, req: RememberRequest, existing: ReceiptEntry): Promise<{ status: number; body: Record<string, unknown> }> {
    const id = req.application_receipt_id;
    const linked = (receiptId: string | null): MemoryRecord | undefined => {
      const entry = receiptId ? this.index.receipts[receiptId] : undefined;
      return receiptId && entry ? this.recordFor(receiptId, entry) : undefined;
    };
    // A linked receipt whose own record is also missing is re-linked when it is reconciled.
    const predecessor = linked(existing.supersedes_receipt_id);
    const successor = linked(existing.superseded_by_receipt_id);

    const orphan = this.adoptableOrphan(id, req.finding);
    const { vectors, profile } = await this.prepare([req.finding], "passage");

    let record: MemoryRecord;
    if (orphan) {
      record = orphan;
      this.reembed(engine, record, vectors[0]);
    } else {
      record = this.addEngineRecord(engine, req, vectors[0], Date.parse(existing.stored_at), predecessor?.id);
    }

    try {
      // Lineage comes only from the index (approved corrections); reset any heuristic links.
      if (record.supersedes !== predecessor?.id) engine.store.update(record.id, { supersedes: predecessor?.id });
      if (record.supersededBy !== successor?.id) engine.store.update(record.id, { supersededBy: successor?.id });
      if (predecessor && predecessor.supersededBy !== record.id) engine.store.update(predecessor.id, { supersededBy: record.id });
      if (successor && successor.supersedes !== record.id) engine.store.update(successor.id, { supersedes: record.id });
    } catch (err) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED", `engine lineage update failed: ${err instanceof Error ? err.message : String(err)}`);
    }

    const next = this.cloneIndex();
    if (!next.embedding_profile) next.embedding_profile = profile;
    next.receipts[id] = { ...next.receipts[id], engine_memory_id: record.id };
    try {
      this.writeIndex(next);
    } catch (err) {
      throw new ServiceError(500, "MEMORY_WRITE_FAILED",
        `engine record re-created but index write failed (retry adopts it): ${err instanceof Error ? err.message : String(err)}`);
    }
    this.assertPersisted(record.id, id);

    return {
      status: 201,
      body: {
        engine_memory_id: record.id,
        application_receipt_id: id,
        stored_at: existing.stored_at,
        embedding_profile: this.currentProfile(),
        persisted: true,
        duplicate: true,
        reconciled: true,
      },
    };
  }

  private inapplicableReasons(entry: ReceiptEntry, record: MemoryRecord, requested: Applicability): string[] {
    const reasons: string[] = [];
    for (const key of Object.keys(INAPPLICABLE_REASON) as Array<keyof Applicability>) {
      const stored = entry.applicability[key];
      if (stored !== null && stored !== undefined && stored !== requested[key]) reasons.push(INAPPLICABLE_REASON[key]);
    }
    if (entry.superseded_by_receipt_id || record.supersededBy) reasons.push("SUPERSEDED");
    return reasons;
  }

  async recall(req: RecallRequest): Promise<Record<string, unknown>> {
    const engine = this.requireReady();
    const { vectors, profile } = await this.prepare([req.query], "query");
    const byEngine = this.engineToReceipt();

    let excludedUnscoped = 0;
    const reasonsById = new Map<string, string[]>();
    for (const m of engine.store.all()) {
      const receiptId = byEngine.get(m.id);
      const entry = receiptId ? this.index.receipts[receiptId] : undefined;
      if (!receiptId || !entry || m.source !== RECEIPT_SOURCE_PREFIX + receiptId) {
        excludedUnscoped++;
        continue;
      }
      if (entry.scope.tenant_id !== req.scope.tenant_id || entry.scope.service_id !== req.scope.service_id) continue;
      reasonsById.set(m.id, this.inapplicableReasons(entry, m, req.applicability));
    }

    const opts = { topN: req.top_k, threshold: req.threshold };
    const [current, past] = withPreparedVectors([[req.query, vectors[0]]], () => [
      engine.retrieval.query(req.query, { ...opts, filter: (m) => reasonsById.get(m.id)?.length === 0 }),
      engine.retrieval.query(req.query, { ...opts, filter: (m) => (reasonsById.get(m.id)?.length ?? 0) > 0 }),
    ]);
    // Upstream touch() updates access counters without persisting; make them durable.
    engine.store.persist();

    if (!this.index.embedding_profile) {
      const next = this.cloneIndex();
      next.embedding_profile = profile;
      this.writeIndex(next);
    }

    const view = (m: MemoryRecord, score: number) => {
      const receiptId = byEngine.get(m.id)!;
      const e = this.index.receipts[receiptId];
      return {
        engine_memory_id: m.id,
        application_receipt_id: receiptId,
        kind: e.kind,
        finding: m.content,
        score: Number(score.toFixed(6)),
        evidence_refs: [...e.evidence_refs],
        applicability: { ...e.applicability },
        stored_at: e.stored_at,
        supersedes_receipt_id: e.supersedes_receipt_id,
        superseded_by_receipt_id: e.superseded_by_receipt_id,
        target_id: e.scope.target_id,
      };
    };

    return {
      items: current.memories.map((r) => view(r.memory, r.relevance)),
      historical: past.memories.map((r) => ({ ...view(r.memory, r.relevance), inapplicable_reasons: reasonsById.get(r.memory.id) ?? [] })),
      excluded_unscoped: excludedUnscoped,
      trace: {
        retrieval_reason:
          "tenant+service scope and version applicability filtered before H-MEM hybrid ranking; " +
          `items: ${current.trace.retrievalReason}; historical: ${past.trace.retrievalReason}`,
        scores: { ...current.trace.scores, ...past.trace.scores },
        candidates: {
          in_scope_applicable: [...reasonsById.values()].filter((r) => r.length === 0).length,
          in_scope_inapplicable: [...reasonsById.values()].filter((r) => r.length > 0).length,
        },
        threshold: req.threshold,
        top_k: req.top_k,
      },
      embedding_profile: this.currentProfile(),
    };
  }

  audit(receiptId: string, scope: Scope): Record<string, unknown> {
    const engine = this.mustEngine();
    const entry = this.index.receipts[receiptId];
    if (!entry || entry.scope.tenant_id !== scope.tenant_id || entry.scope.service_id !== scope.service_id) {
      throw new ServiceError(404, "MEMORY_NOT_FOUND", "receipt not found in this tenant and service");
    }
    const history = engine.ledger.history(entry.engine_memory_id).map(redactLedgerEntry);
    return {
      application_receipt_id: receiptId,
      engine_memory_id: entry.engine_memory_id,
      kind: entry.kind,
      scope: { ...entry.scope },
      applicability: { ...entry.applicability },
      evidence_refs: [...entry.evidence_refs],
      stored_at: entry.stored_at,
      correction_review_id: entry.correction_review_id,
      supersedes_receipt_id: entry.supersedes_receipt_id,
      superseded_by_receipt_id: entry.superseded_by_receipt_id,
      engine_record_present: engine.store.get(entry.engine_memory_id) !== undefined,
      history,
      limitations: [...AUDIT_LIMITATIONS],
    };
  }

  /** Re-embed every engine record with the configured provider and record the new profile. */
  async reindex(): Promise<Record<string, unknown>> {
    const engine = this.mustEngine();
    const records = engine.store.all();
    let profile = this.embedder.configuredProfile(null);
    const vectors: number[][] = [];
    const BATCH = 16;
    let dims: number | null = null;
    for (let i = 0; i < records.length; i += BATCH) {
      let res;
      try {
        res = await this.embedder.embed(records.slice(i, i + BATCH).map((r) => r.content), "passage");
      } catch (err) {
        throw new ServiceError(503, "MEMORY_EMBEDDING_UNAVAILABLE", err instanceof Error ? err.message : "embedding provider failed");
      }
      if (dims !== null && res.dimensions !== dims) {
        throw new ServiceError(503, "MEMORY_EMBEDDING_UNAVAILABLE", "provider returned inconsistent dimensions during reindex");
      }
      dims = res.dimensions;
      vectors.push(...res.vectors);
    }
    // All vectors fetched before any write: a provider failure leaves state untouched.
    records.forEach((r, i) => engine.store.update(r.id, { embedding: vectors[i] }));
    profile = this.embedder.configuredProfile(dims);
    const next = this.cloneIndex();
    next.embedding_profile = records.length > 0 ? profile : null;
    this.writeIndex(next);
    this.profileMismatch = false;
    return { reindexed: records.length, embedding_profile: this.currentProfile() };
  }
}

function redactLedgerEntry(e: LedgerEntry): Record<string, unknown> {
  const strip = (s?: Partial<MemoryRecord>) => {
    if (!s) return undefined;
    const { embedding: _embedding, ...rest } = s;
    return rest;
  };
  let details = e.details;
  if (details && typeof details.query === "string") {
    details = { ...details, query: details.query.length > 200 ? `${details.query.slice(0, 200)}…` : details.query };
  }
  const out: Record<string, unknown> = { memoryId: e.memoryId, action: e.action, actor: e.actor, timestamp: e.timestamp };
  const prev = strip(e.previousState);
  const next = strip(e.newState);
  if (prev) out.previousState = prev;
  if (next) out.newState = next;
  if (details) out.details = details;
  return out;
}
