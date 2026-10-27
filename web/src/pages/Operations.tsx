import { Settings2, Server, Lock, Wallet, FlaskConical, ListChecks, Brain, Cpu, Target } from "lucide-react";
import type { Json, Resource } from "../lib/api";
import { useGet } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import { humanize, shortTs, money } from "../lib/format";
import { Card, CardHeader, Empty, ErrorBox, Hash, KV, Notice, PageHeader, PageSkeleton, StatusChip, KindBadge } from "../components/ui";

function depStatus(v: unknown): string {
  if (v === true) return "PASS";
  if (v === false) return "FAIL";
  const s = String(v ?? "unknown");
  if (s === "ready" || s === "configured") return "ready";
  if (s.startsWith("unavailable") || s === "not_configured") return "unavailable";
  return "unknown";
}

export default function Operations() {
  const { isAdmin } = useAuth();
  const r = useGet<Resource<Json>>(isAdmin ? "/v1/operations" : null);
  if (!isAdmin) return <Empty title="Admins only" icon={Lock}>Operations shows readiness, slots, jobs, outbox and budgets. Sign in with the admin sandbox token.</Empty>;
  if (r.loading && !r.data) return <PageSkeleton />;
  if (r.error && !r.data) return <ErrorBox error={r.error} title="Could not load operations" />;
  if (!r.data) return null;
  const res = r.data;
  const d = res.data;
  const deps = d.dependencies ?? {};
  const slot = d.execution_slot ?? {};
  return (
    <div className="rise">
      <PageHeader
        eyebrow={<><Settings2 className="size-4" /> Operations</>}
        title={<>System <em>readiness</em></>}
        sub="Redacted readiness, versions, the global mutation slot, jobs, memory outbox, budgets and trial profiles. No admin mutation exists."
        chips={<><StatusChip status={res.status} size="md" /><KindBadge kind={d.runtime_mode} prefix="mode" /><StatusChip status={d.sandbox_writes_enabled ? "ACTIVE" : "off"} label={d.sandbox_writes_enabled ? "sandbox writes enabled" : "sandbox writes disabled"} size="md" /></>}
        right={<button onClick={r.reload} className="rounded-full bg-white px-4 py-2 text-[14px] font-semibold ring-1 ring-line hover:text-accent">Refresh</button>}
      />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title="Dependencies" icon={Server} />
          <ul className="divide-y divide-line px-5 pb-4 sm:px-6">
            {Object.entries(deps).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between gap-3 py-2.5 text-[14px]">
                <span className="font-semibold text-ink">{humanize(k)}</span>
                <span className="flex items-center gap-2"><span className="mono text-[12.5px] text-muted">{String(v)}</span><StatusChip status={depStatus(v)} size="xs" /></span>
              </li>
            ))}
            <li className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-[14px]">
              <span className="font-semibold text-ink">Zetaris sources</span>
              {d.zetaris_sources && typeof d.zetaris_sources === "object" ? (
                <span className="flex flex-wrap justify-end gap-1">
                  {Object.entries(d.zetaris_sources).map(([g, n]) => <span key={g} className="mono rounded bg-lav px-1.5 py-0.5 text-[12px] text-ink-2">{g} → {String(n)}</span>)}
                </span>
              ) : <span className="mono text-[12.5px] text-muted">{d.zetaris_sources ? String(d.zetaris_sources) : "not configured"}</span>}
            </li>
          </ul>
        </Card>
        <Card>
          <CardHeader title="Versions & model" icon={Cpu} />
          <div className="px-5 pb-5 sm:px-6">
            <KV rows={[
              ["Policy", <span className="mono text-[12px]">{d.policy_version}</span>],
              ["Data manifest", <span className="mono text-[12px]">{d.data_manifest_id}</span>],
              ["Agent model", <span className="mono text-[12.5px] break-all">{d.model_id}</span>],
              ["Executor", d.executor],
              ["GCP executor", d.gcp_executor],
            ]} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Execution slot" icon={Lock} sub="One durable global mutation slot for trials, actions and recovery" />
          <div className="px-5 pb-5 sm:px-6">
            {slot.holder_id ? (
              <KV rows={[["Holder", `${slot.holder_kind} ${String(slot.holder_id).slice(0, 8)}`], ["Since", shortTs(slot.acquired_at)]]} />
            ) : <div className="flex items-center gap-2 rounded-xl bg-pass-bg/60 px-3 py-3 text-[14px] text-pass"><StatusChip status="PASS" size="xs" label="free" /> No trial or action holds the slot.</div>}
            <div className="mt-4 text-[12px] font-semibold uppercase tracking-wider text-faint">Allowed targets</div>
            <ul className="mt-1 space-y-1">{(d.allowed_target_ids ?? []).map((t: string) => <li key={t} className="mono flex items-center gap-2 text-[12px] text-ink-2"><Target className="size-3.5 text-accent" />{t}</li>)}</ul>
          </div>
        </Card>
        <Card>
          <CardHeader title="Active actions & jobs" icon={ListChecks} />
          <div className="space-y-3 px-5 pb-5 sm:px-6 text-[14px]">
            <div>Active actions: {(d.active_actions ?? []).length ? (d.active_actions ?? []).map((a: Json) => <span key={a.id} className="mono ml-1">{String(a.id).slice(0, 8)} <StatusChip status={a.status} size="xs" /></span>) : <span className="text-faint">none</span>}</div>
            <div>
              Jobs:
              {(d.jobs ?? []).length ? (
                <ul className="mt-1 space-y-1">{d.jobs.map((j: Json, i: number) => <li key={i} className="flex items-center gap-2"><StatusChip status={j.status} size="xs" /> <span className="mono text-[12px]">{j.kind ?? j.job_kind ?? ""} {j.n !== undefined ? `× ${j.n}` : String(j.id ?? "").slice(0, 8)}</span></li>)}</ul>
              ) : <span className="text-faint"> none queued</span>}
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Memory outbox" icon={Brain} />
          <ul className="divide-y divide-line px-5 pb-4 sm:px-6">
            {(d.memory_outbox ?? []).map((m: Json, i: number) => (
              <li key={i} className="flex items-center justify-between py-2.5 text-[14px]"><StatusChip status={m.status} size="xs" /><span className="font-display text-[20px] font-bold">{m.n}</span></li>
            ))}
            {!(d.memory_outbox ?? []).length && <li className="py-3 text-[14px] text-faint">Empty.</li>}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Budget profiles" icon={Wallet} />
          <div className="px-5 pb-5 sm:px-6">
            {(d.budget_profiles ?? []).map((b: Json) => (
              <KV key={b.id} rows={[["Profile", <span className="mono text-[12px]">{b.id}</span>], ["Max run cost", money(b.max_run_cost_usd)], ["Max model calls", b.max_model_calls], ["Per call (conservative)", money(b.max_conservative_cost_per_call_usd, "USD", 4)], ["Evidence time cap", `${b.max_evidence_seconds} s`]]} />
            ))}
          </div>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title="Trial profiles" icon={FlaskConical} sub="Created only by the operator command; editing the profile file invalidates it" />
          <div className="overflow-x-auto px-2 pb-3">
            <table className="w-full text-[14px]">
              <thead><tr className="text-left text-[12px] uppercase tracking-wider text-faint">{["Profile", "Status", "Approved by", "Approved", "Expires", "Hash"].map((h) => <th key={h} className="px-4 py-2">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-line">
                {(d.trial_profiles ?? []).map((t: Json) => (
                  <tr key={t.id}><td className="mono px-4 py-2">{t.id}</td><td className="px-4 py-2"><StatusChip status={t.status} size="xs" /></td><td className="px-4 py-2">{t.approved_by}</td><td className="px-4 py-2">{shortTs(t.approved_at)}</td><td className="px-4 py-2">{shortTs(t.expires_at)}</td><td className="px-4 py-2"><Hash value={t.profile_hash} n={10} /></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
      {res.blockers?.length > 0 && <div className="mt-5"><Notice tone="warn" title="Blockers">{res.blockers.join(" · ")}</Notice></div>}
    </div>
  );
}
