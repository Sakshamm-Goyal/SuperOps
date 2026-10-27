import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FileText, Fingerprint, ShieldCheck, Brain, Eye, Download } from "lucide-react";
import { ApiError, getToken, type Json } from "../lib/api";
import { useGet } from "../lib/hooks";
import { humanize, shortTs, planTitle } from "../lib/format";
import { Button, Card, CardHeader, ErrorBox, Hash, IdLink, KV, PageHeader, PageSkeleton, StatusChip, KindBadge } from "../components/ui";

export default function ReportDetail() {
  const { id = "" } = useParams();
  const r = useGet<Json>(`/v1/reports/${id}?format=json`);
  const [html, setHtml] = useState<string | null>(null);
  const [htmlErr, setHtmlErr] = useState<ApiError | null>(null);
  const [htmlLoading, setHtmlLoading] = useState(false);

  async function loadHtml() {
    setHtmlLoading(true);
    setHtmlErr(null);
    try {
      // The HTML route needs the bearer token, so fetch it and render it in a fully sandboxed frame.
      const t = await fetch(`/v1/reports/${id}?format=html`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
      if (!t.ok) throw new ApiError(t.status, { code: `HTTP_${t.status}`, message: "Could not load the HTML report" });
      setHtml(await t.text());
    } catch (e) {
      setHtmlErr(e instanceof ApiError ? e : new ApiError(0, { code: "CLIENT_ERROR", message: String(e) }));
    } finally {
      setHtmlLoading(false);
    }
  }

  if (r.loading && !r.data) return <PageSkeleton />;
  if (r.error && !r.data) return <ErrorBox error={r.error} title="Could not load the report" />;
  if (!r.data) return null;
  const d = r.data;
  const inv = d.investigation ?? {};
  const download = () => {
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `greenops-report-${id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <div className="rise">
      <div className="mb-3 text-[12px] text-faint"><Link className="hover:text-accent" to={`/app/investigations/${id}`}>investigation <span className="mono">{id.slice(0, 8)}</span></Link> / report</div>
      <PageHeader
        eyebrow={<><FileText className="size-4" /> {d.report_version ?? "report"}</>}
        title={<>Investigation <em>report</em></>}
        sub={`${d.question ?? inv.question ?? ""} — built from committed state only; no agent ran to produce it.`}
        chips={<><StatusChip status={inv.status ?? d.outcome?.status} size="md" /><span className="text-[12px] text-muted">generated {shortTs(d.generated_at)}</span></>}
        right={<><Button variant="secondary" icon={Download} onClick={download}>JSON</Button><Button variant="secondary" icon={Eye} loading={htmlLoading} onClick={loadHtml}>HTML view</Button></>}
      />
      <div className="mb-5 flex min-w-0 flex-wrap items-center gap-2 rounded-2xl bg-white px-4 py-3 ring-1 ring-line">
        <Fingerprint className="size-4 text-accent" /><span className="text-[14px] font-semibold text-ink">Content hash</span><span className="min-w-0 max-w-full"><Hash value={d.content_hash} n={20} /></span>
      </div>
      {htmlErr && <div className="mb-5"><ErrorBox error={htmlErr} /></div>}
      {html && (
        <Card className="mb-5 overflow-hidden">
          <CardHeader title="HTML report" icon={Eye} sub="Rendered in a sandboxed frame (no scripts)" right={<Button size="sm" variant="ghost" onClick={() => setHtml(null)}>Close</Button>} />
          <iframe title="HTML report" sandbox="" srcDoc={html} className="h-[640px] w-full border-t border-line bg-white" />
        </Card>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Plans" icon={ShieldCheck} sub={`${(d.plans ?? []).length} plans`} />
          <ul className="divide-y divide-line px-5 pb-4 sm:px-6">
            {(d.plans ?? []).map((p: Json) => (
              <li key={p.id} className="flex items-center gap-3 py-2.5">
                <StatusChip status={p.status} size="xs" />
                <span className="min-w-0 flex-1 truncate text-[14px] text-ink">{planTitle(p)}</span>
                <IdLink kind="plan" id={p.id} />
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Trials, approvals, actions" icon={ShieldCheck} />
          <div className="px-5 pb-5 sm:px-6">
            <KV rows={[
              ["Trials", <span className="flex flex-wrap gap-1">{(d.trials ?? []).map((t: Json) => <Link key={t.id} to={`/app/trials/${t.id}`}><StatusChip status={t.status} size="xs" label={`${t.status} ${String(t.id).slice(0, 6)}`} /></Link>)}{!(d.trials ?? []).length && "none"}</span>],
              ["Approvals", (d.approvals ?? []).length || "none"],
              ["Actions", <span className="flex flex-wrap gap-1">{(d.actions ?? []).map((a: Json) => <IdLink key={a.id} kind="action" id={a.id} />)}{!(d.actions ?? []).length && "none"}</span>],
              ["Action journal entries", (d.action_journal ?? []).length],
              ["Model calls", (d.model_calls ?? []).length],
            ]} />
          </div>
        </Card>
        <Card className="lg:col-span-2 overflow-hidden">
          <CardHeader title="Evidence receipts" icon={Fingerprint} sub={`${(d.evidence_receipts ?? []).length} receipts`} />
          <div className="overflow-x-auto">
            <table className="w-full text-[13.5px]">
              <thead><tr className="border-y border-line bg-wash/60 text-left text-[12px] uppercase tracking-wider text-faint">{["Template", "Completeness", "Rows", "Pages", "Sources", "Result hash", "Mode"].map((h) => <th key={h} className="whitespace-nowrap px-4 py-2">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-line">
                {(d.evidence_receipts ?? []).map((e: Json) => (
                  <tr key={e.id}>
                    <td className="mono px-4 py-2">{e.template_id} v{e.template_version}</td>
                    <td className="px-4 py-2"><StatusChip status={e.completeness} size="xs" /></td>
                    <td className="px-4 py-2 tnum">{e.row_count}</td>
                    <td className="px-4 py-2 tnum">{e.page_count}</td>
                    <td className="mono px-4 py-2 text-[12.5px]">{(e.sources ?? []).join(", ")}</td>
                    <td className="px-4 py-2"><Hash value={e.result_hash} n={8} /></td>
                    <td className="px-4 py-2"><KindBadge kind={e.runtime_mode} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card>
          <CardHeader title="Labels & limitations" icon={ShieldCheck} />
          <div className="space-y-3 px-5 pb-5 sm:px-6 text-[14px]">
            {d.labels && <KV rows={Object.entries(d.labels).map(([k, v]) => [humanize(k), typeof v === "object" ? JSON.stringify(v) : String(v)])} />}
            {(d.limitations ?? []).length > 0 && <ul className="list-disc space-y-1 pl-5 text-muted">{d.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>}
          </div>
        </Card>
        <Card>
          <CardHeader title="Memory outbox" icon={Brain} />
          <div className="px-5 pb-5 sm:px-6">
            {(d.memory_outbox ?? []).length ? (
              <ul className="divide-y divide-line">
                {d.memory_outbox.map((m: Json, i: number) => (
                  <li key={i} className="flex items-center gap-2 py-2 text-[13.5px]">
                    <StatusChip status={m.status} size="xs" /><span className="flex-1 truncate">{humanize(m.receipt_kind ?? m.kind)}</span>
                    {m.application_receipt_id && <IdLink kind="memory" id={m.application_receipt_id} />}
                  </li>
                ))}
              </ul>
            ) : <div className="text-[14px] text-faint">Nothing queued for memory.</div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
