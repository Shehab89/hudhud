import { notFound } from "next/navigation";
import ArticleItem from "@/components/ArticleItem";
import DemoBanner from "@/components/DemoBanner";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { donut, lineSeries } from "@/components/charts/options";
import { BaseBadge, Bar, ContentTypeBadge, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary } from "@/lib/api";
import { fmtDate, fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";
import { COLLECTABLE, L, SCORE_TEXT } from "@/lib/registry";

const SEL = {
  en: { title: "Selection record", why: "Why this source is monitored", audience: "Audience evidence", metric: "Measure", value: "Value", asOf: "As of", src: "Source",
    noAudience: "No citable audience figure recorded.", components: "Score components", reach: "Reach", coverage: "Yemen coverage", regional: "Regional importance",
    cited: "Cited by other media", historical: "Historical importance", camp: "Yemeni camp", sub: "Detail", regionalAl: "Regional alignment", domestic: "Domestic orientation",
    conf: "Confidence", assessed: "Assessed", status: "Review", classification: "Classification", accounts: "Accounts", followers: "followers", collected: "collected",
    notCollected: "registered, not collected (REQUIRES CONFIGURATION)", confirmed: "confirmed by",
    halo: "Regional and historical importance are recorded but not scored for institutional (tier B) sources, so official status cannot raise influence.", archived: "Archived: this source is from an earlier registry and is no longer collected." },
  ar: { title: "سجل الاختيار", why: "لماذا يُرصد هذا المصدر", audience: "أدلة الجمهور", metric: "المقياس", value: "القيمة", asOf: "بتاريخ", src: "المصدر",
    noAudience: "لم يُسجَّل رقم جمهور قابل للاستشهاد.", components: "مكونات الدرجة", reach: "الانتشار", coverage: "تغطية اليمن", regional: "الأهمية الإقليمية",
    cited: "الاستشهاد به في وسائل أخرى", historical: "الأهمية التاريخية", camp: "المعسكر اليمني", sub: "تفصيل", regionalAl: "الانحياز الإقليمي", domestic: "التوجه المحلي",
    conf: "الثقة", assessed: "تاريخ التقييم", status: "المراجعة", classification: "التصنيف", accounts: "الحسابات", followers: "متابع", collected: "يُجمع",
    notCollected: "مسجل ولا يُجمع (يتطلب إعدادًا)", confirmed: "تأكيد من",
    halo: "تُسجَّل الأهمية الإقليمية والتاريخية دون احتسابها للمصادر المؤسسية (الفئة ب)، كي لا ترفع الصفة الرسمية درجة التأثير.", archived: "مؤرشف: هذا المصدر من سجل سابق ولم يعد يُجمع." },
};

interface Orientation { simplified: string; dimensions: Record<string, unknown>; confidence: number; evidence: string | null; method: string;
  valid_from: string | null; valid_to: string | null; last_reviewed: string | null; review_status: string;
  evidence_items: { url: string; type: string | null; note: string | null; accessed_at: string | null }[] }
interface Stats { articles: number; series: { day: string; articles: number }[]; categories: { slug: string; articles: number }[];
  sentiment: Record<string, number>; tone: { tone: string; articles: number }[];
  frames: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
  terminology: { entity: string; entity_name: string; term: string; alias_type: string; framing_note: string | null; mentions: number }[];
  actors: { slug: string; name_en: string; name_ar: string | null; articles: number; mean_targeted_sentiment: number | null }[] }
interface Audience { metric: string; value: number; as_of?: string | null; source_url: string }
interface Selection { reason?: string; audience_evidence?: Audience[];
  influence_evidence?: { regional_importance?: string; cited_by_other_media?: string; historical_importance?: string; note?: string; urls?: string[] };
  yemen_coverage?: { frequency?: string; evidence?: string; urls?: string[] };
  institutional_importance?: { level?: string; note?: string };
  influence_components?: Record<string, unknown> & { indicators?: number; reach?: number; rubric?: string; reason?: string; not_scored?: string[] } }
interface AccountFull { platform: string; handle: string; url: string; handle_evidence?: string; followers?: number | null; followers_as_of?: string | null; followers_source?: string }
interface SourceDetail { note: string; scores_note: string; slug: string; category: string; tier: string | null; region: string | null; platform: string | null;
  content_type: string; registry_status: string; yemen_political_alignment: string; sub_alignment: string | null; regional_alignment: string;
  domestic_political_orientation: string | null; classification_confidence: number | null; assessment_date: string | null;
  influence_score: number | null; institutional_importance: string | null; reliability_score: number | null; selection: Selection;
  accounts: AccountFull[]; holder: { kind?: string; role?: string; affiliation?: string } | null; wikidata: string | null; name: string; name_native: string | null; url: string; country: string | null;
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
  const u = SEL[l], sc = SCORE_TEXT[l], sel = s.selection ?? {}, comp = sel.influence_components ?? {};
  const camp = s.yemen_political_alignment, reg = s.regional_alignment;
  const maxF = Math.max(1, ...s.stats.frames.map((f) => f.articles));
  const maxC = Math.max(1, ...s.stats.categories.map((f) => f.articles));
  return (
    <>
      <PageHeader title={s.name} intro={s.name_native ?? undefined}>
        <div className="flex flex-wrap gap-4 text-sm text-muted">
          <ContentTypeBadge type={s.content_type} l={l} />
          <span>{L.category(s.category, l)}{s.tier ? ` · ${L.tier(s.tier, l)}` : ""}{s.region ? ` · ${L.region(s.region, l)}` : ""}</span>
          {s.region === "yemen" && <BaseBadge base={s.operating_base} d={d} />}
          <span className="uppercase">{s.languages.join(" ")}</span>
          {s.country && <span>{s.country}</span>}
          {!s.is_demo && <a className="text-accent-2" href={s.url} rel="noopener noreferrer" target="_blank">{s.url} ↗</a>}
        </div>
      </PageHeader>
      <DemoBanner d={d} show={s.is_demo} />
      {s.registry_status === "archived" && <p className="mb-6 text-sm text-muted rounded-md border border-line px-3 py-2">{u.archived}</p>}
      <Section title={u.title} note={sc.note} className="mb-8">
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-1 flex flex-col gap-3">
            <div><h3 className="label-caps text-muted mb-1">{u.why}</h3><p className="text-sm">{sel.reason ?? "–"}</p>
              {s.holder?.role && <p className="text-sm text-muted mt-1">{s.holder.role}</p>}</div>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm items-baseline">
              <dt className="text-muted">{sc.influence}</dt>
              <dd className="num font-semibold">{s.influence_score !== null ? `${Math.round(s.influence_score)} ${sc.outOf}` : <span className="font-normal text-muted">{sc.notScored}</span>}</dd>
              <dt className="text-muted">{sc.institutional}</dt>
              <dd>{s.institutional_importance ? L.level(s.institutional_importance, l) : "–"}{sel.institutional_importance?.note ? <span className="block text-xs text-muted">{sel.institutional_importance.note}</span> : null}</dd>
              <dt className="text-muted">{sc.reliability}</dt>
              <dd className="text-muted">{s.reliability_score !== null ? s.reliability_score.toFixed(2) : sc.notAssessed}</dd>
            </dl>
          </Panel>
          <Panel className="flex flex-col gap-3">
            <h3 className="label-caps text-muted">{u.components} <span className="normal-case font-mono">{comp.rubric ?? ""}</span></h3>
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 text-sm">
              {([["reach", u.reach], ["yemen_coverage", u.coverage], ["regional_importance", u.regional], ["cited_by_other_media", u.cited], ["historical_importance", u.historical]] as const).map(([k, label]) => (
                <div key={k} className="contents"><dt className="text-muted">{label}</dt><dd className="num">{comp[k] !== undefined ? String(comp[k]) : "–"}</dd></div>))}
            </dl>
            {comp.reason && <p className="text-xs text-muted">{sc.notScored} ({comp.reason})</p>}
            {comp.not_scored?.length ? <p className="text-xs text-muted">{u.halo}</p> : null}
            {sel.yemen_coverage?.frequency && <p className="text-xs text-muted">{u.coverage}: {L.frequency(sel.yemen_coverage.frequency, l)}{sel.yemen_coverage.evidence ? `. ${sel.yemen_coverage.evidence}` : ""}</p>}
            {sel.influence_evidence?.note && <p className="text-xs text-muted">{sel.influence_evidence.note}</p>}
            {[...(sel.influence_evidence?.urls ?? []), ...(sel.yemen_coverage?.urls ?? [])].map((x) => <a key={x} href={x} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-2 break-all">{x}</a>)}
          </Panel>
          <Panel className="flex flex-col gap-2 min-w-0">
            <h3 className="label-caps text-muted">{u.audience}</h3>
            {(sel.audience_evidence ?? []).length ? (
              <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-xs text-muted text-start"><th className="text-start font-normal">{u.metric}</th><th className="text-end font-normal">{u.value}</th><th className="text-end font-normal">{u.asOf}</th></tr></thead>
                <tbody>{(sel.audience_evidence ?? []).map((a, i) => (
                  <tr key={i} className="border-t border-line"><td className="py-1"><a href={a.source_url} target="_blank" rel="noopener noreferrer" className="text-accent-2 hover:underline">{L.metric(a.metric, l)} ↗</a></td>
                    <td className="py-1 text-end num">{fmtNumber(a.value, l)}</td><td className="py-1 text-end text-xs text-muted num">{a.as_of ?? ""}</td></tr>))}</tbody></table></div>
            ) : <p className="text-sm text-muted">{u.noAudience}</p>}
            {s.accounts.length > 0 && (
              <div className="flex flex-col gap-1 mt-2"><h3 className="label-caps text-muted">{u.accounts}</h3>
                <ul className="flex flex-col gap-1 text-sm">{s.accounts.map((a) => (
                  <li key={a.url} className="flex flex-col"><a href={a.url} target="_blank" rel="noopener noreferrer" className="text-accent-2 hover:underline">{L.platform(a.platform, l)} @{a.handle}</a>
                    <span className="text-xs text-muted">{a.followers ? `${fmtNumber(a.followers, l)} ${u.followers}${a.followers_as_of ? ` (${a.followers_as_of})` : ""} · ` : ""}{COLLECTABLE.has(a.platform) ? u.collected : u.notCollected}{a.handle_evidence ? <> · <a href={a.handle_evidence} target="_blank" rel="noopener noreferrer" className="underline">{u.confirmed}</a></> : null}</span></li>))}</ul></div>
            )}
          </Panel>
        </div>
      </Section>
      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Section title={u.classification} note={d.sources.orientationNote}>
          <Panel>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm mb-3">
              <dt className="text-muted">{u.camp}</dt><dd>{L.yemen(camp, l)}</dd>
              {s.sub_alignment && <><dt className="text-muted">{u.sub}</dt><dd>{s.sub_alignment}</dd></>}
              <dt className="text-muted">{u.regionalAl}</dt><dd>{L.regional(reg, l)}</dd>
              {s.domestic_political_orientation && <><dt className="text-muted">{u.domestic}</dt><dd>{s.domestic_political_orientation.replaceAll("_", " ")}</dd></>}
              {s.classification_confidence !== null && <><dt className="text-muted">{u.conf}</dt><dd className="num">{s.classification_confidence.toFixed(2)}</dd></>}
              {s.assessment_date && <><dt className="text-muted">{u.assessed}</dt><dd className="num">{s.assessment_date}</dd></>}
            </dl>
            {s.orientation ? (
              <div className="flex flex-col gap-2 text-sm">
                <p className="font-medium">{s.orientation.simplified.replaceAll("_", " ")} <span className="text-muted font-normal">({d.common.confidence} {s.orientation.confidence.toFixed(2)} · {s.orientation.method} · {s.orientation.review_status})</span></p>
                
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
