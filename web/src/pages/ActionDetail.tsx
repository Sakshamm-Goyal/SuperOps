import { Link, useParams } from "react-router-dom";
import {
  Activity, ShieldCheck, Undo2, Brain, AlertOctagon, Info, PenLine, FileCheck2, BadgeCheck, CheckCircle2, XCircle, Server, ArrowRight, Hourglass,
} from "lucide-react";
import type { Json, Resource } from "../lib/api";
import { useGet } from "../lib/hooks";
import { shortTs, STATUS_MEANING, humanize, num } from "../lib/format";
import { Card, CardHeader, ErrorBox, Hash, IdLink, KindBadge, KV, Notice, PageHeader, PageSkeleton, StatusChip, cx, Pill, LiveAwsBadge } from "../components/ui";
import { useCopilotInvestigation } from "../components/Copilot";

const ACTIVE = ["QUEUED", "EXECUTING", "PENDING_VERIFICATION", "RECOVERING"];
const STAGES: { id: string; label: string; icon: typeof PenLine; sub: string; awsSub: string }[] = [
  { id: "INTENT", label: "Intent persisted", icon: PenLine, sub: "Plan hash, expected version and idempotent operation id written before any provider call", awsSub: "Plan hash, expected version and idempotent operation id written before any AWS call" },
  { id: "WRITE_APPLIED", label: "Write applied", icon: FileCheck2, sub: "Compare-and-set write to the target; new config version recorded", awsSub: "EC2 stop → modify instance type → tag version → start; downtime measured stop to running" },
  { id: "VERIFIED", label: "Verified", icon: BadgeCheck, sub: "Config read back from the running worker and a fresh workload passed", awsSub: "Type read back, EC2 status checks OK and CloudWatch CPU measured against the policy limit" },
];

