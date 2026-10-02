import { notFound } from "next/navigation";
import ArticleItem from "@/components/ArticleItem";
import EChart from "@/components/EChart";
import { donut, lineSeries } from "@/components/charts/options";
import { BaseBadge, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

interface TopicDetail {
  id: number; label: string; label_ar: string | null; label_method: string; llm_description: string | null; terms: [string, number][];
  size: number; language_distribution: Record<string, number>; quality: Record<string, unknown>;
  model: { scope: string; algorithm: string; metrics: Record<string, number> };
  global_topic: { id: number; label: string; confidence: number } | null;
  series: { day: string; articles: number }[]; top_sources: { slug: string; name: string; operating_base: string; articles: number }[];
  sentiment: Record<string, number>; representative_articles: ArticleSummary[]; recent_articles: ArticleSummary[];
}

export default async function TopicPage(props: PageProps<{ id: string }>) {
  const { l, d, p, sp } = await setup(props);
  const t = await tryApi<TopicDetail>(`/topics/${encodeURIComponent(p.id)}${filterQuery(sp)}`);
  if (!t) notFound();
  const sent = d.sentiment as Record<string, string>;
  return (
    <>
      <PageHeader title={pick(l, t.label, t.label_ar)} intro={t.llm_description ?? undefined}>
        <p className="text-sm text-muted">{d.topics.labelMethod}: {t.label_method} · {d.topics.model}: {t.model.algorithm} ({t.model.scope}) · {d.topics.coherence}: {String(t.quality.coherence_npmi ?? "–")}</p>
      </PageHeader>
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={d.topics.keywords}>
          <Panel>
            <ul className="flex flex-wrap gap-2" dir="auto">{t.terms.slice(0, 20).map(([w, s]) => <li key={w} className="rounded border border-line px-2 py-0.5 text-sm" title={String(s)}>{w}</li>)}</ul>
            <p className="text-xs text-muted mt-3">{Object.entries(t.language_distribution).map(([k, v]) => `${k.toUpperCase()} ${v}`).join(" · ")}</p>
          </Panel>
        </Section>
        <Section title={d.dashboard.timelineTitle} className="lg:col-span-2">
          <Panel><EChart ariaLabel={d.dashboard.timelineTitle} height={220} option={lineSeries(t.series, l === "ar")} /></Panel>
        </Section>
      </div>
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={d.common.sources}>
          <Panel>
            <ul className="flex flex-col gap-2 text-sm">{t.top_sources.map((s) => (
              <li key={s.slug} className="flex justify-between gap-2"><span>{s.name}<br /><BaseBadge base={s.operating_base} d={d} /></span><span className="num text-muted">{fmtNumber(s.articles, l)}</span></li>))}</ul>
          </Panel>
        </Section>
        <Section title={d.common.sentiment}>
          <Panel><EChart ariaLabel={d.common.sentiment} height={220} option={donut(Object.entries(t.sentiment).map(([k, v]) => ({ name: sent[k] ?? k, value: v, color: SENTIMENT_COLORS[k] })))} /></Panel>
        </Section>
        <Section title={d.topics.representative}>
          <Panel className="!py-1"><ul>{t.representative_articles.slice(0, 3).map((a) => <ArticleItem key={a.id} a={a} l={l} d={d} />)}</ul></Panel>
        </Section>
      </div>
      <Section title={d.topics.recent}>
        <Panel className="!py-1"><ul>{t.recent_articles.map((a) => <ArticleItem key={a.id} a={a} l={l} d={d} />)}</ul></Panel>
      </Section>
    </>
  );
}
