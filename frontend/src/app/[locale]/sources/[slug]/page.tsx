import { notFound } from "next/navigation";
import ArticleItem from "@/components/ArticleItem";
import DemoBanner from "@/components/DemoBanner";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { donut, lineSeries } from "@/components/charts/options";
import { BaseBadge, Bar, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary } from "@/lib/api";
import { fmtDate, fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

interface Orientation { simplified: string; dimensions: Record<string, unknown>; confidence: number; evidence: string | null; method: string;
  valid_from: string | null; valid_to: string | null; last_reviewed: string | null; review_status: string;
  evidence_items: { url: string; type: string | null; note: string | null; accessed_at: string | null }[] }
interface Stats { articles: number; series: { day: string; articles: number }[]; categories: { slug: string; articles: number }[];
  sentiment: Record<string, number>; tone: { tone: string; articles: number }[];
  frames: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
  terminology: { entity: string; entity_name: string; term: string; alias_type: string; framing_note: string | null; mentions: number }[];
  actors: { slug: string; name_en: string; name_ar: string | null; articles: number; mean_targeted_sentiment: number | null }[] }
interface SourceDetail { note: string; slug: string; name: string; name_native: string | null; url: string; country: string | null;
  source_type: string; source_group: string; operating_base: string; languages: string[]; ownership: string | null;
  ownership_evidence_urls: string[]; access_policy: string; active: boolean; is_demo: boolean; notes: string | null;
  health: { status: string; last_success_at: string | null; consecutive_failures: number };
  feeds: { url: string; type: string; verified: boolean; verified_at: string | null; active: boolean; health_status: string; last_item_count: number | null; notes: string | null }[];
  orientation: Orientation | null; orientation_history: Orientation[]; stats: Stats; recent_articles: ArticleSummary[] }

export default async function SourcePage(props: PageProps<{ slug: string }>) {
  const { l, d, p, sp } = await setup(props);
  const s = await tryApi<SourceDetail>(`/sources/${encodeURIComponent(p.slug)}${filterQuery(sp)}`);
  if (!s) notFound();
  const sent = d.sentiment as Record<string, string>;
  const maxF = Math.max(1, ...s.stats.frames.map((f) => f.articles));
  const maxC = Math.max(1, ...s.stats.categories.map((f) => f.articles));
  return (
    <>
      <PageHeader title={s.name} intro={s.name_native ?? undefined}>
        <div className="flex flex-wrap gap-4 text-sm text-muted">
          <BaseBadge base={s.operating_base} d={d} />
          <span>{s.source_group.replaceAll("_", " ")} · {s.source_type.replaceAll("_", " ")}</span>
          <span className="uppercase">{s.languages.join(" ")}</span>
          {s.country && <span>{s.country}</span>}
          {!s.is_demo && <a className="text-accent-2" href={s.url} rel="noopener noreferrer" target="_blank">{s.url} ↗</a>}
        </div>
      </PageHeader>
      <DemoBanner d={d} show={s.is_demo} />
      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Section title={d.common.orientation} note={d.sources.orientationNote}>
          <Panel>
            {s.orientation ? (
              <div className="flex flex-col gap-2 text-sm">
                <p className="font-medium">{s.orientation.simplified.replaceAll("_", " ")} <span className="text-muted font-normal">({d.common.confidence} {s.orientation.confidence.toFixed(2)} · {s.orientation.method} · {s.orientation.review_status})</span></p>
                {Object.keys(s.orientation.dimensions).length > 0 && <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">{Object.entries(s.orientation.dimensions).map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k.replaceAll("_", " ")}</dt><dd>{String(v)}</dd></div>)}</dl>}
                {s.orientation.evidence && <p className="text-muted">{s.orientation.evidence}</p>}
                <ul className="flex flex-col gap-1 text-xs">{s.orientation.evidence_items.map((e) => <li key={e.url}><a className="text-accent-2 break-all" href={e.url} rel="noopener noreferrer" target="_blank">{e.url}</a>{e.note && ` · ${e.note}`}</li>)}</ul>
                {s.orientation_history.length > 1 && <p className="text-xs text-muted">{d.sources.history}: {s.orientation_history.map((o) => `${o.simplified} (${o.valid_from ?? "?"}–${o.valid_to ?? ""})`).join("; ")}</p>}
              </div>
            ) : <p className="text-sm text-muted">{d.common.unknown}</p>}
            {s.ownership && <p className="text-sm mt-3"><span className="text-muted">{d.sources.ownership}:</span> {s.ownership}</p>}
          </Panel>
        </Section>
        <Section title={d.sources.feeds}>
          <Panel>
            <ul className="flex flex-col gap-2 text-sm">
              {s.feeds.map((f) => (
                <li key={f.url} className="flex flex-col"><span className="font-mono text-xs break-all">{f.url}</span>
                  <span className="text-xs text-muted">{f.type} · {f.verified ? `${d.sources.verified} ${f.verified_at ?? ""}` : "unverified"} · {f.active ? f.health_status : d.sources.inactive}{f.notes ? ` · ${f.notes}` : ""}</span></li>
              ))}
              {s.feeds.length === 0 && <li className="text-muted">{d.common.none}</li>}
            </ul>
            <p className="text-xs text-muted mt-3">{d.common.health}: {s.health.status}{s.health.last_success_at ? ` · ${fmtDate(s.health.last_success_at, l)}` : ""} · access: {s.access_policy}</p>
            {s.notes && <p className="text-xs text-muted mt-2">{s.notes}</p>}
          </Panel>
        </Section>
      </div>
      <FilterBar d={d} sp={sp} />
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={`${d.dashboard.timelineTitle} · ${fmtNumber(s.stats.articles, l)}`} className="lg:col-span-2"><Panel><EChart ariaLabel={d.dashboard.timelineTitle} height={220} option={lineSeries(s.stats.series, l === "ar")} /></Panel></Section>
        <Section title={d.common.sentiment}><Panel><EChart ariaLabel={d.common.sentiment} height={220} option={donut(Object.entries(s.stats.sentiment).map(([k, v]) => ({ name: sent[k] ?? k, value: v, color: SENTIMENT_COLORS[k] })))} /></Panel></Section>
      </div>
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Section title={d.common.categories}><Panel><ul className="flex flex-col gap-2 text-sm">{s.stats.categories.map((c) => <li key={c.slug}><div className="flex justify-between"><span className="font-mono text-xs">{c.slug}</span><span className="num text-muted">{c.articles}</span></div><Bar value={c.articles} max={maxC} /></li>)}</ul></Panel></Section>
        <Section title={d.common.frames}><Panel><ul className="flex flex-col gap-2 text-sm">{s.stats.frames.map((f) => <li key={f.slug}><div className="flex justify-between"><span>{pick(l, f.name_en, f.name_ar)}</span><span className="num text-muted">{f.articles}</span></div><Bar value={f.articles} max={maxF} color="var(--accent)" /></li>)}</ul></Panel></Section>
        <Section title={d.common.terminology}><Panel><ul className="flex flex-col gap-1.5 text-sm">{s.stats.terminology.slice(0, 14).map((t) => <li key={`${t.entity}-${t.term}`} title={t.framing_note ?? undefined} className="flex justify-between gap-2"><span dir="auto">{t.term} <span className="text-xs text-muted">· {(d.aliasTypes as Record<string, string>)[t.alias_type] ?? t.alias_type}</span></span><span className="num text-muted">{t.mentions}</span></li>)}</ul></Panel></Section>
      </div>
      <Section title={d.dashboard.latestTitle}><Panel className="!py-1"><ul>{s.recent_articles.map((a) => <ArticleItem key={a.id} a={a} l={l} d={d} />)}</ul></Panel></Section>
    </>
  );
}
