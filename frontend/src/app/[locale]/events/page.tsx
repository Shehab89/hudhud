import Link from "next/link";
import FilterBar from "@/components/FilterBar";
import { Empty, PageHeader, Panel } from "@/components/ui";
import { filterQuery, tryApi } from "@/lib/api";
import { fmtDate, fmtNumber, pick } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Events" };

interface Ev { id: number; type: string; date: string; title: string | null; confidence: number; reports: number; sources: number;
  location: { slug: string; name_en: string; name_ar: string | null } | null }
interface EvDetail { id: number; type: string; date: string; confidence: number; method: string;
  actors: { slug: string; name_en: string; name_ar: string | null; mentions: number }[];
  reports_list: { article: { id: number; title: string; source: { name: string } }; evidence_sentence: string | null; trigger: string | null }[] }

export default async function EventsPage(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const type = one(sp.event_type);
  const sel = one(sp.event);
  const [data, detail] = await Promise.all([
    tryApi<{ note: string; total: number; types: Record<string, number>; items: Ev[] }>(`/events${filterQuery(sp, { event_type: type, limit: 100 })}`),
    sel ? tryApi<EvDetail>(`/events/${encodeURIComponent(sel)}`) : Promise.resolve(null),
  ]);
  const byDay = new Map<string, Ev[]>();
  for (const e of data?.items ?? []) byDay.set(e.date, [...(byDay.get(e.date) ?? []), e]);
  return (
    <>
      <PageHeader title={d.events.title} intro={d.events.intro}>
        <nav className="flex flex-wrap gap-2 text-sm">
          <Link href="?" className={`rounded-full border px-3 py-0.5 ${!type ? "border-accent" : "border-line"}`}>{d.common.all}</Link>
          {Object.entries(data?.types ?? {}).sort((a, b) => b[1] - a[1]).map(([t, n]) => (
            <Link key={t} href={`?event_type=${t}`} className={`rounded-full border px-3 py-0.5 ${type === t ? "border-accent" : "border-line"}`}>{t.replaceAll("_", " ")} <span className="text-muted num">{n}</span></Link>
          ))}
        </nav>
      </PageHeader>
      <FilterBar d={d} sp={sp} keep={["event_type"]} />
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Panel>
          {byDay.size ? (
            <ol className="flex flex-col gap-5 border-s border-line ps-4">
              {[...byDay.entries()].map(([day, evs]) => (
                <li key={day} className="relative">
                  <span className="absolute -start-[1.4rem] top-1 size-2.5 rounded-full bg-accent" aria-hidden />
                  <h2 className="text-sm font-semibold num mb-1">{fmtDate(day, l, { weekday: "short", day: "numeric", month: "short" })}</h2>
                  <ul className="flex flex-col gap-1 text-sm">
                    {evs.map((e) => (
                      <li key={e.id}><Link href={`?${new URLSearchParams({ event: String(e.id), ...(type ? { event_type: type } : {}) })}`} className="hover:underline">
                        <span className="font-medium">{e.type.replaceAll("_", " ")}</span>{e.location && <> · {pick(l, e.location.name_en, e.location.name_ar)}</>}</Link>
                        <span className="text-xs text-muted num"> · {fmtNumber(e.reports, l)} {d.events.reports} · {fmtNumber(e.sources, l)} {d.events.outlets} · {e.confidence.toFixed(2)}</span></li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ) : <Empty d={d} />}
        </Panel>
        <div>
          {detail ? (
            <Panel className="sticky top-24 flex flex-col gap-3">
              <h2 className="font-semibold">{detail.type.replaceAll("_", " ")} · <span className="num">{fmtDate(detail.date, l)}</span></h2>
              <p className="text-xs text-muted">{d.common.method}: {detail.method} · {d.common.confidence} {detail.confidence.toFixed(2)}</p>
              <ul className="flex flex-wrap gap-1.5">{detail.actors.map((a) => <li key={a.slug}><Link className="text-xs rounded-full border border-line px-2 py-0.5" href={`/${l}/actors/${a.slug}`}>{pick(l, a.name_en, a.name_ar)}</Link></li>)}</ul>
              <ul className="flex flex-col gap-3 text-sm">{detail.reports_list.map((r) => (
                <li key={r.article.id}><Link className="font-medium hover:underline" href={`/${l}/news/${r.article.id}`} dir="auto">{r.article.title}</Link>
                  <span className="text-xs text-muted"> · {r.article.source.name}</span>
                  {r.evidence_sentence && <p className="text-muted text-xs border-s-2 border-line ps-2 mt-1" dir="auto">“{r.evidence_sentence}”</p>}</li>))}</ul>
            </Panel>
          ) : <p className="text-sm text-muted">{data?.note}</p>}
        </div>
      </div>
    </>
  );
}
