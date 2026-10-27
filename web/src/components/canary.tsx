import { Server } from "lucide-react";
import type { Json } from "../lib/api";
import { num, shortTs } from "../lib/format";
import { cx } from "./ui";

/** The canary's limit is the server's own policy figure, read from its check text; never assumed. */
function limitFrom(checks: Json[] | undefined, id: string): number | null {
  const m = /policy limit (\d+(?:\.\d+)?)%/.exec((checks ?? []).find((c) => c.check_id === id)?.detail ?? "");
  return m ? Number(m[1]) : null;
}

/** Half-ring gauge: measured value against a policy limit marker. */
function LimitGauge({ label, value, limit }: { label: string; value: number | null; limit: number | null }) {
  const size = 200, r = 78, cx0 = 100, cy0 = 96;
  const len = Math.PI * r;
  const v = value == null ? 0 : Math.max(0, Math.min(100, value));
  const over = value != null && limit != null && value > limit;
  const a = limit == null ? null : Math.PI * (1 - limit / 100);
  return (
    <div className="flex flex-col items-center rounded-2xl bg-wash px-4 pb-4 pt-3">
      <svg viewBox={`0 0 ${size} 112`} className="w-full max-w-[220px]" role="img" aria-label={`${label}: ${value == null ? "unknown" : `${num(value, 1)}%`}${limit != null ? ` against a ${limit}% limit` : ""}`}>
        <path d={`M ${cx0 - r} ${cy0} A ${r} ${r} 0 0 1 ${cx0 + r} ${cy0}`} fill="none" stroke="#e4e7f4" strokeWidth={14} strokeLinecap="round" />
        {value != null && (
          <path d={`M ${cx0 - r} ${cy0} A ${r} ${r} 0 0 1 ${cx0 + r} ${cy0}`} fill="none" stroke={over ? "#d63c44" : "#2438f5"} strokeWidth={14} strokeLinecap="round"
            strokeDasharray={`${(len * v) / 100} ${len}`} style={{ transition: "stroke-dasharray 800ms cubic-bezier(.2,.7,.2,1)" }} />
        )}
        {a != null && (
          <g>
            <line x1={cx0 + (r - 13) * Math.cos(a)} y1={cy0 - (r - 13) * Math.sin(a)} x2={cx0 + (r + 13) * Math.cos(a)} y2={cy0 - (r + 13) * Math.sin(a)} stroke="#d63c44" strokeWidth={3} strokeLinecap="round" />
          </g>
        )}
        <text x={cx0} y={cy0 - 8} textAnchor="middle" className="font-display" style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.03em" }} fill={over ? "#d63c44" : "#0b1030"}>
          {value == null ? "—" : `${num(value, 1)}%`}
        </text>
      </svg>
      <div className="-mt-1 text-center text-[14px] font-semibold text-ink">{label}</div>
      <div className="mt-0.5 text-[14px] text-muted">{limit != null ? <>limit <b className="text-fail">{limit}%</b> · {over ? "over the limit" : `${num(limit - (value ?? 0), 1)} points of headroom`}</> : "limit not reported"}</div>
    </div>
  );
}

/** Real AWS canary: a disposable instance of the candidate type ran the target's workload profile. */
export function CanaryResult({ r, compact }: { r: Json; compact?: boolean }) {
  const s = r.summary ?? {};
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[15px] text-ink-2">
        <span className="grid size-8 place-items-center rounded-lg bg-[#ff9900]/15 text-[#9a5b00]"><Server className="size-4" /></span>
        <span><b className="text-ink">Canary on real AWS:</b> a disposable <span className="mono rounded bg-lav px-1.5 text-[14px]">{r.candidate_instance_type}</span> ran the same workload for {r.measure_minutes} min.</span>
      </div>
      <div className={cx("grid gap-3", compact ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_0.9fr]")}>
        <LimitGauge label="Peak 1-minute CPU" value={s.cpu_max_pct ?? null} limit={limitFrom(r.checks, "TRIAL-CPU-HEADROOM")} />
        <LimitGauge label="Peak memory" value={s.mem_max_pct ?? null} limit={limitFrom(r.checks, "TRIAL-MEM-HEADROOM")} />
        {!compact && (
          <div className="flex flex-col justify-center gap-3 rounded-2xl bg-wash p-4 text-[14px] text-ink-2 sm:col-span-2 lg:col-span-1">
            <div><span className="text-muted">Mean CPU</span> <b className="ml-1 text-ink">{s.cpu_avg_pct == null ? "—" : `${num(s.cpu_avg_pct, 1)}%`}</b></div>
            <div><span className="text-muted">CloudWatch datapoints</span> <b className="ml-1 text-ink">{s.datapoints ?? "—"}</b> <span className="text-muted">(1-minute)</span></div>
            <div className="text-[14px] text-muted">Instance {r.canary_instance_id} · from {shortTs(r.window_start)}. Terminated after the window; missing measurements make the trial INCOMPLETE, never PASS.</div>
          </div>
        )}
      </div>
    </div>
  );
}
