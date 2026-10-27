import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Search, ArrowRight, Brain, BrainCircuit, Filter, Cloud, Bot, Play } from "lucide-react";
import type { Json, Page } from "../lib/api";
import { useGet, useMutation } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import { PageHeader, Button, Card, StatusChip, ErrorBox, Empty, Drawer, Skeleton, KindBadge, cx, Notice, AutopilotBadge, LiveAwsBadge } from "../components/ui";
import { ago, humanize, shortTs, signatureParts, modeLabel, isAutopilot, isLiveAws } from "../lib/format";

const STATUSES = ["ALL", "RUNNING", "AWAITING_APPROVAL", "NEEDS_REVIEW", "NO_CHANGE", "COMPLETED", "FAILED", "CANCELLED"] as const;

function PlanDots({ plans }: { plans: Json[] }) {
  if (!plans?.length) return <span className="text-[12px] text-faint">no plans</span>;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {plans.map((p: Json) => {
        const s = signatureParts(p.signature);
        const color =
          p.status === "REJECTED" ? "bg-fail" : p.status === "AWAITING_APPROVAL" ? "bg-warn" : p.status === "DRAFT" ? "bg-line-2" : ["VERIFIED", "COMPLETED", "APPROVED"].includes(p.status) ? "bg-pass" : "bg-accent";
        return (
          <span key={p.plan_id} title={`${p.signature} — ${p.status}`} className="inline-flex items-center gap-1 rounded-full bg-wash px-1.5 py-0.5 text-[10.5px] font-medium text-ink-2 ring-1 ring-line">
            <span className={cx("size-1.5 rounded-full", color)} />
            {s.path === "ai" ? <Bot className="size-3" /> : <Cloud className="size-3" />}
          </span>
        );
      })}
    </div>
  );
}

const SERVICE_DEFAULTS: Record<string, { question: string; start: string; end: () => string }> = {
  "support-demo": { question: "Find a testable saving while preserving service and support policy", start: "2026-09-30T00:00:00Z", end: () => "2026-10-21T00:00:00Z" },
  "superops-aws": {
    question: "Find a safe, testable saving on the live AWS sandbox without breaking policy",
    start: "2026-10-27T05:50:00Z",
    // now, rounded down to the minute, UTC
    end: () => new Date(Math.floor(Date.now() / 60000) * 60000).toISOString().replace(".000Z", "Z"),
  },
};

