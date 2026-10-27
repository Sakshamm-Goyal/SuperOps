import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Ban, Brain, CheckCircle2, ClipboardList, FlaskConical, Hourglass, LineChart, ShieldCheck, Server } from "lucide-react";
import type { InvestigationData, Json, MemoryItem, PlanSummary, Resource } from "../lib/api";
import { useGet } from "../lib/hooks";
import { checkLabel, money, num, shortTs, signatureParts, STATUS_MEANING } from "../lib/format";
import type { Story } from "../lib/story";
import { CpuEvidenceChart } from "./plan";
import { CanaryResult } from "./canary";
import { DowntimeChip, asRunbook } from "./runbook";
import { StatusChip, cx, Skeleton } from "./ui";

/** One numbered step of the vertical story: number + title + one plain-English line, then the evidence. */
function Step({ n, icon: Icon, title, summary, tone = "accent", last, children }: { n: number; icon: typeof Ban; title: string; summary: ReactNode; tone?: "accent" | "fail" | "pass" | "muted"; last?: boolean; children?: ReactNode }) {
  return (
    <li className="relative grid grid-cols-[40px_1fr] gap-4 sm:grid-cols-[48px_1fr] sm:gap-5">
      {!last && <span className="absolute left-[19px] top-12 bottom-0 w-px bg-line-2 sm:left-[23px]" aria-hidden />}
      <span className={cx("relative z-10 grid size-10 place-items-center rounded-2xl text-white shadow-sm sm:size-12",
        tone === "fail" ? "bg-fail" : tone === "pass" ? "bg-pass" : tone === "muted" ? "bg-faint" : "bg-accent")}>
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0 pb-10">
        <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-faint">Step {n}</div>
        <h3 className="mt-0.5 font-display text-[22px] font-bold tracking-tight text-ink">{title}</h3>
        <p className="mt-1 max-w-3xl text-[15px] leading-relaxed text-ink-2">{summary}</p>
        {children && <div className="mt-4">{children}</div>}
      </div>
    </li>
  );
}

function useInventory(d: InvestigationData) {
  const e = (d.evidence ?? []).find((x) => x.kind === "inventory");
  const r = useGet<Resource<Json>>(e ? `/v1/evidence/${e.id}` : null);
  const byId = new Map<string, Json>();
  for (const row of (r.data?.data?.rows ?? []) as Json[]) byId.set(row.resource_id, row);
  return byId;
}

function instanceOf(sig: string | undefined) {
  const s = signatureParts(sig);
  return { id: s.target, to: s.change };
}

/** Text after "under policy …:" in a stored finding — the server's own reasons, shown verbatim. */
function reasonOf(finding: string | undefined) {
  if (!finding) return "";
  const i = finding.indexOf(": ");
  return i > 0 ? finding.slice(i + 2) : finding;
}

