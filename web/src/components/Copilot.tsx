import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowUp, Brain, Database, FileSearch, Network, RotateCcw, Sparkles, Wrench, CircleAlert, BookOpen, ShieldCheck,
  FlaskConical, Zap, Activity, Clock3, type LucideIcon,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { api, ApiError, uuid, type CopilotCitation, type CopilotMessage, type CopilotReply, type CopilotToolCall } from "../lib/api";
import { cx, recordHref, ErrorBox } from "./ui";
import { ago } from "../lib/format";

export const DEFAULT_PROMPTS = [
  "Why was worker-prod-01 → e2-standard-2 rejected?",
  "What did we learn from previous runs?",
  "Which change is safest to approve now and what blocks it?",
  "Summarise today's investigation for my manager",
];

// ---- page → copilot context (which investigation the user is looking at) ----
const CopilotCtx = createContext<{ investigationId: string | null; setInvestigationId: (id: string | null) => void }>({ investigationId: null, setInvestigationId: () => undefined });

export function CopilotContextProvider({ children }: { children: ReactNode }) {
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  return <CopilotCtx.Provider value={{ investigationId, setInvestigationId }}>{children}</CopilotCtx.Provider>;
}

/** Pages call this to tell the copilot which investigation is in view. */
export function useCopilotInvestigation(id: string | null | undefined) {
  const { setInvestigationId } = useContext(CopilotCtx);
  useEffect(() => {
    setInvestigationId(id ?? null);
    return () => setInvestigationId(null);
  }, [id, setInvestigationId]);
}

export function useCopilotContextId() {
  return useContext(CopilotCtx).investigationId;
}

// ---- tool + citation chips ----
function toolMeta(t: CopilotToolCall, mode: string | undefined): { icon: LucideIcon; label: string } {
  const inp = t.input ?? {};
  const id8 = (v: unknown) => (typeof v === "string" ? v.slice(0, 8) : "");
  const clip = (v: unknown, n = 36) => {
    const s = typeof v === "string" ? v : v === undefined ? "" : JSON.stringify(v);
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  };
  switch (t.tool) {
    case "system_status": return { icon: Activity, label: "checked system status" };
    case "list_investigations": return { icon: FileSearch, label: `listed investigations${inp.status ? ` · ${inp.status}` : ""}` };
    case "get_investigation": return { icon: FileSearch, label: `read investigation ${id8(inp.investigation_id)}` };
    case "get_investigation_events": return { icon: Clock3, label: `read timeline ${id8(inp.investigation_id)}` };
    case "get_record": {
      const icon = inp.kind === "trial" ? FlaskConical : inp.kind === "plan" ? ShieldCheck : inp.kind === "evidence" ? Database : inp.kind === "memory" ? Brain : inp.kind === "report" ? BookOpen : FileSearch;
      return { icon, label: `read ${inp.kind ?? "record"} ${id8(inp.id)}` };
    }
    case "recall_memory": return { icon: Brain, label: `recalled Meterless memory${inp.query ? `: “${clip(inp.query, 30)}”` : ""}` };
    case "query_evidence":
      // Only connected_demo goes through Zetaris; sample mode reads a local fixture database.
      return { icon: Network, label: `${mode === "connected_demo" ? "queried Zetaris" : "queried evidence"}${inp.template_id ? `: ${inp.template_id}` : ""}` };
  }
  return { icon: Wrench, label: t.tool.replace(/_/g, " ") };
}

