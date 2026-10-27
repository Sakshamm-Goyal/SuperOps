import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Search, Clock3, Leaf, DollarSign, Bot, Network, Brain, Cpu, Sparkles, ArrowRight, Activity, ShieldCheck, Ban, Info, BadgeCheck,
} from "lucide-react";
import { api, ApiError, type Overview as OverviewT, type Page, type Json, type Resource, type InvestigationData } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card, CardHeader, Stat, PageHeader, StatusChip, ErrorBox, PageSkeleton, Empty, KindBadge, Notice, cx, Button, LiveAwsBadge } from "../components/ui";
import { Gauge, BarList, StackBar, MiniBars } from "../components/charts";
import { SavingsFunnel } from "../components/SavingsFunnel";
import { ago, money, num, checkLabel, modeLabel, humanize, eventLabel, isAutopilot, isLiveAws } from "../lib/format";

const STATUS_COLORS: Record<string, string> = {
  AWAITING_APPROVAL: "#e0a100",
  NEEDS_REVIEW: "#f3c969",
  REJECTED: "#d63c44",
  FAILED: "#e88a8f",
  DRAFT: "#b8bfdc",
  VALIDATED: "#5c6cff",
  APPROVED: "#2438f5",
  COMPLETED: "#0d8f62",
  VERIFIED: "#0d8f62",
  NO_CHANGE: "#8a91ae",
  CANCELLED: "#d5daee",
  RUNNING: "#2438f5",
  QUEUED: "#8d99ff",
  STALE: "#b86e00",
  NEEDS_EVIDENCE: "#f59e0b",
};

interface Derived {
  ov: OverviewT;
  derived: boolean;
  perDay: { label: string; value: number }[];
  autopilotRuns?: number;
  invs?: { id: string; service_id: string; status: string; created_at: string }[];
}

async function deriveOverview(): Promise<Derived> {
  const page = await api.get<Page<Json>>("/v1/investigations?limit=100");
  const items = page.items;
  const byStatus: Record<string, number> = {};
  const planStatus: Record<string, number> = {};
  for (const i of items) {
    byStatus[i.status] = (byStatus[i.status] ?? 0) + 1;
    for (const p of i.outcome?.plans ?? []) planStatus[p.status] = (planStatus[p.status] ?? 0) + 1;
  }
  // Read details of the most recent investigations that produced plans, for check and sponsor detail.
  const withPlans = items.filter((i) => (i.outcome?.plans ?? []).length).slice(0, 8);
  const details = await Promise.all(withPlans.map((i) => api.get<Resource<InvestigationData>>(`/v1/investigations/${i.id}`).catch(() => null)));
  const rej: Record<string, number> = {};
  let proposed = 0;
  let proposedAny = false;
  let recalls = 0, hits = 0;
  let mem: Json = null;
  let fed: Json = null;
  for (const d of details) {
    if (!d) continue;
    for (const p of d.data.plans ?? []) {
      if (p.status === "REJECTED") for (const c of p.screening?.checks ?? []) if (c.status === "FAIL") rej[c.check_id] = (rej[c.check_id] ?? 0) + 1;
    }
    const m = d.data.memory;
    if (m?.status === "used") { recalls += 1; hits += (m.applicable ?? []).length; }
    if (!mem && m?.embedding_profile) mem = m;
    if (!fed && d.data.federation) fed = d.data.federation;
  }
  // Proposed saving (derived view): the server's own projected gross saving for the latest investigation's plans awaiting
  // approval, summed only when they share one horizon. No re-normalisation in the browser.
  const latest = details.find(Boolean);
  const horizons = new Set<string>();
  for (const p of latest?.data.plans ?? []) {
    const imp = p.impacts;
    if (p.status === "AWAITING_APPROVAL" && imp?.result_kind === "projected" && imp.gross_saving) {
      proposed += Number(imp.gross_saving);
      horizons.add(String(imp.horizon_hours));
      proposedAny = true;
    }
  }
  if (horizons.size > 1) proposedAny = false;
  const days: Record<string, number> = {};
  for (const i of items) {
    const k = String(i.created_at).slice(0, 10);
    days[k] = (days[k] ?? 0) + 1;
  }
  const keys = Object.keys(days).sort().slice(-10);
  const ov: OverviewT = {
    request_id: page.request_id,
    runtime_mode: items[0]?.runtime_mode ?? "unknown",
    service_id: "support-demo",
    generated_at: new Date().toISOString(),
    investigations: { total: items.length, by_status: byStatus },
    plans: { total: Object.values(planStatus).reduce((a, b) => a + b, 0), by_status: planStatus },
    savings: { proposed_monthly_usd: proposedAny ? proposed.toFixed(2) : null, verified_monthly_usd: null, basis: `Projected gross saving at dated rates over a ${[...horizons][0] ?? "?"} h horizon (latest investigation, plans awaiting approval)` },
    carbon: { proposed_monthly_kgco2e: null, basis: "Unknown" },
    rejections_by_check: Object.entries(rej).map(([check_id, count]) => ({ check_id, count })).sort((a, b) => b.count - a.count),
    memory: { status: mem?.status ?? "unknown", semantic: mem?.embedding_profile?.semantic ?? null, embedding_model: mem?.embedding_profile?.model_id ?? null, records: null, recalls, applicable_hits: hits },
    federation: { mode: fed?.source_system ?? "unknown", sources: (fed?.sources ?? []).map((s: string) => ({ group: s.split(":")[1] ?? s, name: s })), receipts: 0, last_receipt_at: null },
    model: { agent_model_id: null, copilot_model_id: null },
    recent: items.slice(0, 8).map((i) => ({ at: i.updated_at ?? i.created_at, kind: `investigation.${String(i.status).toLowerCase()}`, investigation_id: i.id, summary: `${humanize(i.status)} · ${i.question}` })),
  };
  return { ov, derived: true, perDay: keys.map((k) => ({ label: k.slice(8), value: days[k] })) };
}

