import { Empty, PageHeader, Panel, Section } from "@/components/ui";
import { tryApi } from "@/lib/api";
import { fmtDate, fmtNumber } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Data quality" };

interface Q { source_health: Record<string, number>;
  failing_feeds: { source: string; name: string; feed_type: string; health: string; consecutive_failures: number; last_success_at: string | null }[];
  sources_silent_7_days: { source: string; name: string; last_article_at: string | null }[];
  daily: { day: string; articles: number; unique_stories: number; sources_active: number; duplicate_rate: number | null }[];
  last_30_days: Record<string, number | null | Record<string, number>>;
  pipeline_runs: { id: number; type: string; status: string; started_at: string; finished_at: string | null }[];
  drift: { day: string; metric: string; value: number; threshold: number; flagged: boolean }[] }
interface Models { analysis_version: string; models: { name: string; provider: string; license: string | null; tasks: string[]; in_use: boolean; versions: { version: string }[] }[];
  llm_last_30_days: { calls: number; cost_usd: number; failed: number } }

export default async function Quality(props: PageProps) {
  const { l, d } = await setup(props);
  const [q, m] = await Promise.all([tryApi<Q>("/quality", { revalidate: 120 }), tryApi<Models>("/models", { revalidate: 600 })]);
  if (!q) return <Empty d={d} />;
  return (
    <>
      <PageHeader title={d.quality.title} intro={d.quality.intro} />
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={d.quality.health}>
          <Panel><dl className="grid grid-cols-2 gap-2 text-sm">{Object.entries(q.source_health).map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="num text-end">{fmtNumber(v, l)}</dd></div>)}</dl></Panel>
        </Section>
        <Section title={d.quality.rates}>
          <Panel><dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-sm">{Object.entries(q.last_30_days).map(([k, v]) => (
            <div key={k} className="contents"><dt className="text-muted">{k.replaceAll("_", " ")}</dt>
              <dd className="num text-end text-xs">{v === null ? "–" : typeof v === "object" ? Object.entries(v).map(([a, b]) => `${a} ${b}`).join(" · ") : typeof v === "number" && v <= 1 && !k.includes("errors") ? `${(v * 100).toFixed(1)}%` : String(v)}</dd></div>))}</dl></Panel>
        </Section>
        <Section title={d.quality.runs}>
          <Panel><ul className="text-sm flex flex-col gap-1">{q.pipeline_runs.map((r) => <li key={r.id} className="flex justify-between gap-2"><span className="num">{fmtDate(r.started_at, l, { dateStyle: "short", timeStyle: "short" })}</span><span className={r.status === "success" ? "" : "text-accent"}>{r.type} · {r.status}</span></li>)}</ul></Panel>
        </Section>
      </div>
      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Section title={d.quality.failing}>
          <Panel>{q.failing_feeds.length ? <ul className="text-sm flex flex-col gap-1">{q.failing_feeds.map((f, i) => <li key={i}>{f.name} <span className="text-xs text-muted">{f.feed_type} · {f.health} · ×{f.consecutive_failures}</span></li>)}</ul> : <p className="text-sm text-muted">{d.common.none}</p>}</Panel>
        </Section>
        <Section title={d.quality.silent}>
          <Panel>{q.sources_silent_7_days.length ? <ul className="text-sm columns-2 gap-4">{q.sources_silent_7_days.map((s) => <li key={s.source}>{s.name}</li>)}</ul> : <p className="text-sm text-muted">{d.common.none}</p>}</Panel>
        </Section>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title={d.quality.drift}>
          <Panel className="!p-0 overflow-x-auto"><table className="w-full text-sm"><tbody>{q.drift.map((r, i) => (
            <tr key={i} className="border-b border-line last:border-0"><td className="p-2 num">{r.day}</td><td className="p-2">{r.metric}</td><td className={`p-2 text-end num ${r.flagged ? "text-accent font-semibold" : ""}`}>{r.value.toFixed(3)} / {r.threshold}</td></tr>))}</tbody></table></Panel>
        </Section>
        <Section title={d.quality.models} note={m ? `analysis ${m.analysis_version} · LLM 30d: ${m.llm_last_30_days.calls} calls, $${m.llm_last_30_days.cost_usd}` : undefined}>
          <Panel><ul className="text-sm flex flex-col gap-1.5">{m?.models.map((x) => (
            <li key={x.name} className={x.in_use ? "" : "text-muted"}><span className="font-mono text-xs break-all">{x.name}</span> <span className="text-xs text-muted">· {x.tasks.join(", ")} · {x.license ?? "?"}{x.in_use ? ` · ${x.versions.map((v) => v.version).join(", ")}` : " · not used in stored results"}</span></li>))}</ul></Panel>
        </Section>
      </div>
    </>
  );
}
