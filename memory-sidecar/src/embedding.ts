// Embedding provider boundary for the GreenOps memory sidecar.
//
// The vendored H-MEM embed() is synchronous. Remote vectors are therefore fetched
// asynchronously *before* each engine call and served to the engine from an exact-text
// cache (see memoryService.ts). This module only talks to the provider and validates
// what it returns; it never falls back to the hash mock in a semantic mode.

import { embed as vendorEmbed, setEmbedder } from "../vendor/hmem/src/embeddings.ts";
import type { EmbeddingMode, SidecarConfig } from "./config.ts";
import { canonicalJson, sha256Hex } from "./util.ts";

export type EmbeddingPurpose = "passage" | "query";

export interface EmbeddingProfile {
  kind: EmbeddingMode;
  model_id: string;
  dimensions: number | null;
  preprocessing_version: string;
  normalization: "l2";
  semantic: boolean;
  profile_hash: string;
}

export class EmbeddingUnavailableError extends Error {}

export function makeProfile(base: Omit<EmbeddingProfile, "profile_hash">): EmbeddingProfile {
  const fields = {
    kind: base.kind,
    model_id: base.model_id,
    dimensions: base.dimensions,
    preprocessing_version: base.preprocessing_version,
    normalization: base.normalization,
    semantic: base.semantic,
  };
  return { ...fields, profile_hash: `sha256:${sha256Hex(canonicalJson(fields))}` };
}

/** Fields that configuration determines; dimensions are learned from the provider. */
export function profileConfigMatches(stored: EmbeddingProfile, configured: EmbeddingProfile): boolean {
  return stored.kind === configured.kind &&
    stored.model_id === configured.model_id &&
    stored.preprocessing_version === configured.preprocessing_version &&
    stored.normalization === configured.normalization &&
    stored.semantic === configured.semantic;
}

/** Preprocessing v1: Unicode NFC normalization only. */
export function preprocess(text: string, version: string): string {
  if (version !== "v1") throw new EmbeddingUnavailableError(`unsupported preprocessing version ${version}`);
  return text.normalize("NFC");
}

export function l2Normalize(vec: number[]): number[] {
  let sum = 0;
  for (const v of vec) sum += v * v;
  const norm = Math.sqrt(sum);
  if (!Number.isFinite(norm) || norm === 0) throw new EmbeddingUnavailableError("embedding has zero or non-finite norm");
  return vec.map((v) => v / norm);
}

export interface EmbeddingResult {
  vectors: number[][];
  dimensions: number;
  durationMs: number;
}

export class EmbeddingClient {
  constructor(private cfg: SidecarConfig["embedding"]) {}

  get mode(): EmbeddingMode {
    return this.cfg.mode;
  }

  configuredProfile(dimensions: number | null): EmbeddingProfile {
    return makeProfile({
      kind: this.cfg.mode,
      model_id: this.cfg.modelId,
      dimensions: this.cfg.mode === "hash_conformance" ? 64 : dimensions,
      preprocessing_version: this.cfg.preprocessingVersion,
      normalization: "l2",
      semantic: this.cfg.mode !== "hash_conformance",
    });
  }

  async embed(texts: string[], purpose: EmbeddingPurpose): Promise<EmbeddingResult> {
    if (texts.length === 0) return { vectors: [], dimensions: 0, durationMs: 0 };
    const started = Date.now();
    const inputs = texts.map((t) => preprocess(t, this.cfg.preprocessingVersion));
    const raw = this.cfg.mode === "hash_conformance" ? inputs.map(hashConformanceVector) : await this.remote(inputs, purpose);
    const dims = raw[0].length;
    if (dims === 0) throw new EmbeddingUnavailableError("provider returned an empty vector");
    const vectors = raw.map((vec) => {
      if (vec.length !== dims) throw new EmbeddingUnavailableError("provider returned inconsistent dimensions");
      return l2Normalize(vec);
    });
    return { vectors, dimensions: dims, durationMs: Date.now() - started };
  }

  private async remote(inputs: string[], purpose: EmbeddingPurpose): Promise<number[][]> {
    const body: Record<string, unknown> = { input: inputs, model: this.cfg.modelId, encoding_format: "float" };
    if (this.cfg.mode === "nvidia") {
      body.input_type = purpose;
      body.truncate = "NONE";
    }
    const headers: Record<string, string> = { "content-type": "application/json", accept: "application/json" };
    if (this.cfg.apiKey) headers.authorization = `Bearer ${this.cfg.apiKey}`;

    let res: Response;
    try {
      res = await fetch(`${this.cfg.baseUrl}/embeddings`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(this.cfg.timeoutMs),
      });
    } catch (err) {
      const name = err instanceof Error ? err.name : "Error";
      throw new EmbeddingUnavailableError(`embedding request failed (${name})`);
    }
    if (!res.ok) {
      await res.body?.cancel().catch(() => undefined);
      throw new EmbeddingUnavailableError(`embedding provider returned HTTP ${res.status}`);
    }
    let parsed: unknown;
    try {
      parsed = await res.json();
    } catch {
      throw new EmbeddingUnavailableError("embedding provider returned invalid JSON");
    }
    const data = (parsed as { data?: unknown })?.data;
    if (!Array.isArray(data) || data.length !== inputs.length) {
      throw new EmbeddingUnavailableError("embedding response data length does not match inputs");
    }
    return data.map((item, i) => {
      const it = item as { index?: unknown; embedding?: unknown };
      if (it === null || typeof it !== "object") throw new EmbeddingUnavailableError("embedding response item is not an object");
      if (it.index !== undefined && it.index !== i) throw new EmbeddingUnavailableError("embedding response is out of order");
      if (!Array.isArray(it.embedding)) throw new EmbeddingUnavailableError("embedding response item has no float vector");
      for (const v of it.embedding) {
        if (typeof v !== "number" || !Number.isFinite(v)) throw new EmbeddingUnavailableError("embedding contains a non-finite value");
      }
      return it.embedding as number[];
    });
  }
}

/**
 * Deterministic conformance vectors: the vendored reference hash mock, called with no
 * registered embedder. NOT semantic; profile carries semantic:false.
 */
function hashConformanceVector(text: string): number[] {
  setEmbedder(null);
  try {
    return vendorEmbed(text);
  } finally {
    setEmbedder(failClosedLookup);
  }
}

// ---- exact-text vector cache served to the synchronous engine ----

const vectorCache = new Map<string, number[]>();

function failClosedLookup(text: string): number[] {
  const v = vectorCache.get(text);
  if (!v) throw new EmbeddingUnavailableError("no prepared embedding for engine text (fail closed)");
  return v;
}

/** Install the fail-closed embedder. Called once at startup. */
export function installFailClosedEmbedder(): void {
  setEmbedder(failClosedLookup);
}

/** Run `fn` with prepared vectors available to the engine; the cache is always cleared after. */
export function withPreparedVectors<T>(entries: Array<[string, number[]]>, fn: () => T): T {
  vectorCache.clear();
  for (const [text, vec] of entries) vectorCache.set(text, vec);
  try {
    return fn();
  } finally {
    vectorCache.clear();
  }
}