async function loadOverview(): Promise<Derived> {
  try {
    const ov = await api.get<OverviewT>("/v1/overview");
    let perDay: { label: string; value: number }[] = [];
    let autopilotRuns = 0;
    let invs: Derived["invs"] = undefined;
    try {
      const page = await api.get<Page<Json>>("/v1/investigations?limit=100");
      const days: Record<string, number> = {};
      for (const i of page.items) days[String(i.created_at).slice(0, 10)] = (days[String(i.created_at).slice(0, 10)] ?? 0) + 1;
      perDay = Object.keys(days).sort().slice(-10).map((k) => ({ label: k.slice(8), value: days[k] }));
      autopilotRuns = page.items.filter((i: Json) => isAutopilot(i)).length;
      invs = page.items.map((i: Json) => ({ id: i.id, service_id: i.service_id, status: i.status, created_at: i.created_at }));
    } catch { /* per-day chart is optional */ }
    return { ov, derived: false, perDay, autopilotRuns, invs };
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 405)) return deriveOverview();
    throw e;
  }
}

function HealthRow({ icon: Icon, name, status, children }: { icon: typeof Network; name: string; status: string | null; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-3.5">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-50 text-accent"><Icon className="size-5" /></span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[14px] font-bold text-ink">{name}</span>
          {status && <StatusChip status={status} size="xs" />}
        </div>
        <div className="mt-0.5 text-[13.5px] leading-snug text-muted">{children}</div>
      </div>
    </div>
  );
}

