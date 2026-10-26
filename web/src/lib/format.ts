// Presentation rules (port of greenops/ui/present.py). Every status carries text plus an icon; colour is only a cue.
import type { Json, PlanSummary, Check } from "./api";

export type Tone = "ok" | "fail" | "attention" | "progress" | "neutral" | "unknown" | "restored";

const STATUS_TONE: Record<string, Tone> = {
  PASS: "ok", PASSED: "ok", ready: "ok", complete: "ok", VERIFIED: "ok", VALIDATED: "ok", COMPLETED: "ok", SENT: "ok",
  ACTIVE: "ok", ELIGIBLE_FOR_TRIAL: "ok", SUCCEEDED: "ok", live: "ok", configured: "ok", used: "ok",
  RECOVERED: "restored",
  FAIL: "fail", FAILED: "fail", REJECTED: "fail", REJECT: "fail", unavailable: "fail", RECOVERY_REQUIRED: "fail",
  UNKNOWN: "unknown", unknown: "unknown",
  INCOMPLETE: "attention", partial: "attention", AWAITING_APPROVAL: "attention", NEEDS_REVIEW: "attention",
  NEEDS_EVIDENCE: "attention", STALE: "attention", APPROVED: "attention", degraded: "attention",
  PENDING_VERIFICATION: "attention", PENDING: "attention", EXPIRED: "attention", REVISE: "attention",
  QUEUED: "progress", RUNNING: "progress", EXECUTING: "progress", RECOVERING: "progress",
  REVOKED: "neutral", CANCEL_REQUESTED: "neutral", DRAFT: "neutral", NO_CHANGE: "neutral", CANCELLED: "neutral",
  NOT_REQUIRED: "neutral", SKIPPED: "neutral", off: "neutral",
};

export function tone(status: unknown): Tone {
  if (status === null || status === undefined || status === "") return "unknown";
  return STATUS_TONE[String(status)] ?? "neutral";
}

export const STATUS_MEANING: Record<string, string> = {
  DRAFT: "Draft — next step is a sandbox trial or more evidence",
  NEEDS_EVIDENCE: "Evidence required before this can be screened",
  REJECTED: "A required check failed; the reason is retained",
  VALIDATED: "Checks passed",
  AWAITING_APPROVAL: "Checks and trial passed — waiting for human review",
  APPROVED: "Scoped approval recorded; execution is still pending",
  STALE: "The plan or approval no longer matches current facts",
  QUEUED: "Accepted and waiting for the worker",
  RUNNING: "Work in progress",
  EXECUTING: "Change in progress — the effect is not yet verified",
  PENDING_VERIFICATION: "Change applied — effect not yet verified; do not retry",
  VERIFIED: "Intended state and required health checks confirmed",
  RECOVERY_REQUIRED: "Human intervention needed; see recovery details",
  RECOVERING: "Restoring the exact prior configuration",
  RECOVERED: "Prior configuration restored and read back; the intended change is not in effect",
  FAILED: "Operation failed; see the precise outcome",
  NO_CHANGE: "Investigation completed without an acceptable change — a justified result",
  NEEDS_REVIEW: "Investigation finished; candidates need human review",
  COMPLETED: "Investigation completed with a verified change",
  CANCELLED: "Cancelled at a safe boundary",
  CANCEL_REQUESTED: "Cancel requested; stops at the next safe stage boundary",
  INCOMPLETE: "The trial could not produce a comparable result; the candidate was not judged",
  PASSED: "Every trial check passed",
};

export const MODE_LABELS: Record<string, string> = {
  sample: "Sample data",
  connected_demo: "Connected demo",
  replay: "Recorded replay",
};

export function modeLabel(mode: string | null | undefined): string {
  if (!mode) return "Unknown mode";
  return MODE_LABELS[mode] ?? `Unknown mode (${mode})`;
}

export function humanize(s: string | null | undefined): string {
  if (!s) return "—";
  return s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

/** Display-only rounding of decimal strings. Missing values stay explicit. */
export function num(value: unknown, places = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString("en-US", { maximumFractionDigits: places, minimumFractionDigits: 0 });
}

export function money(value: unknown, currency = "USD", places = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  const sym = currency === "USD" ? "$" : "";
  const s = Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: places, minimumFractionDigits: Math.min(places, 2) });
  return `${n < 0 ? "−" : ""}${sym}${s}${sym ? "" : ` ${currency}`}`;
}

