import { useState } from "react";
import { Bot, CheckSquare, ClipboardList, Hand, Hourglass, RotateCcw, Terminal, TriangleAlert, Zap } from "lucide-react";
import type { Json } from "../lib/api";
import { CopyButton, Tabs, cx } from "./ui";

export interface Runbook {
  title: string;
  downtime?: { expected: boolean; estimate_seconds: number | null; basis?: string };
  preconditions?: string[];
  automated?: { who?: string; steps?: string[] };
  manual?: { note?: string; steps?: { title: string; command: string }[] };
  rollback?: { steps?: { title: string; command: string }[] };
}

export function downtimeText(dt: Runbook["downtime"] | undefined): string {
  if (!dt) return "Downtime unknown";
  if (!dt.expected) return "No downtime";
  return dt.estimate_seconds == null ? "Downtime expected · duration unknown" : `Downtime expected · ~${dt.estimate_seconds} s`;
}

/** Measured vs estimated is read from the server's own basis text; never inferred from the number. */
export function downtimeIsMeasured(dt: Runbook["downtime"] | undefined): boolean {
  return !!dt?.basis && /^measured/i.test(dt.basis);
}

export function DowntimeChip({ dt, large }: { dt: Runbook["downtime"] | undefined; large?: boolean }) {
  const expected = !!dt?.expected;
  return (
    <span
      title={dt?.basis}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ring-inset",
        large ? "px-3 py-1 text-[12.5px]" : "px-2 py-0.5 text-[11px]",
        expected ? "bg-warn-bg text-warn ring-warn/30" : "bg-pass-bg text-pass ring-pass/25",
      )}
    >
      {expected ? <Hourglass className="size-3.5" /> : <Zap className="size-3.5" />}
      {downtimeText(dt)}
      {expected && dt?.basis && <span className="font-normal opacity-80">· {downtimeIsMeasured(dt) ? "measured" : "estimate"}</span>}
    </span>
  );
}

function CommandBlock({ title, command, n }: { title: string; command: string; n?: number }) {
  return (
    <li className="rounded-xl border border-line bg-white">
      <div className="flex items-center gap-2 px-3 pt-2.5 text-[12.5px] font-semibold text-ink">
        {n !== undefined && <span className="grid size-5 place-items-center rounded-full bg-lav text-[10.5px] font-bold text-accent">{n}</span>}
        {title}
      </div>
      <div className="group relative m-2 mt-1.5 rounded-lg bg-ink">
        <pre className="mono whitespace-pre-wrap break-all px-3 py-2.5 pr-10 text-[11.5px] leading-relaxed text-[#dfe3ff]">
          <span className="select-none text-white/35">$ </span>{command}
        </pre>
        <CopyButton value={command} className="absolute right-1.5 top-1.5 !text-white/60 hover:!bg-white/10 hover:!text-white" />
      </div>
    </li>
  );
}

