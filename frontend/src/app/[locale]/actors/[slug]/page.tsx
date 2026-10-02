import Link from "next/link";
import { notFound } from "next/navigation";
import ArticleItem from "@/components/ArticleItem";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { groupedBars, lineSeries } from "@/components/charts/options";
import { BaseBadge, DemoBadge, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary } from "@/lib/api";
import { pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

interface Actor { slug: string; name_en: string; name_ar: string | null; entity_type: string; description: string | null; wikidata_id: string | null;
  parent: { slug: string; name_en: string } | null;
  aliases: { surface_form: string; language: string; alias_type: string; framing_note: string | null }[];
  series: { day: string; articles: number }[];
  targeted_sentiment_by_operating_base: Record<string, Record<string, number>>;
  targeted_sentiment_examples: { sentiment: string; score: number; evidence_sentence: string; confidence: number; method: string; article_id: number; title: string; source: string; operating_base: string; is_demo: boolean }[];
  terminology: { term: string; language: string; alias_type: string; framing_note: string | null; operating_base: string; mentions: number }[];
  co_mentioned: { slug: string; name_en: string; name_ar: string | null; articles: number }[]; recent_articles: ArticleSummary[] }

export default async function ActorPage(props: PageProps<{ slug: string }>) {
  const { l, d, p, sp } = await setup(props);
  const a = await tryApi<Actor>(`/actors/${encodeURIComponent(p.slug)}${filterQuery(sp)}`);
  if (!a) notFound();
  const bases = d.bases as Record<string, string>;
  const sent = d.sentiment as Record<string, string>;
  const at = d.aliasTypes as Record<string, string>;
  const baseKeys = Object.keys(a.targeted_sentiment_by_operating_base);
  const shares = (k: string, s: string) => {
    const row = a.targeted_sentiment_by_operating_base[k]; const tot = Object.values(row).reduce((x, y) => x + y, 0) || 1;
    return (row[s] ?? 0) / tot;
  };
  return (
    <>
      <PageHeader title={pick(l, a.name_en, a.name_ar)} intro={a.description ?? undefined}>
        <p className="text-sm text-muted">{a.entity_type.replaceAll("_", " ")}{a.parent && <> · <Link className="text-accent-2" href={`/${l}/actors/${a.parent.slug}`}>{a.parent.name_en}</Link></>}
          {a.wikidata_id && <> · <a className="text-accent-2" href={`https://www.wikidata.org/wiki/${a.wikidata_id}`} rel="noopener noreferrer" target="_blank">Wikidata</a></>}</p>
      </PageHeader>
      <FilterBar d={d} sp={sp} />
      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Section title={d.actors.aliases} note={d.actors.aliasNote}>
          <Panel>
            <ul className="flex flex-wrap gap-2">
              {a.aliases.map((x) => (
                <li key={`${x.surface_form}-${x.language}`} title={x.framing_note ?? undefined} className="rounded-md border border-line px-2 py-1 text-sm" dir="auto">
                  {x.surface_form} <span className="text-[0.68rem] text-muted">{x.language.toUpperCase()} · {at[x.alias_type] ?? x.alias_type}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </Section>
        <Section title={d.dashboard.timelineTitle}><Panel><EChart ariaLabel={d.dashboard.timelineTitle} height={220} option={lineSeries(a.series, l === "ar")} /></Panel></Section>
      </div>
      <Section title={d.actors.targeted} note={d.actors.targetedNote} className="mb-8">
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel>
            {baseKeys.length ? (
              <EChart ariaLabel={d.actors.targeted} height={260}
                option={groupedBars(baseKeys.map((k) => bases[k] ?? k), ["negative", "neutral", "positive"].map((s) => ({ name: sent[s], color: SENTIMENT_COLORS[s], data: baseKeys.map((k) => shares(k, s)) })), { percent: true, rtl: l === "ar" })} />
            ) : <p className="text-sm text-muted">{d.common.noData}</p>}
          </Panel>
          <Panel>
            <h3 className="label-caps text-muted mb-2">{d.actors.examples}</h3>
            <ul className="flex flex-col gap-3 text-sm max-h-80 overflow-y-auto">
              {a.targeted_sentiment_examples.map((e, i) => (
                <li key={i} className="flex flex-col gap-1">
                  <span className="text-xs"><span style={{ color: SENTIMENT_COLORS[e.sentiment] }}>{sent[e.sentiment]}</span> · {e.source} <BaseBadge base={e.operating_base} d={d} /> {e.is_demo && <DemoBadge d={d} />}</span>
                  <Link href={`/${l}/news/${e.article_id}`} className="border-s-2 border-line ps-2 text-muted hover:text-ink" dir="auto">“{e.evidence_sentence}”</Link>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </Section>
      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Section title={d.actors.terminologyTitle}>
          <Panel className="!p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>{a.terminology.map((t, i) => (
                <tr key={i} className="border-b border-line last:border-0" title={t.framing_note ?? undefined}>
                  <td className="p-2" dir="auto">{t.term}</td><td className="p-2 text-xs text-muted">{at[t.alias_type] ?? t.alias_type}</td>
                  <td className="p-2"><BaseBadge base={t.operating_base} d={d} /></td><td className="p-2 text-end num">{t.mentions}</td>
                </tr>))}</tbody>
            </table>
          </Panel>
        </Section>
        <Section title={d.actors.coMentioned}>
          <Panel><ul className="flex flex-wrap gap-2">{a.co_mentioned.map((c) => <li key={c.slug}><Link className="rounded-full border border-line px-2.5 py-0.5 text-sm hover:border-accent inline-block" href={`/${l}/actors/${c.slug}`}>{pick(l, c.name_en, c.name_ar)} <span className="text-muted num">{c.articles}</span></Link></li>)}</ul></Panel>
        </Section>
      </div>
      <Section title={d.dashboard.latestTitle}><Panel className="!py-1"><ul>{a.recent_articles.map((x) => <ArticleItem key={x.id} a={x} l={l} d={d} />)}</ul></Panel></Section>
    </>
  );
}
