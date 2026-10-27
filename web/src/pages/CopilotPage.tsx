import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Sparkles, Lock, Network, Brain, FileSearch, Search } from "lucide-react";
import type { Json, Page } from "../lib/api";
import { useGet } from "../lib/hooks";
import { CopilotChat } from "../components/Copilot";
import { Card, StatusChip, cx } from "../components/ui";
import { ago } from "../lib/format";

export default function CopilotPage() {
  const [params, setParams] = useSearchParams();
  const [inv, setInv] = useState<string | null>(params.get("investigation"));
  const list = useGet<Page<Json>>("/v1/investigations?limit=25");

  function pick(id: string | null) {
    setInv(id);
    if (id) params.set("investigation", id);
    else params.delete("investigation");
    setParams(params, { replace: true });
  }

  return (
    <div className="rise grid gap-5 xl:grid-cols-[300px_1fr] xl:items-start">
      <aside className="space-y-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.14em] text-faint"><Sparkles className="size-4" /> Ops Copilot</div>
          <h1 className="display text-[32px] text-ink">Ask <em>why</em>.</h1>
          <p className="mt-2 text-[14px] text-muted">A chat agent on Claude Haiku 4.5 that reads committed investigations, plans, trials, evidence and memory, and cites what it used.</p>
        </div>
        <Card className="p-4">
          <div className="space-y-2.5 text-[13.5px] text-ink-2">
            <div className="flex items-start gap-2"><FileSearch className="mt-0.5 size-4 shrink-0 text-accent" /> Reads records through the same API scope as you.</div>
            <div className="flex items-start gap-2"><Network className="mt-0.5 size-4 shrink-0 text-accent" /> Can run allow-listed evidence queries.</div>
            <div className="flex items-start gap-2"><Brain className="mt-0.5 size-4 shrink-0 text-accent" /> Can recall scoped memory.</div>
            <div className="flex items-start gap-2"><Lock className="mt-0.5 size-4 shrink-0 text-fail" /> Cannot approve, execute, revoke or change anything.</div>
          </div>
        </Card>
        <Card className="overflow-hidden">
          <div className="border-b border-line px-4 py-3 text-[12px] font-semibold uppercase tracking-wider text-faint">Context</div>
          <div className="max-h-[max(160px,min(420px,calc(100vh-27rem)))] overflow-y-auto scroll-thin">
            <button onClick={() => pick(null)} className={cx("flex w-full items-center gap-2 px-4 py-2.5 text-left text-[14px]", !inv ? "bg-accent-50 font-semibold text-accent" : "hover:bg-wash")}>
              <Search className="size-3.5" /> All records
            </button>
            {(list.data?.items ?? []).map((i: Json) => (
              <button key={i.id} onClick={() => pick(i.id)} className={cx("flex w-full flex-col gap-0.5 border-t border-line px-4 py-2.5 text-left", inv === i.id ? "bg-accent-50" : "hover:bg-wash")}>
                <span className="flex items-center justify-between gap-2">
                  <span className={cx("mono text-[12px]", inv === i.id ? "font-semibold text-accent" : "text-ink-2")}>{i.id.slice(0, 8)}</span>
                  <StatusChip status={i.status} size="xs" />
                </span>
                <span className="truncate text-[12.5px] text-muted">{ago(i.created_at)} · {i.question}</span>
              </button>
            ))}
          </div>
        </Card>
      </aside>
      <Card className="flex h-[calc(100vh-9rem)] min-h-[520px] flex-col overflow-hidden xl:sticky xl:top-20">
        <CopilotChat investigationId={inv} />
      </Card>
    </div>
  );
}
