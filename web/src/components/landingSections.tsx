import type { ReactNode } from "react";
import {
  Bot, Cpu, Sparkles, Users, Cloud, Server, Activity, Tag, Network, ClipboardList, Hourglass, Terminal, RotateCcw, ShieldCheck,
  Ban, CheckCircle2, Lock, KeyRound,
} from "lucide-react";
import { Pill, cx } from "./ui";

interface AgentRow { name: string; does: string; bound: string }

const NEMOTRON: AgentRow[] = [
  { name: "Coordinator", does: "Scopes the run: which paths, which resources, which question.", bound: "No evidence access beyond the scope it sets" },
  { name: "Investigator", does: "Reads federated evidence through approved SQL templates and recalls scoped memory.", bound: "Read-only templates, validated parameters" },
  { name: "Optimizer", does: "Proposes and revises at most three candidates per path.", bound: "Every proposal is screened by code, not trusted" },
  { name: "Critic", does: "Asks for more evidence, a revision or a trial before anything moves.", bound: "Cannot pass a check that code failed" },
  { name: "Support agent", does: "Answers real support tickets inside AI-workflow trials, so quality is measured, not assumed.", bound: "Graded by an independent verifier" },
];

function Group({ icon: Icon, model, note, children }: { icon: typeof Cpu; model: string; note: string; children: ReactNode }) {
  return (
    <div className="grid gap-4 border-t border-line py-8 lg:grid-cols-[260px_1fr] lg:gap-10">
      <div>
        <div className="flex items-center gap-2.5">
          <span className="grid size-10 place-items-center rounded-xl bg-accent text-white"><Icon className="size-5" /></span>
          <div className="font-display text-[17px] font-bold leading-tight tracking-tight text-ink">{model}</div>
        </div>
        <p className="mt-2 text-[13px] leading-snug text-muted">{note}</p>
      </div>
      <div className="divide-y divide-line">{children}</div>
    </div>
  );
}

function Row({ a }: { a: AgentRow }) {
  return (
    <div className="grid gap-1 py-3.5 first:pt-0 last:pb-0 sm:grid-cols-[150px_1fr] sm:gap-6 xl:grid-cols-[150px_1fr_260px]">
      <div className="font-display text-[19px] font-bold tracking-tight text-ink">{a.name}</div>
      <div className="text-[14.5px] leading-relaxed text-ink-2">{a.does}</div>
      <div className="flex items-start gap-1.5 text-[12.5px] text-muted xl:justify-end xl:text-right"><Lock className="mt-0.5 size-3.5 shrink-0 text-accent xl:order-2" />{a.bound}</div>
    </div>
  );
}

export function AgentsSection() {
  return (
    <section id="agents" className="mx-auto max-w-[1240px] scroll-mt-20 px-4 pb-20 sm:px-6 lg:pb-28">
      <div className="grid items-end gap-6 lg:grid-cols-[1fr_1fr]">
        <div>
          <div className="mb-4 flex justify-center lg:justify-start"><Pill icon={Users} tone="accent">The agents</Pill></div>
          <h2 className="display text-center text-[36px] sm:text-[48px] lg:text-left">Seven agents. <em>One</em> human step.</h2>
        </div>
        <blockquote className="rounded-2xl border-l-4 border-accent bg-accent-50 px-5 py-4 text-[15.5px] leading-relaxed text-ink-2">
          <b className="text-ink">Autonomous up to the write:</b> from scoping to the approval gate a run needs no human; the one human step is approving the exact hash of a single change.
        </blockquote>
      </div>

      <div className="mt-12">
        <Group icon={Cpu} model="NVIDIA Nemotron 3.5 Super" note="Five bounded roles orchestrated with Google ADK. Typed outputs, allow-listed tools, no write credentials.">
          {NEMOTRON.map((a) => <Row key={a.name} a={a} />)}
        </Group>
        <Group icon={Sparkles} model="Claude Haiku 4.5" note="Advisory chat for operators, managers and judges.">
          <Row a={{ name: "Ops Copilot", does: "Answers why a plan was rejected, what memory skipped and what blocks approval — and cites the records it read.", bound: "Read-only; cannot approve, execute or change anything" }} />
        </Group>
        <Group icon={Bot} model="Autopilot" note="A deterministic loop, not a language model.">
          <Row a={{ name: "Autopilot", does: "Fingerprints Zetaris evidence and re-investigates when inventory, telemetry, billing, prices or policy change materially.", bound: "Can start runs; can never approve or execute" }} />
        </Group>
        <div className="flex flex-wrap items-center gap-3 border-t border-line pt-6 text-[13px] text-muted">
          <KeyRound className="size-4 text-accent" />
          Then a person approves one plan hash and one trial hash for 15 minutes. Authority lives in PostgreSQL, not in any agent.
        </div>
      </div>
    </section>
  );
}