export default function Overview() {
  const { me } = useAuth();
  const [state, setState] = useState<{ d?: Derived; err?: ApiError; loading: boolean }>({ loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    loadOverview()
      .then((d) => alive && setState({ d, loading: false }))
      .catch((e) => alive && setState({ err: e instanceof ApiError ? e : new ApiError(0, { code: "CLIENT_ERROR", message: String(e) }), loading: false }));
    return () => { alive = false; };
  }, [tick]);

  const d = state.d;
  const ov = d?.ov;
  const [svc, setSvc] = useState<string>("all");
  const scoped = useMemo(() => {
    if (!d?.invs || svc === "all") return null;
    const list = d.invs.filter((i) => i.service_id === svc);
    const by: Record<string, number> = {};
    const days: Record<string, number> = {};
    for (const i of list) {
      by[i.status] = (by[i.status] ?? 0) + 1;
      const k = String(i.created_at).slice(0, 10);
      days[k] = (days[k] ?? 0) + 1;
    }
    return {
      ids: new Set(list.map((i) => i.id)),
      total: list.length,
      by,
      perDay: Object.keys(days).sort().slice(-10).map((k) => ({ label: k.slice(8), value: days[k] })),
    };
  }, [d, svc]);
  const rejectedShare = useMemo(() => {
    if (!ov || !ov.plans.total) return null;
    return (ov.plans.by_status.REJECTED ?? 0) / ov.plans.total;
  }, [ov]);

  if (state.loading && !d) return <PageSkeleton />;
  if (state.err) return <ErrorBox error={state.err} title="Could not load the overview" />;
  if (!ov) return null;

  const awaiting = ov.plans.by_status.AWAITING_APPROVAL ?? 0;
  const recent = scoped ? ov.recent.filter((r) => scoped.ids.has(r.investigation_id)) : ov.recent;
  const services = Array.from(new Set((d?.invs ?? []).map((i) => i.service_id))).sort();
  const firstName = me?.display_name?.split(" ").slice(-1)[0];

  return (
    <div className="rise">
      <PageHeader
        eyebrow={<><span>Overview</span><span className="text-line-2">/</span><span className="normal-case tracking-normal">{svc === "all" ? "all services" : svc}</span></>}
        title={<>Every service, <em>at a glance</em></>}
        sub={`Welcome back${firstName ? `, ${firstName}` : ""}. Every figure below links back to a committed record.`}
        chips={
          <>
            <KindBadge kind={ov.runtime_mode === "sample" ? "sample" : ov.runtime_mode} prefix="mode" />
            <span className="text-[12px] text-faint">generated {ago(ov.generated_at)}</span>
          </>
        }
        right={
          <>
            <Button variant="secondary" size="md" onClick={() => setTick((t) => t + 1)} loading={state.loading}>Refresh</Button>
            <Link to="/app/investigations?new=1"><Button icon={Search}>New investigation</Button></Link>
          </>
        }
      />

      {services.length > 1 && (
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <div className="flex max-w-full gap-1 overflow-x-auto rounded-full bg-lav p-1 scroll-thin" role="tablist" aria-label="Filter by service">
            {["all", ...services].map((x) => (
              <button key={x} role="tab" aria-selected={svc === x} onClick={() => setSvc(x)}
                className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-[13.5px] font-semibold transition", svc === x ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink")}>
                {x === "all" ? "All services" : <span className="mono">{x}</span>}
                {isLiveAws(x) && <LiveAwsBadge size="xs" />}
              </button>
            ))}
          </div>
          {scoped && <span className="text-[12px] text-faint">Filters investigation counts, runs per day and recent activity; plan, savings and sponsor figures stay tenant-wide.</span>}
        </div>
      )}

      {d.derived && (
        <div className="mb-5">
          <Notice tone="info" icon={Info} title="Derived view">
            <span className="text-[14px]">The <code className="mono">/v1/overview</code> endpoint isn't available on this API, so these figures are computed in your browser from recent investigations. Verified savings, carbon and model ids need that endpoint.</span>
          </Notice>
        </div>
      )}

      {!d.derived && <SavingsFunnel ov={ov} />}

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label={scoped ? `Investigations · ${svc}` : "Investigations"} icon={Search} value={scoped ? scoped.total : ov.investigations.total}
          sub={<span className="flex flex-wrap gap-x-3">{Object.entries(scoped ? scoped.by : ov.investigations.by_status).map(([k, v]) => <span key={k}>{humanize(k)} <b className="text-ink tnum">{v}</b></span>)}</span>} />
        <Stat label="Awaiting approval" icon={Clock3} value={awaiting} sub="Plans that passed screening and a matched trial" footnote="Approval binds the exact plan + trial hash for 15 min" />
        <Stat accent label={d.derived ? "Proposed saving" : "Proposed monthly saving"} icon={DollarSign}
          value={ov.savings.proposed_monthly_usd === null ? "—" : money(ov.savings.proposed_monthly_usd)}
          sub={ov.savings.proposed_monthly_usd === null ? "No projected saving available" : <>Projected, latest investigation{ov.savings.latest_investigation_id && <> · <Link className="underline" to={`/app/investigations/${ov.savings.latest_investigation_id}`}>{ov.savings.latest_investigation_id.slice(0, 8)}</Link></>}</>}
          footnote="Proposed ≠ achieved. A projection, not an invoice saving." />
        <Stat label="Verified monthly saving" icon={BadgeCheck}
          value={ov.savings.verified_monthly_usd === null ? "—" : money(ov.savings.verified_monthly_usd)}
          sub={ov.savings.verified_monthly_usd === null ? "No verified action has measured a saving yet" : "Projection of changes verified in the sandbox analogue"}
          footnote={<span className="flex items-start gap-1"><Leaf className="mt-0.5 size-3 shrink-0" /> Carbon: {ov.carbon.proposed_monthly_kgco2e === null ? `unknown (${ov.carbon.basis})` : `${num(ov.carbon.proposed_monthly_kgco2e)} kgCO₂e proposed · ${ov.carbon.basis}`}</span>} />
      </div>
      <details className="mt-3 text-[13px] text-muted">
        <summary className="cursor-pointer select-none font-semibold text-ink-2 hover:text-accent">How these savings are calculated</summary>
        <p className="mt-1.5 max-w-4xl">{ov.savings.basis}</p>
      </details>


      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3 [&>*]:min-w-0">
        <Card className="flex flex-col">
          <CardHeader title="Stopped by evidence" icon={Ban} sub="Share of candidate plans rejected before execution" />
          <div className="flex flex-1 flex-col items-center justify-center px-5 pb-6">
            <Gauge value={rejectedShare} label={`${ov.plans.by_status.REJECTED ?? 0} of ${ov.plans.total} plans rejected`} sub="Each kept its reason and evidence — a rejection is a result." />
          </div>
        </Card>
        <Card>
          <CardHeader title="Rejections by check" icon={ShieldCheck} sub="Which deterministic check stopped a plan" />
          <div className="px-5 pb-6 sm:px-6">
            {ov.rejections_by_check.length ? (
              <BarList items={ov.rejections_by_check.slice(0, 7).map((r) => ({ label: <span><b className="font-semibold text-ink">{checkLabel(r.check_id)}</b> <span className="mono text-[12px] text-faint">{r.check_id}</span></span>, value: r.count ?? r.n ?? 0, tone: "fail" as const }))} />
            ) : (
              <Empty title="No rejections yet" icon={ShieldCheck}>When a check refuses a plan it shows up here.</Empty>
            )}
          </div>
        </Card>
        <Card>
          <CardHeader title="Pipeline" icon={Activity} sub="Plans and investigations by status" />
          <div className="space-y-6 px-5 pb-6 sm:px-6">
            <div>
              <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-faint">Plans · {ov.plans.total}</div>
              <StackBar parts={Object.entries(ov.plans.by_status).map(([k, v]) => ({ label: humanize(k), value: v, color: STATUS_COLORS[k] ?? "#b8bfdc" }))} />
            </div>
            <div>
              <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-faint">Investigations per day</div>
              {(scoped ? scoped.perDay : d.perDay).length ? <MiniBars data={(scoped ? scoped.perDay : d.perDay).map((p, i, a) => ({ ...p, highlight: i === a.length - 1 }))} height={110} /> : <div className="text-sm text-muted">No runs</div>}
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1fr] [&>*]:min-w-0">
        <Card>
          <CardHeader title="Sponsor health" icon={Network} sub="What each integration contributed to recent runs" />
          <div className="divide-y divide-line px-5 pb-3 sm:px-6">
            <HealthRow icon={Network} name="Zetaris federation" status={/sample|local/.test(ov.federation.mode) ? "unknown" : ov.federation.receipts || ov.federation.sources.length ? "ready" : "unknown"}>
              Mode <b className="text-ink">{ov.federation.mode === "local_sample_postgres" ? "local sample database — not Zetaris federation" : ov.federation.mode}</b>
              {ov.federation.sources.length > 0 && <> · sources {ov.federation.sources.map((s) => <span key={s.name} className="mono mx-0.5 rounded bg-lav px-1 text-[12px] text-ink-2">{s.name}</span>)}</>}
              {" · "}{ov.federation.receipts} receipts{ov.federation.last_receipt_at && <> · last {ago(ov.federation.last_receipt_at)}</>}
            </HealthRow>
            <HealthRow icon={Brain} name="Meterless H-MEM" status={ov.memory.status}>
              Embedder <b className="text-ink">{ov.memory.embedding_model ?? "unknown"}</b>
              {ov.memory.semantic === false && <span className="text-warn"> (hash conformance — not semantic-recall evidence)</span>}
              {ov.memory.semantic === true && <span className="text-pass"> (semantic)</span>}
              {" · "}{ov.memory.records ?? "?"} records{ov.memory.pending ? ` (${ov.memory.pending} pending)` : ""} · {ov.memory.recalls} recalls · {ov.memory.applicable_hits} applicable hits
              {ov.memory.engine && <> · engine {ov.memory.engine}{ov.memory.engine_sha && <span className="mono text-[12px]"> @{ov.memory.engine_sha}</span>}</>}
            </HealthRow>
            <HealthRow icon={Cpu} name="NVIDIA Nemotron agents" status={ov.model.agent_model_id ? "configured" : null}>
              {ov.model.agent_model_id ? <span className="mono text-[12px] text-ink">{ov.model.agent_model_id}</span> : "Model id not reported by this API"} · coordinator, investigator, optimizer, critic roles via Google ADK
            </HealthRow>
            <HealthRow icon={Sparkles} name="Claude Ops Copilot" status={ov.model.copilot_model_id ? "configured" : null}>
              {ov.model.copilot_model_id ? <span className="mono text-[12px] text-ink">{ov.model.copilot_model_id}</span> : "Model id not reported by this API"} · advisory chat over committed records
            </HealthRow>
            <HealthRow icon={Bot} name="Autopilot" status={d.autopilotRuns ? "ACTIVE" : null}>
              Re-investigates when Zetaris evidence drifts; it can never approve or execute.{d.autopilotRuns ? <> · <Link to="/app/investigations" className="font-semibold text-accent hover:underline">{d.autopilotRuns} drift-triggered run{d.autopilotRuns === 1 ? "" : "s"}</Link></> : " No drift-triggered runs yet."}
            </HealthRow>
          </div>
        </Card>
        <Card>
          <CardHeader title="Recent activity" icon={Clock3} right={<Link to="/app/investigations" className="text-[14px] font-semibold text-accent hover:underline">All investigations</Link>} />
          <ol className="relative px-5 pb-5 sm:px-6">
            {recent.length === 0 && <Empty title="Nothing yet" icon={Clock3}>{scoped ? `No recent activity for ${svc} in the latest events.` : "Start an investigation to see activity here."}</Empty>}
            {recent.slice(0, 8).map((r, i) => (
              <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                {i < Math.min(recent.length, 8) - 1 && <span className="absolute left-[7px] top-5 h-full w-px bg-line" />}
                <span className={cx("relative mt-1.5 size-[15px] shrink-0 rounded-full border-[3px] border-white ring-1", i === 0 ? "bg-accent ring-accent/40" : "bg-line-2 ring-line")} />
                <Link to={`/app/investigations/${r.investigation_id}`} className="group min-w-0 flex-1 rounded-xl px-2 py-1 -mx-2 hover:bg-lav">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-[14px] font-semibold text-ink group-hover:text-accent">{eventLabel(r.kind)}</span>
                    <ArrowRight className="size-3.5 shrink-0 text-faint opacity-0 group-hover:opacity-100" />
                  </div>
                  {r.summary && r.summary !== r.kind && <div className="truncate text-[12px] text-muted">{r.summary}</div>}
                  <div className="text-[12.5px] text-faint">{r.actor && <span className="mono">{r.actor} · </span>}{ago(r.at)} · <span className="mono">{r.investigation_id.slice(0, 8)}</span></div>
                </Link>
              </li>
            ))}
          </ol>
        </Card>
      </div>
      <p className="mt-6 text-center text-[12px] text-faint">Runtime mode: {modeLabel(ov.runtime_mode)} · request {ov.request_id}</p>
    </div>
  );
}
