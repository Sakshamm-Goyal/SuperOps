import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FlaskConical, ShieldCheck, Gauge as GaugeIcon, Server, ListChecks, Info } from "lucide-react";
import type { Json, Resource } from "../lib/api";
import { useGet } from "../lib/hooks";
import { checkLabel, num, pct, shortTs, usageBasisLabel, STATUS_MEANING } from "../lib/format";
import { Card, CardHeader, CheckRow, ErrorBox, Hash, IdLink, KindBadge, KV, Notice, PageHeader, PageSkeleton, StatusChip, Stat, cx, Tabs } from "../components/ui";
import { CategoryGrid, PairBars } from "../components/charts";
import { CanaryResult } from "../components/canary";

function CloudTrial({ r }: { r: Json }) {
  const s = r.summary ?? {};
  const runs: Json[] = r.runs ?? [];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Baseline p95 (server)" value={`${num(s.baseline_p95_ms, 1)} ms`} icon={GaugeIcon} />
        <Stat label="Candidate p95 (server)" value={`${num(s.candidate_p95_ms, 1)} ms`} icon={GaugeIcon} accent />
        <Stat label="Failures" value={`${s.candidate_failures ?? "—"}`} sub={`baseline ${s.baseline_failures ?? "—"}`} icon={ShieldCheck} />
        <Stat label="Pooled samples" value={num(s.pooled_samples?.candidate, 0)} sub={`baseline ${num(s.pooled_samples?.baseline, 0)} · ${(s.discarded_windows ?? []).length} windows re-measured`} icon={ListChecks} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Baseline vs candidate" icon={GaugeIcon} sub={s.method} />
          <div className="px-5 pb-5 sm:px-6">
            <PairBars unit=" ms" rows={[
              { label: "Server p95", baseline: s.baseline_p95_ms ?? null, candidate: s.candidate_p95_ms ?? null },
              { label: "Client p95", baseline: s.client_p95_ms?.baseline ?? null, candidate: s.client_p95_ms?.candidate ?? null },
            ]} />
            {(s.pair_p95_ratios ?? []).length > 0 && <div className="mt-4 text-[12px] text-muted">Paired p95 ratios: <span className="mono">{s.pair_p95_ratios.map((x: number) => x.toFixed(3)).join(" · ")}</span></div>}
          </div>
        </Card>
        <Card>
          <CardHeader title="Fixtures" icon={Server} sub="Two sandbox workers under identical offered load" />
          <div className="px-5 pb-5 sm:px-6">
            <KV rows={[
              ["Baseline fixture", <span className="mono text-[12px]">{r.fixtures?.baseline?.id}</span>],
              ["Baseline config", <Hash value={r.fixtures?.baseline?.config_hash} />],
              ["Candidate fixture", <span className="mono text-[12px]">{r.fixtures?.candidate?.id}</span>],
              ["Candidate config", <Hash value={r.fixtures?.candidate?.config_hash} />],
              ["Workload", <span className="mono text-[12px]">{r.workload?.id} {r.workload?.version}</span>],
              ["Workload hash", <Hash value={r.workload?.hash} />],
              ["Experiment cost", r.experiment_cost ? `${r.experiment_cost.amount} ${r.experiment_cost.currency} (${r.experiment_cost.basis})` : "—"],
            ]} />
          </div>
        </Card>
      </div>
      <Card className="overflow-hidden">
        <CardHeader title="Judged windows" icon={ListChecks} sub="Each pair runs both sides; windows with load-generator lag are re-measured" />
        <div className="overflow-x-auto">
          <table className="w-full text-[13.5px]">
            <thead><tr className="border-y border-line bg-wash/60 text-left text-[12px] uppercase tracking-wider text-faint">
              {["Pair", "Side", "Attempt", "Completed / offered", "Failures", "p50", "p95", "Server p95", "Lag p95"].map((h) => <th key={h} className="px-4 py-2">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-line">
              {runs.map((x, i) => (
                <tr key={i} className={cx(x.side === "candidate" && "bg-accent-50/30")}>
                  <td className="px-4 py-2 tnum">{x.pair}</td>
                  <td className="px-4 py-2 font-semibold capitalize">{x.side}</td>
                  <td className="px-4 py-2 tnum">{x.attempt}</td>
                  <td className="px-4 py-2 tnum">{x.completed} / {x.offered}</td>
                  <td className={cx("px-4 py-2 tnum", x.failures ? "font-semibold text-fail" : "")}>{x.failures}</td>
                  <td className="px-4 py-2 tnum">{num(x.p50_ms, 1)} ms</td>
                  <td className="px-4 py-2 tnum">{num(x.p95_ms, 1)} ms</td>
                  <td className="px-4 py-2 tnum">{num(x.server_p95_ms, 1)} ms</td>
                  <td className="px-4 py-2 tnum">{num(x.schedule_lag_p95_ms, 2)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function AiTrial({ r }: { r: Json }) {
  const b = r.baseline ?? {};
  const c = r.candidate ?? {};
  const [filter, setFilter] = useState<"changed" | "all">("changed");
  const baseById = new Map<string, Json>((b.per_case ?? []).map((x: Json) => [x.case_id, x]));
  const cases: Json[] = (c.per_case ?? []).filter((x: Json) => filter === "all" || baseById.get(x.case_id)?.accepted !== x.accepted || x.critical);
  const disc = r.paired_discordance ?? {};
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Baseline accepted" value={`${b.accepted}/${b.cases}`} sub={`${b.critical_failures} critical · Wilson 95% ${b.wilson_95 ? `${pct(b.wilson_95[0])}–${pct(b.wilson_95[1])}` : "—"}`} icon={ShieldCheck} />
        <Stat label="Candidate accepted" value={`${c.accepted}/${c.cases}`} sub={`${c.critical_failures} critical · Wilson 95% ${c.wilson_95 ? `${pct(c.wilson_95[0])}–${pct(c.wilson_95[1])}` : "—"}`} icon={ShieldCheck} accent />
        <Stat label="Cost / accepted change" value={r.cost_per_accepted_reduction != null ? `−${pct(r.cost_per_accepted_reduction)}` : "—"} sub={`${c.cost_per_accepted_usd ?? "—"} vs ${b.cost_per_accepted_usd ?? "—"} USD`} icon={GaugeIcon} />
        <Stat label="Paired discordance" value={`${disc.baseline_only ?? 0} / ${disc.candidate_only ?? 0}`} sub={`baseline-only / candidate-only passes · both ${disc.both_pass ?? 0}`} icon={ListChecks} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Accepted by category" icon={ListChecks} sub="Development cases only — holdout data is never shown" />
          <div className="px-5 pb-5 sm:px-6"><CategoryGrid base={b.by_category ?? {}} cand={c.by_category ?? {}} /></div>
        </Card>
        <Card>
          <CardHeader title="Usage" icon={GaugeIcon} sub={r.cost_basis} />
          <div className="px-5 pb-5 sm:px-6">
            <PairBars rows={[
              { label: "Input tokens", baseline: b.input_tokens ?? null, candidate: c.input_tokens ?? null },
              { label: "Tool calls", baseline: b.tool_calls ?? null, candidate: c.tool_calls ?? null },
              { label: "Total cost (USD)", baseline: Number(b.total_cost_usd) || null, candidate: Number(c.total_cost_usd) || null },
            ]} />
            <div className="mt-3 text-[12px] text-muted">Usage basis: {usageBasisLabel(c.usage_basis)} · model <span className="mono">{c.model_id}</span> · deduped lookups {c.deduped_lookups}</div>
          </div>
        </Card>
      </div>
      <Card className="overflow-hidden">
        <CardHeader title="Per-case results" icon={ListChecks} sub={`Verifier ${r.verifier ?? "?"}`} right={<Tabs value={filter} onChange={setFilter} tabs={[{ id: "changed", label: "Changed or critical" }, { id: "all", label: "All cases" }]} />} />
        <div className="max-h-[480px] overflow-auto scroll-thin">
          <table className="w-full text-[13.5px]">
            <thead className="sticky top-0 bg-white"><tr className="border-y border-line text-left text-[12px] uppercase tracking-wider text-faint">
              {["Case", "Category", "Expected", "Observed", "Baseline", "Candidate"].map((h) => <th key={h} className="px-4 py-2">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-line">
              {cases.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-faint">No case changed outcome.</td></tr>}
              {cases.map((x) => {
                const bx = baseById.get(x.case_id);
                return (
                  <tr key={x.case_id} className={cx(!x.accepted && "bg-fail-bg/40")}>
                    <td className="mono px-4 py-2">{x.case_id}</td>
                    <td className="px-4 py-2 capitalize">{String(x.category).replace(/_/g, " ")}</td>
                    <td className="mono px-4 py-2 text-[12.5px]">{x.expected}</td>
                    <td className="mono px-4 py-2 text-[12.5px]">{x.observed}</td>
                    <td className="px-4 py-2"><StatusChip status={bx ? (bx.accepted ? "PASS" : "FAIL") : null} size="xs" /></td>
                    <td className="px-4 py-2"><span className="inline-flex items-center gap-1"><StatusChip status={x.accepted ? "PASS" : "FAIL"} size="xs" />{x.critical && <span className="rounded bg-fail px-1 text-[11px] font-bold text-white">CRITICAL</span>}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export default function TrialDetail() {
  const { id = "" } = useParams();
  const t = useGet<Resource<Json>>(`/v1/trials/${id}`, { pollMs: 2000, shouldPoll: (d) => ["QUEUED", "RUNNING"].includes(d?.status ?? "") });
  if (t.loading && !t.data) return <PageSkeleton />;
  if (t.error && !t.data) return <ErrorBox error={t.error} title="Could not load the trial" />;
  if (!t.data) return null;
  const res = t.data;
  const d = res.data;
  const r = d.result ?? {};
  const isAi = r.kind === "ai_dev_suite" || d.suite_id === "support-dev-v1";
  const isCanary = r.kind === "aws_canary" || d.suite_id === "aws-canary-v1";
  return (
    <div className="rise">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-faint">
        <Link to={`/app/plans/${d.plan_id}`} className="hover:text-accent">plan <span className="mono">{String(d.plan_id).slice(0, 8)}</span></Link><span>/</span><span>trial <span className="mono">{id.slice(0, 8)}</span></span>
      </div>
      <PageHeader
        eyebrow={<><FlaskConical className="size-4" /> {isAi ? "AI development suite" : isCanary ? "Canary on real AWS" : "Matched workload trial"} · {d.suite_id}</>}
        title={<>Trial <em>{res.status === "PASSED" ? "passed" : res.status === "FAILED" ? "rejected" : (res.status ?? "unknown").toLowerCase()}</em></>}
        sub={STATUS_MEANING[res.status ?? ""]}
        chips={<><StatusChip status={res.status} size="md" /><KindBadge kind={res.result_kind} prefix="result" /><KindBadge kind={res.data_origin} prefix="data" /><KindBadge kind={res.runtime_mode} prefix="mode" /></>}
        right={<div className="text-right text-[12px] text-muted"><div>trial hash</div><Hash value={d.trial_hash} /></div>}
      />
      {["QUEUED", "RUNNING"].includes(res.status ?? "") && <div className="mb-5"><Notice tone="info" icon={Info} title="Trial in progress">{isCanary ? "A disposable canary EC2 instance of the candidate type is being launched, loaded with the target's workload and measured in CloudWatch; it is terminated afterwards. " : ""}This page re-reads the trial every 2 s.</Notice></div>}
      {isCanary && r.kind && <Card className="mb-5 p-5 sm:p-6"><CanaryResult r={r} /></Card>}
      <Card className="mb-5">
        <CardHeader title="Trial checks" icon={ShieldCheck} />
        <ul className="divide-y divide-line px-5 pb-4 sm:px-6">
          {(r.checks ?? []).map((c: Json) => <CheckRow key={c.check_id} id={c.check_id} label={checkLabel(c.check_id)} status={c.status} detail={c.detail} />)}
          {!(r.checks ?? []).length && <li className="py-3 text-[14px] text-faint">No checks recorded yet.</li>}
        </ul>
        {(r.limitations ?? []).length > 0 && <div className="border-t border-line px-5 py-3 text-[12px] text-muted sm:px-6"><b className="text-ink-2">Limitations:</b> {r.limitations.join(" · ")}</div>}
      </Card>
      {r.kind && !isCanary ? (isAi ? <AiTrial r={r} /> : <CloudTrial r={r} />) : null}
      <Card className="mt-5">
        <CardHeader title="Provenance" icon={Info} />
        <div className="grid gap-6 px-5 pb-5 sm:px-6 md:grid-cols-2">
          <KV rows={[["Actor", d.actor_id], ["Trial profile", <span className="mono text-[12px]">{d.trial_profile_id}</span>], ["Profile hash", <Hash value={r.profile_hash} />], ["Started", shortTs(d.started_at)], ["Finished", shortTs(d.finished_at)], ["Executor", r.executor]]} />
          <KV rows={[["Plan", <IdLink kind="plan" id={d.plan_id} />], ["Plan hash", <Hash value={d.plan_hash} />], ...Object.entries(r.versions ?? {}).map(([k, v]) => [k.replace(/_/g, " "), v ? <span className="mono text-[12.5px] break-all">{String(v)}</span> : <span className="text-faint">none</span>] as [string, React.ReactNode])]} />
        </div>
      </Card>
    </div>
  );
}
