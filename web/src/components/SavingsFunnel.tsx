import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldX, Filter, ArrowRight } from "lucide-react";
import { api, type InvestigationData, type Json, type Page, type Resource, type Overview } from "../lib/api";
import { checkLabel, money } from "../lib/format";
import { Card, CardHeader, KindBadge, Skeleton, cx } from "./ui";

export interface FunnelCounts {
  investigations: number;
  proposed: number;
  screened: number;
  trialPassed: number;
  approved: number;
  verified: number;
  rejected: number;
  topRejection: { check: string; n: number } | null;
  firstVerifiedAction: string | null;
}

/** Stage counts across every investigation, derived from committed read models (no arithmetic on money). */
export async function loadFunnel(): Promise<FunnelCounts> {
  const page = await api.get<Page<Json>>("/v1/investigations?limit=100");
  const withPlans = page.items.filter((i) => (i.outcome?.plans ?? []).length);
  const details = (await Promise.all(withPlans.map((i) => api.get<Resource<InvestigationData>>(`/v1/investigations/${i.id}`).catch(() => null)))).filter(Boolean) as Resource<InvestigationData>[];
  const c: FunnelCounts = { investigations: page.items.length, proposed: 0, screened: 0, trialPassed: 0, approved: 0, verified: 0, rejected: 0, topRejection: null, firstVerifiedAction: null };
  const rej: Record<string, number> = {};
  for (const r of details) {
    const d = r.data;
    const passedTrial = new Set((d.trials ?? []).filter((t) => t.status === "PASSED").map((t) => t.plan_id));
    const actions = d.actions ?? [];
    const actedPlans = new Set(actions.map((a: Json) => a.plan_id));
    const verifiedPlans = new Set(actions.filter((a: Json) => a.status === "VERIFIED").map((a: Json) => a.plan_id));
    for (const p of d.plans ?? []) {
      c.proposed += 1;
      if (p.screening?.outcome === "ELIGIBLE_FOR_TRIAL") c.screened += 1;
      if (passedTrial.has(p.id)) c.trialPassed += 1;
      if (p.status === "APPROVED" || actedPlans.has(p.id)) c.approved += 1;
      if (verifiedPlans.has(p.id)) c.verified += 1;
      if (p.status === "REJECTED") {
        c.rejected += 1;
        for (const ch of p.screening?.checks ?? []) if (ch.status === "FAIL") rej[ch.check_id] = (rej[ch.check_id] ?? 0) + 1;
      }
    }
    const va = actions.find((a: Json) => a.status === "VERIFIED");
    if (va && !c.firstVerifiedAction) c.firstVerifiedAction = va.id;
  }
  const top = Object.entries(rej).sort((a, b) => b[1] - a[1])[0];
  c.topRejection = top ? { check: top[0], n: top[1] } : null;
  return c;
}

const STAGES: { key: keyof FunnelCounts; label: string; basis: string; kind: string }[] = [
  { key: "proposed", label: "Proposed by agents", basis: "projected at dated rates", kind: "projected" },
  { key: "screened", label: "Passed deterministic screening", basis: "code-owned checks on evidence", kind: "measured" },
  { key: "trialPassed", label: "Passed a matched trial", basis: "measured on sandbox fixtures", kind: "measured" },
  { key: "approved", label: "Approved by a human", basis: "exact plan + trial hash, 15 min", kind: "observed" },
  { key: "verified", label: "Executed and verified", basis: "measured · local analogue", kind: "measured" },
];