export function ToolChips({ calls }: { calls: CopilotToolCall[] }) {
  const { me } = useAuth();
  if (!calls.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {calls.map((c, i) => {
        const m = toolMeta(c, me?.runtime_mode);
        const Icon = m.icon;
        return (
          <span
            key={i}
            title={`${c.tool}${c.input ? ` ${JSON.stringify(c.input)}` : ""}${c.duration_ms !== undefined ? ` · ${c.duration_ms} ms` : ""}`}
            className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1", c.ok === false ? "bg-fail-bg text-fail ring-fail/20" : "bg-lav text-ink-2 ring-line")}
          >
            <Icon className="size-3" aria-hidden />
            {m.label}
            {c.ok === false && <CircleAlert className="size-3" aria-label="tool call failed" />}
            {c.duration_ms !== undefined && <span className="text-faint tnum">{c.duration_ms < 1000 ? `${c.duration_ms}ms` : `${(c.duration_ms / 1000).toFixed(1)}s`}</span>}
          </span>
        );
      })}
    </div>
  );
}

export function CitationChips({ cites, onNavigate }: { cites: CopilotCitation[]; onNavigate?: () => void }) {
  const [all, setAll] = useState(false);
  if (!cites.length) return null;
  const shown = all ? cites : cites.slice(0, 6);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">Sources</span>
      {shown.map((c, i) => (
        <Link
          key={`${c.kind}-${c.id}-${i}`}
          to={recordHref(c.kind, c.id)}
          onClick={onNavigate}
          className="inline-flex max-w-[240px] items-center gap-1 rounded-md bg-white px-2 py-0.5 text-[11px] font-medium text-accent-700 ring-1 ring-accent-100 hover:bg-accent-50"
          title={`${c.kind} ${c.id}`}
        >
          <span className="text-faint">{c.kind}</span>
          <span className="truncate">{(c.label || c.id.slice(0, 8)).replace(new RegExp(`^${c.kind}\\s*`, "i"), "") || c.id.slice(0, 8)}</span>
        </Link>
      ))}
      {cites.length > 6 && (
        <button onClick={() => setAll((x) => !x)} className="rounded-md px-1.5 py-0.5 text-[11px] font-semibold text-muted hover:text-accent">
          {all ? "show fewer" : `+${cites.length - 6} more`}
        </button>
      )}
    </div>
  );
}

function Markdown({ text, onNavigate }: { text: string; onNavigate?: () => void }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) =>
            href && href.startsWith("/") ? (
              <Link to={href} onClick={onNavigate}>{children}</Link>
            ) : (
              <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>
            ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

const THINKING_STEPS: { icon: LucideIcon; text: string }[] = [
  { icon: FileSearch, text: "Reading committed investigation records" },
  { icon: Network, text: "Checking evidence receipts" },
  { icon: Brain, text: "Looking at memory recall" },
  { icon: Sparkles, text: "Writing the answer" },
];

function Thinking() {
  const [i, setI] = useState(0);
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % THINKING_STEPS.length), 2200);
    const s = setInterval(() => setSecs((x) => x + 1), 1000);
    return () => { clearInterval(t); clearInterval(s); };
  }, []);
  return (
    <div className="rise flex gap-3">
      <Avatar />
      <div className="rounded-2xl rounded-tl-md bg-white px-4 py-3 ring-1 ring-line">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <span className="flex gap-1">
            {[0, 1, 2].map((d) => <span key={d} className="pulse-dot size-1.5 rounded-full bg-accent" style={{ animationDelay: `${d * 0.2}s` }} />)}
          </span>
          Thinking <span className="font-normal text-faint tnum">{secs}s</span>
        </div>
        <ul className="mt-2 space-y-1">
          {THINKING_STEPS.map((s, k) => {
            const Icon = s.icon;
            return (
              <li key={k} className={cx("flex items-center gap-2 text-[12px] transition", k === i ? "text-accent" : "text-faint")}>
                <Icon className="size-3.5" aria-hidden /> {s.text}
              </li>
            );
          })}
        </ul>
        <div className="mt-2 text-[11px] text-faint">Typical steps shown; the tools actually used appear with the answer. Replies can take up to 40 s.</div>
      </div>
    </div>
  );
}

function Avatar() {
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent to-[#6b78ff] text-white shadow-sm">
      <Sparkles className="size-4" aria-hidden />
    </span>
  );
}