// ---- Live on AWS ----

type Shape = "spiky" | "steady" | "flat";
function Spark({ shape }: { shape: Shape }) {
  const pts = Array.from({ length: 40 }, (_, i) => {
    let v = shape === "steady" ? 45 + Math.sin(i / 3) * 3 : shape === "flat" ? 22 + Math.sin(i / 5) * 2 : 18 + Math.sin(i / 2.5) * 4;
    if (shape === "spiky" && (i === 12 || i === 31)) v = 88;
    if (shape === "spiky" && (i === 13 || i === 30)) v = 52;
    return [i * 5, 60 - v * 0.6] as const;
  });
  const d = pts.map(([x, y], k) => `${k ? "L" : "M"}${x},${y.toFixed(1)}`).join("");
  return (
    <svg viewBox="0 0 195 60" className="h-12 w-full" aria-hidden preserveAspectRatio="none">
      <line x1="0" x2="195" y1={60 - 80 * 0.6} y2={60 - 80 * 0.6} stroke="#ff8a8f" strokeDasharray="4 3" strokeWidth="1" />
      <path d={`${d}L195,60L0,60Z`} fill="rgb(141 153 255 / .18)" />
      <path d={d} fill="none" stroke="#a9b3ff" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

const INSTANCES: { name: string; type: string; env: string; shape: Shape; profile: string; outcome: string; tone: "fail" | "pass" | "warn"; icon: typeof Ban; story: string }[] = [
  { name: "superops-api-01", type: "c7g.xlarge", env: "prod", shape: "spiky", profile: "spiky", outcome: "Refused on the real peak", tone: "fail", icon: Ban,
    story: "Low average CPU invites a downsize. The 1-minute CloudWatch peak breaks the 80% limit on the smaller type, so screening refuses it." },
  { name: "superops-worker-01", type: "c7g.xlarge", env: "staging", shape: "steady", profile: "steady", outcome: "Canary, then a real resize", tone: "pass", icon: CheckCircle2,
    story: "A disposable c7g.large canary runs the same workload and stays inside the limits; after a human approves, the agent resizes the real instance." },
  { name: "superops-batch-01", type: "c7g.large", env: "prod", shape: "flat", profile: "quiet", outcome: "Refused by policy", tone: "warn", icon: Lock,
    story: "Under a change freeze. Even a sensible saving is refused by policy, and the reason is kept in memory for the next run." },
];

const PROMISE: { icon: typeof Ban; label: string }[] = [
  { icon: ClipboardList, label: "The plan" },
  { icon: Hourglass, label: "Expected downtime, measured from the last real stop/start" },
  { icon: Bot, label: "The automated steps" },
  { icon: Terminal, label: "The exact AWS CLI commands" },
  { icon: RotateCcw, label: "The rollback" },
];

export function LiveAwsSection() {
  return (
    <section id="aws" className="relative scroll-mt-20 overflow-hidden bg-ink py-20 text-white lg:py-28">
      <div className="absolute inset-0 opacity-[0.12]" style={{ backgroundImage: "linear-gradient(to right, rgb(255 255 255 / .35) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / .35) 1px, transparent 1px)", backgroundSize: "32px 32px" }} aria-hidden />
      <div className="absolute -right-40 -top-40 size-[520px] rounded-full bg-accent/30 blur-3xl" aria-hidden />
      <div className="relative mx-auto max-w-[1240px] px-4 sm:px-6">
        <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:items-end">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white ring-1 ring-white/20"><Cloud className="size-3.5" /> Live on AWS</span>
            <h2 className="display mt-4 text-[36px] text-white sm:text-[48px]">Not a mock. <em className="!text-[#a9b3ff]">Real</em> instances, real peaks.</h2>
          </div>
          <ul className="grid gap-x-6 gap-y-2.5 text-[14px] text-white/80 sm:grid-cols-2">
            {[
              [Server, "Three Graviton EC2 instances in ap-south-1"],
              [ShieldCheck, "A dedicated, self-expiring VPC"],
              [Activity, "CloudWatch metrics at 1-minute resolution"],
              [Tag, "Rates from the AWS Price List"],
              [Network, "All of it federated through Zetaris"],
            ].map(([I, t]) => {
              const Icon = I as typeof Server;
              return <li key={t as string} className="flex items-center gap-2.5"><Icon className="size-4 shrink-0 text-[#a9b3ff]" />{t as string}</li>;
            })}
          </ul>
        </div>

        <div className="mt-12 grid gap-4 lg:grid-cols-3">
          {INSTANCES.map((x) => (
            <article key={x.name} className="flex flex-col rounded-2xl bg-white/[0.06] p-5 ring-1 ring-white/12 backdrop-blur">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="mono text-[14px] font-semibold text-white">{x.name}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                    <span className="mono rounded bg-white/10 px-1.5 py-0.5">{x.type}</span>
                    <span className={cx("rounded px-1.5 py-0.5 font-semibold uppercase", x.env === "prod" ? "bg-[#ff9900]/20 text-[#ffc266]" : "bg-white/10 text-white/80")}>{x.env}</span>
                    <span className="rounded bg-white/10 px-1.5 py-0.5 text-white/70">{x.profile}</span>
                  </div>
                </div>
                <Server className="size-5 text-white/40" />
              </div>
              <div className="mt-4"><Spark shape={x.shape} /></div>
              <div className="mt-1 text-[10.5px] text-white/40">Illustrative shape · dashed line = 80% CPU limit</div>
              <div className={cx("mt-4 inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-bold", x.tone === "fail" ? "bg-fail/25 text-[#ffb3b6]" : x.tone === "pass" ? "bg-pass/25 text-[#8ee6c0]" : "bg-[#ff9900]/20 text-[#ffc266]")}>
                <x.icon className="size-3.5" /> {x.outcome}
              </div>
              <p className="mt-3 text-[13.5px] leading-relaxed text-white/75">{x.story}</p>
            </article>
          ))}
        </div>

        <div className="mt-12 rounded-[24px] bg-white p-6 text-ink sm:p-8">
          <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr] lg:items-center">
            <p className="font-display text-[20px] font-semibold leading-snug tracking-tight sm:text-[23px]">
              Before any change you see the plan, the expected downtime (measured from the last real stop/start), the automated steps, the exact AWS CLI commands to do it yourself, and the rollback.{" "}
              <span className="text-accent">Approve, and the agent does the rest:</span> stop, resize, start, read back, verify in CloudWatch, restore if anything is off.
            </p>
            <ol className="grid gap-2 sm:grid-cols-2">
              {PROMISE.map((p, i) => (
                <li key={p.label} className={cx("flex items-center gap-3 rounded-xl bg-wash px-3.5 py-3 text-[13.5px] font-medium text-ink-2", i === PROMISE.length - 1 && "sm:col-span-2")}>
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-50 text-accent"><p.icon className="size-4" /></span>
                  {p.label}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
