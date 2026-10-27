import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Network, Brain, Cpu, Sparkles, ArrowRight, Award, Database, Clock3, ExternalLink, Bot } from "lucide-react";
import { api, ApiError, type InvestigationData, type InvestigationEvent, type Json, type Overview, type Page, type Resource } from "../lib/api";
import { ago, num, shortTs } from "../lib/format";
import { Card, ErrorBox, Hash, IdLink, KV, PageHeader, PageSkeleton, StatusChip, cx, Notice } from "../components/ui";

interface Proof {
  ov: Overview;
  inv: Resource<InvestigationData> | null;
  receipt: Resource<Json> | null;
  events: InvestigationEvent[];
}

/** Newest connected investigation whose evidence went through Zetaris, plus its receipt and model events. */
async function loadProof(): Promise<Proof> {
  const ov = await api.get<Overview>("/v1/overview");
  const page = await api.get<Page<Json>>("/v1/investigations?limit=50");
  let inv: Resource<InvestigationData> | null = null;
  for (const i of page.items.filter((x) => x.runtime_mode === "connected_demo" && x.status !== "FAILED").slice(0, 6)) {
    const r = await api.get<Resource<InvestigationData>>(`/v1/investigations/${i.id}`).catch(() => null);
    if (r?.data.federation) { inv = r; break; }
  }
  const fedId = inv?.data.federation?.evidence_id;
  const receipt = fedId ? await api.get<Resource<Json>>(`/v1/evidence/${fedId}`).catch(() => null) : null;
  const events = inv ? (await api.get<{ items: InvestigationEvent[] }>(`/v1/investigations/${inv.id}/events?limit=500`).catch(() => ({ items: [] }))).items : [];
  return { ov, inv, receipt, events };
}

function SponsorCard({ icon: Icon, name, role, status, statusLabel, children, footer }: { icon: typeof Network; name: string; role: string; status: string; statusLabel: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-line bg-wash/50 px-5 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-accent text-white shadow-[0_10px_24px_-12px_rgb(36_56_245/0.9)]"><Icon className="size-5" /></span>
          <div>
            <div className="font-display text-[18px] font-bold tracking-tight text-ink">{name}</div>
            <div className="text-[13.5px] text-muted">{role}</div>
          </div>
        </div>
        <StatusChip status={status} label={statusLabel} size="md" />
      </div>
      <div className="flex-1 px-5 py-4 sm:px-6">{children}</div>
      {footer && <div className="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3 sm:px-6">{footer}</div>}
    </Card>
  );
}

function Big({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="rounded-xl bg-wash p-3">
      <div className="font-display text-[24px] font-extrabold leading-none tracking-tight text-ink">{value}</div>
      <div className="mt-1 text-[12.5px] text-muted">{label}</div>
    </div>
  );
}