function NewInvestigation({ open, onClose, mode }: { open: boolean; onClose: () => void; mode: string }) {
  const nav = useNavigate();
  const m = useMutation<{ investigation_id: string; status: string }>();
  const services = useGet<Page<Json>>(open ? "/v1/services" : null);
  const [service, setService] = useState("support-demo");
  const [question, setQuestion] = useState(SERVICE_DEFAULTS["support-demo"].question);
  const [start, setStart] = useState(SERVICE_DEFAULTS["support-demo"].start);
  const [end, setEnd] = useState(SERVICE_DEFAULTS["support-demo"].end());

  function pickService(id: string) {
    setService(id);
    const d = SERVICE_DEFAULTS[id];
    if (d) {
      setQuestion(d.question);
      setStart(d.start);
      setEnd(d.end());
    }
  }
  const svcList: Json[] = services.data?.items ?? [{ service_id: "support-demo", display_name: "Support demo service", runtime_modes: [mode] }];
  const svc = svcList.find((x) => x.service_id === service);
  const modeOk = !svc?.runtime_modes || svc.runtime_modes.includes(mode);
  const [memory, setMemory] = useState<"on" | "off">("on");
  const [trialProfile, setTrialProfile] = useState("sandbox-trials-v1");
  const [budget, setBudget] = useState("sandbox-approved-budget-v1");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const r = await m.run("/v1/investigations", {
      service_id: service,
      question,
      interval: { start, end },
      runtime_mode: mode,
      budget_profile_id: budget,
      approved_trial_profile_id: trialProfile || undefined,
      memory_mode: memory,
    });
    if (r) {
      onClose();
      nav(`/app/investigations/${r.investigation_id}`);
    }
  }

  const input = "h-10 w-full rounded-xl bg-wash px-3 text-[14px] text-ink ring-1 ring-line outline-none focus:ring-2 focus:ring-accent/50";
  return (
    <Drawer open={open} onClose={onClose} title="New investigation">
      <form onSubmit={submit} className="space-y-5 p-5">
        <Notice tone="info" icon={BrainCircuit}>
          <span className="text-[13px]">Agents will propose at most three candidates per path. Starting an investigation changes nothing on a target: trials run on sandbox fixtures or a disposable canary, and every write needs a separate human approval.</span>
        </Notice>
        <div>
          <span className="mb-1.5 block text-[13px] font-semibold text-ink">Service</span>
          <div className="grid gap-2 sm:grid-cols-2">
            {svcList.map((x) => (
              <button type="button" key={x.service_id} onClick={() => pickService(x.service_id)} className={cx("rounded-xl p-3 text-left ring-1 transition", service === x.service_id ? "bg-accent-50 ring-accent" : "bg-white ring-line hover:ring-accent/40")}>
                <span className="flex items-center justify-between gap-2">
                  <span className="mono text-[12.5px] font-semibold text-ink">{x.service_id}</span>
                  {isLiveAws(x.service_id) && <LiveAwsBadge size="xs" />}
                </span>
                <span className="mt-0.5 block text-[11.5px] text-muted">{x.display_name}</span>
                <span className="mt-1 block text-[10.5px] text-faint">modes: {(x.runtime_modes ?? []).join(", ")}</span>
              </button>
            ))}
          </div>
          {!modeOk && <div className="mt-2"><Notice tone="warn" title="This service does not run in the server's mode">The server runs <b>{mode}</b>; {service} supports {(svc?.runtime_modes ?? []).join(", ")}. The request will be refused.</Notice></div>}
          {isLiveAws(service) && <p className="mt-2 text-[11.5px] text-muted">Live AWS: real CloudWatch metrics and Price List through Zetaris, and a real canary EC2 instance for the trial (about 15 minutes end to end). Nothing on the live instances changes until a human approves.</p>}
        </div>
        <div>
          <label htmlFor="q" className="mb-1.5 block text-[13px] font-semibold text-ink">Question</label>
          <textarea id="q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} maxLength={2000} required className={cx(input, "h-auto py-2.5")} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="st" className="mb-1.5 block text-[13px] font-semibold text-ink">Interval start (UTC)</label>
            <input id="st" value={start} onChange={(e) => setStart(e.target.value)} className={cx(input, "mono text-[12.5px]")} required />
          </div>
          <div>
            <label htmlFor="en" className="mb-1.5 block text-[13px] font-semibold text-ink">Interval end (UTC)</label>
            <input id="en" value={end} onChange={(e) => setEnd(e.target.value)} className={cx(input, "mono text-[12.5px]")} required />
          </div>
        </div>
        <div>
          <span className="mb-1.5 block text-[13px] font-semibold text-ink">Memory</span>
          <div className="grid grid-cols-2 gap-2">
            {(["on", "off"] as const).map((v) => (
              <button type="button" key={v} onClick={() => setMemory(v)} className={cx("flex items-start gap-2 rounded-xl p-3 text-left ring-1 transition", memory === v ? "bg-accent-50 ring-accent" : "bg-white ring-line hover:ring-accent/40")}>
                <Brain className={cx("mt-0.5 size-4", memory === v ? "text-accent" : "text-faint")} />
                <span>
                  <span className="block text-[13px] font-semibold text-ink">Memory {v}</span>
                  <span className="block text-[11.5px] text-muted">{v === "on" ? "Recall prior outcomes and skip known failures" : "Screen every option from scratch (ablation)"}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="tp" className="mb-1.5 block text-[13px] font-semibold text-ink">Trial profile</label>
            <input id="tp" value={trialProfile} onChange={(e) => setTrialProfile(e.target.value)} className={cx(input, "mono text-[12.5px]")} />
          </div>
          <div>
            <label htmlFor="bp" className="mb-1.5 block text-[13px] font-semibold text-ink">Budget profile</label>
            <input id="bp" value={budget} onChange={(e) => setBudget(e.target.value)} className={cx(input, "mono text-[12.5px]")} required />
          </div>
        </div>
        <div className="flex items-center justify-between rounded-xl bg-wash px-3 py-2.5 text-[13px]">
          <span className="text-muted">Runtime mode (set by the server)</span>
          <KindBadge kind={mode} />
        </div>
        {mode === "replay" && <Notice tone="warn" title="Replay mode cannot create investigations">The server will refuse this request with 409.</Notice>}
        <ErrorBox error={m.error} title="Could not start the investigation" />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" icon={Play} loading={m.pending}>Start investigation</Button>
        </div>
        <p className="text-[11.5px] text-faint">Sent with a fresh Idempotency-Key; retrying after a network error reuses it, so the run is never created twice.</p>
      </form>
    </Drawer>
  );
}

export default function Investigations() {
  const { me, canOperate } = useAuth();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState<string>(params.get("status") ?? "ALL");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(params.get("new") === "1");
  const list = useGet<Page<Json>>(`/v1/investigations?limit=100${status !== "ALL" ? `&status=${status}` : ""}`, {
    pollMs: 4000,
    shouldPoll: (d) => !!d?.items.some((i: Json) => i.status === "QUEUED" || i.status === "RUNNING"),
  });

  // ?new=1 opens the drawer once; strip it straight away so a later navigation is never overridden.
  useEffect(() => {
    if (params.get("new") === "1") {
      const next = new URLSearchParams(params);
      next.delete("new");
      setParams(next, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const items = useMemo(() => {
    const all = list.data?.items ?? [];
    const s = q.trim().toLowerCase();
    return s ? all.filter((i: Json) => `${i.id} ${i.question} ${i.status} ${(i.outcome?.plans ?? []).map((p: Json) => p.signature).join(" ")}`.toLowerCase().includes(s)) : all;
  }, [list.data, q]);

  return (
    <div className="rise">
      <PageHeader
        eyebrow="Investigations"
        title={<>Every question, <em>every receipt</em></>}
        sub="Each investigation scopes the service, reads federated evidence, and proposes bounded candidates that must survive screening, critique and a matched trial."
        right={
          canOperate ? (
            <Button icon={Plus} onClick={() => setOpen(true)}>New investigation</Button>
          ) : (
            <span className="text-[12.5px] text-muted">Viewer role: read-only</span>
          )
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-2 overflow-x-auto scroll-thin">
            <Filter className="size-4 shrink-0 text-faint" />
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={cx("whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition", status === s ? "bg-ink text-white" : "bg-wash text-muted hover:text-ink")}
              >
                {s === "ALL" ? "All" : humanize(s)}
              </button>
            ))}
          </div>
          <label className="flex h-10 items-center gap-2 rounded-full bg-wash px-3.5 ring-1 ring-line focus-within:ring-accent/50 lg:w-72">
            <Search className="size-4 text-faint" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search id, question, target" className="min-w-0 flex-1 bg-transparent text-[13.5px] outline-none placeholder:text-faint" />
          </label>
        </div>

        {list.error && <div className="p-4"><ErrorBox error={list.error} /></div>}
        {list.loading && !list.data && (
          <div className="space-y-2 p-4">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16" />)}</div>
        )}
        {list.data && items.length === 0 && (
          <div className="p-6">
            <Empty title={q || status !== "ALL" ? "No investigations match" : "No investigations yet"} icon={Search} action={canOperate && !q ? <Button icon={Plus} onClick={() => setOpen(true)}>Start the first one</Button> : undefined}>
              {q || status !== "ALL" ? "Clear the filter or search to see more." : "Start an investigation to have agents look for a testable saving."}
            </Empty>
          </div>
        )}

        {items.length > 0 && (
          <>
            {/* Desktop table */}
            <table className="hidden w-full text-left md:table">
              <thead>
                <tr className="border-b border-line bg-wash/60 text-[11.5px] font-semibold uppercase tracking-wider text-faint">
                  <th className="px-5 py-3">Investigation</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Plans</th>
                  <th className="px-3 py-3">Memory</th>
                  <th className="px-3 py-3">Created</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {items.map((i: Json) => (
                  <tr key={i.id} className="group cursor-pointer transition hover:bg-accent-50/40">
                    <td className="max-w-[420px] px-5 py-3.5">
                      <Link to={`/app/investigations/${i.id}`} className="block">
                        <div className="flex min-w-0 items-center gap-2">
                          {isAutopilot(i) && <AutopilotBadge size="xs" />}
                          {isLiveAws(i.service_id) && <LiveAwsBadge size="xs" />}
                          <span className="truncate text-[14px] font-semibold text-ink group-hover:text-accent">{i.question}</span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-2 text-[11.5px] text-faint">
                          <span className="mono">{i.id.slice(0, 8)}</span>
                          <span>·</span>
                          <span className="mono">{i.service_id}</span>
                          <span>·</span>
                          <span>{modeLabel(i.runtime_mode)}</span>
                          {i.outcome?.error && <span className="truncate text-fail">· {i.outcome.error.code}</span>}
                        </div>
                      </Link>
                    </td>
                    <td className="px-3 py-3.5"><StatusChip status={i.status} /></td>
                    <td className="px-3 py-3.5"><PlanDots plans={i.outcome?.plans ?? []} /></td>
                    <td className="px-3 py-3.5 text-[12.5px] text-muted">{i.memory_mode === "on" ? <span className="inline-flex items-center gap-1 text-accent"><Brain className="size-3.5" /> on</span> : "off"}</td>
                    <td className="px-3 py-3.5 text-[12.5px] text-muted" title={shortTs(i.created_at)}>{ago(i.created_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <Link to={`/app/investigations/${i.id}`} aria-label="Open investigation" className="inline-grid size-8 place-items-center rounded-full text-faint group-hover:bg-white group-hover:text-accent">
                        <ArrowRight className="size-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Mobile cards */}
            <ul className="divide-y divide-line md:hidden">
              {items.map((i: Json) => (
                <li key={i.id}>
                  <Link to={`/app/investigations/${i.id}`} className="block p-4 active:bg-lav">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 text-[14px] font-semibold text-ink">{isAutopilot(i) && <span className="mr-1.5 inline-block align-middle"><AutopilotBadge size="xs" /></span>}{isLiveAws(i.service_id) && <span className="mr-1.5 inline-block align-middle"><LiveAwsBadge size="xs" /></span>}{i.question}</div>
                      <StatusChip status={i.status} size="xs" />
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <PlanDots plans={i.outcome?.plans ?? []} />
                      <span className="text-[11.5px] text-faint"><span className="mono">{i.id.slice(0, 8)}</span> · {ago(i.created_at)}</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
      {me && <NewInvestigation open={open} onClose={() => setOpen(false)} mode={me.runtime_mode} />}
    </div>
  );
}
