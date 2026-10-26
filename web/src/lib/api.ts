// Thin typed client over the GreenOps Verify v1 API (docs/API_REFERENCE.md).
// The browser never decides authority: it sends the bearer token, an Idempotency-Key per user action, and
// renders whatever the server says (next_allowed_actions, blockers, labels).

/* eslint-disable @typescript-eslint/no-explicit-any */
export type Json = any;

export interface Resource<T = Json> {
  schema_version: string;
  id: string;
  status: string | null;
  runtime_mode: string | null;
  result_kind: string | null;
  data_origin: string | null;
  next_allowed_actions: string[];
  blockers: string[];
  request_id: string;
  data: T;
}

export interface Page<T = Json> {
  items: T[];
  next_cursor: string | null;
  request_id: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Json;
  retryable?: boolean;
  request_id?: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: Json;
  retryable: boolean;
  requestId?: string;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message || body.code);
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.retryable = !!body.retryable;
    this.requestId = body.request_id;
  }
}

const TOKEN_KEY = "greenops.token";
let token: string | null = null;
try {
  token = sessionStorage.getItem(TOKEN_KEY);
} catch {
  token = null;
}

export function getToken(): string | null {
  return token;
}

export function setToken(t: string | null) {
  token = t;
  try {
    if (t) sessionStorage.setItem(TOKEN_KEY, t);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* sessionStorage unavailable: keep the token in memory only */
  }
}