export default function SponsorProof() {
  const [state, setState] = useState<{ p?: Proof; err?: ApiError }>({});
  useEffect(() => {
    loadProof().then((p) => setState({ p })).catch((e) => setState({ err: e instanceof ApiError ? e : new ApiError(0, { code: "CLIENT_ERROR", message: String(e) }) }));
  }, []);
  if (state.err) return <ErrorBox error={state.err} title="Could not load sponsor proof" />;
  if (!state.p) return <PageSkeleton />;
  const { ov, inv, receipt, events } = state.p;
  const fed = ov.federation;
  const mem = ov.memory;
  const rc = receipt?.data?.receipt ?? {};
  const fedLive = fed.mode === "zetaris" && fed.receipts > 0;
  const modelEvents = events.filter((e) => e.kind.startsWith("model."));
  const calls: Json[] = inv?.data.progress?.model_calls ?? [];
  const nvidiaLive = modelEvents.some((e) => String(e.payload?.model_id ?? "").startsWith("nvidia/"));
  const im = inv?.data.memory;
  const firstMem = im?.applicable?.[0];

  return (
    <div className="rise">
      <PageHeader
        eyebrow={<><Award className="size-4" /> Sponsor proof</>}
        title={<>Real integrations, <em>receipts attached</em></>}
        sub="What each sponsor technology did in this deployment, read live from the API. Every figure links to the record it came from."
        chips={inv ? <span className="text-[13.5px] text-muted">Reference run <Link className="mono text-accent hover:underline" to={`/app/investigations/${inv.id}`}>{inv.id.slice(0, 8)}</Link> · {inv.runtime_mode} · {ago(inv.data.investigation?.created_at)}</span> : undefined}
      />
      {!inv && <div className="mb-5"><Notice tone="unknown" title="No connected run found">Proof below falls back to the server overview only. Start a connected_demo investigation to attach run-level receipts.</Notice></div>}

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Zetaris */}
        <SponsorCard icon={Network} name="Zetaris" role="Federated SQL across two physical sources" status={fedLive ? "PASS" : "UNKNOWN"} statusLabel={fedLive ? "live federation" : fed.mode}
          footer={receipt ? <Link to={`/app/evidence/${receipt.id}`} className="inline-flex items-center gap-1 text-[14px] font-semibold text-accent hover:underline">Open the receipt and joined rows <ArrowRight className="size-3.5" /></Link> : undefined}>
          <div className="grid grid-cols-3 gap-2">
            <Big value={fed.sources.length} label="registered sources" />
            <Big value={fed.receipts} label="query receipts" />
            <Big value={fed.last_receipt_at ? ago(fed.last_receipt_at) : "—"} label="last receipt" />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {fed.sources.map((s) => <span key={s.name} className="inline-flex items-center gap-1.5 rounded-lg bg-white px-2 py-1 text-[12px] ring-1 ring-line"><Database className="size-3.5 text-accent" /><span className="mono">{s.name}</span><span className="text-faint">{s.group}</span></span>)}
          </div>
          {receipt ? (
            <div className="mt-4 rounded-xl border border-line p-3">
              <div className="mb-1 flex items-center justify-between text-[12px]">
                <span className="font-semibold text-ink">Newest cross-source receipt · <span className="mono">{rc.template_id} v{rc.template_version}</span></span>
                <StatusChip status={rc.completeness} size="xs" />
              </div>
              <KV rows={[
                ["Sources joined", <span className="flex flex-wrap gap-1">{(rc.sources ?? []).map((s: string) => <span key={s} className="mono rounded bg-lav px-1 text-[12.5px]">{s}</span>)}</span>],
                ["Request IDs", (rc.request_ids ?? []).length ? <span className="mono break-all text-[12px]">{rc.request_ids.join(", ")}</span> : <span className="text-faint">none</span>],
                ["Pages / rows", `${rc.page_count ?? "—"} / ${rc.row_count ?? "—"}`],
                ["Query close", rc.query_close ?? rc.close_status ?? "—"],
                ["Duration", rc.duration_ms !== undefined ? `${num(rc.duration_ms, 0)} ms` : "—"],
                ["Result hash", <Hash value={rc.result_hash} />],
              ]} />
            </div>
          ) : <div className="mt-4 text-[13.5px] text-faint">No federation receipt found on a connected run.</div>}
        </SponsorCard>

        {/* Meterless */}
        <SponsorCard icon={Brain} name="Meterless H-MEM" role="Scoped, versioned memory of experiment outcomes" status={mem.status === "ready" ? (mem.semantic ? "PASS" : "partial") : "UNKNOWN"} statusLabel={mem.status === "ready" ? (mem.semantic ? "semantic recall" : "hash conformance") : mem.status}
          footer={<>{firstMem && <Link to={`/app/memories/${firstMem.memory_id}`} className="inline-flex items-center gap-1 text-[14px] font-semibold text-accent hover:underline">Open a recalled record <ArrowRight className="size-3.5" /></Link>}{inv && <Link to={`/app/investigations/${inv.id}#memory`} className="ml-auto text-[13.5px] font-semibold text-muted hover:text-accent">Recall in the reference run</Link>}</>}>
          <div className="grid grid-cols-3 gap-2">
            <Big value={mem.records ?? "—"} label="records stored" />
            <Big value={mem.recalls} label="recalls" />
            <Big value={mem.applicable_hits} label="applicable hits" />
          </div>
          <div className="mt-3">
            <KV rows={[
              ["Engine", <span>{mem.engine ?? "Meterless H-MEM"}{mem.engine_sha && <span className="mono ml-1 rounded bg-lav px-1 text-[12.5px]">@{mem.engine_sha}</span>}</span>],
              ["Embedding model", <span className="mono text-[12px]">{mem.embedding_model ?? "unknown"}</span>],
              ["Semantic", mem.semantic === true ? "yes — real embeddings, not the reference hash" : mem.semantic === false ? "no — hash conformance path" : "unknown"],
              ["Pending writes", mem.pending ?? "—"],
              ...(im ? [["In the reference run", `${(im.applicable ?? []).length} applicable · ${(im.historical ?? []).length} historical (retest required)`] as [string, ReactNode]] : []),
            ]} />
          </div>
        </SponsorCard>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        {/* NVIDIA */}
        <SponsorCard icon={Cpu} name="NVIDIA Nemotron" role="Agent reasoning (via Google ADK) and memory embeddings" status={nvidiaLive ? "PASS" : ov.model.agent_model_id ? "configured" : "UNKNOWN"} statusLabel={nvidiaLive ? "live model calls" : ov.model.agent_model_id ? "configured" : "unknown"}
          footer={inv ? <Link to={`/app/investigations/${inv.id}#timeline`} className="inline-flex items-center gap-1 text-[14px] font-semibold text-accent hover:underline">See every agent turn in the timeline <ArrowRight className="size-3.5" /></Link> : undefined}>
          <KV rows={[
            ["Agent model", <span className="mono break-all text-[12px]">{ov.model.agent_model_id ?? "not reported"}</span>],
            ["Embedding model", <span className="mono text-[12px]">{mem.embedding_model ?? "—"}</span>],
          ]} />
          {calls.length > 0 && (
            <table className="mt-3 w-full text-[13.5px]">
              <thead><tr className="text-left text-[12px] uppercase tracking-wider text-faint"><th className="py-1">Role</th><th>Requests</th><th className="text-right">Tokens in / out</th></tr></thead>
              <tbody className="divide-y divide-line">
                {calls.map((c) => (
                  <tr key={c.role}><td className="py-1.5 font-semibold capitalize text-ink">{c.role}</td><td>{c.requests}</td><td className="text-right text-muted">{c.input_tokens ?? "unknown"} / {c.output_tokens ?? "unknown"}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          {modelEvents.length > 0 && (
            <ul className="mt-3 space-y-1">
              {modelEvents.slice(0, 5).map((e) => (
                <li key={e.seq} className="flex items-center justify-between gap-2 text-[12.5px]">
                  <span className="text-ink-2">{e.kind.replace("model.", "")}</span>
                  <span className="mono truncate text-faint">{e.payload?.model_id} · {e.payload?.duration_ms !== undefined ? `${num(e.payload.duration_ms, 0)} ms` : "—"}</span>
                </li>
              ))}
            </ul>
          )}
        </SponsorCard>

        {/* Claude */}
        <SponsorCard icon={Sparkles} name="Claude Haiku 4.5" role="Ops Copilot: advisory chat over committed records" status={ov.model.copilot_model_id ? "configured" : "UNKNOWN"} statusLabel={ov.model.copilot_model_id ? "configured" : "not reported"}
          footer={<Link to="/app/copilot" className="inline-flex items-center gap-1 text-[14px] font-semibold text-accent hover:underline">Ask the copilot <ArrowRight className="size-3.5" /></Link>}>
          <KV rows={[
            ["Model", <span className="mono text-[12px]">{ov.model.copilot_model_id ?? "—"}</span>],
            ["Tools", "system status, investigations, events, records, memory recall, read-only evidence templates"],
            ["Authority", "none — it cannot approve, execute or change anything"],
          ]} />
          <p className="mt-3 text-[12px] text-muted">Each reply lists the tools it called and cites the records it used, so an answer can be checked against the same evidence the agents saw.</p>
        </SponsorCard>
      </div>

      <div className="mt-5 flex items-start gap-3 rounded-2xl bg-ink px-5 py-4 text-white">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-white/10"><Bot className="size-4" /></span>
        <div className="text-[14px]">
          <b>Automation.</b> <span className="text-white/80">Autopilot re-investigates when Zetaris evidence drifts (receipt hashes over inventory, telemetry, billing, prices and policy change); it can never approve or execute — the API refuses its trials, approvals, revokes, cancels and executions.</span>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl bg-white px-5 py-4 text-[13.5px] text-muted ring-1 ring-line">
        <Clock3 className="size-4 text-accent" /> Read {shortTs(ov.generated_at)} from <span className="mono">/v1/overview</span>{inv && <>, <span className="mono">/v1/investigations/{inv.id.slice(0, 8)}</span></>}{receipt && <> and <IdLink kind="evidence" id={receipt.id} label="the evidence receipt" /></>}.
        {firstMem && <span className="inline-flex items-center gap-1">Example memory: <IdLink kind="memory" id={firstMem.memory_id} label="record" /></span>}
        <a href="/docs" target="_blank" rel="noreferrer" className={cx("ml-auto inline-flex items-center gap-1 font-semibold text-accent hover:underline")}>API docs <ExternalLink className="size-3.5" /></a>
      </div>
    </div>
  );
}
