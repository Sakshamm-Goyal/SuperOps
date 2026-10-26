import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, Search, ShieldCheck, FlaskConical, KeyRound, Brain, XCircle, CheckCircle2, Clock3, Network, Trophy,
  CircleHelp, Lock, Scale, Database, Fingerprint, Layers, Ban, Gauge as GaugeIcon, Leaf,
} from "lucide-react";
import { CloudIllustration, IntegrationHub, Logo, SPONSOR_NODES } from "../components/illustrations";
import { Pill, cx } from "../components/ui";
import { useAuth } from "../lib/auth";

function FloatCard({ className, children, delay = 0 }: { className?: string; children: ReactNode; delay?: number }) {
  return (
    <div className={cx("absolute rounded-2xl bg-white p-3.5 shadow-[var(--shadow-float)] ring-1 ring-line", className)} style={{ animationDelay: `${delay}s` }}>
      {children}
    </div>
  );
}

function Eyebrow({ icon: Icon, children }: { icon: typeof Search; children: ReactNode }) {
  return (
    <div className="mb-4 flex justify-center lg:justify-start">
      <Pill icon={Icon} tone="accent">{children}</Pill>
    </div>
  );
}

/** Illustrative CPU shape for the landing section — figures annotated are from the bundled sample run. */
function AverageLiedChart() {
  const pts = useMemo(() => {
    const out: [number, number][] = [];
    for (let i = 0; i <= 168; i++) {
      const day = Math.sin((i / 24) * Math.PI * 2 - 1.2) * 0.5 + 0.5;
      let v = 6 + day * 9 + ((i * 37) % 11) * 0.4;
      if (i === 121) v = 80; // the burst
      if (i === 120 || i === 122) v = 44;
      if (i === 49) v = 38;
      out.push([i, v]);
    }
    return out;
  }, []);
  const W = 560, H = 230, pl = 8, pr = 8, pt = 12, pb = 18;
  const x = (i: number) => pl + (i / 168) * (W - pl - pr);
  const y = (v: number) => pt + (H - pt - pb) * (1 - v / 100);
  const d = pts.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Illustrative CPU line: low average, a short burst near 80 percent, and a much lower allowed line for the smaller machine">
      <defs>
        <linearGradient id="lied" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#2438f5" stopOpacity=".16" />
          <stop offset="1" stopColor="#2438f5" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 25, 50, 75, 100].map((v) => <line key={v} x1={pl} x2={W - pr} y1={y(v)} y2={y(v)} stroke="#eceef8" />)}
      <path d={`${d}L${x(168)},${y(0)}L${x(0)},${y(0)}Z`} fill="url(#lied)" />
      <path d={d} fill="none" stroke="#2438f5" strokeWidth="1.5" strokeLinejoin="round" />
      <line x1={pl} x2={W - pr} y1={y(10.4)} y2={y(10.4)} stroke="#8a91ae" strokeDasharray="5 4" strokeWidth="1.4" />
      <line x1={pl} x2={W - pr} y1={y(20)} y2={y(20)} stroke="#d63c44" strokeDasharray="7 4" strokeWidth="1.8" />
      <circle cx={x(121)} cy={y(80)} r="10" fill="#d63c44" fillOpacity=".15" />
      <circle cx={x(121)} cy={y(80)} r="4.5" fill="#d63c44" stroke="#fff" strokeWidth="1.5" />
    </svg>
  );
}

const STEPS = [
  {
    n: "01", icon: Search, title: "Investigate",
    body: "Bounded agents read federated cost, telemetry and AI-usage evidence through approved SQL templates, then propose at most three candidates per path.",
    foot: "Zetaris · Nemotron · H-MEM recall",
  },
  {
    n: "02", icon: Scale, title: "Screen & critique",
    body: "Deterministic code checks peak CPU, forecast stress, memory, coverage, freshness, policy and economics. A critic demands evidence or a revision.",
    foot: "Code owns arithmetic and policy",
  },
  {
    n: "03", icon: FlaskConical, title: "Trial",
    body: "Survivors run a matched trial: identical offered load for cloud, a locked development suite with an independent verifier for AI.",
    foot: "Measured, not modelled",
  },
  {
    n: "04", icon: KeyRound, title: "Approve & verify",
    body: "A human approves the exact plan hash and trial hash for 15 minutes. The executor writes once, reads back, and stores the outcome in memory.",
    foot: "PostgreSQL holds authority",
  },
];

