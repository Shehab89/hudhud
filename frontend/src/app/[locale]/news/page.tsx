import ArticleItem from "@/components/ArticleItem";
import DemoBanner from "@/components/DemoBanner";
import FilterBar from "@/components/FilterBar";
import { Empty, PageHeader, Panel } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary, type Paged } from "@/lib/api";
import { fmtNumber } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

export const metadata = { title: "News" };
const LIMIT = 30;

export default async function News(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const q = one(sp.q);
  const page = Math.max(1, parseInt(one(sp.page) || "1", 10) || 1);
  const data = await tryApi<Paged<ArticleSummary>>(`/articles${filterQuery(sp, { q, limit: LIMIT, offset: (page - 1) * LIMIT })}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / LIMIT)) : 1;
  const link = (n: number) => `?${new URLSearchParams({ ...Object.fromEntries(Object.entries(sp).map(([k, v]) => [k, one(v)])), page: String(n) })}`;
  return (
    <>
      <PageHeader title={d.news.title} intro={d.news.intro}>
        <form method="get" className="flex gap-2 max-w-xl" role="search">
          <input name="q" defaultValue={q} placeholder={d.common.searchPlaceholder} aria-label={d.common.search}
            className="flex-1 rounded-md border border-line bg-surface px-3 py-2" />
          <button className="rounded-md bg-accent text-accent-ink px-4 py-2 text-sm font-medium">{d.common.search}</button>
        </form>
      </PageHeader>
      <DemoBanner d={d} show={!!data?.contains_demo} />
      <FilterBar d={d} sp={sp} keep={["q"]} />
      <p className="text-sm text-muted mb-2 num">{fmtNumber(data?.total ?? 0, l)} {d.common.articles}</p>
      <Panel className="!py-1">
        {data?.items.length ? <ul>{data.items.map((a) => <ArticleItem key={a.id} a={a} l={l} d={d} />)}</ul> : <Empty d={d} />}
      </Panel>
      {pages > 1 && (
        <nav className="flex items-center justify-between mt-4 text-sm" aria-label={d.common.page}>
          {page > 1 ? <a className="text-accent-2" href={link(page - 1)}>← {d.common.prev}</a> : <span />}
          <span className="text-muted num">{d.common.page} {fmtNumber(page, l)} {d.common.of} {fmtNumber(pages, l)}</span>
          {page < pages ? <a className="text-accent-2" href={link(page + 1)}>{d.common.next} →</a> : <span />}
        </nav>
      )}
    </>
  );
}
