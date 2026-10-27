import { useEffect, useMemo, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  AlertOctagon, ArrowRight, Ban, Bot, Brain, CheckCircle2, Clock3, Cloud, FileText, FlaskConical, Gauge as GaugeIcon,
  History, Network, Scale, Search, Sparkles, StopCircle, Trophy, UserCheck, XCircle, Cpu, Database, Hourglass, Fingerprint,
} from "lucide-react";
import type { InvestigationData, InvestigationEvent, Json, MemoryItem, PlanSummary, Resource } from "../lib/api";
import { useGet, useMutation } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import { buildStory, STAGES, type Story } from "../lib/story";
import {
  ago, checkLabel, checkOf, eventLabel, planTitle, isAutopilot, isLiveAws, humanize, money, num, pct, shortTs, STATUS_MEANING, ts, signatureParts, impactBasis,
} from "../lib/format";
import {
  Button, Card, CardHeader, Empty, ErrorBox, Hash, IdLink, KindBadge, Notice, PageSkeleton, StatusChip, cx, KV, Pill, AutopilotBadge, LiveAwsBadge,
} from "../components/ui";
import { CategoryGrid, PairBars } from "../components/charts";
import { CpuEvidenceChart, PlanCard, useTelemetrySummary } from "../components/plan";
import { CanaryResult } from "../components/canary";
import { StoryFlow } from "../components/storyFlow";
import { useCopilotInvestigation } from "../components/Copilot";

const LIVE = ["QUEUED", "RUNNING", "CANCEL_REQUESTED"];

function Section({ id, eyebrow, title, sub, children, right }: { id: string; eyebrow: string; title: ReactNode; sub?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-32">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[12.5px] font-semibold uppercase tracking-[0.16em] text-accent">{eyebrow}</div>
          <h2 className="display mt-1 text-[26px] text-ink sm:text-[30px]">{title}</h2>
          {sub && <p className="mt-1 max-w-3xl text-[14px] text-muted">{sub}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Stepper({ stage, status }: { stage: string | undefined; status: string }) {
  const idx = STAGES.findIndex((s) => s.id === stage);
  const live = LIVE.includes(status);
  const failed = status === "FAILED" || status === "CANCELLED";
  return (
    <ol className="grid gap-3 md:grid-cols-4">
      {STAGES.map((s, i) => {
        const done = idx > i || (s.id === "DONE" && idx === i && !live);
        const current = idx === i && live;
        const broke = failed && idx === i;
        return (
          <li key={s.id} className={cx("relative rounded-2xl border p-4 transition", current ? "border-accent bg-accent-50/60 shadow-[0_10px_30px_-18px_rgb(36_56_245/0.8)]" : done ? "border-line bg-white" : broke ? "border-fail/30 bg-fail-bg/40" : "border-dashed border-line-2 bg-white/50")}>
            <div className="flex items-center gap-2">
              <span className={cx("grid size-7 place-items-center rounded-full text-[12px] font-bold", done ? "bg-accent text-white" : current ? "bg-white text-accent ring-2 ring-accent" : broke ? "bg-fail text-white" : "bg-lav text-faint")}>
                {done ? <CheckCircle2 className="size-4" /> : current ? <Hourglass className="size-3.5 animate-pulse" /> : broke ? <XCircle className="size-4" /> : i + 1}
              </span>
              <span className={cx("text-[14px] font-bold", done || current ? "text-ink" : "text-faint")}>{s.label}</span>
            </div>
            <p className="mt-2 text-[12px] leading-snug text-muted">{s.sub}</p>
          </li>
        );
      })}
    </ol>
  );
}

function Counter({ value, label, icon: Icon, tone = "default" }: { value: number; label: string; icon: typeof Search; tone?: "default" | "fail" | "pass" | "warn" | "accent" }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white p-4 ring-1 ring-line">
      <span className={cx("grid size-10 place-items-center rounded-xl", tone === "fail" ? "bg-fail-bg text-fail" : tone === "pass" ? "bg-pass-bg text-pass" : tone === "warn" ? "bg-warn-bg text-warn" : tone === "accent" ? "bg-accent text-white" : "bg-accent-50 text-accent")}>
        <Icon className="size-5" />
      </span>
      <div>
        <div className="font-display text-[26px] font-extrabold leading-none tracking-tight text-ink">{value}</div>
        <div className="mt-1 text-[12px] text-muted">{label}</div>
      </div>
    </div>
  );
}

function Moment({ n, title, icon: Icon, children, verdict }: { n: number; title: ReactNode; icon: typeof Search; children: ReactNode; verdict?: ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-wash/50 px-5 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-xl bg-white text-accent ring-1 ring-line"><Icon className="size-[18px]" /></span>
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wider text-faint">Moment {n}</div>
            <h3 className="font-display text-[17px] font-bold tracking-tight text-ink">{title}</h3>
          </div>
        </div>
        {verdict}
      </div>
      <div className="p-5 sm:p-6">{children}</div>
    </Card>
  );
}

function MiniStat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "fail" | "pass" }) {
  return (
    <div className="rounded-xl bg-wash p-3">
      <div className="text-[12.5px] text-muted">{label}</div>
      <div className={cx("mt-0.5 font-display text-[22px] font-bold tracking-tight", tone === "fail" ? "text-fail" : tone === "pass" ? "text-pass" : "text-ink")}>{value}</div>
      {sub && <div className="text-[12px] text-faint">{sub}</div>}
    </div>
  );
}

function targetKeyOfSig(sig: string | undefined): string | null {
  if (!sig || !sig.startsWith("cloud:")) return null;
  const body = sig.slice(6);
  return body.slice(0, body.lastIndexOf(":"));
}

