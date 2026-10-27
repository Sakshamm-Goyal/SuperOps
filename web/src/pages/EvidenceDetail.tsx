import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Fingerprint, Database, Table2, Search } from "lucide-react";
import type { Json, Resource } from "../lib/api";
import { useGet } from "../lib/hooks";
import { humanize, shortTs } from "../lib/format";
import { Card, CardHeader, ErrorBox, Hash, KindBadge, KV, Notice, PageHeader, PageSkeleton, StatusChip } from "../components/ui";

export default function EvidenceDetail() {
  const { id = "" } = useParams();
  const r = useGet<Resource<Json>>(`/v1/evidence/${id}`);
  const [q, setQ] = useState("");
  const rows: Json[] = r.data?.data?.rows ?? [];
  const cols = useMemo(() => Array.from(new Set(rows.flatMap((x) => Object.keys(x ?? {})))), [rows]);
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? rows.filter((x) => JSON.stringify(x).toLowerCase().includes(s)) : rows;
  }, [rows, q]);
  if (r.loading && !r.data) return <PageSkeleton />;
  if (r.error && !r.data) return <ErrorBox error={r.error} title="Could not load the evidence" />;
  if (!r.data) return null;
  const res = r.data;
  const d = res.data;
  const rc = d.receipt ?? {};
  const sample = d.source_system === "local_sample_postgres";
  return (
    <div className="rise">
      <PageHeader
        eyebrow={<><Fingerprint className="size-4" /> Evidence <span className="mono normal-case tracking-normal">{id.slice(0, 8)}</span></>}
        title={<>{humanize(d.kind)}{d.subject ? <> · <em>{String(d.subject).split("/").slice(-1)[0]}</em></> : null}</>}
        sub={d.subject ? <span className="mono text-[14px]">{d.subject}</span> : undefined}
        chips={<><StatusChip status={res.status} size="md" label={`completeness ${res.status}`} /><KindBadge kind={res.result_kind} prefix="result" /><KindBadge kind={res.data_origin} prefix="data" /><KindBadge kind={res.runtime_mode} prefix="mode" /></>}
      />
      {sample && <div className="mb-5"><Notice tone="unknown" icon={Database} title="Local fixture database, not Zetaris federation">In sample mode evidence comes from a local PostgreSQL fixture. The receipt shape is the same; it is not federation proof.</Notice></div>}
      {(d.quality_flags ?? []).length > 0 && !sample && <div className="mb-5"><Notice tone="warn" title="Quality flags">{d.quality_flags.join(" · ")}</Notice></div>}
      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <Card className="self-start">
          <CardHeader title="Query receipt" icon={Fingerprint} />
          <div className="px-5 pb-5">
            <KV rows={[
              ["Template", <span className="mono text-[12px]">{rc.template_id} v{rc.template_version}</span>],
              ["Source system", <span className="mono text-[12px]">{d.source_system}</span>],
              ["Sources", (rc.sources ?? []).map((s: string) => <span key={s} className="mono mr-1 rounded bg-lav px-1 text-[12.5px]">{s}</span>)],
              ["Request IDs", (rc.request_ids ?? []).length ? <span className="mono text-[12px] break-all">{rc.request_ids.join(", ")}</span> : <span className="text-faint">none recorded</span>],
              ["Pages", rc.page_count],
              ["Rows", `${d.row_count}${d.rows_truncated ? " (first 500 shown)" : ""}`],
              ["Duration", rc.duration_ms !== undefined ? `${rc.duration_ms} ms` : "—"],
              ["Parameter hash", <Hash value={rc.parameter_hash} />],
              ["Result hash", <Hash value={rc.result_hash} />],
              ["Close status", rc.close_status ?? rc.query_close ?? "—"],
              ["Observed", d.observed_from ? `${shortTs(d.observed_from)} → ${shortTs(d.observed_to)}` : "—"],
              ["Retrieved", shortTs(d.retrieved_at)],
            ]} />
            {(rc.warnings ?? []).length > 0 && <div className="mt-3 rounded-lg bg-warn-bg/60 px-3 py-2 text-[12.5px] text-warn">{rc.warnings.join(" · ")}</div>}
          </div>
        </Card>
        <Card className="min-w-0 overflow-hidden">
          <CardHeader title="Source rows" icon={Table2} sub={`${filtered.length} of ${rows.length} shown${d.rows_truncated ? ` · ${d.row_count} total, API returns at most 500` : ""}`}
            right={<label className="flex h-9 items-center gap-2 rounded-full bg-wash px-3 ring-1 ring-line"><Search className="size-3.5 text-faint" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter rows" className="w-32 bg-transparent text-[13.5px] outline-none sm:w-44" /></label>} />
          <div className="max-h-[620px] overflow-auto scroll-thin">
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 z-10 bg-white"><tr className="border-y border-line text-left text-[11.5px] uppercase tracking-wider text-faint">
                <th className="px-3 py-2">#</th>{cols.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2">{c}</th>)}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {filtered.map((x, i) => (
                  <tr key={i} className="hover:bg-accent-50/30">
                    <td className="px-3 py-1.5 text-faint tnum">{i + 1}</td>
                    {cols.map((c) => {
                      const v = x?.[c];
                      return <td key={c} className="mono whitespace-nowrap px-3 py-1.5 text-ink-2">{v === null || v === undefined ? <span className="text-faint">null</span> : typeof v === "object" ? JSON.stringify(v) : String(v)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
