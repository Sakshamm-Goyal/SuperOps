import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cx } from "./ui";

function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((e) => setW(Math.floor(e[0].contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Semicircle gauge. `value` in 0..1; null renders an honest "unknown" gauge. */
export function Gauge({ value, label, sub, size = 220 }: { value: number | null; label: ReactNode; sub?: ReactNode; size?: number }) {
  const r = size / 2 - 14;
  const cx0 = size / 2;
  const cy0 = size / 2 + 4;
  const len = Math.PI * r;
  const v = value === null ? 0 : Math.max(0, Math.min(1, value));
  const ticks = Array.from({ length: 21 }, (_, i) => i / 20);
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 18} viewBox={`0 0 ${size} ${size / 2 + 18}`} role="img" aria-label={typeof label === "string" ? label : "gauge"}>
        {ticks.map((t) => {
          const a = Math.PI * (1 - t);
          const r1 = r + 9;
          const r2 = Math.round(t * 20) % 5 === 0 ? r + 15 : r + 12;
          return <line key={t} x1={cx0 + r1 * Math.cos(a)} y1={cy0 - r1 * Math.sin(a)} x2={cx0 + r2 * Math.cos(a)} y2={cy0 - r2 * Math.sin(a)} stroke="#d5daee" strokeWidth={1.2} />;
        })}
        <path d={`M ${cx0 - r} ${cy0} A ${r} ${r} 0 0 1 ${cx0 + r} ${cy0}`} fill="none" stroke="#eef0ff" strokeWidth={16} strokeLinecap="round" />
        {value !== null && (
          <path
            d={`M ${cx0 - r} ${cy0} A ${r} ${r} 0 0 1 ${cx0 + r} ${cy0}`}
            fill="none"
            stroke="url(#gauge-grad)"
            strokeWidth={16}
            strokeLinecap="round"
            strokeDasharray={`${len * v} ${len}`}
            style={{ transition: "stroke-dasharray 900ms cubic-bezier(.2,.7,.2,1)" }}
          />
        )}
        <defs>
          <linearGradient id="gauge-grad" x1="0" x2="1">
            <stop offset="0" stopColor="#8d99ff" />
            <stop offset="1" stopColor="#2438f5" />
          </linearGradient>
        </defs>
        <text x={cx0} y={cy0 - 14} textAnchor="middle" className="fill-ink font-display" style={{ fontSize: size / 6.2, fontWeight: 800, letterSpacing: "-0.04em" }}>
          {value === null ? "—" : `${Math.round(v * 100)}%`}
        </text>
      </svg>
      <div className="-mt-1 text-center text-[14px] font-semibold text-ink">{label}</div>
      {sub && <div className="mt-0.5 text-center text-xs text-muted">{sub}</div>}
    </div>
  );
}

/** Horizontal bar list (e.g. rejections by check). */
export function BarList({ items, max, valueSuffix = "" }: { items: { label: ReactNode; value: number; hint?: string; tone?: "accent" | "fail" | "pass" | "warn" }[]; max?: number; valueSuffix?: string }) {
  const m = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-2.5">
      {items.map((it, i) => (
        <li key={i} title={it.hint}>
          <div className="mb-1 flex items-center justify-between gap-3 text-[14px]">
            <span className="min-w-0 truncate text-ink-2">{it.label}</span>
            <span className="tnum font-semibold text-ink">{it.value}{valueSuffix}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-lav">
            <div
              className={cx("h-full rounded-full", it.tone === "fail" ? "bg-fail/80" : it.tone === "pass" ? "bg-pass/80" : it.tone === "warn" ? "bg-warn/70" : "bg-accent")}
              style={{ width: `${Math.max(3, (it.value / m) * 100)}%`, transition: "width 700ms" }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Stacked horizontal bar of status counts. */
export function StackBar({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const total = parts.reduce((a, b) => a + b.value, 0);
  if (!total) return <div className="h-3 rounded-full bg-lav" />;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-lav">
        {parts.filter((p) => p.value > 0).map((p) => (
          <div key={p.label} title={`${p.label}: ${p.value}`} style={{ width: `${(p.value / total) * 100}%`, background: p.color }} className="h-full border-r-2 border-white last:border-r-0" />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {parts.filter((p) => p.value > 0).map((p) => (
          <span key={p.label} className="inline-flex items-center gap-1.5 text-xs text-muted">
            <span className="size-2 rounded-full" style={{ background: p.color }} />
            {p.label} <span className="tnum font-semibold text-ink">{p.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Vertical mini bars: e.g. investigations per day. */
export function MiniBars({ data, height = 120 }: { data: { label: string; value: number; highlight?: boolean }[]; height?: number }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="flex items-end gap-1.5" style={{ height }}>
      {data.map((d, i) => (
        <div key={i} className="group flex flex-1 flex-col items-center justify-end gap-1.5" title={`${d.label}: ${d.value}`}>
          <span className="text-[11px] font-semibold text-ink opacity-0 transition group-hover:opacity-100 tnum">{d.value}</span>
          <div
            className={cx("w-full max-w-7 rounded-md transition-all", d.highlight ? "bg-accent" : d.value ? "bg-accent-100 group-hover:bg-accent/60" : "bg-lav")}
            style={{ height: `${Math.max(4, (d.value / max) * (height - 34))}px` }}
          />
          <span className="text-[11px] text-faint">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

export interface SeriesPoint { t: number; v: number }
export interface RefLine { y: number; label: string; color: string; dash?: string }

/**
 * Time series with reference lines (peak-vs-allowed). Display only: checks used every observation, the chart shows
 * at most the 500 rows the evidence API returns.
 */
export function SeriesChart({ points, refs = [], unit = "", height = 260, yMax, peak }: { points: SeriesPoint[]; refs?: RefLine[]; unit?: string; height?: number; yMax?: number; peak?: SeriesPoint | null }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const pad = { l: 44, r: 12, t: 18, b: 26 };
  const w = Math.max(width, 280);
  const iw = w - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const { t0, t1, ymax } = useMemo(() => {
    const ts = points.map((p) => p.t);
    const vmax = Math.max(...points.map((p) => p.v), ...refs.map((r) => r.y), 0.0001);
    return { t0: Math.min(...ts), t1: Math.max(...ts), ymax: yMax ?? niceCeil(vmax * 1.12) };
  }, [points, refs, yMax]);
  const x = (t: number) => pad.l + ((t - t0) / Math.max(1, t1 - t0)) * iw;
  const y = (v: number) => pad.t + ih - (v / ymax) * ih;
  const path = useMemo(() => points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(""), [points, w, ymax]); // eslint-disable-line react-hooks/exhaustive-deps
  const area = points.length ? `${path}L${x(points[points.length - 1].t).toFixed(1)},${pad.t + ih}L${x(points[0].t).toFixed(1)},${pad.t + ih}Z` : "";
  const yt = [0, 0.25, 0.5, 0.75, 1].map((f) => f * ymax);
  const short = t1 - t0 < 2 * 86400000;
  const days = Math.max(1, Math.round((t1 - t0) / 86400000));
  const nTicks = short ? Math.min(6, Math.max(2, points.length)) : Math.min(6, days + 1);
  const xt = Array.from({ length: nTicks }, (_, i) => t0 + ((t1 - t0) * i) / Math.max(1, nTicks - 1));
  const tickLabel = (t: number) =>
    short ? new Date(t).toISOString().slice(11, 16) : new Date(t).toLocaleDateString("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
  const hp = hover !== null ? points[hover] : null;

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const t = t0 + ((px - pad.l) / iw) * (t1 - t0);
    let lo = 0, hi = points.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (points[mid].t < t) lo = mid + 1; else hi = mid;
    }
    setHover(Math.max(0, Math.min(points.length - 1, lo)));
  }

  return (
    <div ref={ref} className="relative w-full select-none">
      {width > 0 && (
        <svg width={w} height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="time series chart">
          <defs>
            <linearGradient id="series-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="#2438f5" stopOpacity="0.18" />
              <stop offset="1" stopColor="#2438f5" stopOpacity="0" />
            </linearGradient>
          </defs>
          {yt.map((v) => (
            <g key={v}>
              <line x1={pad.l} x2={w - pad.r} y1={y(v)} y2={y(v)} stroke="#eceef8" />
              <text x={pad.l - 8} y={y(v) + 4} textAnchor="end" className="fill-faint" style={{ fontSize: 10.5 }}>{fmtTick(v)}</text>
            </g>
          ))}
          {xt.map((t, i) => (
            <text key={i} x={x(t)} y={height - 6} textAnchor={i === 0 ? "start" : i === xt.length - 1 ? "end" : "middle"} className="fill-faint" style={{ fontSize: 10.5 }}>
              {tickLabel(t)}
            </text>
          ))}
          {unit && <text x={pad.l - 8} y={pad.t - 3} textAnchor="end" className="fill-faint" style={{ fontSize: 10, fontWeight: 600 }}>{unit.trim()}</text>}
          <path d={area} fill="url(#series-fill)" />
          <path d={path} fill="none" stroke="#2438f5" strokeWidth={1.4} strokeLinejoin="round" />
          {refs.map((r) => (
            <line key={r.label} x1={pad.l} x2={w - pad.r} y1={y(r.y)} y2={y(r.y)} stroke={r.color} strokeWidth={1.6} strokeDasharray={r.dash ?? "6 4"} />
          ))}
          {labelSlots(refs.map((r) => y(r.y) - 19)).map((ly, i) => {
            const r = refs[i];
            return (
              <g key={r.label}>
                <rect x={w - pad.r - labelWidth(r.label) - 8} y={ly} width={labelWidth(r.label) + 8} height={16} rx={5} fill="#fff" stroke={r.color} strokeOpacity={0.35} />
                <text x={w - pad.r - 4} y={ly + 11.5} textAnchor="end" style={{ fontSize: 10.5, fontWeight: 600 }} fill={r.color}>{r.label}</text>
              </g>
            );
          })}
          {peak && (
            <g>
              <circle cx={x(peak.t)} cy={y(peak.v)} r={9} fill="#d63c44" fillOpacity={0.15} />
              <circle cx={x(peak.t)} cy={y(peak.v)} r={4} fill="#d63c44" stroke="#fff" strokeWidth={1.5} />
            </g>
          )}
          {hp && (
            <g>
              <line x1={x(hp.t)} x2={x(hp.t)} y1={pad.t} y2={pad.t + ih} stroke="#0b1030" strokeOpacity={0.2} />
              <circle cx={x(hp.t)} cy={y(hp.v)} r={4} fill="#2438f5" stroke="#fff" strokeWidth={2} />
            </g>
          )}
        </svg>
      )}
      {hp && (
        <div
          className="pointer-events-none absolute top-1 rounded-lg bg-ink px-2.5 py-1.5 text-[12px] text-white shadow-lg"
          style={{ left: Math.min(Math.max(x(hp.t) - 70, 0), w - 150) }}
        >
          <div className="tnum font-semibold">{fmtTick(hp.v)}{unit}</div>
          <div className="text-white/70">{new Date(hp.t).toISOString().slice(0, 16).replace("T", " ")} UTC</div>
        </div>
      )}
    </div>
  );
}

/** Nudge reference-line labels apart so close lines stay readable. Returns new top positions in input order. */
function labelSlots(tops: number[]): number[] {
  const order = tops.map((t, i) => ({ t, i })).sort((a, b) => a.t - b.t);
  const out = [...tops];
  let prev = -Infinity;
  for (const o of order) {
    const t = Math.max(o.t, prev + 18);
    out[o.i] = t;
    prev = t;
  }
  return out;
}

function labelWidth(s: string) {
  return s.length * 5.9 + 6;
}
function niceCeil(v: number) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return m * p;
}
function fmtTick(v: number) {
  if (Number.isInteger(v)) return v.toLocaleString("en-US");
  const a = Math.abs(v);
  if (a >= 100) return v.toFixed(0);
  if (a >= 10) return v.toFixed(1);
  if (a >= 0.1 || a === 0) return v.toFixed(2);
  return v.toPrecision(3);
}

/** Paired comparison bars: baseline vs candidate. */
export function PairBars({ rows, unit = "" }: { rows: { label: string; baseline: number | null; candidate: number | null; better?: "lower" | "higher" }[]; unit?: string }) {
  return (
    <div className="space-y-4">
      {rows.map((r) => {
        const m = Math.max(r.baseline ?? 0, r.candidate ?? 0, 0.000001);
        const worse = r.baseline !== null && r.candidate !== null && (r.better === "higher" ? r.candidate < r.baseline : r.candidate > r.baseline);
        return (
          <div key={r.label}>
            <div className="mb-1.5 text-[12px] font-semibold text-ink-2">{r.label}</div>
            {(["baseline", "candidate"] as const).map((side) => {
              const v = r[side];
              return (
                <div key={side} className="mb-1 flex items-center gap-2">
                  <span className="w-16 shrink-0 text-[12px] text-muted">{side}</span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-lav">
                    <div className={cx("h-full rounded-full", side === "baseline" ? "bg-ink-2/35" : worse ? "bg-fail/80" : "bg-accent")} style={{ width: `${v === null ? 0 : Math.max(2, (v / m) * 100)}%` }} />
                  </div>
                  <span className="w-20 shrink-0 text-right text-[12px] font-semibold tnum text-ink">{v === null ? "—" : `${fmtTick(v)}${unit}`}</span>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/** Small category grid (AI suite): accepted/total per category, baseline vs candidate. */
export function CategoryGrid({ base, cand }: { base: Record<string, { accepted: number; total: number }>; cand: Record<string, { accepted: number; total: number }> }) {
  const cats = Object.keys(cand);
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {cats.map((c) => {
        const b = base[c];
        const k = cand[c];
        const lost = b && k.accepted < b.accepted;
        return (
          <div key={c} className={cx("rounded-xl border p-3", lost ? "border-fail/30 bg-fail-bg/50" : "border-line bg-white")}>
            <div className="text-[12px] font-semibold capitalize text-ink">{c.replace(/_/g, " ")}</div>
            <div className="mt-2 flex items-center gap-1">
              {Array.from({ length: k.total }, (_, i) => (
                <span key={i} className={cx("h-2 flex-1 rounded-full", i < k.accepted ? (lost ? "bg-fail/70" : "bg-pass/70") : "bg-line")} />
              ))}
            </div>
            <div className="mt-1.5 flex justify-between text-[12px] text-muted tnum">
              <span>candidate {k.accepted}/{k.total}</span>
              {b && <span>baseline {b.accepted}/{b.total}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
