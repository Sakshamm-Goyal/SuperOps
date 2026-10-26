import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowRight, Ban, CheckCircle2, ChevronDown, Clock3, FlaskConical, KeyRound, Lock, Play, RotateCcw, ShieldCheck, Undo2, Brain, Leaf,
} from "lucide-react";
import type { Json, Resource } from "../lib/api";
import { useGet, useMutation, useNow } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import { checkLabel, environmentOf, humanize, impactBasis, money, num, planTitle, shortTs, ts, STATUS_MEANING } from "../lib/format";
import { Button, Card, CardHeader, CheckRow, ErrorBox, Hash, IdLink, KindBadge, KV, Notice, PageSkeleton, StatusChip, cx, Empty } from "../components/ui";
import { CriticBlock, ImpactSummary, PathIcon } from "../components/plan";
import { useCopilotInvestigation } from "../components/Copilot";

function Countdown({ until }: { until: string }) {
  const now = useNow(1000);
  const ms = new Date(until).getTime() - now;
  if (Number.isNaN(ms)) return <span>—</span>;
  if (ms <= 0) return <span className="text-fail">expired</span>;
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const frac = Math.min(1, ms / (15 * 60000));
  return (
    <span className="inline-flex items-center gap-2">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
        <circle cx="11" cy="11" r="9" fill="none" stroke="#eef0ff" strokeWidth="3" />
        <circle cx="11" cy="11" r="9" fill="none" stroke={frac < 0.2 ? "#d63c44" : "#2438f5"} strokeWidth="3" strokeDasharray={`${frac * 56.5} 56.5`} transform="rotate(-90 11 11)" strokeLinecap="round" />
      </svg>
      <span className={cx("mono font-semibold tnum", frac < 0.2 ? "text-fail" : "text-ink")}>{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}</span>
    </span>
  );
}

function BoundHash({ label, value, current, trialId }: { label: string; value?: string; current?: string; trialId?: string }) {
  const match = !!value && !!current && value === current;
  return (
    <div className="flex min-w-0 items-center gap-2">
      <span className="w-9 shrink-0 text-[11px] text-muted">{label}</span>
      <span className="min-w-0 flex-1"><Hash value={value} n={14} /></span>
      {trialId && <IdLink kind="trial" id={trialId} />}
      {value && current && (
        <span title={match ? "Matches the current record" : "Differs from the current record"} className={cx("shrink-0 rounded px-1 text-[10px] font-bold", match ? "bg-pass-bg text-pass" : "bg-fail-bg text-fail")}>{match ? "MATCH" : "DIFFERS"}</span>
      )}
    </div>
  );
}

