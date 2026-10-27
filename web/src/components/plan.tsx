import { useState } from "react";
import { Link } from "react-router-dom";
import { Bot, ChevronDown, Cloud, MessageSquareWarning, ArrowRight, FlaskConical, Gavel, Leaf } from "lucide-react";
import type { Json, PlanSummary, Resource, InvestigationData } from "../lib/api";
import { useGet } from "../lib/hooks";
import { checkLabel, checkOf, environmentOf, impactBasis, money, num, planReason, planTitle, pct, tone } from "../lib/format";
import { CheckRow, KindBadge, StatusChip, cx, IdLink, Skeleton, Notice } from "./ui";
import { SeriesChart, type RefLine } from "./charts";

export function PathIcon({ path, className }: { path: string; className?: string }) {
  return path === "ai" ? <Bot className={className} aria-hidden /> : <Cloud className={className} aria-hidden />;
}

export function ImpactSummary({ imp, compact }: { imp: Json; compact?: boolean }) {
  if (!imp) return <div className="text-[12.5px] text-faint">No impact recorded.</div>;
  const isAi = imp.suite || imp.cost_per_accepted_reduction !== undefined;
  return (
    <div className={cx("rounded-xl bg-wash p-3", compact && "p-2.5")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">{isAi ? "Cost per accepted task" : "Gross saving"}</span>
        <KindBadge kind={imp.result_kind} />
      </div>
      {isAi ? (
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-display text-[22px] font-bold tracking-tight text-ink">{imp.cost_per_accepted_reduction != null ? `−${pct(imp.cost_per_accepted_reduction)}` : "—"}</span>
          <span className="text-[12px] text-muted tnum">{imp.accepted ? `accepted ${imp.accepted}` : ""}</span>
        </div>
      ) : (
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-display text-[22px] font-bold tracking-tight text-ink">{money(imp.gross_saving, imp.currency ?? "USD")}</span>
          {imp.horizon_hours && <span className="text-[12px] text-muted">over {num(imp.horizon_hours, 0)} h</span>}
        </div>
      )}
      <div className="mt-1 text-[11.5px] leading-snug text-muted">{impactBasis(imp)}{imp.note ? ` — ${imp.note}` : ""}</div>
      {!compact && imp.carbon && (
        <div className="mt-2 flex items-start gap-1.5 border-t border-line pt-2 text-[11.5px] text-muted">
          <Leaf className="mt-0.5 size-3.5 shrink-0 text-pass" />
          {imp.carbon.result_kind === "unknown" || !imp.carbon.baseline_kg_co2e ? (
            <span>Carbon unknown{imp.carbon.reason ? ` — ${imp.carbon.reason}` : ""}</span>
          ) : (
            <span>
              {num(imp.carbon.baseline_kg_co2e)} → {num(imp.carbon.candidate_kg_co2e)} kgCO₂e · {imp.carbon.basis} ({imp.carbon.coverage}; factor {imp.carbon.factor_kg_per_kwh} kg/kWh, {imp.carbon.factor_source})
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function CriticBlock({ critic }: { critic: Json }) {
  if (!critic) return null;
  const reqs: Json[] = critic.evidence_requests ?? [];
  return (
    <div className="rounded-xl border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Gavel className="size-3.5 text-accent" />
        <span className="text-[12px] font-semibold text-ink">Critic</span>
        <StatusChip status={critic.verdict} size="xs" />
        {critic.trial?.status && (
          <span className="ml-auto inline-flex items-center gap-1 text-[11.5px] text-muted">
            <FlaskConical className="size-3" /> trial <StatusChip status={critic.trial.status} size="xs" />
          </span>
        )}
      </div>
      {critic.note && <p className="mt-1.5 text-[12.5px] leading-snug text-muted">{critic.note}</p>}
      {reqs.length > 0 && (
        <div className="mt-2 flex items-start gap-1.5 text-[12px] text-warn">
          <MessageSquareWarning className="mt-0.5 size-3.5 shrink-0" />
          <span>Evidence requested: {reqs.map((r) => (typeof r === "string" ? r : r.kind ?? JSON.stringify(r))).join(", ")}</span>
        </div>
      )}
      {critic.trial?.critic?.note && critic.trial.critic.verdict !== "SKIPPED" && (
        <p className="mt-1.5 border-t border-line pt-1.5 text-[12px] text-muted">Post-trial: {critic.trial.critic.note}</p>
      )}
    </div>
  );
}

export function PlanCard({ plan, feedback }: { plan: PlanSummary; feedback?: Json[] }) {
  const [open, setOpen] = useState(false);
  const checks = plan.screening?.checks ?? [];
  const failing = checks.filter((c) => c.status !== "PASS");
  const passCount = checks.length - failing.length;
  const t = tone(plan.status);
  return (
    <article className={cx("card flex flex-col overflow-hidden", t === "attention" && "ring-2 ring-warn/30")}>
      <div className={cx("h-1", t === "fail" ? "bg-fail/70" : t === "attention" ? "bg-warn/70" : t === "ok" ? "bg-pass/70" : "bg-line")} />
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-faint">
              <PathIcon path={plan.path} className="size-3.5" /> {plan.path} · candidate {plan.candidate_no ?? "?"}{plan.revision && plan.revision > 1 ? ` · revision ${plan.revision}` : ""}
            </div>
            <h4 className="mt-1 font-display text-[16px] font-bold leading-snug tracking-tight text-ink">{planTitle(plan)}</h4>
            <div className="mt-0.5 text-[11.5px] text-muted">{environmentOf(plan.target_key)} · <span className="mono">{plan.target_key}</span></div>
          </div>
          <StatusChip status={plan.status} />
        </div>

        <p className={cx("text-[12.5px] leading-snug", t === "fail" ? "text-fail" : "text-ink-2")}>{planReason(plan, feedback)}</p>

        <div className="flex flex-wrap gap-1">
          {checks.map((c) => (
            <span key={c.check_id} title={`${c.check_id}: ${c.detail ?? ""}`} className={cx("rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold", c.status === "PASS" ? "bg-pass-bg text-pass" : c.status === "FAIL" ? "bg-fail-bg text-fail" : "bg-unk-bg text-unk")}>
              {checkLabel(c.check_id)}
            </span>
          ))}
        </div>

        <ImpactSummary imp={plan.impacts} compact />
        <CriticBlock critic={plan.critic} />

        <button onClick={() => setOpen((o) => !o)} className="flex items-center justify-between rounded-lg px-1 text-[12.5px] font-semibold text-ink-2 hover:text-accent" aria-expanded={open}>
          <span>Screening checks · {passCount}/{checks.length} pass</span>
          <ChevronDown className={cx("size-4 transition", open && "rotate-180")} />
        </button>
        {open && (
          <ul className="-mt-1 divide-y divide-line">
            {checks.map((c) => <CheckRow key={c.check_id} id={c.check_id} label={checkLabel(c.check_id)} status={c.status} detail={c.detail} measured={c.measured} limit={c.limit} />)}
          </ul>
        )}
        {plan.rationale && open && (
          <div className="rounded-xl bg-lav/60 p-3 text-[12px] text-muted">
            <div className="mb-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-faint">Model rationale — untrusted text, not evidence or authority</div>
            {plan.rationale}
          </div>
        )}
        <div className="mt-auto flex items-center justify-between border-t border-line pt-3">
          <IdLink kind="plan" id={plan.id} />
          <Link to={`/app/plans/${plan.id}`} className="inline-flex items-center gap-1 text-[13px] font-semibold text-accent hover:underline">
            Open plan <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>
    </article>
  );
}

// ---- Evidence-backed CPU chart (peak vs allowed) ----

function useEvidenceRows(d: InvestigationData, kind: string, subject?: string | null) {
  const e = (d.evidence ?? []).find((x) => x.kind === kind && (subject === undefined || x.subject === subject));
  const r = useGet<Resource<Json>>(e ? `/v1/evidence/${e.id}` : null);
  return { rows: (r.data?.data?.rows ?? []) as Json[], loading: r.loading, error: r.error, evidenceId: e?.id ?? null, res: r.data };
}

export function CpuEvidenceChart({ d, targetKey, plan, height = 260 }: { d: InvestigationData; targetKey: string; plan?: PlanSummary | null; height?: number }) {
  const [, project, resource] = (() => {
    const parts = targetKey.split("/");
    return [parts[0], parts[1], parts.slice(2).join("/")];
  })();
  const inv = useEvidenceRows(d, "inventory");
  const summ = useEvidenceRows(d, "telemetry_summary");
  const series = useEvidenceRows(d, "telemetry_series", targetKey);
  const invRow = inv.rows.find((r) => r.resource_id === resource && r.project_id === project);
  const sumRow = summ.rows.find((r) => r.resource_id === resource && r.project_id === project);
  const vcpu = invRow?.vcpu ? Number(invRow.vcpu) : null;

  if (series.loading || inv.loading) return <Skeleton className="h-64 w-full" />;
  if (!series.evidenceId) return <Notice tone="unknown" title="No telemetry series in this investigation">The investigator did not request a series for {targetKey}, so no chart can be drawn from evidence.</Notice>;
  if (!vcpu) return <Notice tone="unknown" title="vCPU count unknown">The inventory evidence has no vCPU for this resource; plotting CPU in vCPU would be a guess.</Notice>;

  // Prefer the server's peak-preserving hourly view (covers the whole interval); fall back to the capped raw rows.
  const hourly: Json[] | null = Array.isArray(series.res?.data?.series_hourly_peak) ? series.res!.data.series_hourly_peak : null;
  const points = (hourly
    ? hourly.filter((h) => h.cpu_percent_max !== null && h.cpu_percent_max !== undefined).map((h) => ({ t: new Date(h.hour).getTime(), v: (Number(h.cpu_percent_max) * vcpu) / 100 }))
    : series.rows
        .filter((r) => r.cpu_percent !== null && r.cpu_percent !== undefined && r.cpu_percent !== "")
        .map((r) => ({ t: new Date(r.observed_at).getTime(), v: (Number(r.cpu_percent) * vcpu) / 100 }))
  ).sort((a, b) => a.t - b.t);
  const rawCount = series.res?.data?.row_count ?? sumRow?.row_count;
  const peakChk = plan ? checkOf(plan, "CHK-CPU-PEAK") : undefined;
  const stressChk = plan ? checkOf(plan, "CHK-CPU-STRESS") : undefined;
  const refs: RefLine[] = [];
  if (peakChk?.limit) refs.push({ y: Number(peakChk.limit), label: `allowed on candidate ${num(peakChk.limit)} vCPU`, color: "#d63c44" });
  if (stressChk?.measured) refs.push({ y: Number(stressChk.measured), label: `forecast stress ${num(stressChk.measured)} vCPU`, color: "#b86e00", dash: "2 4" });
  if (sumRow?.avg_cpu_percent) refs.push({ y: (Number(sumRow.avg_cpu_percent) * vcpu) / 100, label: `average ${num((Number(sumRow.avg_cpu_percent) * vcpu) / 100)} vCPU`, color: "#5e6687" });
  const peakPt = points.reduce<{ t: number; v: number } | null>((m, p) => (!m || p.v > m.v ? p : m), null);

  return (
    <div>
      <SeriesChart points={points} refs={refs} unit=" vCPU" height={height} peak={peakPt} />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11.5px] text-faint">
        <span>
          {hourly
            ? <>Hourly peak of every observation: {points.length} hours from {num(rawCount, 0)} raw samples, so no spike is averaged away. The checks used every raw observation.</>
            : <>{points.length} of {rawCount ?? "?"} observations shown (the evidence API returns at most 500 rows); the checks used every observation.</>}{" "}
          Current machine {invRow?.machine_type} · {vcpu} vCPU.
        </span>
        <span className="flex items-center gap-2">
          <KindBadge kind={series.res?.data_origin} /> <IdLink kind="evidence" id={series.evidenceId} label="series evidence" />
        </span>
      </div>
    </div>
  );
}

export function useTelemetrySummary(d: InvestigationData, targetKey: string | null) {
  const summ = useEvidenceRows(d, "telemetry_summary");
  const inv = useEvidenceRows(d, "inventory");
  if (!targetKey) return null;
  const parts = targetKey.split("/");
  const project = parts[1];
  const resource = parts.slice(2).join("/");
  const s = summ.rows.find((r) => r.resource_id === resource && r.project_id === project);
  const i = inv.rows.find((r) => r.resource_id === resource && r.project_id === project);
  return { summary: s, inventory: i };
}