function JsonBlock({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-faint">—</span>;
  return <pre className="mono max-h-64 overflow-auto rounded-xl bg-wash p-3 text-[12.5px] leading-relaxed text-ink-2 scroll-thin">{JSON.stringify(value, null, 2)}</pre>;
}

function show(v: unknown) {
  return v === undefined ? "—" : v === null ? "null" : typeof v === "object" ? JSON.stringify(v) : String(v);
}

function BeforeAfter({ before, after, beforeHash, afterHash }: { before: Json; after: Json; beforeHash?: string; afterHash?: string }) {
  const b = before ?? {};
  const a = after ?? {};
  const keys = Array.from(new Set([...Object.keys(b), ...Object.keys(a)]));
  return (
    <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-stretch">
      {(["before", "after"] as const).map((side, i) => (
        <div key={side} className={cx("contents")}>
          {i === 1 && <div className="hidden items-center justify-center sm:flex"><ArrowRight className="size-5 text-accent" /></div>}
          <div className={cx("rounded-2xl border p-4", side === "after" ? "border-pass/30 bg-pass-bg/40" : "border-line bg-wash/60")}>
            <div className="text-[12px] font-semibold uppercase tracking-wider text-faint">{side === "before" ? "Before" : "After (read back)"}</div>
            <dl className="mt-2 space-y-1">
              {keys.length === 0 && <div className="text-[14px] text-faint">No state recorded.</div>}
              {keys.map((k) => (
                <div key={k} className="flex items-baseline justify-between gap-3">
                  <dt className="mono text-[12px] text-muted">{k}</dt>
                  <dd className={cx("font-display text-[22px] font-bold", side === "after" && show(b[k]) !== show(a[k]) ? "text-pass" : "text-ink")}>{show(side === "before" ? b[k] : a[k])}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-2 border-t border-line/70 pt-2 text-[12px] text-faint">config hash <Hash value={side === "before" ? beforeHash : afterHash} n={12} /></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function JournalStepper({ journal, status, aws }: { journal: Json[]; status: string; aws?: boolean }) {
  const byStage = new Map(journal.map((j) => [j.stage, j]));
  const extra = journal.filter((j) => !STAGES.some((s) => s.id === j.stage));
  return (
    <div>
      <ol className="grid gap-3 md:grid-cols-3">
        {STAGES.map((s, i) => {
          const j = byStage.get(s.id);
          const Icon = s.icon;
          const pending = !j && ACTIVE.includes(status);
          return (
            <li key={s.id} className={cx("relative rounded-2xl border p-4", j ? "border-accent/25 bg-white" : "border-dashed border-line-2 bg-white/50")}>
              <div className="flex items-center gap-2">
                <span className={cx("grid size-8 place-items-center rounded-xl", j ? (s.id === "VERIFIED" ? "bg-pass text-white" : "bg-accent text-white") : "bg-lav text-faint")}>
                  {pending ? <Hourglass className="size-4 animate-pulse" /> : <Icon className="size-4" />}
                </span>
                <div>
                  <div className={cx("text-[14px] font-bold", j ? "text-ink" : "text-faint")}>{s.label}</div>
                  <div className="mono text-[11.5px] text-faint">{s.id}{j ? ` · #${j.seq} · ${shortTs(j.at)}` : ""}</div>
                </div>
              </div>
              <p className="mt-2 text-[12px] leading-snug text-muted">{aws ? s.awsSub : s.sub}</p>
              {j && s.id === "INTENT" && (
                <div className="mt-2 space-y-1 text-[12.5px]">
                  <div className="flex items-center gap-1"><span className="w-20 shrink-0 text-faint">plan hash</span><Hash value={j.detail?.plan_hash} n={10} /></div>
                  <div className="flex items-center gap-1"><span className="w-20 shrink-0 text-faint">expects</span><span className="mono">v{j.detail?.expected_version}</span></div>
                  <div className="flex items-center gap-1"><span className="w-20 shrink-0 text-faint">change</span><span className="mono break-all">{show(j.detail?.change)}</span></div>
                </div>
              )}
              {j && s.id === "WRITE_APPLIED" && (
                <div className="mt-2 space-y-1 text-[12.5px]">
                  {j.detail?.downtime_seconds !== undefined && (
                    <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-lg bg-warn-bg px-2 py-1 text-[12px] font-semibold text-warn"><Hourglass className="size-3.5" /> {j.detail.downtime_seconds} s measured downtime</div>
                  )}
                  <div className="flex items-center gap-1"><span className="w-20 shrink-0 text-faint">new version</span><span className="mono">v{j.detail?.new_version}</span></div>
                  <div className="flex items-center gap-1"><span className="w-20 shrink-0 text-faint">config hash</span><Hash value={j.detail?.config_hash} n={10} /></div>
                </div>
              )}
              {j && s.id === "VERIFIED" && j.detail?.summary && <div className="mt-2 rounded-lg bg-pass-bg/60 px-2 py-1 text-[12.5px] text-pass">{j.detail.summary}</div>}
              {i < STAGES.length - 1 && <ArrowRight className="absolute -right-3 top-1/2 hidden size-4 -translate-y-1/2 text-line-2 md:block" />}
            </li>
          );
        })}
      </ol>
      {extra.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {extra.map((j) => (
            <li key={j.seq} className="rounded-xl bg-wash px-3 py-2 text-[12px]"><b className="text-ink">{humanize(j.stage)}</b> <span className="text-faint">#{j.seq} · {shortTs(j.at)}</span><div className="mono mt-0.5 break-all text-[12px] text-muted">{show(j.detail)}</div></li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ActionDetail() {
  const { id = "" } = useParams();
  const r = useGet<Resource<Json>>(`/v1/actions/${id}`, { pollMs: 2000, shouldPoll: (d) => ACTIVE.includes(d?.status ?? "") });
  const plan = useGet<Resource<Json>>(r.data?.data?.plan_id ? `/v1/plans/${r.data.data.plan_id}` : null);
  useCopilotInvestigation(plan.data?.data?.investigation_id);
  if (r.loading && !r.data) return <PageSkeleton />;
  if (r.error && !r.data) return <ErrorBox error={r.error} title="Could not load the action" />;
  if (!r.data) return null;
  const res = r.data;
  const d = res.data;
  const status = res.status ?? "UNKNOWN";
  const journal: Json[] = d.journal ?? [];
  const v = d.verification ?? {};
  const checks: [string, boolean][] = Object.entries(v.checks ?? {}) as [string, boolean][];
  const w = v.workload;
  const rb = v.readback;
  const intent = journal.find((j) => j.stage === "INTENT");
  const beforeHash = intent?.detail?.before_config_hash;
  const afterHash = rb?.loaded_config_hash ?? journal.find((j) => j.stage === "WRITE_APPLIED")?.detail?.config_hash;
  const invId = plan.data?.data?.investigation_id;
  const aws = d.executor === "aws";
  const meas = v.measurement;
  const downtime = journal.find((j) => j.stage === "WRITE_APPLIED")?.detail?.downtime_seconds;
  const execLabel = aws ? `Real AWS EC2 change${rb?.region ? ` · ${rb.region}` : ""}` : d.executor_label ?? d.executor;

  return (
    <div className="rise">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-faint">
        {invId && <><Link to={`/app/investigations/${invId}`} className="mono hover:text-accent">{String(invId).slice(0, 8)}</Link><span>/</span></>}
        <Link to={`/app/plans/${d.plan_id}`} className="hover:text-accent">plan <span className="mono">{String(d.plan_id).slice(0, 8)}</span></Link><span>/</span>
        <span>action <span className="mono">{id.slice(0, 8)}</span></span>
      </div>
      {status === "VERIFIED" ? (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="mr-1 inline-flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.14em] text-faint"><Activity className="size-4" /> Action</span>
          <KindBadge kind={res.result_kind} prefix="result" />
          <Pill icon={Server} className="!py-0.5">{execLabel}</Pill>
          {aws && <LiveAwsBadge />}
        </div>
      ) : (
        <PageHeader
        eyebrow={<><Activity className="size-4" /> Action · {d.target_key}</>}
        title={<>Change <em>{status === "VERIFIED" ? "verified" : humanize(status).toLowerCase()}</em></>}
        sub={STATUS_MEANING[status]}
        chips={
          <>
            <StatusChip status={status} size="md" />
            <KindBadge kind={res.result_kind} prefix="result" />
            <Pill icon={Server} className="!py-0.5">{execLabel}</Pill>
            {aws && <LiveAwsBadge />}
            {downtime !== undefined && <span className="inline-flex items-center gap-1 rounded-full bg-warn-bg px-2.5 py-0.5 text-[12.5px] font-semibold text-warn ring-1 ring-inset ring-warn/30"><Hourglass className="size-3" /> {downtime} s downtime (measured)</span>}
          </>
        }
      />
      )}
      {ACTIVE.includes(status) && <div className="mb-5"><Notice tone="info" icon={Info} title="In progress — do not retry">This page re-reads the action every 2 s. An ambiguous write is reconciled by the worker, never blindly retried.</Notice></div>}
      {status === "RECOVERY_REQUIRED" && <div className="mb-5"><Notice tone="fail" icon={AlertOctagon} title="Human intervention required">Run the documented operator procedure (<span className="mono">make resolve-action</span>). Foreign changes are never claimed or overwritten.</Notice></div>}
      {status === "VERIFIED" && (
        <section className="mb-5 overflow-hidden rounded-[22px] border border-pass/30 bg-gradient-to-br from-pass-bg to-white shadow-[var(--shadow-card)]">
          <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[1.1fr_1fr] lg:items-center">
            <div>
              <div className="flex items-center gap-3">
                <span className="grid size-12 place-items-center rounded-2xl bg-pass text-white shadow-sm"><CheckCircle2 className="size-6" /></span>
                <div>
                  <h2 className="font-display text-[24px] font-bold tracking-tight text-ink sm:text-[28px]">{aws ? "Change verified on AWS" : "Change verified"}</h2>
                  <p className="text-[14px] text-muted">{aws ? `Real EC2 instance ${rb?.instance_id ?? d.target_key}${rb?.region ? ` · ${rb.region}` : ""}` : `${d.target_key} · local analogue, not a cloud change`}{d.verified_at ? ` · ${shortTs(d.verified_at)}` : ""}</p>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-3">
                {Object.keys(d.before_state ?? {}).map((k) => (
                  <div key={k} className="flex flex-wrap items-center gap-3">
                    <span className="mono rounded-xl bg-white px-3 py-2 text-[18px] font-semibold text-muted ring-1 ring-line">{String(d.before_state[k])}</span>
                    <ArrowRight className="size-5 text-pass" />
                    <span className="mono rounded-xl bg-pass px-3 py-2 text-[18px] font-semibold text-white">{String(d.after_state?.[k] ?? "—")}</span>
                    <span className="hidden text-[14px] text-muted sm:inline">{humanize(k).toLowerCase()}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {downtime !== undefined && <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[14px] font-semibold text-warn ring-1 ring-warn/30"><Hourglass className="size-4" /> {downtime} s downtime, measured stop → running</span>}
                {meas?.cpu_max_pct != null && <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[14px] font-semibold text-ink-2 ring-1 ring-line">Peak CPU after {num(meas.cpu_max_pct, 1)}% vs {num(meas.limit_pct, 0)}% limit</span>}
              </div>
            </div>
            <ul className="grid gap-x-4 gap-y-2 rounded-2xl bg-white p-4 ring-1 ring-line sm:grid-cols-2">
              {checks.map(([k, ok]) => (
                <li key={k} className="flex items-center gap-2 text-[14px] text-ink">
                  {ok ? <CheckCircle2 className="size-4 shrink-0 text-pass" /> : <XCircle className="size-4 shrink-0 text-fail" />}
                  {humanize(k).replace(/\bec2\b/i, "EC2").replace(/\bcpu\b/i, "CPU").replace(/\bslo\b/i, "SLO")}
                </li>
              ))}
              {checks.length === 0 && <li className="text-[14px] text-muted">No verification checks recorded.</li>}
            </ul>
          </div>
        </section>
      )}
      {aws && status !== "VERIFIED" && (
        <div className="mb-5"><Notice tone="warn" icon={Server} title="Real AWS EC2 change">This action changes a real EC2 instance in the permitted SuperOps sandbox ({d.target_key}): stop, change type, start, read back and measure.</Notice></div>
      )}
      {d.executor === "local_analogue" && (
        <div className="mb-5"><Notice tone="unknown" icon={Server} title="Local analogue executor">A real configuration change on a local sandbox worker ({d.target_key}) that stands in for the GCP resize. It proves the approval → write → read-back → verify loop; it is not a cloud change and not an invoice saving.</Notice></div>
      )}

      <div className="space-y-5">
        <Card>
          <CardHeader title="Execution journal" icon={Activity} sub="Persisted stages, in order. Intent is written before the provider call so an unknown outcome can be reconciled." />
          <div className="px-5 pb-5 sm:px-6"><JournalStepper journal={journal} status={status} aws={aws} /></div>
        </Card>

        <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
          <Card>
            <CardHeader title="Before and after" icon={ShieldCheck} sub="After is what the running worker reported on read-back, not what was intended" />
            <div className="px-5 pb-5 sm:px-6"><BeforeAfter before={d.before_state} after={d.after_state} beforeHash={beforeHash} afterHash={afterHash} /></div>
          </Card>
          <Card>
            <CardHeader title="Verification checks" icon={BadgeCheck} right={v.ok !== undefined ? <StatusChip status={v.ok ? "PASS" : "FAIL"} size="sm" /> : undefined} />
            <div className="px-5 pb-5 sm:px-6">
              {checks.length === 0 ? <div className="text-[14px] text-faint">No verification recorded yet.</div> : (
                <ul className="divide-y divide-line">
                  {checks.map(([k, ok]) => (
                    <li key={k} className="flex items-center justify-between gap-3 py-2 text-[14px]">
                      <span className="flex items-center gap-2 text-ink">{ok ? <CheckCircle2 className="size-4 text-pass" /> : <XCircle className="size-4 text-fail" />}{humanize(k).replace(/\bec2\b/i, "EC2").replace(/\bcpu\b/i, "CPU").replace(/\bslo\b/i, "SLO")}</span>
                      <span className={cx("text-[12px] font-bold", ok ? "text-pass" : "text-fail")}>{ok ? "PASS" : "FAIL"}</span>
                    </li>
                  ))}
                </ul>
              )}
              {w && (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {[["Completed", `${w.completed}/${w.offered}`], ["Failures", w.failures], ["p95", `${num(w.p95_ms, 1)} ms`]].map(([l, val]) => (
                    <div key={l as string} className="rounded-xl bg-wash p-2.5"><div className="text-[12px] text-muted">{l}</div><div className="font-display text-[18px] font-bold text-ink">{val}</div></div>
                  ))}
                </div>
              )}
              {w && <div className="mt-2 text-[12px] text-faint">Fresh workload after the change · server p95 {num(w.server_p95_ms, 1)} ms · schedule lag p95 {num(w.schedule_lag_p95_ms, 2)} ms</div>}
              {meas && (
                <div className="mt-3">
                  <div className="grid grid-cols-3 gap-2">
                    {[["Peak CPU", meas.cpu_max_pct == null ? "—" : `${num(meas.cpu_max_pct, 1)}%`], ["Mean CPU", meas.cpu_avg_pct == null ? "—" : `${num(meas.cpu_avg_pct, 1)}%`], ["Limit", meas.limit_pct == null ? "—" : `${num(meas.limit_pct, 0)}%`]].map(([l, val]) => (
                      <div key={l as string} className="rounded-xl bg-wash p-2.5"><div className="text-[12px] text-muted">{l}</div><div className="font-display text-[18px] font-bold text-ink">{val}</div></div>
                    ))}
                  </div>
                  {meas.cpu_max_pct != null && meas.limit_pct != null && (
                    <div className="relative mt-2 h-2.5 overflow-hidden rounded-full bg-lav">
                      <div className={cx("h-full rounded-full", Number(meas.cpu_max_pct) > Number(meas.limit_pct) ? "bg-fail" : "bg-pass")} style={{ width: `${Math.min(100, Number(meas.cpu_max_pct))}%` }} />
                      <div className="absolute inset-y-0 w-0.5 bg-fail" style={{ left: `${Math.min(100, Number(meas.limit_pct))}%` }} />
                    </div>
                  )}
                  <div className="mt-2 text-[12px] text-faint">{meas.datapoints} datapoints from {shortTs(meas.window_start)} · {meas.source}</div>
                </div>
              )}
            </div>
          </Card>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader title={aws ? "Read-back from EC2" : "Read-back from the running worker"} icon={Server} />
            <div className="px-5 pb-5 sm:px-6">
              {rb && aws ? (
                <KV rows={[
                  ["Instance", <span className="mono text-[12px]">{rb.instance_id} · {rb.region}</span>],
                  ["Instance type", <span className="mono font-semibold">{rb.instance_type}</span>],
                  ["State", <StatusChip status={rb.state === "running" ? "PASS" : "UNKNOWN"} label={rb.state} size="xs" />],
                  ["Config version tag", <span className="mono">v{rb.version}</span>],
                  ["Writer tag", <span className="mono break-all text-[12.5px]">{rb.writer}</span>],
                ]} />
              ) : rb ? (
                <KV rows={[
                  ["Worker", <span className="mono text-[12px]">{rb.worker_id}</span>],
                  ["Loaded version", <span className="mono">v{rb.loaded_version}</span>],
                  ["Loaded config hash", <Hash value={rb.loaded_config_hash} />],
                  ["Writer", <span className="mono break-all text-[12.5px]">{rb.loaded_config?.writer}</span>],
                  ["Process", <span className="mono text-[12px]">pid {rb.pid} · since {shortTs(rb.started_at)}</span>],
                ]} />
              ) : <div className="text-[14px] text-faint">No read-back recorded.</div>}
            </div>
          </Card>
          <Card>
            <CardHeader title="Record" icon={Activity} />
            <div className="px-5 pb-5 sm:px-6">
              <KV rows={[
                ["Plan", <IdLink kind="plan" id={d.plan_id} />],
                ["Approval", <span className="mono text-[12px]">{String(d.approval_id ?? "—").slice(0, 8)}</span>],
                ["Actor", d.actor_id],
                ["Operation IDs", (d.operation_ids ?? []).length ? <span className="mono break-all text-[12px]">{d.operation_ids.join(", ")}</span> : "—"],
                ["Created", shortTs(d.created_at)],
                ["Verified", d.verified_at ? shortTs(d.verified_at) : "—"],
                ["Memory sync", <span className="inline-flex items-center gap-1"><Brain className="size-3.5 text-accent" /><StatusChip status={d.memory_sync_status} size="xs" /></span>],
              ]} />
            </div>
          </Card>
        </div>

        {(d.recovery || d.error) && (
          <Card>
            <CardHeader title="Recovery and errors" icon={Undo2} />
            <div className="space-y-3 px-5 pb-5 sm:px-6"><JsonBlock value={d.recovery} />{d.error && <JsonBlock value={d.error} />}</div>
          </Card>
        )}
      </div>
    </div>
  );
}
