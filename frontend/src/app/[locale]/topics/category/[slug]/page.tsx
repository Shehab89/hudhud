import Link from "next/link";
import { notFound } from "next/navigation";
import ArticleItem from "@/components/ArticleItem";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { donut, lineSeries } from "@/components/charts/options";
import { BASE_COLORS, Bar, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary, type Paged } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

interface Cat {
  slug: string; name_en: string; name_ar: string | null; description: string | null;
  subcategories: { slug: string; name_en: string; name_ar: string | null }[];
  series: { day: string; articles: number }[]; top_sources: { slug: string; name: string; operating_base: string; articles: number }[];
  by_operating_base: Record<string, number>; top_actors: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
  sentiment: Record<string, number>; frames: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
}

export default async function CategoryPage(props: PageProps<{ slug: string }>) {
  const { l, d, p, sp } = await setup(props);
  const [c, arts] = await Promise.all([
    tryApi<Cat>(`/categories/${encodeURIComponent(p.slug)}${filterQuery(sp)}`),
    tryApi<Paged<ArticleSummary>>(`/articles${filterQuery({ ...sp, category: p.slug }, { limit: 12 })}`),
  ]);
  if (!c) notFound();
  const bases = d.bases as Record<string, string>;
  const sent = d.sentiment as Record<string, string>;
  const maxA = Math.max(1, ...c.top_actors.map((a) => a.articles));
  const maxF = Math.max(1, ...c.frames.map((f) => f.articles));
  return (
    <>
      <PageHeader title={pick(l, c.name_en, c.name_ar)} intro={c.description ?? undefined}>
        <div className="flex flex-wrap gap-2 text-sm">{c.subcategories.map((s) => <Link key={s.slug} className="rounded-full border border-line px-2.5 py-0.5 hover:border-accent" href={`/${l}/topics/category/${s.slug}`}>{pick(l, s.name_en, s.name_ar)}</Link>)}</div>
      </PageHeader>
      <FilterBar d={d} sp={sp} />
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={d.dashboard.timelineTitle} className="lg:col-span-2"><Panel><EChart ariaLabel={d.dashboard.timelineTitle} height={240} option={lineSeries(c.series, l === "ar")} /></Panel></Section>
        <Section title={d.dashboard.byBase}><Panel><EChart ariaLabel={d.dashboard.byBase} height={240} option={donut(Object.entries(c.by_operating_base).map(([k, v]) => ({ name: bases[k] ?? k, value: v, color: BASE_COLORS[k] })))} /></Panel></Section>
      </div>
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={d.common.frames}><Panel><ul className="flex flex-col gap-2 text-sm">{c.frames.map((f) => <li key={f.slug}><div className="flex justify-between"><span>{pick(l, f.name_en, f.name_ar)}</span><span className="num text-muted">{fmtNumber(f.articles, l)}</span></div><Bar value={f.articles} max={maxF} /></li>)}</ul></Panel></Section>
        <Section title={d.dashboard.actorsTitle}><Panel><ul className="flex flex-col gap-2 text-sm">{c.top_actors.map((a) => <li key={a.slug}><div className="flex justify-between"><Link className="hover:underline" href={`/${l}/actors/${a.slug}`}>{pick(l, a.name_en, a.name_ar)}</Link><span className="num text-muted">{fmtNumber(a.articles, l)}</span></div><Bar value={a.articles} max={maxA} color="var(--accent)" /></li>)}</ul></Panel></Section>
        <Section title={d.common.sentiment}><Panel><EChart ariaLabel={d.common.sentiment} height={240} option={donut(Object.entries(c.sentiment).map(([k, v]) => ({ name: sent[k] ?? k, value: v, color: SENTIMENT_COLORS[k] })))} /></Panel></Section>
      </div>
      <Section title={d.dashboard.latestTitle}><Panel className="!py-1"><ul>{arts?.items.map((a) => <ArticleItem key={a.id} a={a} l={l} d={d} />)}</ul></Panel></Section>
    </>
  );
}