export function SavingsFunnel({ ov }: { ov: Overview }) {
  const [c, setC] = useState<FunnelCounts | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let alive = true;
    loadFunnel().then((x) => alive && setC(x)).catch(() => alive && setErr(true));
    return () => { alive = false; };
  }, []);
  const max = Math.max(1, c?.proposed ?? 1);
  const blocked = ov.savings.blocked_monthly_usd;

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1.6fr_1fr]">
      <Card>
        <CardHeader title="Savings funnel" icon={Filter} sub={c ? `Every candidate plan across ${c.investigations} investigations — each stage narrows what may happen next` : "Every candidate plan, stage by stage"} />
        <div className="px-5 pb-5 sm:px-6">
          {!c && !err && <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11" />)}</div>}
          {err && <div className="text-[13px] text-faint">Could not read the investigations to build the funnel.</div>}
          {c && (
            <ol className="space-y-2">
              {STAGES.map((s, i) => {
                const n = c[s.key] as number;
                const w = Math.max(6, (n / max) * 100);
                const money$ = s.key === "proposed" ? ov.savings.proposed_monthly_usd : s.key === "verified" ? ov.savings.verified_monthly_usd : null;
                return (
                  <li key={s.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:grid-cols-[200px_minmax(0,1fr)_auto]">
                    <div className="min-w-0 sm:order-none">
                      <div className="truncate text-[13px] font-semibold text-ink">{s.label}</div>
                      <div className="truncate text-[11px] text-faint">{s.basis}</div>
                    </div>
                    <div className="order-3 col-span-2 sm:order-none sm:col-span-1">
                      <div className="h-9 overflow-hidden rounded-xl bg-lav">
                        <div
                          className={cx("flex h-full items-center rounded-xl px-3 text-[13px] font-bold text-white transition-all duration-700", i === STAGES.length - 1 ? "bg-pass" : "bg-accent")}
                          style={{ width: `${w}%`, opacity: 1 - i * 0.12 }}
                        >
                          {n}
                        </div>
                      </div>
                    </div>
                    <div className="flex min-w-[96px] flex-col items-end text-right">
                      {money$ !== null && money$ !== undefined ? (
                        <>
                          <span className="font-display text-[15px] font-bold text-ink">{money(money$)}</span>
                          <span className="text-[10.5px] text-faint">{s.key === "verified" ? "projection of verified change" : "projected, latest run"}</span>
                        </>
                      ) : (
                        <>
                          <KindBadge kind={s.kind === "observed" ? "human" : s.kind} />
                          {i > 0 && (c[STAGES[i - 1].key] as number) > 0 && <span className="mt-0.5 text-[10.5px] text-faint">{Math.round((n / (c[STAGES[i - 1].key] as number)) * 100)}% of previous</span>}
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
          <p className="mt-4 text-[11.5px] text-faint">
            Dollar figures are the server's projections at dated synthetic rates; even the verified figure is a projection of a change verified on the local analogue, not an invoice saving.
          </p>
        </div>
      </Card>
      <div className="card relative flex flex-col overflow-hidden bg-ink p-6 text-white">
        <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "linear-gradient(to right, rgb(255 255 255 / .2) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / .2) 1px, transparent 1px)", backgroundSize: "28px 28px" }} aria-hidden />
        <div className="relative flex items-center justify-between">
          <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-white/60">Risk avoided</span>
          <span className="grid size-9 place-items-center rounded-full bg-white/10"><ShieldX className="size-4" /></span>
        </div>
        {blocked != null ? (
          <>
            <div className="relative mt-4 font-display text-[52px] font-extrabold leading-none tracking-tight">{money(blocked)}</div>
            <div className="relative mt-2 text-[14px] text-white/80">Tempting projected savings the evidence refused in the latest run — the risk avoided, not money lost.</div>
          </>
        ) : (
          <>
            <div className="relative mt-4 font-display text-[52px] font-extrabold leading-none tracking-tight">{c ? c.rejected : "…"} <span className="text-[22px] font-bold text-white/70">plans stopped</span></div>
            <div className="relative mt-2 text-[14px] text-white/80">Each rejection kept its reason and evidence. The latest run had no rejected candidate with a projected saving, so no dollar figure is claimed.</div>
          </>
        )}
        <div className="relative mt-auto space-y-2 pt-6 text-[13px]">
          {blocked != null && <div className="flex items-center justify-between border-t border-white/15 pt-3"><span className="text-white/60">Plans rejected with a kept reason</span><b className="font-display text-[20px]">{c ? c.rejected : "…"}</b></div>}
          {c?.topRejection && <div className={cx("flex items-center justify-between", blocked == null && "border-t border-white/15 pt-3")}><span className="text-white/60">Most common stop</span><b>{checkLabel(c.topRejection.check)} · {c.topRejection.n}</b></div>}
          {c?.firstVerifiedAction && (
            <Link to={`/app/actions/${c.firstVerifiedAction}`} className="mt-2 flex items-center justify-between rounded-xl bg-white/10 px-3 py-2 font-semibold hover:bg-white/15">
              See the verified change <ArrowRight className="size-4" />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
