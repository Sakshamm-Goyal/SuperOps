// Strict, hand-written request validation. Unknown fields are rejected everywhere.

export class ValidationError extends Error {
  constructor(public field: string, message: string) {
    super(`${field}: ${message}`);
  }
}

export const MEMORY_KINDS = [
  "screening_rejection",
  "rejected_trial",
  "validated_plan",
  "verified_outcome",
  "ai_eval_aggregate",
  "correction",
] as const;
export type MemoryKind = (typeof MEMORY_KINDS)[number];

export interface Scope {
  tenant_id: string;
  service_id: string;
}
export interface TargetScope extends Scope {
  target_id: string | null;
}
export interface Applicability {
  policy_version: string;
  workload_version: string;
  config_version: string;
  model_version: string | null;
  test_version: string | null;
}
export interface RememberRequest {
  application_receipt_id: string;
  kind: MemoryKind;
  scope: TargetScope;
  finding: string;
  evidence_refs: string[];
  applicability: Applicability;
  content_hash: string;
  supersedes_receipt_id: string | null;
  correction_review_id: string | null;
  tags: string[];
}
export interface RecallRequest {
  scope: Scope;
  query: string;
  applicability: Applicability;
  top_k: number;
  threshold: number;
}

const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const HASH_RE = /^sha256:[0-9a-f]{64}$/;
// eslint-disable-next-line no-control-regex
const CONTROL_RE = /[\u0000-\u001f\u007f]/;

function obj(v: unknown, field: string, allowed: readonly string[], required: readonly string[]): Record<string, unknown> {
  if (v === null || typeof v !== "object" || Array.isArray(v)) throw new ValidationError(field, "must be an object");
  const o = v as Record<string, unknown>;
  for (const k of Object.keys(o)) {
    if (!allowed.includes(k)) throw new ValidationError(field === "body" ? k : `${field}.${k}`, "unknown field");
  }
  for (const k of required) {
    if (!(k in o)) throw new ValidationError(field === "body" ? k : `${field}.${k}`, "is required");
  }
  return o;
}

function str(v: unknown, field: string, min: number, max: number, opts: { multiline?: boolean } = {}): string {
  if (typeof v !== "string") throw new ValidationError(field, "must be a string");
  if (v.length < min || v.length > max) throw new ValidationError(field, `length must be ${min}..${max}`);
  if (min > 0 && v.trim().length === 0) throw new ValidationError(field, "must not be blank");
  if (!opts.multiline && CONTROL_RE.test(v)) throw new ValidationError(field, "must not contain control characters");
  if (opts.multiline && /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(v)) {
    throw new ValidationError(field, "must not contain control characters");
  }
  return v;
}

function nullableStr(v: unknown, field: string, min: number, max: number): string | null {
  return v === null ? null : str(v, field, min, max);
}

export function uuid(v: unknown, field: string): string {
  if (typeof v !== "string" || !UUID_RE.test(v)) throw new ValidationError(field, "must be a UUID");
  return v.toLowerCase();
}

function strArray(v: unknown, field: string, maxItems: number, maxLen: number): string[] {
  if (!Array.isArray(v)) throw new ValidationError(field, "must be an array of strings");
  if (v.length > maxItems) throw new ValidationError(field, `at most ${maxItems} items`);
  return v.map((x, i) => str(x, `${field}[${i}]`, 1, maxLen));
}

export function scopeId(v: unknown, field: string): string {
  return str(v, field, 1, 128);
}

function scope(v: unknown, field: string): Scope {
  const o = obj(v, field, ["tenant_id", "service_id"], ["tenant_id", "service_id"]);
  return { tenant_id: scopeId(o.tenant_id, `${field}.tenant_id`), service_id: scopeId(o.service_id, `${field}.service_id`) };
}

function targetScope(v: unknown, field: string): TargetScope {
  const o = obj(v, field, ["tenant_id", "service_id", "target_id"], ["tenant_id", "service_id", "target_id"]);
  return {
    tenant_id: scopeId(o.tenant_id, `${field}.tenant_id`),
    service_id: scopeId(o.service_id, `${field}.service_id`),
    target_id: nullableStr(o.target_id, `${field}.target_id`, 1, 512),
  };
}