// ---- Moment 1: the tempting change ----
function MomentTrap({ d, s }: { d: InvestigationData; s: Story }) {
  const p = s.trap;
  const recalledProd = s.notRepeated.find((m) => m.kind === "screening_rejection" && targetKeyOfSig(m.signature) && (d.evidence ?? []).some((e) => e.kind === "telemetry_series" && e.subject === targetKeyOfSig(m.signature)));
  const targetKey = p?.target_key ?? targetKeyOfSig(recalledProd?.signature) ?? null;
  const tel = useTelemetrySummary(d, targetKey);
  if (!p && !recalledProd) {
    return (
      <Moment n={1} title="The tempting change that would have hurt production" icon={GaugeIcon}>
        <p className="text-[14px] text-muted">This run did not screen a candidate that failed on peak CPU.{s.notRepeated.length ? ` Memory kept ${s.notRepeated.length} previously rejected candidate${s.notRepeated.length === 1 ? "" : "s"} out of this run — see “What memory changed” above.` : ""}</p>
      </Moment>
    );
  }
  if (!p && recalledProd) {
    const sp = signatureParts(recalledProd.signature);
    return (
      <Moment n={1} title="The tempting change — skipped because memory remembered" icon={GaugeIcon} verdict={<Pill icon={Brain} tone="accent">Not proposed again</Pill>}>
        <p className="mb-4 text-[14px] leading-relaxed text-ink-2">
          <b>{sp.target}</b> → <code className="mono rounded bg-lav px-1 text-[13.5px]">{sp.change}</code> looks idle on average. A previous run already rejected it under the same policy,
          so the optimizer did not spend a candidate slot on it. The chart below is this run's own telemetry for that worker.
        </p>
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <MiniStat label="Average CPU" value={`${num(tel?.summary?.avg_cpu_percent, 1)}%`} sub="telemetry_summary" />
          <MiniStat label="Peak CPU" value={`${num(tel?.summary?.peak_cpu_percent, 1)}%`} sub={`of ${tel?.inventory?.vcpu ?? "?"} vCPU`} tone="fail" />
          <MiniStat label="Current machine" value={<span className="text-[17px]">{tel?.inventory?.machine_type ?? "—"}</span>} sub={tel?.inventory?.environment} />
        </div>
        {targetKey && <CpuEvidenceChart d={d} targetKey={targetKey} />}
        <div className="mt-4 rounded-xl border border-accent/20 bg-accent-50/60 p-3 text-[13.5px] text-ink-2">
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wider text-accent"><Brain className="size-3.5" /> Recalled finding (verbatim)</div>
          <span className="[overflow-wrap:anywhere]">{recalledProd.finding}</span>
          <div className="mt-1.5"><IdLink kind="memory" id={recalledProd.memory_id} label="memory record" /></div>
        </div>
      </Moment>
    );
  }
  const plan = p!;
  const peak = checkOf(plan, "CHK-CPU-PEAK");
  const stress = checkOf(plan, "CHK-CPU-STRESS");
  const policy = checkOf(plan, "CHK-POLICY");
  const sp = signatureParts(plan.screening?.signature);
  const imp = plan.impacts ?? {};
  const fails = [peak, stress, checkOf(plan, "CHK-MEM-PEAK"), policy].filter((x) => x && x.status === "FAIL");
  return (
    <Moment n={1} title="The tempting change that would have hurt production" icon={GaugeIcon} verdict={<StatusChip status="REJECTED" size="md" />}>
      <p className="mb-4 text-[14px] leading-relaxed text-ink-2">
        The agent proposed <b>{sp.target}</b> → <code className="mono rounded bg-lav px-1 text-[13.5px]">{sp.change}</code>. On average the worker looks idle, so the cheaper
        machine looks safe. The deterministic screen checks the <b>recorded peak</b> instead.
      </p>
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MiniStat label="Average CPU" value={`${num(tel?.summary?.avg_cpu_percent, 1)}%`} sub="mean over the interval" />
        <MiniStat label="Peak demand" value={`${num(peak?.measured)} vCPU`} sub={peak?.check_id} tone="fail" />
        <MiniStat label="Allowed on candidate" value={`${num(peak?.limit)} vCPU`} sub="80% of candidate vCPU" />
        <MiniStat label="Saving refused" value={money(imp.gross_saving, imp.currency ?? "USD")} sub={`${impactBasis(imp)}; not achieved`} />
      </div>
      {plan.target_key && <CpuEvidenceChart d={d} targetKey={plan.target_key} plan={plan} />}
      <div className="mt-4 flex gap-3 rounded-xl border border-fail/25 bg-fail-bg/60 p-4">
        <Ban className="mt-0.5 size-4 shrink-0 text-fail" />
        <div className="text-[14px] text-ink-2">
          <b className="text-fail">Rejected.</b> {fails.map((c) => `${c!.check_id}: ${c!.detail}`).join(" · ")}
        </div>
      </div>
    </Moment>
  );
}

// ---- Moment 2: the revision that passed a matched trial ----
function MomentRevision({ d, s }: { d: InvestigationData; s: Story }) {
  const p = s.revision;
  const trial = p ? (d.trials ?? []).find((t) => t.plan_id === p.id) : undefined;
  const tr = useGet<Resource<Json>>(trial ? `/v1/trials/${trial.id}` : null);
  if (!p) {
    return (
      <Moment n={2} title="The evidence-driven revision that passed a matched trial" icon={FlaskConical}>
        {s.notJudged.length ? (
          <div className="space-y-2">
            {s.notJudged.map((q) => (
              <Notice key={q.id} tone="warn" icon={Clock3} title={`${signatureParts(q.screening?.signature).target} → ${signatureParts(q.screening?.signature).change}: not judged`}>
                The trial could not deliver comparable load, so the candidate was not judged either way. It stays a draft — an operator can re-run its trial from the <Link className="text-accent underline" to={`/app/plans/${q.id}`}>plan page</Link>.
              </Notice>
            ))}
          </div>
        ) : (
          <p className="text-[14px] text-muted">No cloud candidate passed a matched trial in this run.</p>
        )}
      </Moment>
    );
  }
  const res = tr.data?.data?.result ?? {};
  const summ = res.summary ?? {};
  const imp = p.impacts ?? {};
  const first = s.rejectedFirst;
  const seriesKey: string | null = p.projection?.resource_key ?? p.target_key ?? null;
  const sp = signatureParts(p.screening?.signature);
  return (
    <Moment n={2} title="The evidence-driven revision that passed a matched trial" icon={FlaskConical} verdict={<StatusChip status={trial?.status} size="md" />}>
      <p className="mb-4 text-[14px] leading-relaxed text-ink-2">
        {first ? (
          <>First try on the same target, <code className="mono rounded bg-lav px-1 text-[13.5px]">{signatureParts(first.screening?.signature).change}</code>, was rejected ({checkOf(first, "CHK-CPU-PEAK")?.detail ?? "failed screening"}). </>
        ) : null}
        <b>{sp.target}</b> → <code className="mono rounded bg-lav px-1 text-[13.5px]">{sp.change}</code>{p.revision && p.revision > 1 ? ` (revision ${p.revision}, after the critic requested more evidence)` : ""} keeps headroom over the recorded peak, then {res.kind === "aws_canary" ? "ran on a disposable canary of the candidate type on real AWS." : "ran against identical offered load on two sandbox fixtures."}
      </p>
      {seriesKey && (d.evidence ?? []).some((e) => e.kind === "telemetry_series" && e.subject === seriesKey) && (
        <div className="mb-5">
          <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-faint">Recorded demand vs what the candidate allows · {seriesKey.split("/").slice(-1)[0]}</div>
          <CpuEvidenceChart d={d} targetKey={seriesKey} plan={p} height={220} />
        </div>
      )}
      {res.kind === "aws_canary" && <div className="mb-5"><CanaryResult r={res} compact /></div>}
      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <div className="grid grid-cols-2 gap-3 self-start">
          {res.kind === "aws_canary" ? (
            <MiniStat label="Canary mean CPU" value={summ.cpu_avg_pct == null ? "—" : `${num(summ.cpu_avg_pct, 1)}%`} sub="workload was active on the candidate" />
          ) : (
            <>
              <MiniStat label="Baseline p95" value={`${num(summ.baseline_p95_ms, 1)} ms`} />
              <MiniStat label="Candidate p95" value={`${num(summ.candidate_p95_ms, 1)} ms`} tone="pass" />
              <MiniStat label="New failures" value={summ.candidate_failures ?? "—"} sub={`baseline ${summ.baseline_failures ?? "—"}`} />
            </>
          )}
          <MiniStat label="Projected saving" value={money(imp.gross_saving, imp.currency ?? "USD")} sub={`over ${num(imp.horizon_hours, 0)} h; not achieved`} />
        </div>
        <div>
          <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-faint">Trial checks</div>
          <ul className="divide-y divide-line rounded-xl border border-line px-3">
            {(res.checks ?? []).map((c: Json) => (
              <li key={c.check_id} className="flex items-start gap-2 py-2 text-[13.5px]">
                {c.status === "PASS" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-pass" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-fail" />}
                <span><b className="text-ink">{checkLabel(c.check_id)}</b> <span className="text-muted">— {c.detail}</span></span>
              </li>
            ))}
            {!res.checks && <li className="py-3 text-[13.5px] text-faint">{tr.loading ? "Loading trial…" : "No trial checks recorded."}</li>}
          </ul>
          {res.limitations?.length > 0 && <p className="mt-2 text-[12.5px] text-faint">Limits: {res.limitations.join("; ")}</p>}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px]">
        <KindBadge kind={tr.data?.result_kind} prefix="trial" /> <KindBadge kind={tr.data?.data_origin} prefix="data" />
        {trial && <IdLink kind="trial" id={trial.id} label="open trial" />} <IdLink kind="plan" id={p.id} label="open plan" />
      </div>
    </Moment>
  );
}

