import Link from "next/link";
import ArticleItem from "@/components/ArticleItem";
import DemoBanner from "@/components/DemoBanner";
import FilterBar from "@/components/FilterBar";
import { Empty, PageHeader, Panel } from "@/components/ui";
import { PUBLIC_API_URL, filterQuery, tryApi, type ArticleSummary } from "@/lib/api";
import { fmtNumber } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Research" };

interface Res { mode: string; total: number; semantic_model: { model: string; version: string; semantic: boolean } | null; contains_demo: boolean;
  items: (ArticleSummary & { score: number; matched_by: string[] })[] }

export default async function Research(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const q = one(sp.q);
  const mode = one(sp.mode) || "hybrid";
  const res = q.length >= 2 ? await tryApi<Res>(`/search${filterQuery(sp, { q, mode, limit: 50 })}`, { revalidate: 60 }) : null;
  const exportBase = `${PUBLIC_API_URL}/api/v1/export/articles${filterQuery(sp, { limit: 1000 })}`;
  const sep = exportBase.includes("?") ? "&" : "?";
  return (
    <>
      <PageHeader title={d.research.title} intro={d.research.intro}>
        <form method="get" className="flex flex-wrap gap-2 max-w-3xl" role="search">
          {["date_from", "date_to", "language", "operating_base", "demo"].map((k) => one(sp[k]) && <input key={k} type="hidden" name={k} value={one(sp[k])} />)}
          <input name="q" defaultValue={q} placeholder={d.common.searchPlaceholder} aria-label={d.common.search} className="flex-1 min-w-60 rounded-md border border-line bg-surface px-3 py-2" />
          <select name="mode" defaultValue={mode} aria-label={d.research.mode} className="rounded-md border border-line bg-surface px-2 py-2 text-sm">
            <option value="hybrid">{d.research.hybrid}</option><option value="keyword">{d.research.keyword}</option><option value="semantic">{d.research.semantic}</option>
          </select>
          <button className="rounded-md bg-accent text-accent-ink px-4 py-2 text-sm font-medium">{d.common.search}</button>
        </form>
      </PageHeader>
      <DemoBanner d={d} show={!!res?.contains_demo} />
      <FilterBar d={d} sp={sp} keep={["q", "mode"]} />
      <div className="flex flex-wrap items-center gap-3 mb-4 text-sm">
        <span className="text-muted">{d.research.exportAs}:</span>
        {["csv", "json", "bibtex", "ris"].map((f) => <a key={f} className="rounded border border-line px-2.5 py-1 hover:border-accent" href={`${exportBase}${sep}format=${f}`}>{f.toUpperCase()}</a>)}
        <Link className="text-accent-2 ms-auto" href={`${PUBLIC_API_URL}/docs`}>{d.research.apiNote} ↗</Link>
      </div>
      {res?.semantic_model && <p className="text-xs text-muted mb-3">{d.research.semanticNote.replace("{model}", `${res.semantic_model.model} (${res.semantic_model.version})`)}</p>}
      {q && <p className="text-sm text-muted mb-2 num">{fmtNumber(res?.total ?? 0, l)} · {mode}</p>}
      <Panel className="!py-1">
        {res?.items.length ? (
          <ul>{res.items.map((a) => <ArticleItem key={a.id} a={a} l={l} d={d}
            extra={<span className="text-xs text-muted font-mono">{d.research.matchedBy}: {a.matched_by.join(" + ")} · {a.score.toFixed(4)}</span>} />)}</ul>
        ) : <Empty d={d} />}
      </Panel>
    </>
  );
}