const APPLICABILITY_FIELDS = ["policy_version", "workload_version", "config_version", "model_version", "test_version"] as const;

function applicability(v: unknown, field: string): Applicability {
  const o = obj(v, field, APPLICABILITY_FIELDS, APPLICABILITY_FIELDS);
  return {
    policy_version: str(o.policy_version, `${field}.policy_version`, 1, 200),
    workload_version: str(o.workload_version, `${field}.workload_version`, 1, 200),
    config_version: str(o.config_version, `${field}.config_version`, 1, 200),
    model_version: nullableStr(o.model_version, `${field}.model_version`, 1, 200),
    test_version: nullableStr(o.test_version, `${field}.test_version`, 1, 200),
  };
}

export function parseRemember(body: unknown): RememberRequest {
  const o = obj(
    body,
    "body",
    ["application_receipt_id", "kind", "scope", "finding", "evidence_refs", "applicability", "content_hash",
      "supersedes_receipt_id", "correction_review_id", "tags"],
    ["application_receipt_id", "kind", "scope", "finding", "evidence_refs", "applicability", "content_hash"]
  );
  if (typeof o.kind !== "string" || !(MEMORY_KINDS as readonly string[]).includes(o.kind)) {
    throw new ValidationError("kind", `must be one of ${MEMORY_KINDS.join(", ")}`);
  }
  if (typeof o.content_hash !== "string" || !HASH_RE.test(o.content_hash)) {
    throw new ValidationError("content_hash", "must match sha256:<64 lowercase hex>");
  }
  const supersedes = o.supersedes_receipt_id === undefined || o.supersedes_receipt_id === null
    ? null
    : uuid(o.supersedes_receipt_id, "supersedes_receipt_id");
  const review = o.correction_review_id === undefined || o.correction_review_id === null
    ? null
    : str(o.correction_review_id, "correction_review_id", 1, 200);
  if (supersedes && !review) {
    throw new ValidationError("correction_review_id", "is required when supersedes_receipt_id is set");
  }
  const receiptId = uuid(o.application_receipt_id, "application_receipt_id");
  if (supersedes && supersedes === receiptId) throw new ValidationError("supersedes_receipt_id", "must differ from application_receipt_id");
  return {
    application_receipt_id: receiptId,
    kind: o.kind as MemoryKind,
    scope: targetScope(o.scope, "scope"),
    finding: str(o.finding, "finding", 1, 2000, { multiline: true }),
    evidence_refs: strArray(o.evidence_refs, "evidence_refs", 50, 512),
    applicability: applicability(o.applicability, "applicability"),
    content_hash: o.content_hash,
    supersedes_receipt_id: supersedes,
    correction_review_id: review,
    tags: o.tags === undefined ? [] : strArray(o.tags, "tags", 20, 64),
  };
}

export function parseRecall(body: unknown): RecallRequest {
  const o = obj(body, "body", ["scope", "query", "applicability", "top_k", "threshold"], ["scope", "query", "applicability"]);
  let topK = 5;
  if (o.top_k !== undefined) {
    if (typeof o.top_k !== "number" || !Number.isInteger(o.top_k) || o.top_k < 1 || o.top_k > 10) {
      throw new ValidationError("top_k", "must be an integer 1..10");
    }
    topK = o.top_k;
  }
  let threshold = 0.2;
  if (o.threshold !== undefined) {
    if (typeof o.threshold !== "number" || !Number.isFinite(o.threshold) || o.threshold < 0 || o.threshold > 1) {
      throw new ValidationError("threshold", "must be a finite number 0..1");
    }
    threshold = o.threshold;
  }
  return {
    scope: scope(o.scope, "scope"),
    query: str(o.query, "query", 1, 1000, { multiline: true }),
    applicability: applicability(o.applicability, "applicability"),
    top_k: topK,
    threshold,
  };
}

export function parseEmptyBody(body: unknown): void {
  obj(body, "body", [], []);
}