export function RunbookPanel({ book, target, executor }: { book: Runbook | null | undefined; target?: string; executor?: string }) {
  const [tab, setTab] = useState<"auto" | "manual">("auto");
  if (!book) return null;
  const dt = book.downtime;
  const auto = book.automated?.steps ?? [];
  const manual = book.manual?.steps ?? [];
  const rollback = book.rollback?.steps ?? [];
  const pre = book.preconditions ?? [];
  return (
    <section className="overflow-hidden rounded-[22px] bg-white shadow-[var(--shadow-float)] ring-1 ring-line">
      <div className="relative overflow-hidden bg-gradient-to-br from-accent to-[#4f5fff] px-5 py-5 text-white sm:px-6">
        <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "linear-gradient(to right, rgb(255 255 255 / .25) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / .25) 1px, transparent 1px)", backgroundSize: "26px 26px" }} aria-hidden />
        <div className="relative flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11.5px] font-semibold uppercase tracking-[0.16em] text-white/70"><ClipboardList className="size-4" /> Change runbook</div>
            <h2 className="mt-1.5 font-display text-[22px] font-bold leading-tight tracking-tight [overflow-wrap:anywhere] sm:text-[26px]">{book.title}</h2>
            {target && <div className="mono mt-1 text-[12px] text-white/70">{target}{executor ? ` · executor ${executor}` : ""}</div>}
          </div>
          <span className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-bold", dt?.expected ? "bg-[#fff3dc] text-warn" : "bg-white text-pass")}>
            {dt?.expected ? <Hourglass className="size-4" /> : <Zap className="size-4" />} {downtimeText(dt)}
          </span>
        </div>
        {dt?.basis && (
          <div className="relative mt-3 inline-flex max-w-full items-center gap-2 rounded-lg bg-white/12 px-2.5 py-1 text-[12px] text-white/90 ring-1 ring-white/20">
            <span className={cx("rounded px-1.5 py-0.5 text-[10.5px] font-bold uppercase", downtimeIsMeasured(dt) ? "bg-pass text-white" : "bg-white/20")}>{downtimeIsMeasured(dt) ? "measured" : "basis"}</span>
            <span className="min-w-0 [overflow-wrap:anywhere]">{dt.basis}</span>
          </div>
        )}
      </div>

      <div className="grid gap-0 lg:grid-cols-[1.35fr_1fr]">
        <div className="min-w-0 p-5 sm:p-6">
          <Tabs<"auto" | "manual">
            stretch
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "auto", label: <span className="flex items-center gap-1.5"><Bot className="hidden size-4 sm:block" /> Let SuperOps do it</span>, count: auto.length },
              { id: "manual", label: <span className="flex items-center gap-1.5"><Hand className="hidden size-4 sm:block" /> Do it yourself</span>, count: manual.length },
            ]}
          />
          {tab === "auto" ? (
            <div className="mt-4">
              {book.automated?.who && <p className="mb-3 rounded-xl bg-accent-50 px-3 py-2 text-[12.5px] text-accent-700"><b>Who:</b> {book.automated.who}</p>}
              {auto.length ? (
                <ol className="relative space-y-2.5">
                  {auto.map((s, i) => (
                    <li key={i} className="relative flex gap-3">
                      {i < auto.length - 1 && <span className="absolute left-[13px] top-7 h-[calc(100%-0.75rem)] w-px bg-line" />}
                      <span className="relative grid size-7 shrink-0 place-items-center rounded-full bg-accent text-[12px] font-bold text-white">{i + 1}</span>
                      <span className="pt-1 text-[13.5px] leading-snug text-ink-2">{s}</span>
                    </li>
                  ))}
                </ol>
              ) : <p className="text-[13px] text-faint">No automated path for this action type.</p>}
            </div>
          ) : (
            <div className="mt-4">
              {book.manual?.note && (
                <div className="mb-3 flex gap-2 rounded-xl border border-warn/30 bg-warn-bg/70 px-3 py-2.5 text-[12.5px] text-ink-2">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" /> <span>{book.manual.note}</span>
                </div>
              )}
              {manual.length ? (
                <ol className="space-y-2">{manual.map((s, i) => <CommandBlock key={i} n={i + 1} title={s.title} command={s.command} />)}</ol>
              ) : <p className="text-[13px] text-faint">No manual commands for this action type{executor === "local_analogue" ? " — the local analogue is changed by the executor only" : ""}.</p>}
            </div>
          )}
        </div>

        <div className="min-w-0 space-y-5 border-t border-line bg-wash/50 p-5 sm:p-6 lg:border-l lg:border-t-0">
          {pre.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wider text-faint"><CheckSquare className="size-3.5" /> Preconditions</div>
              <ul className="space-y-1.5">
                {pre.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] text-ink-2">
                    <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded border border-line-2 bg-white" aria-hidden />
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-faint">Re-checked by the executor immediately before the first write; listed here so a human can check them too.</p>
            </div>
          )}
          <div>
            <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wider text-faint"><RotateCcw className="size-3.5" /> Rollback</div>
            {rollback.length ? <ol className="space-y-2">{rollback.map((s, i) => <CommandBlock key={i} title={s.title} command={s.command} />)}</ol> : <p className="text-[13px] text-faint">No rollback steps recorded.</p>}
            <p className="mt-2 text-[11px] text-faint">Automatic recovery restores the exact previous state only if nothing else changed the target in between.</p>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-faint"><Terminal className="size-3.5" /> Generated deterministically from the plan's immutable core — no model wrote this runbook.</div>
        </div>
      </div>
    </section>
  );
}

export function asRunbook(x: Json): Runbook | null {
  return x && typeof x === "object" && x.title ? (x as Runbook) : null;
}
