import { useEffect, useState, type ReactNode, type ButtonHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { createPortal } from "react-dom";
import {
  AlertTriangle, Ban, Check, CheckCircle2, CircleDashed, CircleHelp, Copy, HardHat, Hourglass, Loader2, RotateCcw,
  X, XCircle, Clock3, Bot, Minus, Cloud, type LucideIcon,
} from "lucide-react";
import { tone, type Tone, humanize, STATUS_MEANING, KIND_LABEL } from "../lib/format";
import type { ApiError } from "../lib/api";

export function cx(...c: (string | false | null | undefined)[]): string {
  return c.filter(Boolean).join(" ");
}

const TONE_STYLE: Record<Tone, { cls: string; icon: LucideIcon }> = {
  ok: { cls: "bg-pass-bg text-pass ring-pass/20", icon: CheckCircle2 },
  fail: { cls: "bg-fail-bg text-fail ring-fail/20", icon: XCircle },
  attention: { cls: "bg-warn-bg text-warn ring-warn/25", icon: AlertTriangle },
  progress: { cls: "bg-accent-50 text-accent ring-accent/20", icon: Loader2 },
  neutral: { cls: "bg-lav text-ink-2 ring-line-2", icon: CircleDashed },
  unknown: { cls: "bg-unk-bg text-unk ring-unk/20", icon: CircleHelp },
  restored: { cls: "bg-accent-50 text-accent-700 ring-accent/20", icon: RotateCcw },
};

// Outcomes sharing a tone still need distinct icons (UX_SPEC).
const STATUS_ICON: Record<string, LucideIcon> = {
  RECOVERY_REQUIRED: HardHat,
  PENDING_VERIFICATION: Clock3,
  EXECUTING: Hourglass,
  REVOKED: Ban,
  WAIVED: Minus,
  EXPIRED: Clock3,
  AWAITING_APPROVAL: Clock3,
};

export function StatusChip({ status, size = "sm", label, title }: { status: string | null | undefined; size?: "xs" | "sm" | "md"; label?: string; title?: string }) {
  const t = tone(status);
  const s = TONE_STYLE[t];
  const Icon = (status && STATUS_ICON[status]) || s.icon;
  const text = label ?? (status === "WAIVED" ? "waived by policy" : status ? status.replace(/_/g, " ") : "UNKNOWN");
  return (
    <span
      title={title ?? (status ? STATUS_MEANING[status] : "No status recorded")}
      className={cx(
        "inline-flex items-center gap-1 rounded-full ring-1 ring-inset font-semibold uppercase tracking-wide whitespace-nowrap",
        size === "xs" && "px-1.5 py-0.5 text-[10px]",
        size === "sm" && "px-2 py-0.5 text-[11px]",
        size === "md" && "px-2.5 py-1 text-xs",
        s.cls,
      )}
    >
      <Icon className={cx(size === "md" ? "size-3.5" : "size-3", t === "progress" && "animate-spin")} aria-hidden />
      {text}
    </span>
  );
}

/** Data-provenance label: sample / synthetic / estimated / replayed / measured / projected / unknown. Never merged. */
export function KindBadge({ kind, prefix }: { kind: string | null | undefined; prefix?: string }) {
  const k = kind ?? "unknown";
  const styles: Record<string, string> = {
    measured: "border-pass/40 text-pass bg-pass-bg/60",
    real_permitted: "border-pass/40 text-pass bg-pass-bg/60",
    observed: "border-pass/40 text-pass bg-pass-bg/60",
    projected: "border-dashed border-accent/50 text-accent bg-accent-50",
    estimated: "border-dashed border-warn/50 text-warn bg-warn-bg/60",
    synthetic: "border-dashed border-unk/40 text-unk bg-unk-bg/60",
    sample: "border-dashed border-unk/40 text-unk bg-unk-bg/60",
    replayed: "border-dotted border-ink-2/40 text-ink-2 bg-lav",
    replay: "border-dotted border-ink-2/40 text-ink-2 bg-lav",
    unknown: "border-unk/40 text-unk bg-unk-bg",
  };
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap", styles[k] ?? "border-line-2 text-muted bg-white")}>
      {prefix && <span className="text-faint font-normal">{prefix}</span>}
      {KIND_LABEL[k] ?? humanize(k)}
    </span>
  );
}

export function Pill({ icon: Icon, children, className, tone: t = "default" }: { icon?: LucideIcon; children: ReactNode; className?: string; tone?: "default" | "accent" | "dark" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
        t === "default" && "bg-white text-ink-2 ring-1 ring-line shadow-sm",
        t === "accent" && "bg-accent-50 text-accent ring-1 ring-accent-100",
        t === "dark" && "bg-ink text-white",
        className,
      )}
    >
      {Icon && <Icon className="size-3.5" aria-hidden />}
      {children}
    </span>
  );
}