export function pct(fraction: unknown, places = 1): string {
  if (fraction === null || fraction === undefined || fraction === "") return "—";
  const n = Number(fraction);
  if (!Number.isFinite(n)) return String(fraction);
  return `${(n * 100).toFixed(places)}%`;
}

export function ts(value: unknown): string {
  if (!value) return "—";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return `${d.toISOString().slice(0, 10)} ${d.toISOString().slice(11, 19)} UTC`;
}

export function shortTs(value: unknown): string {
  if (!value) return "—";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
}

export function ago(value: unknown, now = Date.now()): string {
  if (!value) return "—";
  const t = new Date(String(value)).getTime();
  if (Number.isNaN(t)) return String(value);
  const s = Math.round((now - t) / 1000);
  if (s < 0) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function shortId(v: unknown): string {
  return v ? String(v).slice(0, 8) : "—";
}

export function shortHash(v: unknown, n = 10): string {
  if (!v) return "—";
  const s = String(v);
  const [algo, digest] = s.includes(":") ? s.split(":", 2) : ["", s];
  return `${algo ? algo + ":" : ""}${digest.slice(0, n)}…${digest.slice(-4)}`;
}

export function signatureParts(sig: string | undefined | null): { path: string; target: string; change: string } {
  if (!sig) return { path: "", target: "—", change: "—" };
  const [path, ...rest] = sig.split(":");
  const body = rest.join(":");
  if (path === "cloud") {
    const i = body.lastIndexOf(":");
    const key = body.slice(0, i);
    return { path, target: key.split("/").slice(-1)[0] || key, change: body.slice(i + 1) };
  }
  if (path === "ai") return { path, target: "support AI workflow", change: body.split(",").join(" · ") };
  return { path, target: body, change: "" };
}

export function planTitle(p: PlanSummary): string {
  const s = signatureParts(p.screening?.signature);
  if (p.path === "cloud") {
    const from = p.projection?.from_machine_type;
    return `${s.target} → ${s.change}${from ? ` (from ${from})` : ""}`;
  }
  if (p.path === "ai") {
    const ctx = /policy_context=([a-z_]+)/.exec(p.screening?.signature ?? "")?.[1];
    return ctx ? `Support workflow · policy context “${ctx.replace(/_/g, " ")}”` : "Support workflow config";
  }
  return p.screening?.signature ?? p.id;
}

export function environmentOf(targetKey: string | null | undefined): string {
  const t = targetKey ?? "";
  if (t.startsWith("local/sandbox/")) return "local sandbox";
  if (t.includes("-prod") || t.includes("/prod")) return "production (not executable)";
  if (t.includes("staging") || t.includes("-stg")) return "staging";
  return "unknown";
}

export function checkOf(p: PlanSummary | Json, id: string): Check | undefined {
  return (p?.screening?.checks ?? []).find((c: Check) => c.check_id === id);
}

export function failingChecks(p: PlanSummary): Check[] {
  return (p.screening?.checks ?? []).filter((c) => c.status !== "PASS");
}

export function planReason(p: PlanSummary, feedback: Json[] = []): string {
  const bad = failingChecks(p);
  if (bad.length) {
    return `${p.status === "REJECTED" ? "Rejected" : "Attention"}: ` + bad.map((c) => `${c.check_id} ${c.status}: ${c.detail ?? ""}`).join("; ");
  }
  const trial = p.critic?.trial;
  if (trial?.status === "FAILED" || trial?.status === "INCOMPLETE") {
    const f = feedback.find((x) => x.trial_id === trial.trial_id || (x.signature === p.screening?.signature && x.trial_id));
    if (f) return `Trial ${trial.status.toLowerCase()}: ${f.reasons}`;
    return `Trial ${trial.status.toLowerCase()} (trial ${shortId(trial.trial_id)})`;
  }
  if (p.stale_reason) return `Stale: ${p.stale_reason}`;
  return STATUS_MEANING[p.status] ?? p.status;
}

export function impactBasis(imp: Json): string {
  if (!imp) return "Unknown";
  if (imp.basis) return imp.basis;
  switch (imp.result_kind) {
    case "projected": return "Projected at dated rate";
    case "measured": return "Measured workload";
    case "observed": return "Observed billing";
    case "estimated": return "Estimated";
  }
  return imp.reason ? `Unknown — ${imp.reason}` : "Unknown";
}

export const KIND_LABEL: Record<string, string> = {
  sample: "Sample",
  synthetic: "Synthetic",
  estimated: "Estimated",
  replayed: "Replayed",
  measured: "Measured",
  projected: "Projected",
  observed: "Observed",
  unknown: "Unknown",
  connected_demo: "Connected demo",
  replay: "Recorded replay",
  human: "Human decision",
};

export function usageBasisLabel(b: string | null | undefined): string {
  if (b === "provider") return "provider-reported usage";
  if (b === "scripted_estimate") return "scripted estimate (not provider billing)";
  return b ? `unknown basis (${b})` : "unknown basis";
}

export const CHECK_LABEL: Record<string, string> = {
  "CHK-IDENTITY": "Resource identity",
  "CHK-COVERAGE-CPU": "CPU coverage",
  "CHK-COVERAGE-MEM": "Memory coverage",
  "CHK-FRESHNESS": "Data freshness",
  "CHK-CPU-PEAK": "Peak CPU",
  "CHK-CPU-STRESS": "Forecast stress",
  "CHK-MEM-PEAK": "Peak memory",
  "CHK-COMPAT": "Machine compatibility",
  "CHK-POLICY": "Policy",
  "CHK-ECONOMICS": "Economics",
  "AI-POLICY": "Policy",
  "AI-CHANGED": "Config changed",
  "AI-USAGE-EVIDENCE": "Usage evidence",
  "AI-DEDUPE-BASIS": "Dedupe basis",
  "AI-TRIAL-REQUIRED": "Trial required",
  "AI-QUALITY-GATE": "Quality gate",
  "AI-ZERO-CRITICAL": "Zero critical failures",
  "AI-NO-REGRESSION": "No regression",
  "AI-COST-PER-ACCEPTED": "Cost per accepted task",
  "TRIAL-COMPARABLE": "Comparable load",
  "TRIAL-NO-NEW-FAILURES": "No new failures",
  "TRIAL-P95-REGRESSION": "p95 regression",
  "TRIAL-P95-SLO": "p95 within SLO",
  "MEM-PRIOR-FAILURE": "Prior failure (memory)",
};

export function checkLabel(id: string): string {
  return CHECK_LABEL[id] ?? id;
}

export const EVENT_LABEL: Record<string, string> = {
  "investigation.created": "Investigation created",
  "stage.entered": "Stage entered",
  "model.coordinator": "Coordinator scoped the run",
  "model.investigator": "Investigator read the evidence",
  "model.optimizer": "Optimizer proposed candidates",
  "model.critic": "Critic reviewed candidates",
  "plan.proposed": "Plan proposed & screened",
  "plan.reviewed": "Critic verdict recorded",
  "plan.rescreened": "Plan revised and re-screened",
  "plan.validated": "Plan validated by trial",
  "plan.post_trial": "Post-trial review",
  "trial.queued": "Trial queued",
  "trial.finished": "Trial finished",
  "candidate.discarded": "Candidate discarded",
  "investigation.finalized": "Investigation finalized",
  "investigation.cancel_requested": "Cancel requested",
  "memory.recalled": "Memory recalled",
  "evidence.retrieved": "Evidence retrieved",
  "investigation.failed": "Investigation failed",
  "investigation.cancelled": "Investigation cancelled",
  "candidate.rejected": "Candidate rejected",
  "plan.stale": "Plan became stale",
  "trial.cancelled": "Trial cancelled",
  "approval.created": "Approval recorded",
  "approval.expired": "Approval expired",
  "approval.revoked": "Approval revoked",
  "action.queued": "Action queued",
  "action.executing": "Action executing",
  "action.verified": "Change verified",
  "action.failed": "Action failed",
  "action.recovered": "Prior config restored",
  "action.recovery_required": "Action needs recovery",
  "action.resolved_manually": "Action resolved manually",
};

export function eventLabel(kind: string): string {
  return EVENT_LABEL[kind] ?? humanize(kind.replace(/\./g, " "));
}

/** Autopilot (drift-triggered) investigations: actor `autopilot`, question prefixed "Autopilot (". */
export function isAutopilot(inv: { question?: string; actor_id?: string } | null | undefined): boolean {
  if (!inv) return false;
  return inv.actor_id === "autopilot" || String(inv.question ?? "").startsWith("Autopilot (");
}