export default function Landing() {
  const { me } = useAuth();
  const ctaTo = me ? "/app" : "/signin";
  return (
    <div className="bg-white text-ink">
      {/* Nav */}
      <header className="absolute inset-x-0 top-0 z-30">
        <div className="mx-auto flex h-20 max-w-[1240px] items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="hidden items-center gap-8 text-[14px] font-medium text-ink-2 md:flex">
            <a href="#how" className="hover:text-accent">How it works</a>
            <a href="#rejections" className="hover:text-accent">Why rejections win</a>
            <a href="#integrations" className="hover:text-accent">Integrations</a>
            <a href="#guarantees" className="hover:text-accent">Guarantees</a>
          </nav>
          <Link to={ctaTo} className="inline-flex h-10 items-center gap-2 rounded-full bg-ink px-4 text-[13.5px] font-semibold text-white hover:bg-ink-2">
            {me ? "Open workbench" : "Sign in"} <ArrowRight className="size-4" />
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden pt-28 pb-16 sm:pt-32 lg:pb-24">
        <div className="grid-paper grid-fade absolute inset-0" aria-hidden />
        <div className="absolute -top-40 right-[-10%] size-[620px] rounded-full bg-accent/10 blur-3xl" aria-hidden />
        <div className="relative mx-auto grid max-w-[1240px] items-center gap-12 px-4 sm:px-6 lg:grid-cols-[1.02fr_1fr]">
          <div className="rise text-center lg:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 lg:justify-start">
              <Pill icon={Trophy} tone="dark">Open Agent Hackathon 2026</Pill>
              <a href="#how"><Pill icon={CircleHelp}>How it works?</Pill></a>
            </div>
            <h1 className="display mt-6 text-[46px] sm:text-[64px] lg:text-[74px]">
              Prove it <em>before</em> you change&nbsp;it.
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-[17px] leading-relaxed text-muted lg:mx-0">
              GreenOps Verify hunts cloud and AI waste in a live support service. Agents propose. Deterministic checks, matched
              trials and a human-approved plan hash decide — and every rejection is remembered so it isn't proposed twice.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
              <Link to={ctaTo} className="inline-flex h-12 items-center gap-2 rounded-full bg-accent px-6 text-[15px] font-semibold text-white shadow-[0_14px_30px_-12px_rgb(36_56_245/0.9)] hover:bg-accent-600">
                Open the workbench <ArrowRight className="size-4" />
              </Link>
              <a href="#rejections" className="inline-flex h-12 items-center gap-2 rounded-full bg-white px-6 text-[15px] font-semibold text-ink ring-1 ring-line-2 hover:ring-accent/40">
                See a rejection
              </a>
            </div>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-muted lg:justify-start">
              <span className="inline-flex items-center gap-1.5"><Lock className="size-4 text-accent" /> No write without an exact-hash approval</span>
              <span className="inline-flex items-center gap-1.5"><Fingerprint className="size-4 text-accent" /> Every number has a receipt</span>
            </div>
          </div>

          {/* Illustration + floating cards (figures from the bundled sample run, synthetic data) */}
          <div className="relative mx-auto h-[360px] w-full max-w-[560px] sm:h-[470px]">
            <CloudIllustration className="absolute inset-x-0 top-6 mx-auto w-[92%]" />
            <FloatCard className="floaty left-0 top-0 w-[200px] sm:top-2 sm:w-[230px]">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-fail"><XCircle className="size-3.5" /> Peak CPU · fail</div>
              <div className="mt-1.5 text-[13px] font-semibold leading-snug text-ink">worker-prod-01 → e2-standard-2</div>
              <div className="mono mt-1 text-[11px] text-muted">peak 6.40 vCPU &gt; 1.60 allowed</div>
            </FloatCard>
            <FloatCard className="floaty right-0 top-16 hidden w-[214px] sm:block" delay={1.2}>
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-pass"><CheckCircle2 className="size-3.5" /> Matched trial · pass</div>
              <div className="mt-2 flex items-end gap-1">
                {[38, 52, 44, 61, 47, 58, 50, 55].map((h, i) => <span key={i} className={cx("w-full rounded-sm", i % 2 ? "bg-accent" : "bg-accent-100")} style={{ height: h / 2 }} />)}
              </div>
              <div className="mono mt-1.5 text-[11px] text-muted">p95 72.1 ms · limit 78.7 ms</div>
            </FloatCard>
            <FloatCard className="floaty bottom-24 left-2 hidden w-[236px] sm:block" delay={2.1}>
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-accent"><Brain className="size-3.5" /> Memory recall</div>
              <div className="mt-1.5 text-[12.5px] leading-snug text-ink-2">Prior failure recalled under policy <b>pol-v1</b> — not proposed again.</div>
            </FloatCard>
            <FloatCard className="floaty bottom-4 right-0 w-[220px] sm:bottom-2 sm:right-3 sm:w-[250px]" delay={0.6}>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-warn"><Clock3 className="size-3.5" /> Awaiting approval</span>
                <span className="mono text-[11px] font-semibold text-ink">15:00</span>
              </div>
              <div className="mono mt-1.5 truncate text-[11px] text-muted">plan sha256:71eded1a…c10c</div>
              <div className="mono truncate text-[11px] text-muted">trial sha256:9ee26825…bc5e</div>
            </FloatCard>
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px] text-faint">Figures from a bundled sample run · synthetic data</div>
          </div>
        </div>
      </section>

      {/* Invariant band */}
      <section className="border-y border-line bg-wash">
        <div className="mx-auto grid max-w-[1240px] grid-cols-2 gap-px px-4 sm:px-6 md:grid-cols-5">
          {[
            ["3", "candidates per path, maximum"],
            ["2", "physical sources federated per receipt"],
            ["15", "minute approval window, then it expires"],
            ["1", "active mutation per target, under a lock"],
            ["0", "writes a model, memory or chat can authorise"],
          ].map(([n, l]) => (
            <div key={l} className="px-2 py-8 text-center md:px-4">
              <div className="font-display text-[44px] font-extrabold leading-none tracking-tight text-ink">{n}</div>
              <div className="mx-auto mt-2 max-w-[180px] text-[13px] text-muted">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-[1240px] scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mb-4 flex justify-center"><Pill icon={Layers} tone="accent">How it works in 4 steps</Pill></div>
          <h2 className="display text-[36px] sm:text-[48px]">Agents <em>propose</em>. Evidence <em>decides</em>.</h2>
          <p className="mt-4 text-[16px] text-muted">Each step narrows what is allowed to happen next. Nothing skips a step, and the browser can't push a plan forward on its own.</p>
        </div>
        <ol className="mt-14 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.n} className="card group relative flex flex-col p-6 transition hover:-translate-y-1 hover:shadow-[var(--shadow-float)]">
              <div className="flex items-center justify-between">
                <span className={cx("grid size-12 place-items-center rounded-2xl", i === 3 ? "bg-accent text-white" : "bg-accent-50 text-accent")}>
                  <s.icon className="size-5" />
                </span>
                <span className="font-display text-[40px] font-extrabold leading-none text-line-2">{s.n}</span>
              </div>
              <h3 className="mt-6 font-display text-[21px] font-bold tracking-tight">{s.title}</h3>
              <p className="mt-2 flex-1 text-[14px] leading-relaxed text-muted">{s.body}</p>
              <div className="mt-5 border-t border-line pt-3 text-[12px] font-semibold text-accent">{s.foot}</div>
              {i < 3 && <ArrowRight className="absolute -right-4 top-1/2 hidden size-5 -translate-y-1/2 text-line-2 xl:block" />}
            </li>
          ))}
        </ol>
      </section>

      {/* Signature: the average lied */}
      <section className="bg-wash py-20 lg:py-28">
        <div className="mx-auto grid max-w-[1240px] items-center gap-12 px-4 sm:px-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="text-center lg:text-left">
            <Eyebrow icon={GaugeIcon}>Peak, not average</Eyebrow>
            <h2 className="display text-[36px] sm:text-[48px]">The average said <em>shrink it</em>. The peak said no.</h2>
            <p className="mt-4 text-[16px] leading-relaxed text-muted">
              The production worker averaged 10.4% CPU over three weeks — the classic downsizing bait. The screen reads every recorded
              observation instead: a 6.40 vCPU burst against 1.60 vCPU allowed on the smaller machine, plus a forecast stress envelope.
              The cheaper machine was refused before anyone had to find out the hard way.
            </p>
            <div className="mt-6 grid grid-cols-3 gap-3 text-left">
              {[
                ["10.4%", "average CPU", "text-ink"],
                ["6.40", "peak vCPU", "text-fail"],
                ["1.60", "vCPU allowed", "text-ink"],
              ].map(([v, l, c]) => (
                <div key={l} className="card p-4">
                  <div className={cx("font-display text-[26px] font-extrabold tracking-tight", c)}>{v}</div>
                  <div className="text-[12px] text-muted">{l}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="card p-5 shadow-[var(--shadow-float)] sm:p-7">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-[12px] font-semibold uppercase tracking-wider text-faint">worker-prod-01 · CPU over 21 days</div>
                <div className="font-display text-[18px] font-bold">CHK-CPU-PEAK <span className="text-fail">FAIL</span></div>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-fail-bg px-2.5 py-1 text-[11px] font-bold uppercase text-fail"><Ban className="size-3" /> Rejected</span>
            </div>
            <div className="mt-4"><AverageLiedChart /></div>
            <div className="mt-3 flex flex-wrap gap-4 text-[12px] text-muted">
              <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 bg-accent" /> observed CPU</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-0 w-5 border-t-2 border-dashed border-faint" /> average</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-0 w-5 border-t-2 border-dashed border-fail" /> allowed on candidate (80% of 2 vCPU)</span>
            </div>
            <div className="mt-3 text-[11px] text-faint">Illustrative shape; the figures are from the bundled sample run. The live chart in the workbench plots the real evidence rows.</div>
          </div>
        </div>
      </section>

      {/* Why rejections are wins */}
      <section id="rejections" className="mx-auto max-w-[1240px] scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
        <div className="grid items-end gap-6 lg:grid-cols-2">
          <div>
            <Eyebrow icon={Trophy}>Why rejections are wins</Eyebrow>
            <h2 className="display text-center text-[36px] sm:text-[48px] lg:text-left">A justified <em>NO_CHANGE</em> is a result, not a failure.</h2>
          </div>
          <p className="text-center text-[16px] leading-relaxed text-muted lg:text-left">
            Most savings tools are scored on how much they cut. This one is scored on whether the cut was safe. Each rejection keeps its reason,
            its evidence and its policy version — and memory makes sure the same mistake isn't paid for twice.
          </p>
        </div>
        <div className="mt-12 grid gap-5 lg:grid-cols-3">
          {[
            {
              icon: GaugeIcon, tag: "Cloud · screening", title: "The tempting downsize", tone: "fail",
              body: "Low average CPU invited a 4× smaller machine. Peak CPU, forecast stress and memory checks all failed; the production target wasn't executable anyway.",
              metric: "6.40 vCPU peak vs 1.60 allowed",
            },
            {
              icon: FlaskConical, tag: "AI workflow · trial", title: "The cheaper prompt that dropped a policy", tone: "fail",
              body: "Truncating policy context cut cost per accepted task, but the independent verifier caught premium exceptions and identity escalations it broke.",
              metric: "32/40 accepted vs 38/40 gate · 2 critical",
            },
            {
              icon: Brain, tag: "Memory · next run", title: "The mistake not repeated", tone: "pass",
              body: "Later investigations recall scoped, version-checked outcomes from Meterless H-MEM. Applicable failures are skipped; stale ones are shown as history only.",
              metric: "Applicability checked outside retrieval",
            },
          ].map((c) => (
            <article key={c.title} className="card flex flex-col p-6">
              <div className="flex items-center justify-between">
                <span className="grid size-11 place-items-center rounded-2xl bg-accent-50 text-accent"><c.icon className="size-5" /></span>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">{c.tag}</span>
              </div>
              <h3 className="mt-5 font-display text-[20px] font-bold tracking-tight">{c.title}</h3>
              <p className="mt-2 flex-1 text-[14px] leading-relaxed text-muted">{c.body}</p>
              <div className={cx("mono mt-5 rounded-xl px-3 py-2 text-[12px]", c.tone === "fail" ? "bg-fail-bg text-fail" : "bg-pass-bg text-pass")}>{c.metric}</div>
            </article>
          ))}
        </div>
      </section>

      {/* Integrations hub */}
      <section id="integrations" className="relative scroll-mt-20 overflow-hidden bg-wash py-20 lg:py-28">
        <div className="grid-paper grid-fade absolute inset-0 opacity-60" aria-hidden />
        <div className="relative mx-auto grid max-w-[1240px] items-center gap-12 px-4 sm:px-6 lg:grid-cols-2">
          <div className="order-2 lg:order-1"><IntegrationHub /></div>
          <div className="order-1 lg:order-2">
            <Eyebrow icon={Network}>Integrations</Eyebrow>
            <h2 className="display text-center text-[36px] sm:text-[48px] lg:text-left">Real <em>federation</em>. Real <em>memory</em>. Bounded agents.</h2>
            <ul className="mt-8 grid gap-3 sm:grid-cols-2">
              {SPONSOR_NODES.map((n) => (
                <li key={n.name} className="card flex gap-3 p-4">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-50 text-accent"><n.icon className="size-5" /></span>
                  <div>
                    <div className="text-[14px] font-bold text-ink">{n.name}</div>
                    <div className="text-[12.5px] leading-snug text-muted">{n.role}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Guarantees */}
      <section id="guarantees" className="mx-auto max-w-[1240px] scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mb-4 flex justify-center"><Pill icon={ShieldCheck} tone="accent">Guarantees</Pill></div>
          <h2 className="display text-[36px] sm:text-[48px]">Honest by <em>construction</em>.</h2>
        </div>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            [Database, "Authority lives in PostgreSQL", "Approvals bind actor, plan hash, trial hash, policy version and expiry. A button, a memory or a chat message can't stand in for one."],
            [Fingerprint, "Every figure has a receipt", "Federated queries record template, parameters hash, sources, pages, completeness and result hash."],
            [Leaf, "Proposed is not achieved", "Savings are projections at dated rates until a verified action measures them. Carbon without factors stays unknown."],
            [CircleHelp, "Unknown stays unknown", "Sample, synthetic, estimated, replayed and measured are separate labels — in storage, in the UI and in exports."],
            [Lock, "One write, read back", "Intent and idempotency persist before the provider call. Ambiguous writes are reconciled, never blindly retried."],
            [Brain, "Memory informs, never authorises", "Recall is scoped by tenant and service, and version applicability is enforced outside retrieval."],
          ].map(([Icon, t, b]) => {
            const I = Icon as typeof Lock;
            return (
              <div key={t as string} className="rounded-2xl border border-line p-5">
                <I className="size-5 text-accent" />
                <div className="mt-3 font-display text-[16px] font-bold">{t as string}</div>
                <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{b as string}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 pb-20 sm:px-6">
        <div className="relative mx-auto max-w-[1240px] overflow-hidden rounded-[32px] bg-accent px-6 py-14 text-center text-white sm:px-12 sm:py-20">
          <div className="absolute inset-0 opacity-25" style={{ backgroundImage: "linear-gradient(to right, rgb(255 255 255 / .25) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / .25) 1px, transparent 1px)", backgroundSize: "32px 32px" }} aria-hidden />
          <div className="relative">
            <h2 className="display text-[36px] text-white sm:text-[56px]">Open the <em className="!text-white">evidence</em>, not a dashboard of guesses.</h2>
            <p className="mx-auto mt-4 max-w-xl text-[16px] text-white/80">Sign in with a sandbox token to read every investigation, plan, trial and receipt — and ask the Ops Copilot why.</p>
            <Link to={ctaTo} className="mt-8 inline-flex h-12 items-center gap-2 rounded-full bg-white px-6 text-[15px] font-semibold text-accent hover:bg-accent-50">
              Open the workbench <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center justify-between gap-3 px-4 py-8 text-[12.5px] text-muted sm:flex-row sm:px-6">
          <Logo />
          <p className="max-w-xl text-center sm:text-right">
            A hackathon project for one sandbox service. Sample mode uses synthetic data; savings are projections at dated rates, not invoice savings.
            Product names belong to their owners and are listed only as integrations.
          </p>
        </div>
      </footer>
    </div>
  );
}
