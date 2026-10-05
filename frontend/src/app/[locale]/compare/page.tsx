import Link from "next/link";
import ArticleItem from "@/components/ArticleItem";
import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { groupedBars, multiLine } from "@/components/charts/options";
import { ContentTypeBadge, Empty, PageHeader, Panel, SENTIMENT_COLORS, Section } from "@/components/ui";
import { filterQuery, tryApi, type ArticleSummary } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";
import { L } from "@/lib/registry";

export const metadata = { title: "Compare voices" };

type T = { en: string; ar: string };
interface Preset { key: string; title: T; groups: { key: string; label: T }[] }
interface GroupStats {
  key: string; label: T; source_count: number; collected_sources: number; demo_sources: number; content_types: Record<string, number>; articles: number;
  sources: { slug: string; name: string; category: string; content_type: string; active: boolean }[];
  series?: { day: string; articles: number }[]; sentiment?: Record<string, number>; tone?: { tone: string; articles: number }[];
  categories?: { slug: string; name_en?: string; name_ar?: string | null; articles: number }[]; frames?: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
  actors?: { slug: string; name_en: string; name_ar: string | null; articles: number; mean_targeted_sentiment: number | null }[];
  places?: { slug: string; name_en: string; name_ar: string | null; articles: number }[];
  terminology?: { term: string; alias_type: string; mentions: number }[]; events?: { event_type: string; events: number }[];
}
interface Comparison { preset: string; title: T; note: string; groups: GroupStats[];
  shared_stories: { story_cluster_id: number; headlines: Record<string, ArticleSummary> }[] }

const PALETTE = ["var(--accent-2)", "var(--accent)", "var(--base-sanaa)", "var(--base-stc)", "var(--base-outside)", "var(--base-gov)"];
const CAMP_COLORS: Record<string, string> = { plc: "var(--base-gov)", ansar_allah: "var(--base-sanaa)", stc: "var(--base-stc)" };

const UI = {
  en: { title: "Compare voices", intro: "Put groups of sources side by side: media and official statements, Yemeni camps, foreign governments, and international media against diplomacy. Each group is measured on what its sources published in the period you choose.",
    pick: "Comparison", source: "source", sources: "sources", collected: "collected", empty: "No sources in this group yet.", noItems: "No collected items in this period. Some sources in this group publish only on platforms that are not collected yet.",
    volume: "Volume over time", frames: "Framing (share of each group's items)", topics: "Topics", actors: "Actors named", places: "Places named", terms: "Terms used", tone: "Tone", sentiment: "Sentiment",
    shared: "The same stories, told by each group", sharedNote: "Stories that every group reported in this period, with one headline from each.", noShared: "No story was reported by every group in this period.",
    members: "Sources in this group", mix: "Content", targeted: "mean sentence tone towards the actor" },
  ar: { title: "مقارنة الأصوات", intro: "ضع مجموعات المصادر جنبًا إلى جنب: الإعلام والبيانات الرسمية، والمعسكرات اليمنية، والحكومات الأجنبية، والإعلام الدولي مقابل الدبلوماسية. تُقاس كل مجموعة بما نشرته مصادرها في الفترة التي تختارها.",
    pick: "المقارنة", source: "مصدر", sources: "مصادر", collected: "يُجمع", empty: "لا توجد مصادر في هذه المجموعة بعد.", noItems: "لا توجد مواد مجمّعة في هذه الفترة. بعض مصادر هذه المجموعة تنشر فقط على منصات لا تُجمع بعد.",
    volume: "الحجم عبر الزمن", frames: "الأطر (نسبة مواد كل مجموعة)", topics: "المواضيع", actors: "الأطراف المذكورة", places: "الأماكن المذكورة", terms: "المصطلحات المستخدمة", tone: "النبرة", sentiment: "المشاعر",
    shared: "القصص نفسها كما روتها كل مجموعة", sharedNote: "قصص غطتها كل المجموعات في هذه الفترة، مع عنوان واحد من كل مجموعة.", noShared: "لم تغطِّ كل المجموعات أي قصة واحدة في هذه الفترة.",
    members: "مصادر هذه المجموعة", mix: "نوع المحتوى", targeted: "متوسط نبرة الجمل تجاه الطرف" },
};