function DiffTable({ before, after }: { before: Json; after: Json }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]));
  if (!keys.length) return <div className="text-[13px] text-faint">No configuration change recorded.</div>;
  const show = (v: unknown) => (v === null ? "null" : v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-faint"><th className="py-1.5 pr-3">Setting</th><th className="py-1.5 pr-3">Before</th><th className="py-1.5">After</th></tr>
        </thead>
        <tbody className="divide-y divide-line">
          {keys.map((k) => {
            const changed = show(before?.[k]) !== show(after?.[k]);
            return (
              <tr key={k}>
                <td className="mono py-2 pr-3 text-[12px] text-ink-2">{k}</td>
                <td className={cx("mono py-2 pr-3 text-[12px]", changed ? "text-fail line-through decoration-fail/40" : "text-muted")}>{show(before?.[k])}</td>
                <td className={cx("mono py-2 text-[12px]", changed ? "font-semibold text-pass" : "text-muted")}>{show(after?.[k])}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ApprovalPanel({ res, reload }: { res: Resource<Json>; reload: () => void }) {
  const { canOperate, me } = useAuth();
  const nav = useNavigate();
  const d = res.data;
  const acts = res.next_allowed_actions ?? [];
  const blockers = res.blockers ?? [];
  const trials: Json[] = d.trials ?? [];
  const passed = [...trials].reverse().find((t) => t.status === "PASSED");
  const ap = d.latest_approval;
  const requiresDowntime = !!d.core?.requires_downtime;
  const [ack, setAck] = useState(false);
  const [confirmExec, setConfirmExec] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const approve = useMutation<Json>();
  const revoke = useMutation<Json>();
  const execute = useMutation<Json>();
  const trial = useMutation<Json>();
  const suite = d.path === "ai" ? "support-dev-v1" : "workload-wl-v1";

  return (
    <div className="space-y-4">
      {/* The receipt: what an approval would bind */}
      <div className="overflow-hidden rounded-[22px] bg-white shadow-[var(--shadow-float)] ring-1 ring-line">
        <div className="bg-ink px-5 py-4 text-white">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.14em] text-white/70"><KeyRound className="size-4" /> Approval scope</span>
            <StatusChip status={ap?.status ?? res.status} size="xs" />
          </div>
          <div className="mt-2 font-display text-[19px] font-bold leading-tight">An approval binds exactly these hashes — nothing else.</div>
        </div>
        <div className="relative my-3 h-0 border-t-2 border-dashed border-line-2" aria-hidden>
          <span className="absolute -left-3 -top-3 size-6 rounded-full bg-wash ring-1 ring-line" />
          <span className="absolute -right-3 -top-3 size-6 rounded-full bg-wash ring-1 ring-line" />
        </div>
        <div className="space-y-3 px-5 pb-5">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Plan hash</div>
            <Hash value={d.plan_hash} n={20} />
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Trial {passed ? <IdLink kind="trial" id={passed.id} /> : null}</div>
            {passed ? <Hash value={passed.trial_hash} n={20} /> : <span className="text-[12.5px] text-faint">No passed trial yet</span>}
          </div>
          <div className="grid grid-cols-2 gap-3 text-[12.5px]">
            <div className="min-w-0"><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Target</div><span className="mono break-all text-[11.5px]">{d.target_key}</span></div>
            <div><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Downtime</div>{requiresDowntime ? <span className="font-semibold text-warn">required</span> : "none"}</div>
          </div>
          <div><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Recovery scope</div><span className="mono break-all text-[11.5px] text-ink-2">{d.recovery_scope}</span></div>
          <div className="flex items-center justify-between rounded-xl bg-wash px-3 py-2 text-[12.5px]">
            <span className="text-muted">Window after approval</span>
            {ap?.status === "ACTIVE" && ap.expires_at ? <Countdown until={ap.expires_at} /> : ap && ap.status !== "REVOKED" && ap.status !== "EXPIRED" ? <span className="font-semibold text-pass">{humanize(ap.status).toLowerCase()}</span> : <span className="mono font-semibold">15:00</span>}
          </div>
          {ap && (
            <div className="rounded-xl border border-line p-3 text-[12px]">
              <div className="flex items-center justify-between"><span className="font-semibold text-ink">Recorded approval</span><StatusChip status={ap.status} size="xs" /></div>
              <div className="mt-1 text-muted">by {ap.actor_id} · {ap.created_at ? `${shortTs(ap.created_at)} · ` : ""}expires {shortTs(ap.expires_at)}</div>
              {ap.plan_hash && (
                <div className="mt-2 space-y-1.5 border-t border-line pt-2">
                  <div className="text-[10.5px] font-semibold uppercase tracking-wider text-faint">Hashes this approval bound</div>
                  <BoundHash label="plan" value={ap.plan_hash} current={d.plan_hash} />
                  <BoundHash label="trial" value={ap.trial_hash} current={trials.find((t) => t.id === ap.trial_id)?.trial_hash} trialId={ap.trial_id} />
                </div>
              )}
              {ap.consumed_action_id && (
                <Link to={`/app/actions/${ap.consumed_action_id}`} className="mt-2 flex items-center justify-between rounded-lg bg-pass-bg/70 px-2.5 py-2 font-semibold text-pass hover:bg-pass-bg">
                  <span className="flex items-center gap-1.5"><CheckCircle2 className="size-3.5" /> Consumed by action {String(ap.consumed_action_id).slice(0, 8)}</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              )}
            </div>
          )}
        </div>
      </div>

      {/* What the server allows now */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-bold text-ink">Allowed now</span>
          <span className="text-[11px] text-faint">computed by the server</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {acts.length ? acts.map((a: string) => <span key={a} className="mono rounded-md bg-pass-bg px-2 py-0.5 text-[11.5px] font-semibold text-pass">{a}</span>) : <span className="text-[12.5px] text-muted">No action is allowed on this plan right now.</span>}
        </div>
        {blockers.length > 0 && (
          <div className="mt-4">
            <div className="text-[12px] font-bold uppercase tracking-wider text-fail">Blockers</div>
            <ul className="mt-1.5 space-y-1.5">
              {blockers.map((b: string) => (
                <li key={b} className="flex items-start gap-2 rounded-lg bg-fail-bg/60 px-3 py-2 text-[12.5px] text-ink-2"><Ban className="mt-0.5 size-3.5 shrink-0 text-fail" /> {b}</li>
              ))}
            </ul>
          </div>
        )}
        {!canOperate && <div className="mt-4 flex items-center gap-2 text-[12.5px] text-muted"><Lock className="size-3.5" /> Your role ({me?.role}) is read-only.</div>}

        {canOperate && acts.includes("run_trial") && (
          <div className="mt-5 border-t border-line pt-4">
            <div className="text-[13px] font-semibold text-ink">Run a matched trial</div>
            <p className="mt-0.5 text-[12px] text-muted">Suite <span className="mono">{suite}</span> · profile <span className="mono">sandbox-trials-v1</span>. Runs on sandbox fixtures; changes nothing.</p>
            <Button className="mt-3 w-full" icon={FlaskConical} loading={trial.pending} onClick={async () => {
              const r = await trial.run(`/v1/plans/${d.id}/trials`, { plan_hash: d.plan_hash, suite_id: suite, approved_trial_profile_id: "sandbox-trials-v1" });
              if (r?.trial_id) nav(`/app/trials/${r.trial_id}`);
            }}>Start trial</Button>
            <div className="mt-2"><ErrorBox error={trial.error} title="Trial not started" /></div>
          </div>
        )}

        {canOperate && acts.includes("approve") && passed && (
          <div className="mt-5 border-t border-line pt-4">
            <div className="text-[13px] font-semibold text-ink">Approve this exact plan</div>
            <p className="mt-0.5 text-[12px] text-muted">Approval does not execute. It records you, these hashes and a 15-minute expiry in PostgreSQL.</p>
            {requiresDowntime && (
              <label className="mt-3 flex items-start gap-2 text-[12.5px] text-ink-2">
                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5 size-4 accent-[#2438f5]" />
                I acknowledge this change requires downtime.
              </label>
            )}
            <Button className="mt-3 w-full" icon={ShieldCheck} loading={approve.pending} disabled={requiresDowntime && !ack} onClick={async () => {
              if (await approve.run(`/v1/plans/${d.id}/approve`, { plan_hash: d.plan_hash, trial_id: passed.id, trial_hash: passed.trial_hash, acknowledge_downtime: requiresDowntime ? ack : false, approved_recovery_scope: d.recovery_scope })) reload();
            }}>Approve plan + trial hash</Button>
            <div className="mt-2"><ErrorBox error={approve.error} title="Approval refused" /></div>
          </div>
        )}

        {canOperate && acts.includes("execute") && ap?.status === "ACTIVE" && (
          <div className="mt-5 border-t border-line pt-4">
            <div className="text-[13px] font-semibold text-ink">Execute once</div>
            <p className="mt-0.5 text-[12px] text-muted">Consumes approval <span className="mono">{String(ap.id).slice(0, 8)}</span>. The executor locks the target, writes once and reads back. A timeout is not proof of failure — read the action.</p>
            {!confirmExec ? (
              <Button className="mt-3 w-full" variant="dark" icon={Play} onClick={() => setConfirmExec(true)}>Execute…</Button>
            ) : (
              <div className="mt-3 flex gap-2">
                <Button variant="ghost" className="flex-1" onClick={() => setConfirmExec(false)}>Back</Button>
                <Button className="flex-1" variant="dark" icon={Play} loading={execute.pending} onClick={async () => {
                  const r = await execute.run(`/v1/plans/${d.id}/execute`, { approval_id: ap.id, plan_hash: d.plan_hash });
                  if (r?.action_id) nav(`/app/actions/${r.action_id}`);
                }}>Confirm execute</Button>
              </div>
            )}
            <div className="mt-2"><ErrorBox error={execute.error} title="Execution refused" /></div>
          </div>
        )}

        {canOperate && acts.includes("revoke_approval") && ap && (
          <div className="mt-5 border-t border-line pt-4">
            <div className="text-[13px] font-semibold text-ink">Revoke approval</div>
            <input value={revokeReason} onChange={(e) => setRevokeReason(e.target.value)} placeholder="Reason (recorded)" className="mt-2 h-9 w-full rounded-lg bg-wash px-3 text-[13px] ring-1 ring-line outline-none focus:ring-accent/50" />
            <Button className="mt-2 w-full" variant="danger" icon={Undo2} loading={revoke.pending} disabled={!revokeReason.trim()} onClick={async () => {
              if (await revoke.run(`/v1/approvals/${ap.id}/revoke`, { reason: revokeReason.trim() })) { setRevokeReason(""); reload(); }
            }}>Revoke before execution</Button>
            <div className="mt-2"><ErrorBox error={revoke.error} title="Revoke refused" /></div>
          </div>
        )}
      </Card>
    </div>
  );
}

export default function PlanDetail() {
  const { id = "" } = useParams();
  const r = useGet<Resource<Json>>(`/v1/plans/${id}`);
  const [showCanon, setShowCanon] = useState(false);
  useCopilotInvestigation(r.data?.data?.investigation_id);
  if (r.loading && !r.data) return <PageSkeleton />;
  if (r.error && !r.data) return <ErrorBox error={r.error} title="Could not load the plan" />;
  if (!r.data) return null;
  const res = r.data;
  const d = res.data;
  const core = d.core ?? {};
  const imp = d.impacts ?? {};
  const checks = d.screening?.checks ?? [];
  const passCount = checks.filter((c: Json) => c.status === "PASS").length;

  return (
    <div className="rise">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-faint">
        <Link to="/app/investigations" className="hover:text-accent">Investigations</Link><span>/</span>
        <Link to={`/app/investigations/${d.investigation_id}`} className="mono hover:text-accent">{String(d.investigation_id).slice(0, 8)}</Link><span>/</span>
        <span>plan <span className="mono">{id.slice(0, 8)}</span></span>
      </div>
      <header className="mb-6">
        <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.14em] text-faint">
          <PathIcon path={d.path} className="size-4" /> {d.path} path · candidate {d.candidate_no} · revision {d.revision} · {humanize(d.action_type)}
        </div>
        <h1 className="display mt-2 text-[28px] text-ink sm:text-[36px]">{planTitle(d)}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusChip status={res.status} size="md" />
          <KindBadge kind={res.result_kind} prefix="impact" />
          <KindBadge kind={res.runtime_mode} prefix="mode" />
          <KindBadge kind={res.data_origin} prefix="data" />
          {d.latest_approval?.consumed_action_id ? (
            <Link to={`/app/actions/${d.latest_approval.consumed_action_id}`} className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-pass hover:underline">
              <CheckCircle2 className="size-3.5" /> Approval consumed by action {String(d.latest_approval.consumed_action_id).slice(0, 8)} — see its verified outcome
            </Link>
          ) : (
            <span className="text-[12.5px] text-muted">{STATUS_MEANING[res.status ?? ""] ?? ""}</span>
          )}
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <div className="min-w-0 space-y-5">
          <Card>
            <CardHeader title="Immutable core" icon={Lock} sub="The canonical plan. Its SHA-256 is the plan hash an approval binds." right={<Hash value={d.plan_hash} />} />
            <div className="space-y-5 px-5 pb-5 sm:px-6">
              <div className="rounded-2xl border border-line p-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[13px] font-bold text-ink">{humanize(core.action?.action_type)}</span>
                  <span className="mono text-[11.5px] text-muted">{core.action?.worker_id ?? core.action?.workflow_id ?? d.target_key} · expects config v{core.action?.expected_config_version ?? "?"}</span>
                </div>
                <DiffTable before={core.action?.before} after={core.action?.after} />
                {core.projection && (
                  <div className="mt-3 rounded-xl bg-lav/60 px-3 py-2 text-[12.5px] text-ink-2">
                    Represents <b>{core.projection.resource_key}</b>: {core.projection.from_machine_type} → {core.projection.to_machine_type} <KindBadge kind={core.projection.result_kind} />
                  </div>
                )}
                <div className="mt-2 text-[11.5px] text-faint">Executor: {core.executor === "local_analogue" ? "local analogue — a real local config change, not a GCP resize" : core.executor} · environment {environmentOf(d.target_key)}</div>
              </div>
              <div className="grid gap-5 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-faint">Version preconditions</div>
                  <KV rows={Object.entries(core.versions ?? {}).map(([k, v]) => [humanize(k), v ? <span className="mono text-[11.5px] break-all">{String(v)}</span> : <span className="text-faint">none</span>])} />
                </div>
                <div>
                  <div className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-faint">Calculation versions</div>
                  <KV rows={Object.entries(core.calculation_versions ?? {}).map(([k, v]) => [humanize(k), <span className="mono text-[11.5px]">{String(v)}</span>])} />
                  <div className="mt-3 mb-1 text-[12px] font-semibold uppercase tracking-wider text-faint">Evidence bound to the plan</div>
                  <div className="flex flex-wrap gap-1">{(core.evidence_ids ?? []).map((e: string) => <IdLink key={e} kind="evidence" id={e} />)}</div>
                </div>
              </div>
              <button onClick={() => setShowCanon((s) => !s)} className="flex items-center gap-1 text-[12.5px] font-semibold text-accent" aria-expanded={showCanon}>
                <ChevronDown className={cx("size-4 transition", showCanon && "rotate-180")} /> Canonical JSON
              </button>
              {showCanon && <pre className="mono max-h-80 overflow-auto rounded-xl bg-ink p-4 text-[11.5px] leading-relaxed text-[#dfe3ff] scroll-thin">{JSON.stringify(JSON.parse(d.canonical_json ?? "{}"), null, 2)}</pre>}
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Screening checks" icon={ShieldCheck} sub={`${passCount}/${checks.length} pass · ${d.screening?.version ?? ""} · ${humanize(d.screening?.outcome)}`} />
              <ul className="divide-y divide-line px-5 pb-4 sm:px-6">
                {checks.map((c: Json) => <CheckRow key={c.check_id} id={c.check_id} label={checkLabel(c.check_id)} status={c.status} detail={c.detail} measured={c.measured} limit={c.limit} />)}
              </ul>
            </Card>
            <div className="space-y-5">
              <Card>
                <CardHeader title="Impact" icon={Leaf} sub={impactBasis(imp)} />
                <div className="space-y-3 px-5 pb-5 sm:px-6">
                  <ImpactSummary imp={imp} />
                  <KV rows={[
                    ...(imp.baseline_cost !== undefined ? [["Baseline cost", money(imp.baseline_cost)], ["Candidate cost", money(imp.candidate_cost)], ["Net saving", imp.net_saving ? money(imp.net_saving) : <span className="text-faint">pending</span>], ["Net status", imp.net_status]] as [string, unknown][] : []),
                    ...(imp.baseline_cost_per_accepted_usd !== undefined ? [["Baseline $/accepted", imp.baseline_cost_per_accepted_usd], ["Candidate $/accepted", imp.candidate_cost_per_accepted_usd], ["Accepted", `${imp.accepted} (baseline ${imp.baseline_accepted})`]] as [string, unknown][] : []),
                    ["Price basis", imp.price_basis ?? imp.cost_basis],
                    ["Commitment", imp.commitment_assumption],
                    ["Horizon", imp.horizon ? `${shortTs(imp.horizon[0])} → ${shortTs(imp.horizon[1])} (${num(imp.horizon_hours, 0)} h)` : undefined],
                  ].filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => [k as string, v as React.ReactNode])} />
                </div>
              </Card>
              <Card>
                <CardHeader title="Critic & memory" icon={Brain} />
                <div className="space-y-3 px-5 pb-5 sm:px-6">
                  <CriticBlock critic={d.critic} />
                  {(d.memory_refs ?? []).length > 0 ? (
                    <div className="flex flex-wrap gap-1">{d.memory_refs.map((m: Json) => <IdLink key={typeof m === "string" ? m : m.memory_id} kind="memory" id={typeof m === "string" ? m : m.memory_id} />)}</div>
                  ) : <div className="text-[12.5px] text-faint">No memory records referenced by this plan.</div>}
                  {d.rationale_untrusted_model_text && (
                    <div className="rounded-xl bg-lav/60 p-3 text-[12px] text-muted">
                      <div className="mb-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-faint">Model rationale — untrusted text, not evidence or authority</div>
                      {d.rationale_untrusted_model_text}
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader title="Trials" icon={FlaskConical} />
            <div className="px-5 pb-5 sm:px-6">
              {(d.trials ?? []).length === 0 ? (
                <Empty title="No trials yet" icon={FlaskConical}>A plan must pass a matched trial before it can be approved.</Empty>
              ) : (
                <ul className="divide-y divide-line">
                  {d.trials.map((t: Json) => (
                    <li key={t.id}>
                      <Link to={`/app/trials/${t.id}`} className="group flex flex-wrap items-center gap-3 py-3">
                        <StatusChip status={t.status} />
                        <span className="mono text-[12px] text-ink-2">{t.suite_id}</span>
                        <span className="text-[12px] text-faint">finished {shortTs(t.finished_at)}</span>
                        <span className="ml-auto mono text-[11.5px] text-faint">{String(t.trial_hash ?? "").slice(0, 20)}…</span>
                        <ArrowRight className="size-4 text-faint group-hover:text-accent" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {d.path === "ai" && (
                <div className="mt-3">
                  {d.holdout_verdict ? (
                    <Notice tone={d.holdout_verdict.decision === "ROLLOUT_ELIGIBLE" ? "ok" : "warn"} icon={CheckCircle2} title={`Holdout verdict: ${d.holdout_verdict.decision}`}>
                      run {d.holdout_verdict.run_id} · freeze <span className="mono">{String(d.holdout_verdict.freeze_hash).slice(0, 18)}…</span> · {ts(d.holdout_verdict.created_at)}
                    </Notice>
                  ) : (
                    <Notice tone="unknown" icon={Clock3} title="No holdout verdict">AI promotion needs a frozen ROLLOUT_ELIGIBLE verdict from the independent evaluator. Holdout answers are never shown here.</Notice>
                  )}
                </div>
              )}
            </div>
          </Card>
        </div>

        <aside className="xl:sticky xl:top-20 xl:self-start">
          <ApprovalPanel res={res} reload={r.reload} />
          <button onClick={r.reload} className="mt-3 inline-flex w-full items-center justify-center gap-1.5 text-[12px] font-semibold text-muted hover:text-accent"><RotateCcw className="size-3.5" /> Re-read plan from the server</button>
        </aside>
      </div>
    </div>
  );
}
