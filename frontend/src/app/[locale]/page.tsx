import Link from "next/link";
import DemoBanner from "@/components/DemoBanner";
import { tryApi, type Overview } from "@/lib/api";
import { fmtDate, fmtNumber } from "@/lib/i18n";
import { MODULES, num2, t } from "@/lib/modules";
import { setup, type PageProps } from "@/lib/page";
import { CATEGORY_ORDER, L } from "@/lib/registry";

const COPY = {
  en: { hero: "How is Yemen being covered, and by whom?", sub: "A multilingual, evidence-based tool for tracking media coverage of Yemen: who reports, in which language, with which words and frames. It describes coverage. It does not rank actors or say what is true.",
    scroll: "Scroll down to select a module", snapshot: "Latest daily summary", discover: "Discover", metrics: "At a glance (last 30 days)",
    measures: "Five measures, never merged into one score", registry: "curated sources", live: "collected now",
    mA: ["A", "Source orientation", "Who the outlet is, with evidence"], mB: ["B", "Sentiment", "Tone of one article"], mC: ["C", "Framing", "How an issue is presented"],
    mD: ["D", "Topic", "What it is about"], mE: ["E", "Actor-targeted sentiment", "How sentences naming an actor read"], noRun: "No pipeline run recorded yet." },
  ar: { hero: "كيف تُغطّى اليمن، ومن يغطيها؟", sub: "أداة متعددة اللغات قائمة على الأدلة لرصد التغطية الإعلامية لليمن: من ينشر وبأي لغة وبأي كلمات وأطر. هي تصف التغطية ولا تصنّف الأطراف ولا تحكم بما هو صحيح.",
    scroll: "مرّر للأسفل لاختيار وحدة", snapshot: "آخر ملخص يومي", discover: "استكشف", metrics: "نظرة سريعة (آخر ٣٠ يومًا)",
    measures: "خمسة مقاييس منفصلة لا تُدمج في درجة واحدة", registry: "مصدرًا منتقى", live: "تُجمع حاليًا",
    mA: ["أ", "توجه المصدر", "من هو المنفذ، مع الأدلة"], mB: ["ب", "المشاعر", "نبرة مقال واحد"], mC: ["ج", "التأطير", "كيف تُعرض القضية"],
    mD: ["د", "الموضوع", "عمّ يتحدث"], mE: ["هـ", "المشاعر تجاه الأطراف", "كيف تُقرأ الجمل التي تذكر طرفًا"], noRun: "لا توجد عملية معالجة مسجلة بعد." },
};

export default async function Home(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const c = COPY[l];
  const [ov, src] = await Promise.all([
    tryApi<Overview>("/overview"),
    tryApi<{ count: number; sources: { active: boolean; articles: number; category: string; feeds: number }[] }>("/sources?demo=exclude"),
  ]);
  const total = src?.count ?? 0;
  const registry = src?.sources.filter((s) => s.active && s.feeds > 0).length ?? 0;
  const byCat = new Map<string, number>();
  for (const s of src?.sources ?? []) byCat.set(s.category, (byCat.get(s.category) ?? 0) + 1);
  const metrics: [string, number | undefined][] = [
    [d.common.articles, ov?.current.articles], [d.common.stories, ov?.current.unique_stories],
    [d.common.sources, registry], [d.common.languages, ov?.current.languages],
  ];
  void sp;
  return (
    <>
      <section className="rounded-xl border border-line bg-surface px-6 py-10 md:py-14 mb-8 relative overflow-hidden">
        <div aria-hidden className="absolute inset-y-0 end-0 w-1/3 opacity-[0.07] bg-[radial-gradient(circle_at_70%_40%,var(--accent),transparent_65%)]" />
        <p className="label-caps text-accent mb-3">{d.site.name}</p>
        <h1 className="text-3xl md:text-5xl font-semibold tracking-tight max-w-3xl text-balance">{c.hero}</h1>
        <p className="mt-4 text-muted max-w-2xl leading-relaxed">{c.sub}</p>
        <a href="#modules" className="mt-6 inline-flex items-center gap-2 text-sm text-accent-2">{c.scroll} <span aria-hidden>↓</span></a>
      </section>

      <DemoBanner d={d} show={!!ov?.contains_demo} />

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr] mb-10">
        <div className="rounded-lg border border-line bg-surface p-5">
          <h2 className="label-caps text-muted mb-3">{c.metrics}</h2>
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {metrics.map(([k, v]) => (
              <div key={k}><dt className="text-xs text-muted">{k}</dt>
                <dd className="text-3xl font-semibold num">{v === undefined ? "–" : fmtNumber(v, l)}</dd></div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted">
            <span className="num">{fmtNumber(total, l)}</span> {c.registry} · <span className="num">{fmtNumber(registry, l)}</span> {c.live}
          </p>
          {byCat.size > 0 && (
            <p className="mt-1 text-xs text-muted">
              {CATEGORY_ORDER.filter((k) => byCat.get(k)).map((k, i) => <span key={k}>{i ? " · " : ""}<span className="num">{fmtNumber(byCat.get(k) ?? 0, l)}</span> {L.category(k, l)}</span>)}
            </p>
          )}
        </div>
        <div className="rounded-lg border border-line bg-surface p-5">
          <h2 className="label-caps text-muted mb-2">{c.snapshot}</h2>
          {ov?.summary?.[l]?.content ? (
            <>
              <p className="text-xs text-muted num mb-1">{fmtDate(ov.summary[l].day, l)}</p>
              <p className="text-sm leading-relaxed line-clamp-5">{ov.summary[l].content}</p>
            </>
          ) : <p className="text-sm text-muted">{d.common.noData}</p>}
          <p className="mt-3 text-xs text-muted">
            {ov?.last_pipeline_run ? <>{d.dashboard.lastRun}: <span className="num">{fmtDate(ov.last_pipeline_run.started_at, l, { dateStyle: "medium", timeStyle: "short" })}</span> · {ov.last_pipeline_run.status}</> : c.noRun}
          </p>
        </div>
      </div>

      <section id="modules" className="scroll-mt-32 mb-12">
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 list-none p-0">
          {MODULES.map((m) => (
            <li key={m.key} className="rounded-lg border border-line bg-surface p-5 flex flex-col gap-3 hover:border-accent transition-colors">
              <span className="num text-4xl font-semibold text-accent leading-none">{num2(m.n, l)}</span>
              <h2 className="text-lg font-semibold">{t(m.title, l)}</h2>
              <p className="text-sm text-muted leading-relaxed flex-1">{t(m.blurb, l)}</p>
              <Link href={`/${l}${m.href}`} className="text-sm font-medium text-accent-2 hover:underline">{c.discover} →</Link>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-lg border border-line p-5">
        <h2 className="text-lg font-semibold mb-3">{c.measures}</h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[c.mA, c.mB, c.mC, c.mD, c.mE].map(([k, n, s]) => (
            <li key={k} className="flex gap-2.5"><span className="size-6 shrink-0 rounded bg-surface-2 text-xs font-semibold grid place-items-center">{k}</span>
              <span><span className="block text-sm font-medium">{n}</span><span className="block text-xs text-muted">{s}</span></span></li>
          ))}
        </ul>
        <Link href={`/${l}/methodology`} className="mt-4 inline-block text-sm text-accent-2">{d.nav.methodology} →</Link>
      </section>
    </>
  );
}