function TopList({ items, max }: { items: { key: string; label: string; n: number; extra?: string }[]; max?: number }) {
  const top = Math.max(1, ...items.map((i) => i.n));
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {items.slice(0, max ?? 6).map((i) => (
        <li key={i.key} className="flex flex-col gap-0.5">
          <span className="flex justify-between gap-2"><span className="truncate" dir="auto">{i.label}{i.extra ? <span className="text-xs text-muted"> {i.extra}</span> : null}</span><span className="num text-muted">{i.n}</span></span>
          <span className="h-1 rounded bg-surface-2" aria-hidden><span className="block h-1 rounded bg-accent-2" style={{ width: `${(i.n / top) * 100}%` }} /></span>
        </li>
      ))}
      {items.length === 0 && <li className="text-muted">–</li>}
    </ul>
  );
}

export default async function ComparePage(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const u = UI[l];
  const presets = (await tryApi<{ presets: Preset[] }>("/compare/presets"))?.presets ?? [];
  const key = one(sp.preset) || presets[0]?.key || "yemeni-camps";
  const demo = one(sp.demo) || "exclude";
  const data = await tryApi<Comparison>(`/compare/groups${filterQuery({ ...sp, demo }, { preset: key })}`);
  const color = (g: string, i: number) => (key === "yemeni-camps" && CAMP_COLORS[g]) || PALETTE[i % PALETTE.length];
  const sent = d.sentiment as Record<string, string>;

  const days = data ? [...new Set(data.groups.flatMap((g) => (g.series ?? []).map((p) => p.day.slice(0, 10))))].sort() : [];
  const frameKeys = data ? [...new Set(data.groups.flatMap((g) => (g.frames ?? []).slice(0, 6).map((f) => f.slug)))] : [];
  const frameName = (slug: string) => { for (const g of data?.groups ?? []) { const f = g.frames?.find((x) => x.slug === slug); if (f) return pick(l, f.name_en, f.name_ar); } return slug; };

  return (
    <>
      <PageHeader title={u.title} intro={u.intro} />
      <nav aria-label={u.pick} className="flex flex-wrap gap-2 mb-5">
        {presets.map((p) => (
          <Link key={p.key} href={`/${l}/compare${filterQuery(sp, { preset: p.key })}`} aria-current={p.key === key ? "page" : undefined}
            className={`rounded-lg border px-3 py-2 text-sm ${p.key === key ? "border-accent bg-accent text-accent-ink" : "border-line bg-surface hover:border-accent-2"}`}>{p.title[l]}</Link>
        ))}
      </nav>
      <FilterBar d={d} sp={{ ...sp, demo }} keep={["preset"]} />
      {!data ? <Empty d={d} /> : (
        <div className="flex flex-col gap-8">
          <p className="text-sm text-muted max-w-3xl">{data.note}</p>
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 17rem), 1fr))" }}>
            {data.groups.map((g, i) => {
              const total = Object.values(g.sentiment ?? {}).reduce((a, b) => a + b, 0) || 1;
              return (
                <Panel key={g.key} className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1">
                    <h2 className="font-semibold flex items-center gap-2"><span aria-hidden className="inline-block size-2.5 rounded-full" style={{ background: color(g.key, i) }} />{g.label[l] ?? g.label.en}</h2>
                    <p className="text-sm"><span className="num font-semibold">{fmtNumber(g.articles, l)}</span> <span className="text-muted">{d.common.articles.toLowerCase()} · <span className="num">{g.source_count}</span> {g.source_count === 1 ? u.source : u.sources}{g.demo_sources === g.source_count && g.source_count > 0 ? <> · <span className="text-demo font-semibold">{d.site.demoBadge}</span></> : <> (<span className="num">{g.collected_sources}</span> {u.collected})</>}</span></p>
                    <div className="flex flex-wrap gap-1">{Object.entries(g.content_types).map(([k, n]) => <span key={k} className="inline-flex items-center gap-1 text-xs"><ContentTypeBadge type={k} l={l} />{k === "journalism" ? <span className="text-muted">{L.contentType(k, l)}</span> : null}<span className="num text-muted">{n}</span></span>)}</div>
                  </div>
                  {g.source_count === 0 ? <p className="text-sm text-muted">{u.empty}</p> : g.articles === 0 ? <p className="text-sm text-muted">{u.noItems}</p> : (
                    <>
                      <div><h3 className="label-caps text-muted mb-1">{u.sentiment}</h3>
                        <div className="flex h-2 rounded overflow-hidden" role="img" aria-label={Object.entries(g.sentiment ?? {}).map(([k, v]) => `${sent[k] ?? k} ${v}`).join(", ")}>
                          {Object.entries(g.sentiment ?? {}).map(([k, v]) => <span key={k} title={`${sent[k] ?? k} ${v}`} style={{ width: `${(v / total) * 100}%`, background: SENTIMENT_COLORS[k] }} />)}</div></div>
                      <div><h3 className="label-caps text-muted mb-1">{u.topics}</h3><TopList items={(g.categories ?? []).map((c) => ({ key: c.slug, label: c.name_en ? pick(l, c.name_en, c.name_ar ?? null) : c.slug.replaceAll("-", " "), n: c.articles }))} max={5} /></div>
                      <div><h3 className="label-caps text-muted mb-1">{u.actors}</h3><TopList items={(g.actors ?? []).map((a) => ({ key: a.slug, label: pick(l, a.name_en, a.name_ar), n: a.articles, extra: a.mean_targeted_sentiment !== null ? `(${a.mean_targeted_sentiment > 0 ? "+" : ""}${a.mean_targeted_sentiment.toFixed(2)})` : undefined }))} max={5} /></div>
                      <div><h3 className="label-caps text-muted mb-1">{u.places}</h3><TopList items={(g.places ?? []).map((p) => ({ key: p.slug, label: pick(l, p.name_en, p.name_ar), n: p.articles }))} max={5} /></div>
                      <div><h3 className="label-caps text-muted mb-1">{u.terms}</h3><TopList items={(g.terminology ?? []).map((t) => ({ key: t.term, label: t.term, n: t.mentions }))} max={5} /></div>
                    </>
                  )}
                  {g.sources.length > 0 && (
                    <details className="text-sm"><summary className="cursor-pointer text-accent-2">{u.members} ({g.sources.length})</summary>
                      <ul className="mt-2 flex flex-col gap-1">{g.sources.map((s) => <li key={s.slug} className="flex justify-between gap-2"><Link href={`/${l}/sources/${s.slug}`} className="hover:underline truncate">{s.name}</Link><span className="text-xs text-muted shrink-0">{L.category(s.category, l)}</span></li>)}</ul></details>
                  )}
                </Panel>
              );
            })}
          </div>
          {days.length > 1 && (
            <Section title={u.volume}><Panel><EChart ariaLabel={u.volume} height={260} option={multiLine(days, data.groups.map((g, i) => {
              const m = new Map((g.series ?? []).map((p) => [p.day.slice(0, 10), p.articles]));
              return { name: g.label[l] ?? g.label.en, data: days.map((x) => m.get(x) ?? 0), color: color(g.key, i) };
            }), l === "ar")} /></Panel></Section>
          )}
          {frameKeys.length > 0 && (
            <Section title={u.frames}><Panel><EChart ariaLabel={u.frames} height={Math.max(220, frameKeys.length * 38)} option={groupedBars(frameKeys.map(frameName), data.groups.map((g, i) => ({
              name: g.label[l] ?? g.label.en, color: color(g.key, i),
              data: frameKeys.map((k) => (g.articles ? (g.frames?.find((f) => f.slug === k)?.articles ?? 0) / g.articles : 0)),
            })), { percent: true, rtl: l === "ar" })} /></Panel></Section>
          )}
          <Section title={u.shared} note={u.sharedNote}>
            {data.shared_stories.length === 0 ? <p className="text-sm text-muted">{u.noShared}</p> : (
              <div className="flex flex-col gap-4">
                {data.shared_stories.map((st) => (
                  <Panel key={st.story_cluster_id} className="grid gap-x-6 gap-y-2" >
                    <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 15rem), 1fr))" }}>
                      {data.groups.map((g, i) => st.headlines[g.key] && (
                        <div key={g.key} className="min-w-0 flex flex-col gap-1">
                          <span className="label-caps flex items-center gap-1.5" style={{ color: color(g.key, i) }}><span aria-hidden className="inline-block size-2 rounded-full" style={{ background: color(g.key, i) }} />{g.label[l] ?? g.label.en}</span>
                          <ul><ArticleItem a={st.headlines[g.key]} l={l} d={d} /></ul>
                        </div>
                      ))}
                    </div>
                  </Panel>
                ))}
              </div>
            )}
          </Section>
        </div>
      )}
    </>
  );
}
