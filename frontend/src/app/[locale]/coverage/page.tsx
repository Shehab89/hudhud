import Link from "next/link";
import ArticleItem from "@/components/ArticleItem";
import DemoBanner from "@/components/DemoBanner";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { choropleth, groupedBars, stackedArea } from "@/components/charts/options";
import { BASE_COLORS, Bar, Empty, Kpi, PageHeader, Panel, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary, type Overview, type Paged, type SearchParams, type Timeline, type Trend } from "@/lib/api";
import { fmtDate, fmtNumber, getDict, hasLocale, pick, type Locale } from "@/lib/i18n";
import { notFound } from "next/navigation";

interface Geo { governorates: { slug: string; name_en: string; name_ar: string | null; admin_code: string | null; articles_including_places: number; events: number }[];
  places: { name_en: string; name_ar: string | null; lat: number | null; lon: number | null; articles: number }[] }
interface Narr { groups: Record<string, { articles: number; frames: Record<string, number> }>; frames: Record<string, { name_en: string; name_ar: string | null }> }
interface Actors { items: { slug: string; name_en: string; name_ar: string | null; entity_type: string; articles: number }[] }

export default async function Dashboard({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<SearchParams> }) {
  const { locale } = await params;
  if (!hasLocale(locale)) notFound();
  const l: Locale = locale;
  const d = getDict(l);
  const sp = await searchParams;
  const fq = filterQuery(sp);
  const [ov, tl, trends, actors, latest, geo, narr] = await Promise.all([
    tryApi<Overview>(`/overview${fq}`),
    tryApi<Timeline>(`/timeline${filterQuery(sp, { split: "operating_base" })}`),
    tryApi<Trend[]>(`/trends?limit=8`),
    tryApi<Actors>(`/actors${filterQuery(sp, { limit: 8 })}`),
    tryApi<Paged<ArticleSummary>>(`/articles${filterQuery(sp, { limit: 8 })}`),
    tryApi<Geo>(`/geography${fq}`),
    tryApi<Narr>(`/compare/narratives${fq}`),
  ]);
  const rtl = l === "ar";
  const bases = d.bases as Record<string, string>;
  const maxTrend = Math.max(1, ...(trends ?? []).map((t) => t.frequency));
  const maxActor = Math.max(1, ...(actors?.items ?? []).map((a) => a.articles));

  const frameKeys = narr ? Object.entries(narr.frames).filter(([k]) => Object.values(narr.groups).some((g) => (g.frames[k] ?? 0) > 0))
    .sort(([a], [b]) => Object.values(narr.groups).reduce((s, g) => s + (g.frames[b] ?? 0), 0) - Object.values(narr.groups).reduce((s, g) => s + (g.frames[a] ?? 0), 0))
    .slice(0, 8) : [];


  return (
    <>
      <PageHeader title={d.dashboard.title} intro={d.dashboard.intro} />
      <DemoBanner d={d} show={!!ov?.contains_demo} />
      <FilterBar d={d} sp={sp} />

      {ov ? (
        <Panel className="!p-0 mb-8">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 divide-line [&>*]:border-line [&>*]:border-b lg:[&>*]:border-b-0 lg:[&>*:not(:last-child)]:border-e">
            <Kpi label={d.common.articles} value={ov.current.articles} previous={ov.previous.articles} l={l} d={d} />
            <Kpi label={d.common.stories} value={ov.current.unique_stories} previous={ov.previous.unique_stories} l={l} d={d} />
            <Kpi label={d.common.sources} value={ov.current.sources_active} previous={ov.previous.sources_active} l={l} d={d} />
            <Kpi label={d.common.languages} value={ov.current.languages} l={l} d={d} />
            <Kpi label={d.common.events} value={ov.current.events} previous={ov.previous.events} l={l} d={d} />
            <Kpi label={d.common.actors} value={ov.current.actors_mentioned} l={l} d={d} />
          </div>
        </Panel>
      ) : <Empty d={d} />}

      <div className="grid gap-8 lg:grid-cols-[1fr_2fr] mb-10">
        <Section title={d.dashboard.summaryTitle} note={d.dashboard.summaryNote}>
          <Panel className="leading-relaxed text-[0.95rem]">
            {ov?.summary?.[l]?.content ? (
              <>
                <p className="label-caps text-muted mb-2 num">{fmtDate(ov.summary[l].day, l)}</p>
                <p>{ov.summary[l].content}</p>
              </>
            ) : <Empty d={d} />}
            {ov?.last_pipeline_run && (
              <p className="mt-4 text-xs text-muted">
                {d.dashboard.lastRun}: <span className="num">{fmtDate(ov.last_pipeline_run.started_at, l, { dateStyle: "medium", timeStyle: "short" })}</span> · {ov.last_pipeline_run.status}
              </p>
            )}
          </Panel>
        </Section>
        <Section title={d.dashboard.timelineTitle} note={d.dashboard.byBase}>
          <Panel>
            {tl && tl.keys.length ? (
              <EChart ariaLabel={d.dashboard.timelineTitle} height={300}
                option={stackedArea(tl.days, tl.keys.map((k) => ({ name: bases[k] ?? k, data: tl.series[k], color: BASE_COLORS[k] })), rtl)} />
            ) : <Empty d={d} />}
          </Panel>
        </Section>
      </div>

      <div className="grid gap-8 lg:grid-cols-2 mb-10">
        <Section title={d.dashboard.trendsTitle} action={<Link className="text-sm text-accent-2" href={`/${l}/topics`}>{d.common.viewAll}</Link>}>
          <Panel>
            {trends?.length ? (
              <ul className="flex flex-col gap-3">
                {trends.map((t) => (
                  <li key={t.id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 items-center">
                    <Link href={`/${l}/topics/category/${t.slug}`} className="hover:underline truncate">{pick(l, t.label, t.label_ar)}</Link>
                    <span className="text-xs num text-muted">
                      {fmtNumber(t.frequency, l)} · <span className={t.status === "emerging" ? "text-accent font-medium" : t.status === "declining" ? "text-accent-2" : ""}>
                        {(d.trend as Record<string, string>)[t.status]} {t.growth_rate >= 0 ? "+" : ""}{fmtNumber(t.growth_rate, l, { style: "percent", maximumFractionDigits: 0 })}
                      </span>
                    </span>
                    <div className="col-span-2"><Bar value={t.frequency} max={maxTrend} /></div>
                  </li>
                ))}
              </ul>
            ) : <Empty d={d} />}
          </Panel>
        </Section>
        <Section title={d.dashboard.actorsTitle} action={<Link className="text-sm text-accent-2" href={`/${l}/actors`}>{d.common.viewAll}</Link>}>
          <Panel>
            {actors?.items?.length ? (
              <ul className="flex flex-col gap-3">
                {actors.items.map((a) => (
                  <li key={a.slug} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 items-center">
                    <Link href={`/${l}/actors/${a.slug}`} className="hover:underline truncate">{pick(l, a.name_en, a.name_ar)}</Link>
                    <span className="text-xs num text-muted">{fmtNumber(a.articles, l)}</span>
                    <div className="col-span-2"><Bar value={a.articles} max={maxActor} color="var(--accent)" /></div>
                  </li>
                ))}
              </ul>
            ) : <Empty d={d} />}
          </Panel>
        </Section>
      </div>

      <div className="grid gap-8 lg:grid-cols-2 mb-10">
        <Section title={d.dashboard.splitTitle} note={d.dashboard.splitNote}>
          <Panel>
            {narr && frameKeys.length ? (
              <EChart ariaLabel={d.dashboard.splitTitle} height={340}
                option={groupedBars(frameKeys.map(([, f]) => pick(l, f.name_en, f.name_ar)),
                  Object.entries(narr.groups).filter(([k]) => k !== "unknown").map(([k, g]) => ({ name: bases[k] ?? k, color: BASE_COLORS[k], data: frameKeys.map(([fk]) => g.frames[fk] ?? 0) })),
                  { percent: true, rtl })} />
            ) : <Empty d={d} />}
          </Panel>
        </Section>
        <Section title={d.dashboard.mapTitle} action={<Link className="text-sm text-accent-2" href={`/${l}/geography`}>{d.common.viewAll}</Link>}>
          <Panel>
            {geo ? (
              <EChart ariaLabel={d.dashboard.mapTitle} height={340} mapGeoUrl="/geo/yemen-adm1.json"
                option={choropleth(
                  geo.governorates.filter((g) => g.admin_code).map((g) => ({ code: g.admin_code as string, name: pick(l, g.name_en, g.name_ar), value: g.articles_including_places })),
                  [], d.geography.articles)} />
            ) : <Empty d={d} />}
          </Panel>
        </Section>
      </div>

      <Section title={d.dashboard.latestTitle} action={<Link className="text-sm text-accent-2" href={`/${l}/news${fq}`}>{d.common.viewAll}</Link>}>
        <Panel className="!py-1">
          {latest?.items.length ? <ul>{latest.items.map((a) => <ArticleItem key={a.id} a={a} l={l} d={d} />)}</ul> : <Empty d={d} />}
        </Panel>
      </Section>
    </>
  );
}
