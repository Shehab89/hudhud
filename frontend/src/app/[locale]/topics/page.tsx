import Link from "next/link";
import FilterBar from "@/components/FilterBar";
import { Bar, Empty, PageHeader, Panel, Section } from "@/components/ui";
import { filterQuery, tryApi, type SearchParams, type Trend } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Topics" };

interface Cats { categories: { id: number; slug: string; name_en: string; name_ar: string | null; count: number; children: { slug: string; name_en: string; name_ar: string | null; count: number }[] }[] }
interface Topics { model: { algorithm: string; metrics: Record<string, number>; documents: number } | null; note?: string;
  topics: { id: number; label: string; label_ar: string | null; label_method: string; terms: [string, number][]; size: number; count: number; quality: { weak?: boolean; coherence_npmi?: number } }[] }

export default async function TopicsPage(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const fq = filterQuery(sp as SearchParams);
  const [cats, topics, trends] = await Promise.all([
    tryApi<Cats>(`/categories${fq}`), tryApi<Topics>(`/topics${fq}`), tryApi<Trend[]>(`/trends?limit=30`),
  ]);
  const trendBy = new Map((trends ?? []).map((t) => [t.slug, t]));
  const maxCat = Math.max(1, ...(cats?.categories ?? []).map((c) => c.count));
  const maxTopic = Math.max(1, ...(topics?.topics ?? []).map((t) => t.count));
  return (
    <>
      <PageHeader title={d.topics.title} intro={d.topics.intro} />
      <FilterBar d={d} sp={sp} />
      <div className="grid gap-8 lg:grid-cols-2">
        <Section title={d.topics.curated}>
          <Panel>
            {cats?.categories.length ? (
              <ul className="flex flex-col gap-4">
                {cats.categories.filter((c) => c.count > 0).map((c) => {
                  const t = trendBy.get(c.slug);
                  return (
                    <li key={c.slug} className="flex flex-col gap-1">
                      <div className="flex justify-between gap-3">
                        <Link className="font-medium hover:underline" href={`/${l}/topics/category/${c.slug}`}>{pick(l, c.name_en, c.name_ar)}</Link>
                        <span className="text-xs text-muted num">{fmtNumber(c.count, l)}{t && ` · ${(d.trend as Record<string, string>)[t.status]}`}</span>
                      </div>
                      <Bar value={c.count} max={maxCat} />
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
                        {c.children.filter((x) => x.count > 0).slice(0, 6).map((x) => (
                          <Link key={x.slug} className="hover:underline" href={`/${l}/topics/category/${x.slug}`}>{pick(l, x.name_en, x.name_ar)} <span className="num">{fmtNumber(x.count, l)}</span></Link>
                        ))}
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : <Empty d={d} />}
          </Panel>
        </Section>
        <Section title={d.topics.discovered}
          note={topics?.model ? `${d.topics.model}: ${topics.model.algorithm} · ${fmtNumber(topics.model.documents, l)} docs · ${d.topics.coherence} ${topics.model.metrics.mean_coherence_npmi ?? "–"} · ${d.topics.diversity} ${topics.model.metrics.diversity ?? "–"}` : topics?.note}>
          <Panel>
            {topics?.topics.length ? (
              <ul className="flex flex-col gap-4">
                {topics.topics.map((t) => (
                  <li key={t.id} className="flex flex-col gap-1">
                    <div className="flex justify-between gap-3">
                      <Link className="font-medium hover:underline" dir="auto" href={`/${l}/topics/${t.id}`}>{pick(l, t.label, t.label_ar)}</Link>
                      <span className="text-xs text-muted num">{fmtNumber(t.count, l)}{t.quality?.weak ? ` · ${d.topics.weak}` : ""}</span>
                    </div>
                    <Bar value={t.count} max={maxTopic} color="var(--accent)" />
                    <p className="text-xs text-muted" dir="auto">{t.terms.slice(0, 8).map(([w]) => w).join(" · ")}</p>
                  </li>
                ))}
              </ul>
            ) : <Empty d={d} />}
          </Panel>
        </Section>
      </div>
    </>
  );
}