interface ChatMsg extends CopilotMessage {
  pending?: boolean;
  failed?: ApiError;
  idemKey?: string;
}

const convKey = (scope: string) => `greenops.copilot.${scope}`;

export function CopilotChat({ investigationId, compact, onNavigate }: { investigationId?: string | null; compact?: boolean; onNavigate?: () => void }) {
  const scope = investigationId ?? "global";
  const [conversationId, setConversationId] = useState<string | null>(() => {
    try { return sessionStorage.getItem(convKey(scope)); } catch { return null; }
  });
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [suggested, setSuggested] = useState<string[]>(DEFAULT_PROMPTS);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [unavailable, setUnavailable] = useState<ApiError | null>(null);
  const [modelId, setModelId] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  // Restore the conversation for this scope.
  useEffect(() => {
    let cid: string | null = null;
    try { cid = sessionStorage.getItem(convKey(scope)); } catch { cid = null; }
    setConversationId(cid);
    setMessages([]);
    if (!cid) return;
    api.get<{ conversation_id: string; messages: CopilotMessage[] }>(`/v1/copilot/conversations/${cid}`)
      .then((r) => {
        setMessages(r.messages ?? []);
        const last = [...(r.messages ?? [])].reverse().find((m) => m.model_id);
        if (last?.model_id) setModelId(last.model_id);
      })
      .catch(() => { try { sessionStorage.removeItem(convKey(scope)); } catch { /* ignore */ } setConversationId(null); });
  }, [scope]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string, retryKey?: string) {
    const msg = text.trim();
    if (!msg || busy) return;
    const key = retryKey ?? uuid();
    const userMsg: ChatMsg = { message_id: `local-${key}`, role: "user", content: msg, at: new Date().toISOString(), idemKey: key };
    setMessages((m) => [...m.filter((x) => x.idemKey !== key), userMsg]);
    setInput("");
    setBusy(true);
    try {
      const body: Record<string, string> = { message: msg };
      if (conversationId) body.conversation_id = conversationId;
      if (investigationId) body.investigation_id = investigationId;
      const r = await api.post<CopilotReply>("/v1/copilot/messages", body, key);
      setConversationId(r.conversation_id);
      try { sessionStorage.setItem(convKey(scope), r.conversation_id); } catch { /* ignore */ }
      if (r.model_id) setModelId(r.model_id);
      if (r.suggested_prompts?.length) setSuggested(r.suggested_prompts);
      setMessages((m) => [
        ...m,
        { message_id: r.message_id, role: "assistant", content: r.reply, at: new Date().toISOString(), tool_calls: r.tool_calls ?? [], citations: r.citations ?? [], model_id: r.model_id },
      ]);
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, { code: "CLIENT_ERROR", message: String(e) });
      if (err.status === 404 || err.status === 405) setUnavailable(err);
      setMessages((m) => m.map((x) => (x.idemKey === key ? { ...x, failed: err } : x)));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    try { sessionStorage.removeItem(convKey(scope)); } catch { /* ignore */ }
    setConversationId(null);
    setMessages([]);
    setSuggested(DEFAULT_PROMPTS);
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5 text-[12px] text-muted">
        <div className="flex min-w-0 items-center gap-2">
          <span className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full bg-accent-50 px-2 py-0.5 font-semibold text-accent"><Zap className="size-3" /> {modelId ?? "Claude Haiku 4.5"}</span>
          {investigationId ? (
            <span className="truncate">Context: investigation <Link className="mono text-accent" to={recordHref("investigation", investigationId)} onClick={onNavigate}>{investigationId.slice(0, 8)}</Link></span>
          ) : (
            <span className="truncate">Context: all your records</span>
          )}
        </div>
        {messages.length > 0 && (
          <button onClick={reset} className="inline-flex items-center gap-1 rounded-full px-2 py-1 hover:bg-lav hover:text-ink">
            <RotateCcw className="size-3" /> New chat
          </button>
        )}
      </div>

      <div ref={scroller} className={cx("min-h-0 flex-1 space-y-5 overflow-y-auto scroll-thin", compact ? "px-4 py-4" : "px-4 py-6 sm:px-8")}>
        {messages.length === 0 && !busy && (
          <div className={cx("mx-auto max-w-xl", compact ? "pt-2" : "pt-8")}>
            <div className="flex items-center gap-3">
              <Avatar />
              <div>
                <div className="font-display text-lg font-bold text-ink">Ask about the evidence, not around it.</div>
                <div className="text-[13px] text-muted">Answers come from committed records and cite them. The copilot is advisory — it cannot approve, execute or change anything.</div>
              </div>
            </div>
            {unavailable && (
              <div className="mt-4"><ErrorBox error={unavailable} title="Copilot is not available on this API yet" /></div>
            )}
            <div className="mt-5 grid gap-2">
              {suggested.map((p) => (
                <button key={p} onClick={() => send(p)} className="group flex items-center justify-between gap-3 rounded-xl bg-white px-4 py-3 text-left text-[13.5px] font-medium text-ink-2 ring-1 ring-line transition hover:ring-accent/40 hover:text-accent">
                  {p}
                  <ArrowUp className="size-4 shrink-0 rotate-45 text-faint group-hover:text-accent" />
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.message_id} className="rise flex flex-col items-end gap-1">
              <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-accent px-4 py-2.5 text-[14px] text-white shadow-sm">{m.content}</div>
              {m.failed && (
                <div className="flex max-w-[85%] flex-col items-end gap-1">
                  <div className="text-right text-[12px] text-fail">{m.failed.code}: {m.failed.message}</div>
                  {m.failed.status !== 404 && (
                    <button className="text-[12px] font-semibold text-accent hover:underline" onClick={() => send(m.content, m.idemKey)}>Retry with the same request key</button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div key={m.message_id} className="rise flex gap-3">
              <Avatar />
              <div className="min-w-0 flex-1 space-y-2">
                {m.tool_calls && m.tool_calls.length > 0 && <ToolChips calls={m.tool_calls} />}
                <div className="rounded-2xl rounded-tl-md bg-white px-4 py-3 ring-1 ring-line">
                  <Markdown text={m.content} onNavigate={onNavigate} />
                </div>
                {m.citations && m.citations.length > 0 && <CitationChips cites={m.citations} onNavigate={onNavigate} />}
                {m.at && <div className="text-[11px] text-faint">{ago(m.at)} · advisory only; check the cited records before acting</div>}
              </div>
            </div>
          ),
        )}
        {busy && <Thinking />}
        {messages.length > 0 && !busy && suggested.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pl-11">
            {suggested.slice(0, 4).map((p) => (
              <button key={p} onClick={() => send(p)} className="rounded-full bg-white px-3 py-1 text-[12px] font-medium text-ink-2 ring-1 ring-line hover:text-accent hover:ring-accent/40">
                {p}
              </button>
            ))}
          </div>
        )}
      </div>

      <form
        className="border-t border-line bg-white p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <div className="flex items-end gap-2 rounded-2xl bg-wash p-1.5 ring-1 ring-line focus-within:ring-accent/50">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, 4000))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={compact ? 1 : 2}
            placeholder={compact ? "Ask about this evidence…" : "Ask why a plan was rejected, what memory skipped, or what blocks approval…"}
            aria-label="Message the Ops Copilot"
            className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-[14px] text-ink outline-none placeholder:text-faint"
          />
          <button type="submit" disabled={!input.trim() || busy} aria-label="Send message" className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-white transition hover:bg-accent-600 disabled:opacity-40">
            <ArrowUp className="size-4" />
          </button>
        </div>
        <div className="mt-1.5 flex justify-between px-1 text-[10.5px] text-faint">
          <span>Enter to send · Shift+Enter for a new line</span>
          <span className="tnum">{input.length}/4000</span>
        </div>
      </form>
    </div>
  );
}
