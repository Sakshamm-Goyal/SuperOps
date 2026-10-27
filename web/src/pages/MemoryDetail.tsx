import { useParams } from "react-router-dom";
import { Brain, ShieldCheck, History, Fingerprint, Info } from "lucide-react";
import type { Json, Resource } from "../lib/api";
import { useGet } from "../lib/hooks";
import { humanize } from "../lib/format";
import { Card, CardHeader, ErrorBox, Hash, IdLink, KV, Notice, PageHeader, PageSkeleton, StatusChip, recordHref } from "../components/ui";
import { Link } from "react-router-dom";

function SourceRef({ v }: { v: string | undefined }) {
  if (!v) return <span className="text-faint">—</span>;
  const [kind, id] = v.split(":", 2);
  if (id && ["plan", "trial", "action", "investigation"].includes(kind)) return <Link className="mono break-all text-[12px] text-accent hover:underline" to={recordHref(kind, id)}>{v}</Link>;
  return <span className="mono text-[12px]">{v}</span>;
}

export default function MemoryDetail() {
  const { id = "" } = useParams();
  const r = useGet<Resource<Json>>(`/v1/memories/${id}`);
  if (r.loading && !r.data) return <PageSkeleton />;
  if (r.error && !r.data) return <ErrorBox error={r.error} title="Could not load the memory record" />;
  if (!r.data) return null;
  const res = r.data;
  const d = res.data;
  const env = d.envelope ?? {};
  const appl: string[] = d.current_policy_applicability ?? [];
  const audit = d.audit;
  const history: Json[] = Array.isArray(audit) ? audit : audit?.history ?? audit?.events ?? audit?.entries ?? [];
  return (
    <div className="rise">
      <PageHeader
        eyebrow={<><Brain className="size-4" /> Meterless H-MEM record</>}
        title={<>{humanize(d.kind)} · <em>{env.scope?.target_id?.split("/").slice(-1)[0] ?? "memory"}</em></>}
        sub={d.note}
        chips={<><StatusChip status={d.sync_status} size="md" label={`sync ${d.sync_status}`} />{appl.map((a) => <StatusChip key={a} status={a.startsWith("APPLICABLE") ? "PASS" : "STALE"} label={humanize(a)} size="md" />)}</>}
      />
      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader title="Finding" icon={Info} sub="Stored outcome text; it informs later investigations and never authorises an action" />
            <div className="px-5 pb-5 sm:px-6">
              <p className="rounded-xl bg-wash p-4 text-[14px] leading-relaxed text-ink-2">{env.finding}</p>
              <div className="mt-3 text-[12px] font-semibold uppercase tracking-wider text-faint">Supporting evidence</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {(env.evidence_refs ?? []).map((e: string) => e.startsWith("trial:") ? <IdLink key={e} kind="trial" id={e.slice(6)} label={e.slice(0, 14)} /> : <IdLink key={e} kind="evidence" id={e} />)}
              </div>
            </div>
          </Card>
          <Card>
            <CardHeader title="Audit history" icon={History} sub="From the memory sidecar's scoped ledger" />
            <div className="px-5 pb-5 sm:px-6">
              {d.audit_error ? (
                <Notice tone="unknown" title={`Audit unavailable: ${d.audit_error}`}>The application receipt exists, but the sidecar could not return its ledger history. The record is shown from the application outbox.</Notice>
              ) : history.length ? (
                <ol className="space-y-2">{history.map((h, i) => <li key={i} className="mono rounded-lg bg-wash px-3 py-2 text-[12.5px] text-ink-2">{JSON.stringify(h)}</li>)}</ol>
              ) : audit ? (
                <pre className="mono max-h-72 overflow-auto rounded-xl bg-wash p-3 text-[12.5px] scroll-thin">{JSON.stringify(audit, null, 2)}</pre>
              ) : (
                <div className="text-[14px] text-faint">No audit history returned.</div>
              )}
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card>
            <CardHeader title="Scope & applicability" icon={ShieldCheck} sub="Checked by the application on every recall, outside retrieval" />
            <div className="px-5 pb-5 sm:px-6">
              <KV rows={[
                ["Tenant", env.scope?.tenant_id],
                ["Service", env.scope?.service_id],
                ["Target", <span className="mono text-[12.5px]">{env.scope?.target_id}</span>],
                ...Object.entries(env.applicability ?? {}).map(([k, v]) => [humanize(k), v ? <span className="mono text-[12.5px] break-all">{String(v)}</span> : <span className="text-faint">none</span>] as [string, React.ReactNode]),
              ]} />
            </div>
          </Card>
          <Card>
            <CardHeader title="Identity" icon={Fingerprint} />
            <div className="px-5 pb-5 sm:px-6">
              <KV rows={[
                ["Receipt id", <span className="mono text-[12.5px]">{env.application_receipt_id ?? id}</span>],
                ["Engine id", <span className="mono text-[12px]">{d.engine_memory_id ?? "—"}</span>],
                ["Content hash", <Hash value={env.content_hash} />],
                ["Source", <SourceRef v={d.source_ref} />],
                ["Tags", (env.tags ?? []).join(", ") || "—"],
              ]} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
