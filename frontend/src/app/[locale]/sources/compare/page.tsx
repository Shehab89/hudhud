import FilterBar from "@/components/FilterBar";
import { BaseBadge, Empty, PageHeader, Panel, SENTIMENT_COLORS } from "@/components/ui";
import { filterQuery, tryApi } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

interface Cmp { stories_covered_by_all: number; sources: { slug: string; name: string; operating_base: string; articles: number;
  sentiment: Record<string, number>; frames: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
  terminology: { term: string; alias_type: string; mentions: number }[]; categories: { slug: string; articles: number }[] }[] }

export default async function Compare(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const slugs = one(sp.slugs);
  const all = await tryApi<{ sources: { slug: string; name: string; articles: number }[] }>(`/sources${filterQuery(sp)}`);
  const data = slugs.split(",").filter(Boolean).length >= 2 ? await tryApi<Cmp>(`/compare/sources${filterQuery(sp, { slugs })}`) : null;
  const options = (all?.sources ?? []).filter((s) => s.articles > 0);
  const sent = d.sentiment as Record<string, string>;
  return (
    <>
      <PageHeader title={d.sources.compare} intro={d.sources.compareHint} />
      <FilterBar d={d} sp={sp} keep={["slugs"]} />
      <form method="get" className="flex flex-wrap gap-2 mb-6 items-end">
        <label className="flex flex-col gap-1 text-xs text-muted flex-1 min-w-64">{d.common.sources}
          <input list="source-slugs" name="slugs" defaultValue={slugs} placeholder="slug-a,slug-b" className="rounded-md border border-line bg-surface px-3 py-2 text-sm" />
        </label>
        <datalist id="source-slugs">{options.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}</datalist>
        <button className="rounded-md bg-accent text-accent-ink px-4 py-2 text-sm">{d.common.apply}</button>
      </form>
      {data ? (
        <>
          <p className="text-sm text-muted mb-4">{d.sources.storiesShared}: <span className="num">{fmtNumber(data.stories_covered_by_all, l)}</span></p>
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(16rem, 1fr))` }}>
            {data.sources.map((s) => {
              const total = Object.values(s.sentiment).reduce((a, b) => a + b, 0) || 1;
              return (
                <Panel key={s.slug} className="flex flex-col gap-3">
                  <div><h2 className="font-semibold">{s.name}</h2><BaseBadge base={s.operating_base} d={d} /><p className="text-sm num">{fmtNumber(s.articles, l)} {d.common.articles}</p></div>
                  <div className="flex h-2 rounded overflow-hidden" aria-label={d.common.sentiment}>
                    {Object.entries(s.sentiment).map(([k, v]) => <span key={k} title={`${sent[k] ?? k} ${v}`} style={{ width: `${(v / total) * 100}%`, background: SENTIMENT_COLORS[k] }} />)}
                  </div>
                  <div><h3 className="label-caps text-muted">{d.common.frames}</h3><ul className="text-sm">{s.frames.slice(0, 5).map((f) => <li key={f.slug} className="flex justify-between"><span>{pick(l, f.name_en, f.name_ar)}</span><span className="num text-muted">{f.articles}</span></li>)}</ul></div>
                  <div><h3 className="label-caps text-muted">{d.common.terminology}</h3><ul className="text-sm">{s.terminology.slice(0, 6).map((t) => <li key={t.term} className="flex justify-between" dir="auto"><span>{t.term}</span><span className="num text-muted">{t.mentions}</span></li>)}</ul></div>
                </Panel>
              );
            })}
          </div>
        </>
      ) : <Empty d={d} />}
    </>
  );
}