type BtnVariant = "primary" | "secondary" | "ghost" | "danger" | "dark";
export function Button({ variant = "primary", size = "md", icon: Icon, loading, children, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: "sm" | "md" | "lg"; icon?: LucideIcon; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]",
        size === "sm" && "h-8 px-3 text-xs",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-12 px-6 text-[15px]",
        variant === "primary" && "bg-accent text-white shadow-[0_6px_20px_-8px_rgb(36_56_245/0.7)] hover:bg-accent-600",
        variant === "secondary" && "bg-white text-ink ring-1 ring-line-2 hover:ring-accent/40 hover:text-accent",
        variant === "ghost" && "text-ink-2 hover:bg-lav",
        variant === "danger" && "bg-white text-fail ring-1 ring-fail/30 hover:bg-fail-bg",
        variant === "dark" && "bg-ink text-white hover:bg-ink-2",
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : Icon ? <Icon className="size-4" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Card({ children, className, as: As = "section" }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" }) {
  return <As className={cx("card", className)}>{children}</As>;
}

export function CardHeader({ title, eyebrow, icon: Icon, right, sub }: { title: ReactNode; eyebrow?: ReactNode; icon?: LucideIcon; right?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 pb-3 sm:px-6">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">{eyebrow}</div>}
        <h3 className="flex items-center gap-2 font-display text-[17px] font-bold tracking-tight text-ink">
          {Icon && (
            <span className="grid size-7 place-items-center rounded-lg bg-accent-50 text-accent">
              <Icon className="size-4" aria-hidden />
            </span>
          )}
          {title}
        </h3>
        {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
      </div>
      {right && <div className="flex shrink-0 items-center gap-2">{right}</div>}
    </div>
  );
}

export function Stat({ label, value, sub, icon: Icon, accent, footnote }: { label: string; value: ReactNode; sub?: ReactNode; icon?: LucideIcon; accent?: boolean; footnote?: ReactNode }) {
  return (
    <div className={cx("card relative overflow-hidden p-5", accent && "bg-accent text-white border-accent")}>
      <div className="flex items-center justify-between">
        <span className={cx("text-[13px] font-medium", accent ? "text-white/80" : "text-muted")}>{label}</span>
        {Icon && (
          <span className={cx("grid size-8 place-items-center rounded-full", accent ? "bg-white/15 text-white" : "bg-accent-50 text-accent")}>
            <Icon className="size-4" aria-hidden />
          </span>
        )}
      </div>
      <div className={cx("mt-3 font-display text-[34px] font-bold leading-none tracking-tight", accent ? "text-white" : "text-ink")}>{value}</div>
      {sub && <div className={cx("mt-2 text-xs", accent ? "text-white/75" : "text-muted")}>{sub}</div>}
      {footnote && <div className={cx("mt-3 border-t pt-2 text-[11px]", accent ? "border-white/20 text-white/70" : "border-line text-faint")}>{footnote}</div>}
    </div>
  );
}

export function Empty({ icon: Icon = CircleDashed, title, children, action }: { icon?: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-2 bg-white/60 px-6 py-10 text-center">
      <span className="grid size-11 place-items-center rounded-2xl bg-lav text-accent">
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="mt-3 font-display text-base font-bold text-ink">{title}</div>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

const ERROR_HINT: Record<string, string> = {
  APPROVAL_STALE: "The target or policy changed since approval. Gather fresh evidence and request a new approval.",
  APPROVAL_EXPIRED: "The 15-minute approval window passed. Approve the exact plan and trial again.",
  PLAN_CHANGED: "The plan hash no longer matches. Reload the plan and review it again.",
  TARGET_BUSY: "Another change holds the target lock. Wait for it to finish.",
  IDEMPOTENCY_CONFLICT: "This action key was already used with a different body. Start the action again.",
  INVALID_STATE: "The record is not in a state that allows this action. Reload to see the current state.",
  HOLDOUT_VERDICT_REQUIRED: "AI promotion needs a frozen holdout verdict from the independent evaluator.",
  TRIAL_NOT_ACCEPTED: "The trial did not pass, so the plan cannot be approved.",
  EVIDENCE_INCOMPLETE: "Evidence was incomplete; the plan cannot move forward until it is complete.",
  FORBIDDEN: "Your role does not allow this action.",
  AUTH_REQUIRED: "Your session token is missing or no longer valid. Sign in again.",
  NETWORK_ERROR: "",
};

export function ErrorBox({ error, title }: { error: ApiError | null | undefined; title?: string }) {
  if (!error) return null;
  const hint = ERROR_HINT[error.code];
  return (
    <div role="alert" className="flex gap-3 rounded-2xl border border-fail/25 bg-fail-bg/70 p-4 text-sm">
      <XCircle className="mt-0.5 size-4 shrink-0 text-fail" aria-hidden />
      <div className="min-w-0">
        <div className="font-semibold text-fail">
          {title ?? "Request failed"} <span className="mono text-xs font-medium">· {error.code}{error.status ? ` · HTTP ${error.status}` : ""}</span>
        </div>
        <div className="mt-0.5 break-words text-ink-2">{error.message}</div>
        {hint && <div className="mt-1 text-muted">{hint}</div>}
        {error.requestId && <div className="mono mt-1 text-[11px] text-faint">request {error.requestId}</div>}
      </div>
    </div>
  );
}

export function Notice({ tone: t = "info", icon: Icon, title, children }: { tone?: "info" | "warn" | "ok" | "fail" | "unknown"; icon?: LucideIcon; title?: ReactNode; children?: ReactNode }) {
  const cls = {
    info: "border-accent/20 bg-accent-50/70 text-accent-700",
    warn: "border-warn/25 bg-warn-bg/70 text-warn",
    ok: "border-pass/25 bg-pass-bg/70 text-pass",
    fail: "border-fail/25 bg-fail-bg/70 text-fail",
    unknown: "border-unk/25 bg-unk-bg/70 text-unk",
  }[t];
  return (
    <div className={cx("flex gap-3 rounded-2xl border p-4 text-sm", cls)}>
      {Icon && <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />}
      <div className="min-w-0">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className="mt-0.5 text-ink-2">{children}</div>}
      </div>
    </div>
  );
}

export function KV({ rows, className }: { rows: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cx("divide-y divide-line text-sm", className)}>
      {rows.map(([k, v], i) => (
        <div key={i} className="grid grid-cols-[minmax(110px,38%)_1fr] gap-3 py-2">
          <dt className="text-muted">{k}</dt>
          <dd className="min-w-0 break-words text-ink">{v ?? <span className="text-faint">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CopyButton({ value, className }: { value: string; className?: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(false), 1400);
    return () => clearTimeout(t);
  }, [done]);
  return (
    <button
      type="button"
      aria-label="Copy to clipboard"
      onClick={() => navigator.clipboard?.writeText(value).then(() => setDone(true)).catch(() => undefined)}
      className={cx("grid size-6 place-items-center rounded-md text-faint hover:bg-lav hover:text-accent", className)}
    >
      {done ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  );
}

export function Hash({ value, n = 12, full }: { value: string | null | undefined; n?: number; full?: boolean }) {
  if (!value) return <span className="text-faint">—</span>;
  const [algo, digest] = value.includes(":") ? value.split(":", 2) : ["", value];
  return (
    <span className="inline-flex max-w-full items-center gap-1 align-middle">
      <span className="mono truncate text-[12px] text-ink-2" title={value}>
        {algo && <span className="text-faint">{algo}:</span>}
        {full ? digest : `${digest.slice(0, n)}…${digest.slice(-4)}`}
      </span>
      <CopyButton value={value} />
    </span>
  );
}

const RECORD_PATH: Record<string, string> = {
  investigation: "/app/investigations",
  plan: "/app/plans",
  trial: "/app/trials",
  action: "/app/actions",
  evidence: "/app/evidence",
  memory: "/app/memories",
  report: "/app/reports",
};

export function recordHref(kind: string, id: string): string {
  return `${RECORD_PATH[kind] ?? "/app"}/${id}`;
}

export function IdLink({ kind, id, label }: { kind: string; id: string | null | undefined; label?: ReactNode }) {
  if (!id) return <span className="text-faint">—</span>;
  return (
    <Link to={recordHref(kind, id)} className="mono inline-flex items-center gap-1 rounded-md bg-lav px-1.5 py-0.5 text-[12px] text-accent-700 hover:bg-accent-100">
      {label ?? id.slice(0, 8)}
    </Link>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-xl bg-line/70", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-72" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

export function PageHeader({ eyebrow, title, sub, right, chips }: { eyebrow?: ReactNode; title: ReactNode; sub?: ReactNode; right?: ReactNode; chips?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {eyebrow && <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.14em] text-faint">{eyebrow}</div>}
        <h1 className="display text-[30px] text-ink sm:text-[38px]">{title}</h1>
        {sub && <p className="mt-2 text-[15px] text-muted">{sub}</p>}
        {chips && <div className="mt-3 flex flex-wrap items-center gap-2">{chips}</div>}
      </div>
      {right && <div className="flex flex-wrap items-center gap-2">{right}</div>}
    </header>
  );
}

export function Drawer({ open, onClose, title, children, width = "max-w-xl" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string }) {
  useEffect(() => {
    if (!open) return;
    const f = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [open, onClose]);
  // Portal to <body>: animated (transformed) ancestors would otherwise become the containing block for `fixed`.
  return createPortal(
    <div className={cx("fixed inset-0 z-50 transition-[visibility] duration-300", !open && "invisible pointer-events-none")} aria-hidden={!open}>
      <div className={cx("absolute inset-0 bg-ink/25 backdrop-blur-[2px] transition-opacity", open ? "opacity-100" : "opacity-0")} onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        className={cx("absolute inset-y-0 right-0 flex w-full flex-col bg-white shadow-2xl transition-transform duration-300", width, open ? "translate-x-0" : "translate-x-full")}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="font-display text-lg font-bold text-ink">{title}</div>
          <button onClick={onClose} aria-label="Close" className="grid size-8 place-items-center rounded-full hover:bg-lav">
            <X className="size-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto scroll-thin">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}

export function Tabs<T extends string>({ tabs, value, onChange, stretch }: { tabs: { id: T; label: ReactNode; count?: number }[]; value: T; onChange: (t: T) => void; stretch?: boolean }) {
  return (
    <div className={cx("flex gap-1 overflow-x-auto rounded-full bg-lav p-1 scroll-thin", stretch && "[&>button]:flex-1 [&>button]:justify-center")} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1.5 text-[12.5px] font-semibold transition sm:px-3.5 sm:text-[13px]",
            value === t.id ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className={cx("rounded-full px-1.5 text-[11px] tnum", value === t.id ? "bg-accent-50 text-accent" : "bg-white/70 text-faint")}>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function CheckRow({ id, status, detail, measured, limit, label }: { id: string; status: string; detail?: string | null; measured?: string | null; limit?: string | null; label?: string }) {
  const t = tone(status);
  return (
    <li className="flex items-start gap-3 py-2.5">
      <span className={cx("mt-0.5 grid size-5 shrink-0 place-items-center rounded-full", t === "ok" ? "bg-pass-bg text-pass" : t === "fail" ? "bg-fail-bg text-fail" : t === "unknown" ? "bg-unk-bg text-unk" : "bg-warn-bg text-warn")}>
        {status === "WAIVED" ? <Minus className="size-3" strokeWidth={3} /> : t === "ok" ? <Check className="size-3" strokeWidth={3} /> : t === "fail" ? <X className="size-3" strokeWidth={3} /> : t === "unknown" ? <CircleHelp className="size-3" /> : <AlertTriangle className="size-3" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="text-[13px] font-semibold text-ink">{label ?? id}</span>
          <span className="mono text-[10.5px] text-faint">{id}</span>
          <span className={cx("ml-auto text-[11px] font-bold uppercase", t === "ok" ? "text-pass" : t === "fail" ? "text-fail" : t === "unknown" ? "text-unk" : "text-warn")}>{status === "WAIVED" ? "Waived by policy" : status}</span>
        </div>
        {detail && <div className="mt-0.5 break-words text-[12.5px] leading-snug text-muted">{detail}</div>}
        {(measured || limit) && (
          <div className="mono mt-1 text-[11px] text-faint">
            measured {measured ?? "—"} · limit {limit ?? "—"}
          </div>
        )}
      </div>
    </li>
  );
}

export function AutopilotBadge({ size = "sm" }: { size?: "xs" | "sm" }) {
  return (
    <span
      title="Started by Autopilot because Zetaris evidence drifted. Autopilot can only start investigations; it can never approve or execute."
      className={cx("inline-flex items-center gap-1 rounded-full bg-ink font-semibold text-white whitespace-nowrap", size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]")}
    >
      <Bot className="size-3" aria-hidden /> Autopilot
    </span>
  );
}

export function LiveAwsBadge({ size = "sm" }: { size?: "xs" | "sm" }) {
  return (
    <span
      title="Live AWS sandbox (ap-south-1): real EC2 instances, CloudWatch metrics and the AWS Price List"
      className={cx("inline-flex items-center gap-1 rounded-full bg-[#ff9900]/15 font-semibold text-[#9a5b00] ring-1 ring-inset ring-[#ff9900]/40 whitespace-nowrap", size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]")}
    >
      <Cloud className="size-3" aria-hidden /> Live AWS
    </span>
  );
}