export function uuid(): string {
  const c: Crypto = globalThis.crypto;
  if (typeof c.randomUUID === "function") return c.randomUUID();
  // RFC4122 v4 fallback (randomUUID needs a secure context)
  const b = new Uint8Array(16);
  c.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

async function request<T>(method: string, path: string, body?: Json, idempotencyKey?: string, tokenOverride?: string): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = tokenOverride ?? token;
  if (t) headers.Authorization = `Bearer ${t}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  let res: Response;
  try {
    // no-store: identical concurrent GETs otherwise wait on Chrome's HTTP cache lock (observed ~15 s stalls).
    res = await fetch(path, { method, headers, cache: "no-store", body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (e) {
    throw new ApiError(0, {
      code: "NETWORK_ERROR",
      message: "The API did not respond. Check that it is running on port 8000. A timed-out write is not proof of failure: retry with the same action or re-read the record.",
    });
  }
  const text = await res.text();
  let parsed: Json = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = null;
  }
  if (!res.ok) {
    if (parsed?.error) throw new ApiError(res.status, parsed.error);
    if (res.status === 404) throw new ApiError(404, { code: "NOT_FOUND", message: parsed?.detail ?? "Not found" });
    if (res.status >= 500) {
      // No error envelope: the dev proxy or a restarting API dropped the connection. The outcome of a write is unknown.
      throw new ApiError(res.status, {
        code: "UPSTREAM_UNAVAILABLE",
        retryable: true,
        message: "The API connection dropped before a reply (it may be restarting). For a write, the outcome is unknown: retry with the same request key or re-read the record.",
      });
    }
    if (res.status === 422 && Array.isArray(parsed?.detail)) {
      throw new ApiError(422, { code: "VALIDATION_ERROR", message: parsed.detail.map((d: Json) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; "), details: parsed.detail });
    }
    throw new ApiError(res.status, { code: `HTTP_${res.status}`, message: parsed?.detail ?? (text.slice(0, 200) || res.statusText) });
  }
  return parsed as T;
}

// Share one in-flight GET per path: several panels often read the same evidence record at once.
const inflight = new Map<string, Promise<unknown>>();
function dedupedGet<T>(path: string, tokenOverride?: string): Promise<T> {
  const key = `${tokenOverride ?? token ?? ""}|${path}`;
  const hit = inflight.get(key);
  if (hit) return hit as Promise<T>;
  const p = request<T>("GET", path, undefined, undefined, tokenOverride).finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

export const api = {
  get: <T = Json>(path: string, tokenOverride?: string) => dedupedGet<T>(path, tokenOverride),
  /** Mutations always carry an Idempotency-Key. Callers generate one per user action and reuse it on retry. */
  post: <T = Json>(path: string, body: Json, idempotencyKey: string) => request<T>("POST", path, body, idempotencyKey),
};

// ---- Typed shapes for the routes the UI reads (only the fields we use; the server may add more) ----

export interface Me {
  actor_id: string;
  display_name: string;
  role: "viewer" | "operator" | "admin" | string;
  runtime_mode: string;
  sandbox_writes_enabled: boolean;
  tenant_id: string;
}

export interface Check {
  check_id: string;
  status: string;
  detail?: string | null;
  measured?: string | null;
  limit?: string | null;
}

export interface Critic {
  verdict?: string;
  note?: string;
  check_ids?: string[];
  evidence_ids?: string[];
  evidence_requests?: Json[];
  candidate_ref?: string;
  trial?: { status?: string; trial_id?: string; critic?: Critic };
  enforcement?: Json;
  enforcement_notes?: Json;
}

export interface PlanSummary {
  id: string;
  path: "cloud" | "ai" | string;
  status: string;
  candidate_no?: number;
  revision?: number;
  action_type?: string;
  executor?: string;
  target_key?: string;
  plan_hash?: string;
  rationale?: string;
  stale_reason?: string | null;
  screening?: { checks?: Check[]; outcome?: string; signature?: string; version?: string };
  critic?: Critic;
  impacts?: Json;
  projection?: Json;
  memory_refs?: Json[];
  updated_at?: string;
}

export interface TrialSummary {
  id: string;
  plan_id?: string;
  status: string;
  suite_id?: string;
  trial_hash?: string;
  finished_at?: string;
}

export interface MemoryItem {
  memory_id: string;
  engine_memory_id?: string;
  kind?: string;
  finding?: string;
  signature?: string;
  source_ref?: string;
  score?: number;
  applicable?: boolean;
  applicability?: Record<string, string | null>;
  inapplicable_reasons?: string[];
  evidence_refs?: string[];
}

export interface InvestigationData {
  investigation: Json;
  progress?: Json;
  plans?: PlanSummary[];
  trials?: TrialSummary[];
  actions?: Json[];
  evidence?: { id: string; kind: string; subject: string | null }[];
  federation?: Json;
  forecast?: Record<string, Json>;
  memory?: { status?: string; applicable?: MemoryItem[]; historical?: MemoryItem[]; queries?: string[]; embedding_profile?: Json; engine?: Json; excluded_unscoped?: Json };
  investigator?: Json;
  outcome?: Json;
  feedback?: Json[];
  queue_order?: string;
}

export interface InvestigationEvent {
  seq: number;
  at: string;
  kind: string;
  actor: string;
  payload: Json;
}

export interface Overview {
  request_id: string;
  runtime_mode: string;
  service_id: string;
  generated_at: string;
  investigations: { total: number; by_status: Record<string, number> };
  plans: { total: number; by_status: Record<string, number> };
  savings: { proposed_monthly_usd: string | null; verified_monthly_usd: string | null; blocked_monthly_usd?: string | null; latest_investigation_id?: string | null; basis: string };
  carbon: { proposed_monthly_kgco2e: string | null; basis: string };
  rejections_by_check: { check_id: string; count?: number; n?: number }[];
  memory: { status: string; semantic: boolean | null; embedding_model: string | null; records: number | null; recalls: number; applicable_hits: number; engine?: string; engine_sha?: string; pending?: number };
  federation: { mode: string; sources: { group: string; name: string }[]; receipts: number; last_receipt_at: string | null };
  model: { agent_model_id: string | null; copilot_model_id: string | null };
  recent: { at: string; kind: string; investigation_id: string; summary: string; actor?: string }[];
}

export interface CopilotToolCall {
  tool: string;
  input?: Json;
  ok?: boolean;
  duration_ms?: number;
}
export interface CopilotCitation {
  kind: "investigation" | "plan" | "trial" | "action" | "evidence" | "memory" | "report" | string;
  id: string;
  label?: string;
}
export interface CopilotReply {
  conversation_id: string;
  message_id: string;
  reply: string;
  model_id?: string;
  tool_calls?: CopilotToolCall[];
  citations?: CopilotCitation[];
  suggested_prompts?: string[];
}
export interface CopilotMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  at?: string;
  tool_calls?: CopilotToolCall[];
  citations?: CopilotCitation[];
  model_id?: string;
}