export function StoryFlow({ d, s }: { d: InvestigationData; s: Story }) {
  const inv = useInventory(d);
  const plans = d.plans ?? [];
  const primary: PlanSummary | null =
    plans.find((p) => (d.actions ?? []).some((a: Json) => a.plan_id === p.id)) ??
    plans.find((p) => ["APPROVED", "AWAITING_APPROVAL"].includes(p.status)) ?? s.revision ?? null;
  const chosen: PlanSummary | null = primary ?? plans.find((p) => p.status !== "REJECTED") ?? null;
  const trial = chosen ? (d.trials ?? []).filter((t) => t.plan_id === chosen.id).slice(-1)[0] : undefined;
  const action = chosen ? (d.actions ?? []).find((a: Json) => a.plan_id === chosen.id) : undefined;
  const trialR = useGet<Resource<Json>>(trial ? `/v1/trials/${trial.id}` : null);
  const planR = useGet<Resource<Json>>(chosen ? `/v1/plans/${chosen.id}` : null);
  const actR = useGet<Resource<Json>>(action ? `/v1/actions/${action.id}` : null);

  const rejectedHere = plans.filter((p) => p.status === "REJECTED");
  const recalled: MemoryItem[] = s.recalled;
  const nameOf = (id: string) => inv.get(id)?.display_name ?? id;
  const seriesKey = primary?.target_key ?? s.trap?.target_key ?? chosen?.target_key ?? (d.evidence ?? []).find((e) => e.kind === "telemetry_series")?.subject ?? null;
  const seriesInst = seriesKey ? seriesKey.split("/").slice(-1)[0] : null;
  const fedSources: string[] = d.federation?.sources ?? [];
  const book = asRunbook(planR.data?.data?.runbook);
  const ad = actR.data?.data;
  const downtime = ad?.journal?.find((j: Json) => j.stage === "WRITE_APPLIED")?.detail?.downtime_seconds;
  const checks = Object.entries(ad?.verification?.checks ?? {}) as [string, boolean][];
  const tr = trialR.data?.data?.result;
  const refusals = rejectedHere.length + recalled.length;

  return (
    <ol className="mt-2">
      <Step n={1} icon={LineChart} title="The evidence"
        summary={<>Real CloudWatch metrics for {inv.size || "the"} instances, read through Zetaris{fedSources.length ? ` (${fedSources.join(", ")})` : ""}. The chart is {seriesInst ? nameOf(seriesInst) : "the target"}'s CPU against what the cheaper type would allow.</>}>
        <div className="card p-4 sm:p-5">
          {seriesKey ? <CpuEvidenceChart d={d} targetKey={seriesKey} plan={primary ?? (s.trap?.target_key === seriesKey ? s.trap : chosen)} height={240} /> : <div className="text-[14px] text-muted">No telemetry series was recorded for this run.</div>}
        </div>
        {(d.investigator?.observations ?? []).length > 0 && (
          <ul className="mt-3 grid gap-2 md:grid-cols-3">
            {(d.investigator.observations as Json[]).map((o) => {
              const id = String(o.resource_key ?? "").split("/").slice(-1)[0];
              const row = inv.get(id);
              return (
                <li key={o.resource_key} className="rounded-2xl bg-white p-4 ring-1 ring-line">
                  <div className="flex items-center gap-2"><Server className="size-4 text-accent" /><span className="text-[14px] font-semibold text-ink">{nameOf(id)}</span></div>
                  <div className="mt-0.5 text-[12px] text-muted">{row ? `${row.machine_type} · ${row.environment}` : id}</div>
                  <p className="mt-2 text-[14px] leading-snug text-ink-2">{o.finding}</p>
                </li>
              );
            })}
          </ul>
        )}
      </Step>

      <Step n={2} icon={Ban} tone={refusals ? "fail" : "muted"} title="What was refused, and why"
        summary={refusals ? <>{refusals} tempting change{refusals === 1 ? " was" : "s were"} stopped by deterministic checks or policy — each reason is kept, and memory stops them being proposed again.</> : <>Nothing was refused in this run.</>}>
        {refusals > 0 && (
          <ul className="space-y-2.5">
            {rejectedHere.map((p) => {
              const x = instanceOf(p.screening?.signature);
              const fails = (p.screening?.checks ?? []).filter((c) => c.status === "FAIL");
              return (
                <li key={p.id}>
                  <Link to={`/app/plans/${p.id}`} className="flex flex-col gap-1 rounded-2xl border border-fail/25 bg-fail-bg/50 p-4 transition hover:border-fail/50 sm:flex-row sm:items-center sm:gap-4">
                    <span className="min-w-0 flex-1">
                      <span className="text-[15px] font-semibold text-ink">{nameOf(x.id)} → {x.to}</span>
                      <span className="mt-0.5 block text-[14px] text-ink-2">{fails.map((c) => `${checkLabel(c.check_id)}: ${c.detail}`).join(" · ") || "Rejected"}</span>
                    </span>
                    <span className="flex items-center gap-2 text-[14px] font-semibold text-fail">Refused in this run <ArrowRight className="size-4" /></span>
                  </Link>
                </li>
              );
            })}
            {recalled.map((m) => {
              const x = instanceOf(m.signature);
              const src = m.source_ref?.startsWith("plan:") ? m.source_ref.slice(5) : null;
              return (
                <li key={m.memory_id} className="flex flex-col gap-1 rounded-2xl border border-line bg-white p-4 sm:flex-row sm:items-center sm:gap-4">
                  <span className="min-w-0 flex-1">
                    <span className="text-[15px] font-semibold text-ink">{nameOf(x.id)} → {x.to}</span>
                    <span className="mt-0.5 block text-[14px] text-ink-2 [overflow-wrap:anywhere]">{reasonOf(m.finding)}</span>
                  </span>
                  <span className="flex flex-wrap items-center gap-2 text-[14px]">
                    <span className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2.5 py-1 font-semibold text-accent"><Brain className="size-3.5" /> Remembered, not re-proposed</span>
                    {src && <Link to={`/app/plans/${src}`} className="font-semibold text-accent hover:underline">original refusal</Link>}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Step>

      <Step n={3} icon={FlaskConical} tone={trial?.status === "PASSED" ? "pass" : trial ? "fail" : "muted"} title={tr?.kind === "aws_canary" ? "The canary" : "The trial"}
        summary={!trial ? <>No candidate reached a trial in this run.</> : tr?.kind === "aws_canary"
          ? <>Before touching the real instance, a disposable {tr.candidate_instance_type} ran the same workload for {tr.measure_minutes} minutes. Peak CPU {num(tr.summary?.cpu_max_pct, 1)}% and memory {num(tr.summary?.mem_max_pct, 1)}% stayed under the 80% limit.</>
          : <>The surviving candidate ran a matched trial: {trial.status === "PASSED" ? "every check passed" : `outcome ${trial.status}`}.</>}>
        {trial && (
          <div className="card p-4 sm:p-5">
            {trialR.loading && !tr ? <Skeleton className="h-40" /> : tr?.kind === "aws_canary" ? <CanaryResult r={tr} compact /> : (
              <ul className="divide-y divide-line">{(tr?.checks ?? []).map((c: Json) => <li key={c.check_id} className="flex items-start gap-2 py-2 text-[14px]"><CheckCircle2 className={cx("mt-0.5 size-4 shrink-0", c.status === "PASS" ? "text-pass" : "text-fail")} /><span><b>{checkLabel(c.check_id)}</b> — {c.detail}</span></li>)}</ul>
            )}
            <div className="mt-3 flex justify-end"><Link to={`/app/trials/${trial.id}`} className="inline-flex items-center gap-1 text-[14px] font-semibold text-accent hover:underline">Open trial <ArrowRight className="size-4" /></Link></div>
          </div>
        )}
      </Step>

      <Step n={4} icon={ClipboardList} tone={chosen ? "accent" : "muted"} title="The plan"
        summary={!chosen ? <>No change was proposed for approval.</> : primary ? <>One exact change, with its runbook: {book?.title ?? signatureParts(chosen.screening?.signature).change}. A person approves this plan hash and trial hash — nothing else.</> : <>A candidate was proposed but is not ready for approval: {(STATUS_MEANING[chosen.status] ?? chosen.status).replace(/^\w/, (c) => c.toLowerCase())}.</>}>
        {chosen && (
          <Link to={`/app/plans/${chosen.id}`} className="card flex flex-col gap-4 p-5 transition hover:shadow-[var(--shadow-float)] sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <div className="font-display text-[19px] font-bold tracking-tight text-ink">{book?.title ?? signatureParts(chosen.screening?.signature).change}</div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StatusChip status={chosen.status} />
                {book && <DowntimeChip dt={book.downtime} />}
                {chosen.impacts?.gross_saving && <span className="text-[14px] text-ink-2">Projected saving <b>{money(chosen.impacts.gross_saving)}</b> over {num(chosen.impacts.horizon_hours, 0)} h</span>}
              </div>
              {planR.data?.data?.latest_approval && (
                <div className="mt-2 text-[14px] text-muted">Approved by {planR.data.data.latest_approval.actor_id} · {shortTs(planR.data.data.latest_approval.created_at)} · {planR.data.data.latest_approval.status.toLowerCase()}</div>
              )}
            </div>
            <span className="inline-flex items-center gap-1 text-[14px] font-semibold text-accent">Open change request <ArrowRight className="size-4" /></span>
          </Link>
        )}
      </Step>

      <Step n={5} last icon={action?.status === "VERIFIED" ? ShieldCheck : Hourglass} tone={action?.status === "VERIFIED" ? "pass" : "muted"} title="The result"
        summary={action
          ? action.status === "VERIFIED"
            ? <>Changed once and verified: {ad?.before_state?.instance_type ?? "before"} → {ad?.after_state?.instance_type ?? "after"}{downtime !== undefined ? `, ${downtime} s of measured downtime` : ""}, {checks.filter(([, v]) => v).length} of {checks.length || 6} checks passed.</>
            : <>The change is {action.status.toLowerCase().replace(/_/g, " ")}.</>
          : <>Nothing has been executed. {chosen ? "The plan is waiting for a human decision." : ""}</>}>
        {action && (
          <Link to={`/app/actions/${action.id}`} className={cx("flex flex-col gap-4 rounded-[20px] border p-5 transition hover:shadow-[var(--shadow-card)] sm:flex-row sm:items-center", action.status === "VERIFIED" ? "border-pass/30 bg-pass-bg/50" : "border-line bg-white")}>
            {ad?.before_state?.instance_type && (
              <div className="flex items-center gap-3 font-display text-[22px] font-bold">
                <span className="mono rounded-lg bg-white px-2.5 py-1 text-[16px] text-ink-2 ring-1 ring-line">{ad.before_state.instance_type}</span>
                <ArrowRight className="size-5 text-pass" />
                <span className="mono rounded-lg bg-pass px-2.5 py-1 text-[16px] text-white">{ad.after_state?.instance_type}</span>
              </div>
            )}
            <div className="flex flex-1 flex-wrap items-center gap-2 sm:justify-end">
              {downtime !== undefined && <span className="inline-flex items-center gap-1 rounded-full bg-white px-3 py-1 text-[14px] font-semibold text-warn ring-1 ring-warn/30"><Hourglass className="size-3.5" /> {downtime} s downtime, measured</span>}
              <StatusChip status={action.status} size="md" />
              <ArrowRight className="size-4 text-faint" />
            </div>
          </Link>
        )}
      </Step>
    </ol>
  );
}