// ---- Moment 3: AI workflow ----
function MomentAI({ s }: { s: Story }) {
  const fail = useGet<Resource<Json>>(s.aiFail ? `/v1/trials/${s.aiFail[1].id}` : null);
  const pass = useGet<Resource<Json>>(s.aiPass ? `/v1/trials/${s.aiPass[1].id}` : null);
  if (!s.aiFail && !s.aiPass) {
    return (
      <Moment n={3} title="AI workflow: cheaper only if quality holds" icon={Bot}>
        <p className="text-[14px] text-muted">No AI candidate was trialled in this run.</p>
      </Moment>
    );
  }
  const rf = fail.data?.data?.result;
  const rp = pass.data?.data?.result;
  const base = (rf ?? rp)?.baseline;
  return (
    <Moment n={3} title="AI workflow: the cheaper prompt that dropped a policy exception" icon={Bot} verdict={rf ? <Pill icon={Trophy} tone="accent">Caught by the verifier</Pill> : undefined}>
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MiniStat label="Baseline accepted" value={base ? `${base.accepted}/${base.cases}` : "—"} sub={base ? `${base.critical_failures} critical failures` : undefined} />
        {rf && <MiniStat label="Truncated policy context" value={`${rf.candidate?.accepted}/${rf.candidate?.cases}`} sub={`${rf.candidate?.critical_failures} critical failures · rejected`} tone="fail" />}
        {rp && <MiniStat label="Relevant policy sections" value={`${rp.candidate?.accepted}/${rp.candidate?.cases}`} sub={rp.cost_per_accepted_reduction != null ? `−${pct(rp.cost_per_accepted_reduction)} cost per accepted task` : undefined} tone="pass" />}
      </div>
      {rf && (
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-faint">Truncated candidate — accepted cases by category</div>
            <CategoryGrid base={rf.baseline?.by_category ?? {}} cand={rf.candidate?.by_category ?? {}} />
          </div>
          <div>
            <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-faint">Why cheaper wasn't better</div>
            <PairBars
              rows={[
                { label: "Cost per accepted task (USD)", baseline: Number(rf.baseline?.cost_per_accepted_usd ?? NaN) || null, candidate: Number(rf.candidate?.cost_per_accepted_usd ?? NaN) || null },
                { label: "Accepted cases", baseline: rf.baseline?.accepted ?? null, candidate: rf.candidate?.accepted ?? null, better: "higher" },
                { label: "Input tokens", baseline: rf.baseline?.input_tokens ?? null, candidate: rf.candidate?.input_tokens ?? null },
              ]}
            />
            <div className="mt-4 flex gap-3 rounded-xl border border-fail/25 bg-fail-bg/60 p-3 text-[13.5px] text-ink-2">
              <Ban className="mt-0.5 size-4 shrink-0 text-fail" />
              <span><b className="text-fail">Rejected by the independent verifier ({rf.verifier}).</b> {(rf.checks ?? []).filter((c: Json) => c.status === "FAIL").map((c: Json) => `${c.check_id}: ${c.detail}`).join(" · ")}</span>
            </div>
          </div>
        </div>
      )}
      {rp && (
        <div className="mt-4 flex gap-3 rounded-xl border border-pass/25 bg-pass-bg/60 p-3 text-[13.5px] text-ink-2">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-pass" />
          <span><b className="text-pass">The revision kept every required outcome</b> at lower cost per accepted task. Cost basis: {rp.cost_basis ?? "unknown"}. Holdout evaluation is separate and controlled by the independent evaluator.</span>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {s.aiFail && <IdLink kind="trial" id={s.aiFail[1].id} label="failed trial" />}
        {s.aiPass && <IdLink kind="trial" id={s.aiPass[1].id} label="passed trial" />}
        <KindBadge kind={(fail.data ?? pass.data)?.data_origin} prefix="data" />
      </div>
    </Moment>
  );
}

// ---- Moment 4: memory ----
function MemoryRow({ m, skipped }: { m: MemoryItem; skipped?: boolean }) {
  return (
    <li className="flex flex-col gap-1.5 py-3 sm:flex-row sm:items-start sm:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-lav px-1.5 py-0.5 text-[11.5px] font-semibold uppercase text-ink-2">{humanize(m.kind)}</span>
          {skipped !== undefined && (skipped ? <Pill icon={Ban} tone="accent" className="!py-0.5 !text-[12px]">skipped this run</Pill> : <span className="text-[12px] text-faint">re-proposed</span>)}
          {m.score !== undefined && <span className="mono text-[12px] text-faint">score {m.score.toFixed(3)}</span>}
        </div>
        <p className="mt-1 text-[13.5px] leading-snug text-ink-2 [overflow-wrap:anywhere]">{m.finding}</p>
        {m.inapplicable_reasons && m.inapplicable_reasons.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {m.inapplicable_reasons.map((r) => <span key={r} className="mono rounded bg-warn-bg px-1.5 py-0.5 text-[11.5px] text-warn">{r}</span>)}
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 text-[12.5px] text-faint">
        <span>policy {m.applicability?.policy_version ?? "?"}</span>
        <IdLink kind="memory" id={m.memory_id} label="record" />
      </div>
    </li>
  );
}

// ---- What memory changed: recalled outcomes and the plans they visibly influenced ----
function memRefIds(p: PlanSummary): string[] {
  return (p.memory_refs ?? []).map((m: Json) => (typeof m === "string" ? m : m?.memory_id ?? m?.id)).filter(Boolean);
}

function MemoryChanged({ d, s }: { d: InvestigationData; s: Story }) {
  const mem = d.memory;
  const applicable = mem?.applicable ?? [];
  if (mem?.status === "off" || !applicable.length) return null;
  const plans = d.plans ?? [];
  const priorFail = (p: PlanSummary) =>
    checkOf(p, "MEM-PRIOR-FAILURE")?.status === "FAIL" || (p.critic?.check_ids ?? []).includes("MEM-PRIOR-FAILURE") || /MEM-PRIOR-FAILURE/.test(p.critic?.note ?? "");
  const rows = applicable.map((m) => {
    const influenced = plans.filter((p) => memRefIds(p).includes(m.memory_id) || (priorFail(p) && p.screening?.signature === m.signature));
    const skipped = s.notRepeated.includes(m);
    return { m, influenced, skipped };
  });
  const effective = rows.filter((r) => r.influenced.length || r.skipped).length;
  return (
    <div className="overflow-hidden rounded-[22px] border border-accent/25 bg-gradient-to-br from-accent-50 to-white shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-accent/15 px-5 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-accent text-white"><Brain className="size-5" /></span>
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wider text-accent">What memory changed</div>
            <div className="font-display text-[17px] font-bold tracking-tight text-ink">
              {applicable.length} applicable memor{applicable.length === 1 ? "y" : "ies"} recalled · {effective} changed what the agents did
            </div>
          </div>
        </div>
        <span className="text-[12.5px] text-muted">Memory informs proposals and critique; it never authorises an action.</span>
      </div>
      <ul className="divide-y divide-accent/10">
        {rows.map(({ m, influenced, skipped }) => {
          const sp = signatureParts(m.signature);
          return (
            <li key={m.memory_id} className="grid gap-3 px-5 py-3.5 sm:px-6 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md bg-white px-1.5 py-0.5 text-[11.5px] font-semibold uppercase text-ink-2 ring-1 ring-line">{humanize(m.kind)}</span>
                  <span className="text-[14px] font-semibold text-ink">{sp.target}{sp.change ? ` → ${sp.change}` : ""}</span>
                  <IdLink kind="memory" id={m.memory_id} label="record" />
                </div>
                <p className="mt-1 line-clamp-2 text-[12px] text-muted [overflow-wrap:anywhere]" title={m.finding}>{m.finding}</p>
              </div>
              <div className="min-w-0 space-y-1.5">
                {influenced.map((p) => (
                  <Link key={p.id} to={`/app/plans/${p.id}`} className="flex items-start gap-2 rounded-xl bg-white px-3 py-2 text-[13.5px] ring-1 ring-line hover:ring-accent/40">
                    <Ban className="mt-0.5 size-3.5 shrink-0 text-fail" />
                    <span className="min-w-0">
                      <b className="text-ink">Re-proposal stopped</b> <span className="mono text-[12px] text-faint">{p.id.slice(0, 8)}</span>
                      {p.critic?.note && <span className="block text-muted [overflow-wrap:anywhere]">Critic: “{p.critic.note}”</span>}
                    </span>
                  </Link>
                ))}
                {skipped && !influenced.length && (
                  <div className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-[13.5px] ring-1 ring-line"><CheckCircle2 className="size-3.5 text-pass" /> <b className="text-ink">Not proposed again</b> <span className="text-muted">— no candidate slot spent</span></div>
                )}
                {!skipped && !influenced.length && (
                  <div className="px-1 text-[12px] text-faint">{m.kind === "validated_plan" ? "Prior success, kept as context" : "Recalled as context; no visible effect on this run's candidates"}</div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function MomentMemory({ d, s }: { d: InvestigationData; s: Story }) {
  const emb = d.memory?.embedding_profile;
  if (s.memoryStatus === "off") {
    return (
      <Moment n={4} title="Memory: the agent does not repeat a known failure" icon={Brain} verdict={<StatusChip status="off" label="memory off" />}>
        <Notice tone="info" icon={Brain} title="Memory was off for this run">Every option was screened from scratch. Start the same investigation with memory on to see prior failures recalled and skipped.</Notice>
      </Moment>
    );
  }
  return (
    <Moment n={4} title="Memory: the agent does not repeat a known failure" icon={Brain} verdict={s.recalled.length ? <Pill icon={Brain} tone="accent">{s.notRepeated.length} of {s.recalled.length} skipped</Pill> : undefined}>
      {s.recalled.length === 0 ? (
        <p className="text-[14px] text-muted">No applicable prior failure was recalled for this run{d.memory?.status ? ` (memory status: ${d.memory.status})` : ""}.</p>
      ) : (
        <>
          <p className="mb-2 text-[14px] text-ink-2">
            Meterless H-MEM recalled <b>{s.recalled.length}</b> applicable prior failure{s.recalled.length === 1 ? "" : "s"}; <b>{s.notRepeated.length}</b> {s.notRepeated.length === 1 ? "was" : "were"} not proposed again.
            Applicability (policy, test, workload, config, model versions) is checked outside retrieval.
          </p>
          <ul className="divide-y divide-line">{s.recalled.map((m) => <MemoryRow key={m.memory_id} m={m} skipped={s.notRepeated.includes(m)} />)}</ul>
        </>
      )}
      {s.historical.length > 0 && (
        <Notice tone="warn" icon={History} title={`${s.historical.length} older record${s.historical.length === 1 ? "" : "s"} no longer match current versions`}>
          Shown as history only — retest required, not used to skip anything.
        </Notice>
      )}
      {emb && (
        <div className="mt-3 text-[12.5px] text-faint">
          Embedder <span className="mono">{emb.model_id}</span> ({emb.kind}, {emb.dimensions}d){emb.semantic === false ? " — hash conformance path, not semantic-recall evidence." : " — semantic."}
        </div>
      )}
    </Moment>
  );
}

// ---- What is left for a human ----
function AwaitingRow({ p }: { p: PlanSummary }) {
  const r = useGet<Resource<Json>>(`/v1/plans/${p.id}`);
  const blockers = r.data?.blockers ?? [];
  const acts = r.data?.next_allowed_actions ?? [];
  const sp = signatureParts(p.screening?.signature);
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 sm:flex-row sm:items-center">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-warn-bg text-warn"><UserCheck className="size-5" /></span>
      <div className="min-w-0 flex-1">
        <div className="text-[14px] font-bold text-ink">{p.path === "ai" ? "Support AI workflow" : sp.target} → <span className="font-medium">{p.path === "ai" ? sp.change : sp.change}</span></div>
        {r.loading ? (
          <div className="text-[13.5px] text-faint">Checking what blocks approval…</div>
        ) : blockers.length ? (
          <ul className="mt-1 space-y-0.5">
            {blockers.map((b: string) => <li key={b} className="flex items-start gap-1.5 text-[13.5px] text-fail"><Ban className="mt-0.5 size-3.5 shrink-0" /> {b}</li>)}
          </ul>
        ) : (
          <div className="mt-0.5 text-[13.5px] text-pass">No blockers reported. Allowed now: {acts.join(", ") || "nothing"}</div>
        )}
      </div>
      <Link to={`/app/plans/${p.id}`} className="inline-flex items-center gap-1 self-start rounded-full bg-ink px-3.5 py-2 text-[13.5px] font-semibold text-white hover:bg-ink-2 sm:self-center">
        Review plan <ArrowRight className="size-3.5" />
      </Link>
    </li>
  );
}

function MomentHuman({ d, s }: { d: InvestigationData; s: Story }) {
  return (
    <Moment n={5} title={(d.actions ?? []).length ? "What a human decided" : "What is left for a human"} icon={UserCheck}>
      {s.awaiting.length === 0 && (d.actions ?? []).length === 0 && <p className="text-[14px] text-muted">Nothing is waiting for approval in this run.</p>}
      <ul className="space-y-3">{s.awaiting.map((p) => <AwaitingRow key={p.id} p={p} />)}</ul>
      {(d.actions ?? []).length > 0 && (
        <ul className="mt-3 space-y-3">
          {(d.actions ?? []).map((a: Json) => {
            const p = (d.plans ?? []).find((x) => x.id === a.plan_id);
            return (
              <li key={a.id}>
                <Link to={`/app/actions/${a.id}`} className={cx("flex flex-col gap-3 rounded-2xl border p-4 transition hover:shadow-[var(--shadow-card)] sm:flex-row sm:items-center", a.status === "VERIFIED" ? "border-pass/30 bg-pass-bg/40" : "border-line bg-white")}>
                  <span className={cx("grid size-10 shrink-0 place-items-center rounded-xl", a.status === "VERIFIED" ? "bg-pass text-white" : "bg-lav text-accent")}><CheckCircle2 className="size-5" /></span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-bold text-ink">{a.status === "VERIFIED" ? "A human approved the exact hashes; the change was executed once and verified" : `Action ${humanize(a.status).toLowerCase()}`}</div>
                    <div className="mt-0.5 text-[13.5px] text-muted">{p ? planTitle(p) : `plan ${String(a.plan_id).slice(0, 8)}`} · memory sync {a.memory_sync_status ?? "unknown"} · {p?.executor === "aws" ? "real AWS EC2 change" : "local analogue, not a cloud resize"}</div>
                  </div>
                  <span className="flex items-center gap-2"><StatusChip status={a.status} /><ArrowRight className="size-4 text-faint" /></span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Moment>
  );
}

// ---- Evidence / federation ----
function FederationReceipt({ d }: { d: InvestigationData }) {
  const fed = d.federation;
  const ev = useGet<Resource<Json>>(fed?.evidence_id ? `/v1/evidence/${fed.evidence_id}` : null);
  if (!fed) return <Empty title="No federation receipt" icon={Network}>This investigation did not record a cross-source query.</Empty>;
  const rc = ev.data?.data?.receipt ?? {};
  const row = (fed.rows ?? [])[0] ?? {};
  const isSample = fed.source_system === "local_sample_postgres";
  return (
    <Card className="overflow-hidden">
      <div className="grid lg:grid-cols-[1.1fr_1fr]">
        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="grid size-9 place-items-center rounded-xl bg-accent text-white"><Network className="size-[18px]" /></span>
            <div>
              <div className="font-display text-[17px] font-bold">Federation receipt</div>
              <div className="text-[12px] text-muted">{rc.template_id ?? "service_cost_rollup"} v{rc.template_version ?? "?"} · {fed.cross_source ? "cross-source join" : "single source"}</div>
            </div>
            <span className="ml-auto"><StatusChip status={rc.completeness ?? ev.data?.status} /></span>
          </div>
          {isSample && (
            <div className="mt-4"><Notice tone="unknown" icon={Database} title="Sample mode: local fixture database">This receipt came from the local sample PostgreSQL, not Zetaris. It shows the receipt shape; it is not federation proof.</Notice></div>
          )}
          {/* sources → join */}
          <div className="mt-5 flex items-center gap-3">
            <div className="flex flex-col gap-2">
              {(fed.sources ?? []).map((s: string) => (
                <span key={s} className="inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-[13.5px] font-semibold ring-1 ring-line"><Database className="size-4 text-accent" /> <span className="mono">{s}</span></span>
              ))}
            </div>
            <svg width="56" height="64" viewBox="0 0 56 64" aria-hidden className="shrink-0">
              <path d="M2 14 C 30 14, 26 32, 54 32" stroke="#2438f5" strokeWidth="1.4" fill="none" className="flow" />
              <path d="M2 50 C 30 50, 26 32, 54 32" stroke="#2438f5" strokeWidth="1.4" fill="none" className="flow" />
            </svg>
            <div className="min-w-0 flex-1 rounded-xl bg-accent-50 p-3 ring-1 ring-accent-100">
              <div className="text-[12px] font-semibold uppercase tracking-wider text-accent">{row.service_id ?? "service"} rollup</div>
              <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 text-[13.5px]">
                <span className="text-muted">cloud cost</span><span className="text-right font-semibold tnum">{money(row.cloud_cost, row.currency ?? "USD")}</span>
                <span className="text-muted">billing rows</span><span className="text-right font-semibold tnum">{num(row.billing_rows, 0)}</span>
                <span className="text-muted">model calls</span><span className="text-right font-semibold tnum">{num(row.model_calls, 0)}</span>
                <span className="text-muted">tokens in/out</span><span className="text-right font-semibold tnum">{num(row.input_tokens, 0)} / {num(row.output_tokens, 0)}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="border-t border-line bg-wash/60 p-5 sm:p-6 lg:border-l lg:border-t-0">
          <KV
            rows={[
              ["Source system", <span className="mono text-[12px]">{fed.source_system}</span>],
              ["Query / request IDs", (rc.request_ids ?? []).length ? <span className="mono text-[12.5px]">{rc.request_ids.join(", ")}</span> : <span className="text-faint">none recorded{isSample ? " (local fixture)" : ""}</span>],
              ["Pages", rc.page_count ?? "—"],
              ["Rows", rc.row_count ?? "—"],
              ["Duration", rc.duration_ms !== undefined ? `${rc.duration_ms} ms` : "—"],
              ["Parameter hash", <Hash value={rc.parameter_hash} />],
              ["Result hash", <Hash value={rc.result_hash} />],
              ["Receipt", rc.receipt_id ? <span className="mono text-[12.5px]">{rc.receipt_id}</span> : "—"],
            ]}
          />
          {(rc.warnings ?? []).length > 0 && <div className="mt-2 text-[12.5px] text-warn">{rc.warnings.join("; ")}</div>}
          <div className="mt-3"><IdLink kind="evidence" id={fed.evidence_id} label="open evidence record" /></div>
        </div>
      </div>
    </Card>
  );
}

function ForecastCards({ d }: { d: InvestigationData }) {
  const f = d.forecast ?? {};
  const keys = Object.keys(f);
  if (!keys.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {keys.map((k) => {
        const x = f[k];
        return (
          <div key={k} className="card p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[14px] font-bold text-ink">{k.split("/").slice(-1)[0]}</span>
              <span className="text-[11.5px] text-faint">{k.split("/")[1]}</span>
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="font-display text-[26px] font-extrabold tracking-tight">{num(x.stress_peak_cpu_pct, 1)}%</span>
              <span className="text-[12px] text-muted">stress peak CPU</span>
            </div>
            <div className="mt-1 text-[12.5px] text-muted">{x.observations} obs · residual q95 {num(x.residual_q95_pct)}% · {x.horizon_quarter_hours / 4} h horizon</div>
            <div className="mt-2 rounded-lg bg-warn-bg/60 px-2 py-1 text-[12px] text-warn">{x.label}</div>
            <div className="mono mt-2 text-[11.5px] text-faint">{x.method}</div>
          </div>
        );
      })}
    </div>
  );
}

function EvidenceList({ d }: { d: InvestigationData }) {
  const ev = d.evidence ?? [];
  if (!ev.length) return <Empty title="No evidence retrieved yet" icon={Database} />;
  return (
    <div className="flex flex-wrap gap-2">
      {ev.map((e) => (
        <Link key={e.id} to={`/app/evidence/${e.id}`} className="group inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 ring-1 ring-line transition hover:ring-accent/40">
          <Fingerprint className="size-3.5 text-accent" />
          <span className="text-[13.5px] font-semibold text-ink group-hover:text-accent">{humanize(e.kind)}</span>
          {e.subject && <span className="text-[12px] text-faint">{e.subject.split("/").slice(-1)[0]}</span>}
          <span className="mono text-[11.5px] text-faint">{e.id.slice(0, 6)}</span>
        </Link>
      ))}
    </div>
  );
}

// ---- Report: investigator + agents ----
function AgentsPanel({ d }: { d: InvestigationData }) {
  const prog = d.progress ?? {};
  const obs: Json[] = d.investigator?.observations ?? [];
  const calls: Json[] = prog.model_calls ?? [];
  const b = prog.budget ?? {};
  return (
    <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
      <Card>
        <CardHeader title="Investigator findings" icon={Search} sub="Model text summarising evidence — each line cites the evidence it read" />
        <ul className="divide-y divide-line px-5 pb-4 sm:px-6">
          {obs.length === 0 && <li className="py-3 text-[14px] text-faint">No investigator observations recorded.</li>}
          {obs.map((o, i) => (
            <li key={i} className="py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[14px] font-semibold text-ink">{String(o.resource_key ?? "").split("/").slice(-1)[0]}</span>
                <span className="flex gap-1">{(o.evidence_ids ?? []).map((e: string) => <IdLink key={e} kind="evidence" id={e} label={e.slice(0, 6)} />)}</span>
              </div>
              <p className="mt-0.5 text-[13.5px] text-muted">{o.finding}</p>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <CardHeader title="Agent budget" icon={Cpu} sub="Bounded roles; usage counted against an approved budget profile" />
        <div className="px-5 pb-5 sm:px-6">
          <div className="grid grid-cols-3 gap-2">
            <MiniStat label="Rounds" value={prog.rounds ?? "—"} />
            <MiniStat label="Requests" value={b.model_requests_used_by_roles ?? "—"} sub={`cap ${b.max_model_calls ?? "?"}`} />
            <MiniStat label="Candidates" value={`${(prog.candidates_used?.cloud ?? 0) + (prog.candidates_used?.ai ?? 0)}`} sub={`cap ${prog.candidate_cap_per_path ?? "?"}/path`} />
          </div>
          <table className="mt-4 w-full text-[13.5px]">
            <thead><tr className="text-left text-[12px] uppercase tracking-wider text-faint"><th className="py-1">Role</th><th>Calls</th><th className="text-right">Tokens in / out</th></tr></thead>
            <tbody className="divide-y divide-line">
              {calls.map((c) => (
                <tr key={c.role}><td className="py-1.5 font-semibold capitalize text-ink">{c.role}</td><td className="tnum">{c.requests}</td><td className="text-right tnum text-muted">{c.input_tokens ?? "unknown"} / {c.output_tokens ?? "unknown"}</td></tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 text-[12px] text-faint">Run cost cap {money(b.max_run_cost_usd)} at a conservative {money(b.conservative_cost_per_call_usd, "USD", 4)} per call.</div>
        </div>
      </Card>
    </div>
  );
}

function Timeline({ events, live }: { events: InvestigationEvent[]; live: boolean }) {
  if (!events.length) return <Empty title="No events yet" icon={Clock3}>{live ? "Waiting for the worker to pick this up…" : "Nothing was recorded."}</Empty>;
  const iconFor = (k: string) =>
    k.startsWith("model.") ? Sparkles : k.startsWith("trial.") ? FlaskConical : k.startsWith("plan.") ? Scale : k.startsWith("stage.") ? ArrowRight : k.includes("memory") ? Brain : k.includes("cancel") ? StopCircle : FileText;
  return (
    <ol className="relative">
      {events.map((e, i) => {
        const Icon = iconFor(e.kind);
        const p = e.payload ?? {};
        const status = p.status ?? p.screening ?? p.critic?.verdict ?? (e.kind === "stage.entered" ? p.stage : undefined);
        const subject = p.signature ?? p.reason ?? (p.plan_id ? `plan ${String(p.plan_id).slice(0, 8)}` : p.trial_id ? `trial ${String(p.trial_id).slice(0, 8)}` : p.output?.focus ?? "");
        return (
          <li key={e.seq} className="relative flex gap-3 pb-4 last:pb-0">
            {i < events.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-line" />}
            <span className={cx("relative grid size-8 shrink-0 place-items-center rounded-full ring-4 ring-wash", e.kind.startsWith("model.") ? "bg-accent text-white" : "bg-white text-accent ring-1")}>
              <Icon className="size-3.5" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-[14px] font-semibold text-ink">{eventLabel(e.kind)}</span>
                {status && typeof status === "string" && <StatusChip status={status} size="xs" />}
                <span className="ml-auto text-[12px] text-faint" title={ts(e.at)}>#{e.seq} · {shortTs(e.at)}</span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[12px] text-muted">
                <span className="mono text-[12px]">{e.actor}</span>
                {subject && <span className="min-w-0 truncate">· {String(subject).slice(0, 140)}</span>}
                {p.model_id && <span className="mono text-[12px] text-faint">· {p.model_id}{p.duration_ms !== undefined ? ` · ${p.duration_ms} ms` : ""}</span>}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const NAV = [
  ["progress", "Progress"],
  ["story", "Story"],
  ["plans", "Plans"],
  ["evidence", "Evidence"],
  ["memory", "Memory"],
  ["agents", "Agents"],
  ["timeline", "Timeline"],
] as const;

export default function InvestigationDetail() {
  const { id = "" } = useParams();
  const { canOperate } = useAuth();
  useCopilotInvestigation(id);
  const inv = useGet<Resource<InvestigationData>>(`/v1/investigations/${id}`, { pollMs: 2000, shouldPoll: (d) => !!d && LIVE.includes(d.status ?? "") });
  const live = !!inv.data && LIVE.includes(inv.data.status ?? "");
  const events = useGet<{ items: InvestigationEvent[]; next_sequence: number }>(`/v1/investigations/${id}/events?limit=500`, { pollMs: 2000, shouldPoll: () => live });
  const cancel = useMutation<Json>();
  const story = useMemo(() => (inv.data ? buildStory(inv.data.data) : null), [inv.data]);
  const loc = useLocation();
  const loaded = !!inv.data;
  useEffect(() => {
    // Deep links like #memory target sections that only exist once the record has loaded.
    if (!loaded || !loc.hash) return;
    const t = setTimeout(() => document.getElementById(loc.hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), 150);
    return () => clearTimeout(t);
  }, [loaded, loc.hash]);

  if (inv.loading && !inv.data) return <PageSkeleton />;
  if (inv.error && !inv.data) return <ErrorBox error={inv.error} title="Could not load the investigation" />;
  if (!inv.data || !story) return null;
  const res = inv.data;
  const d = res.data;
  const i = d.investigation ?? {};
  const status = res.status ?? "UNKNOWN";
  const outcome = d.outcome ?? {};
  const plans = d.plans ?? [];
  const cloud = plans.filter((p) => p.path === "cloud");
  const ai = plans.filter((p) => p.path === "ai");
  const evs = events.data?.items ?? [];

  return (
    <div className="rise space-y-8">
      {/* Header */}
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-faint">
          <Link to="/app/investigations" className="hover:text-accent">Investigations</Link>
          <span>/</span>
          <span className="mono">{id.slice(0, 8)}</span>
        </div>
        <div className="flex flex-wrap items-start justify-between gap-4 lg:flex-nowrap">
          <div className="min-w-0 flex-1">
            <h1 className="display max-w-4xl text-[26px] text-ink sm:text-[32px]">{i.question}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusChip status={status} size="md" />
              {isAutopilot(i) && <AutopilotBadge />}
              {isLiveAws(i.service_id) && <LiveAwsBadge />}
              <KindBadge kind={res.runtime_mode} prefix="mode" />
              <KindBadge kind={res.data_origin} prefix="data" />
              <Pill icon={Brain} className="!py-0.5">memory {i.memory_mode}</Pill>
              <span className="text-[12px] text-muted">{shortTs(i.interval_start)} → {shortTs(i.interval_end)} · policy {i.policy_version} · by {i.actor_id} · {ago(i.created_at)}</span>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Link to={`/app/reports/${id}`}><Button variant="secondary" icon={FileText}>Report</Button></Link>
            {canOperate && res.next_allowed_actions.includes("cancel") && (
              <Button variant="danger" icon={StopCircle} loading={cancel.pending} onClick={async () => { if (await cancel.run(`/v1/investigations/${id}/cancel`, { reason: "operator cancelled from the workbench" })) inv.reload(); }}>
                Cancel
              </Button>
            )}
          </div>
        </div>
        <div className="mt-3"><ErrorBox error={cancel.error} title="Cancel failed" /></div>
      </div>

      {/* Outcome banner */}
      {status === "NO_CHANGE" ? (
        <Notice tone="ok" icon={Trophy} title="Justified no-change — the evidence loop worked">{STATUS_MEANING.NO_CHANGE}. Every candidate's reason is retained below.</Notice>
      ) : outcome.error ? (
        <Notice tone="fail" icon={AlertOctagon} title={`${status}: ${outcome.error.code}`}>{outcome.error.message}</Notice>
      ) : live ? (
        <Notice tone="info" icon={Hourglass} title={`${humanize(status)} — stage ${d.progress?.stage ?? i.stage ?? "?"}`}>Polling persisted events every 2 s. Leaving this page does not stop the run.</Notice>
      ) : status === "COMPLETED" && (d.actions ?? []).some((a: Json) => a.status === "VERIFIED") ? (
        <Link to={`/app/actions/${(d.actions ?? []).find((a: Json) => a.status === "VERIFIED").id}`} className="flex items-center gap-3 rounded-2xl border border-pass/30 bg-pass-bg/60 p-4 transition hover:border-pass/50">
          <CheckCircle2 className="size-5 shrink-0 text-pass" />
          <span className="min-w-0 flex-1 text-[15px] text-ink-2"><b className="text-ink">Completed with a verified change.</b> One plan was approved by a person, executed once and verified{outcome.decided_at ? ` · decided ${shortTs(outcome.decided_at)}` : ""}.</span>
          <span className="hidden items-center gap-1 text-[14px] font-semibold text-pass sm:inline-flex">See the result <ArrowRight className="size-4" /></span>
        </Link>
      ) : STATUS_MEANING[status] ? (
        <Notice tone={status === "AWAITING_APPROVAL" || status === "NEEDS_REVIEW" ? "warn" : "info"} icon={status === "AWAITING_APPROVAL" ? UserCheck : CheckCircle2} title={humanize(status)}>{STATUS_MEANING[status]}{outcome.decided_at ? ` · decided ${shortTs(outcome.decided_at)}` : ""}</Notice>
      ) : null}

      {/* Section nav */}
      <nav className="sticky top-16 z-20 -mx-4 overflow-x-auto border-b border-line/70 bg-wash px-4 py-2 scroll-thin sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        <div className="flex gap-1">
          {(live ? NAV : [NAV[1], NAV[0], ...NAV.slice(2)]).map(([k, l]) => (
            <a key={k} href={`#${k}`} className="whitespace-nowrap rounded-full px-3 py-1.5 text-[13.5px] font-semibold text-muted hover:bg-white hover:text-ink">{l}</a>
          ))}
        </div>
      </nav>

      {live ? <>
      <Section id="progress" eyebrow="Progress" title={<>How far the run <em>got</em></>} right={live ? <span className="inline-flex items-center gap-2 text-[13.5px] font-semibold text-accent"><span className="pulse-dot size-2 rounded-full bg-accent" /> live</span> : undefined}>
        <Stepper stage={d.progress?.stage ?? i.stage} status={status} />
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Counter value={story.counts.screened} label="Candidates screened" icon={Scale} />
          <Counter value={story.counts.rejected} label="Rejected with evidence" icon={Ban} tone="fail" />
          <Counter value={story.counts.trialsPassed} label="Passed a matched trial" icon={FlaskConical} tone="pass" />
          <Counter value={story.counts.awaiting} label="Awaiting approval" icon={UserCheck} tone="warn" />
          <Counter value={story.counts.recalled} label="Prior failures recalled" icon={Brain} tone="accent" />
        </div>
        {live && (
          <Card className="mt-4 p-5 sm:p-6">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[14px] font-bold text-ink">Latest events</span>
              <span className="text-[12.5px] text-faint">newest first · {evs.length} so far</span>
            </div>
            <Timeline events={[...evs].reverse().slice(0, 6)} live />
          </Card>
        )}
      </Section>

      <Section id="story" eyebrow="The story" title={!isLiveAws(i.service_id) ? <>The decisions that <em>mattered</em></> : (d.actions ?? []).some((a: Json) => a.status === "VERIFIED") ? <>From evidence to a <em>verified change</em></> : (plans.length && plans.every((p) => p.status === "REJECTED")) || status === "NO_CHANGE" ? <>Why <em>nothing</em> was changed</> : <>From evidence to a <em>decision</em></>} sub="Every number below is read from a committed record; where a step didn't happen, the page says so.">
        {live ? (
          <Empty title="The story is written when the run finishes" icon={Hourglass}>Follow progress above and the timeline below.</Empty>
        ) : (
          isLiveAws(i.service_id) ? (
            <StoryFlow d={d} s={story} />
          ) : (
          <div className="space-y-5">
            <MemoryChanged d={d} s={story} />
            <MomentTrap d={d} s={story} />
            <MomentRevision d={d} s={story} />
            <MomentAI s={story} />
            <MomentMemory d={d} s={story} />
            <MomentHuman d={d} s={story} />
          </div>
          )
        )}
      </Section>

      </> : <>
      <Section id="story" eyebrow="The story" title={!isLiveAws(i.service_id) ? <>The decisions that <em>mattered</em></> : (d.actions ?? []).some((a: Json) => a.status === "VERIFIED") ? <>From evidence to a <em>verified change</em></> : (plans.length && plans.every((p) => p.status === "REJECTED")) || status === "NO_CHANGE" ? <>Why <em>nothing</em> was changed</> : <>From evidence to a <em>decision</em></>} sub="Every number below is read from a committed record; where a step didn't happen, the page says so.">
        {live ? (
          <Empty title="The story is written when the run finishes" icon={Hourglass}>Follow progress above and the timeline below.</Empty>
        ) : (
          isLiveAws(i.service_id) ? (
            <StoryFlow d={d} s={story} />
          ) : (
          <div className="space-y-5">
            <MemoryChanged d={d} s={story} />
            <MomentTrap d={d} s={story} />
            <MomentRevision d={d} s={story} />
            <MomentAI s={story} />
            <MomentMemory d={d} s={story} />
            <MomentHuman d={d} s={story} />
          </div>
          )
        )}
      </Section>

      <Section id="progress" eyebrow="Progress" title={<>How far the run <em>got</em></>} right={live ? <span className="inline-flex items-center gap-2 text-[13.5px] font-semibold text-accent"><span className="pulse-dot size-2 rounded-full bg-accent" /> live</span> : undefined}>
        <Stepper stage={d.progress?.stage ?? i.stage} status={status} />
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Counter value={story.counts.screened} label="Candidates screened" icon={Scale} />
          <Counter value={story.counts.rejected} label="Rejected with evidence" icon={Ban} tone="fail" />
          <Counter value={story.counts.trialsPassed} label="Passed a matched trial" icon={FlaskConical} tone="pass" />
          <Counter value={story.counts.awaiting} label="Awaiting approval" icon={UserCheck} tone="warn" />
          <Counter value={story.counts.recalled} label="Prior failures recalled" icon={Brain} tone="accent" />
        </div>
        {live && (
          <Card className="mt-4 p-5 sm:p-6">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[14px] font-bold text-ink">Latest events</span>
              <span className="text-[12.5px] text-faint">newest first · {evs.length} so far</span>
            </div>
            <Timeline events={[...evs].reverse().slice(0, 6)} live />
          </Card>
        )}
      </Section>

      </>}

      <Section id="plans" eyebrow="Plans" title={<>Candidates, <em>side by side</em></>} sub={d.queue_order ? `Queue order: ${d.queue_order}.` : undefined}>
        {plans.length === 0 ? (
          <Empty title="No plans" icon={Scale}>{live ? "Candidates appear here once the optimizer proposes them." : "This run produced no candidate plans."}</Empty>
        ) : (
          <div className="space-y-6">
            {[["cloud", "Cloud path", Cloud, cloud], ["ai", "AI workflow path", Bot, ai]].map(([k, label, Icon, list]) => {
              const L = list as PlanSummary[];
              if (!L.length) return null;
              const I = Icon as typeof Cloud;
              return (
                <div key={k as string}>
                  <div className="mb-3 flex items-center gap-2 text-[14px] font-bold text-ink-2"><I className="size-4 text-accent" /> {label as string} <span className="text-faint">· {L.length} of {d.progress?.candidate_cap_per_path ?? 3} allowed</span></div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{L.map((p) => <PlanCard key={p.id} plan={p} feedback={d.feedback} />)}</div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      <Section id="evidence" eyebrow="Evidence" title={<>Where the numbers <em>came from</em></>} sub="Evidence is read through approved, versioned SQL templates; each read leaves a receipt.">
        <div className="space-y-5">
          <FederationReceipt d={d} />
          {Object.keys(d.forecast ?? {}).length > 0 && (
            <div>
              <div className="mb-3 text-[14px] font-bold text-ink-2">Forecast stress envelopes</div>
              <ForecastCards d={d} />
            </div>
          )}
          <div>
            <div className="mb-3 text-[14px] font-bold text-ink-2">All evidence records · {(d.evidence ?? []).length}</div>
            <EvidenceList d={d} />
          </div>
        </div>
      </Section>

      <Section id="memory" eyebrow="Memory" title={<>What the agents <em>remembered</em></>} sub="Recall is scoped to this tenant and service before scoring; applicability is enforced after retrieval. Memory informs — it never authorises.">
        <Card className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip status={d.memory?.status ?? "unknown"} label={`memory ${d.memory?.status ?? "unknown"}`} />
            {(d.memory?.queries ?? []).map((q, qi) => <span key={`${qi}-${q}`} className="rounded-lg bg-lav px-2 py-1 text-[12px] text-ink-2">“{q}”</span>)}
          </div>
          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <div>
              <div className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-pass">Applicable · {(d.memory?.applicable ?? []).length}</div>
              {(d.memory?.applicable ?? []).length ? (
                <ul className="divide-y divide-line">{(d.memory?.applicable ?? []).map((m) => <MemoryRow key={m.memory_id} m={m} />)}</ul>
              ) : <p className="py-3 text-[14px] text-faint">None.</p>}
            </div>
            <div>
              <div className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-warn">Historical — not applicable · {(d.memory?.historical ?? []).length}</div>
              {(d.memory?.historical ?? []).length ? (
                <ul className="divide-y divide-line">{(d.memory?.historical ?? []).map((m) => <MemoryRow key={m.memory_id} m={m} />)}</ul>
              ) : <p className="py-3 text-[14px] text-faint">None.</p>}
            </div>
          </div>
          {d.memory?.engine && (
            <div className="mt-4 border-t border-line pt-3 text-[12.5px] text-faint">
              Engine <span className="mono">{d.memory.engine.package}@{d.memory.engine.version}</span> (upstream <span className="mono">{String(d.memory.engine.upstream_sha ?? "").slice(0, 10)}</span>) · embedder <span className="mono">{d.memory.embedding_profile?.model_id}</span>
              {d.memory.embedding_profile?.semantic === false && <span className="text-warn"> — hash conformance, not semantic-recall evidence</span>}
            </div>
          )}
        </Card>
      </Section>

      <Section id="agents" eyebrow="Agents" title={<>What each role <em>did</em></>}>
        <AgentsPanel d={d} />
      </Section>

      <Section id="timeline" eyebrow="Timeline" title={<>Every persisted <em>event</em></>} sub="Monotonic, persisted and polled — there is no push channel." right={<span className="text-[12px] text-faint">{evs.length} events</span>}>
        <Card className="p-5 sm:p-6">
          {events.error ? <ErrorBox error={events.error} /> : <Timeline events={evs} live={live} />}
        </Card>
      </Section>
    </div>
  );
}
