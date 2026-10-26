// Environment configuration for the GreenOps memory sidecar. Fails fast on invalid configuration.

import path from "node:path";

export type EmbeddingMode = "nvidia" | "openai_compatible" | "hash_conformance";

export interface SidecarConfig {
  authToken: string;
  dataDir: string;
  port: number;
  host: string;
  embedding: {
    mode: EmbeddingMode;
    baseUrl: string;
    modelId: string;
    apiKey: string | null;
    preprocessingVersion: string;
    timeoutMs: number;
  };
}

export class ConfigError extends Error {}

const MODES: readonly EmbeddingMode[] = ["nvidia", "openai_compatible", "hash_conformance"];
export const HASH_MODEL_ID = "meterless-hmem-reference-fnv1a-64";

export function loadConfig(env: NodeJS.ProcessEnv): SidecarConfig {
  const authToken = env.MEMORY_AUTH_TOKEN ?? "";
  if (authToken.length < 16) throw new ConfigError("MEMORY_AUTH_TOKEN is required (at least 16 characters)");

  const dataDirRaw = env.HMEM_DATA_DIR ?? "";
  if (dataDirRaw.trim() === "") throw new ConfigError("HMEM_DATA_DIR is required (durable directory)");

  const port = env.PORT === undefined || env.PORT === "" ? 7410 : Number(env.PORT);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new ConfigError("PORT must be an integer 0..65535");

  const host = env.HOST && env.HOST !== "" ? env.HOST : "127.0.0.1";

  const mode = env.EMBEDDING_MODE as EmbeddingMode | undefined;
  if (!mode || !MODES.includes(mode)) {
    throw new ConfigError(`EMBEDDING_MODE is required: one of ${MODES.join(", ")}`);
  }

  const timeoutMs = env.EMBEDDING_TIMEOUT_MS === undefined || env.EMBEDDING_TIMEOUT_MS === ""
    ? 15000
    : Number(env.EMBEDDING_TIMEOUT_MS);
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 120000) {
    throw new ConfigError("EMBEDDING_TIMEOUT_MS must be an integer 100..120000");
  }

  const baseUrl = (env.EMBEDDING_BASE_URL && env.EMBEDDING_BASE_URL !== ""
    ? env.EMBEDDING_BASE_URL
    : "https://integrate.api.nvidia.com/v1").replace(/\/+$/, "");
  if (mode !== "hash_conformance") {
    let parsed: URL;
    try { parsed = new URL(baseUrl); } catch { throw new ConfigError("EMBEDDING_BASE_URL is not a valid URL"); }
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") throw new ConfigError("EMBEDDING_BASE_URL must be http(s)");
  }

  const apiKey = env.EMBEDDING_API_KEY && env.EMBEDDING_API_KEY !== "" ? env.EMBEDDING_API_KEY : null;
  if (mode === "nvidia" && !apiKey) throw new ConfigError("EMBEDDING_API_KEY is required when EMBEDDING_MODE=nvidia");

  const modelId = mode === "hash_conformance"
    ? HASH_MODEL_ID
    : env.EMBEDDING_MODEL_ID && env.EMBEDDING_MODEL_ID !== "" ? env.EMBEDDING_MODEL_ID : "nvidia/nemotron-3.5-embed-1b";

  const preprocessingVersion = env.EMBEDDING_PREPROCESSING_VERSION && env.EMBEDDING_PREPROCESSING_VERSION !== ""
    ? env.EMBEDDING_PREPROCESSING_VERSION
    : "v1";
  if (preprocessingVersion !== "v1") throw new ConfigError("EMBEDDING_PREPROCESSING_VERSION: only v1 is implemented");

  return {
    authToken,
    dataDir: path.resolve(dataDirRaw),
    port,
    host,
    embedding: { mode, baseUrl, modelId, apiKey, preprocessingVersion, timeoutMs },
  };
}
