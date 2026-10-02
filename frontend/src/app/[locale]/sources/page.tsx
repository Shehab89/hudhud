import Link from "next/link";
import FilterBar from "@/components/FilterBar";
import { BaseBadge, DemoBadge, PageHeader, Panel } from "@/components/ui";
import { filterQuery, tryApi } from "@/lib/api";
import { fmtNumber } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Sources" };

interface Src { slug: string; name: string; name_native: string | null; country: string | null; source_type: string; source_group: string;
  operating_base: string; languages: string[]; active: boolean; is_demo: boolean; health_status: string;
  orientation: { simplified: string; confidence: number; method: string } | null; articles: number }

export default async function SourcesPage(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const group = one(sp.group);
  const data = await tryApi<{ sources: Src[] }>(`/sources${filterQuery(sp, { group })}`);
  const groups = new Map<string, Src[]>();
  for (const s of data?.sources ?? []) groups.set(s.source_group, [...(groups.get(s.source_group) ?? []), s]);
  return (
    <>
      <PageHeader title={d.sources.title} intro={d.sources.intro}>
        <p className="text-sm text-muted max-w-3xl">{d.sources.orientationNote}</p>
        <Link href={`/${l}/sources/compare`} className="text-sm text-accent-2">{d.sources.compare} →</Link>
      </PageHeader>
      <FilterBar d={d} sp={sp} keep={["group"]} />
      <div className="flex flex-col gap-8">
        {[...groups.entries()].map(([g, list]) => (
          <section key={g} className="flex flex-col gap-2">
            <h2 className="text-lg font-semibold">{g.replaceAll("_", " ")} <span className="text-sm text-muted num">({fmtNumber(list.length, l)})</span></h2>
            <Panel className="!p-0 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-muted text-xs text-start">
                  <tr className="border-b border-line">
                    <th className="text-start p-2.5 font-medium">{d.common.source}</th>
                    <th className="text-start p-2.5 font-medium">{d.common.operatingBase}</th>
                    <th className="text-start p-2.5 font-medium">{d.common.languages}</th>
                    <th className="text-start p-2.5 font-medium">{d.common.orientation}</th>
                    <th className="text-start p-2.5 font-medium">{d.common.health}</th>
                    <th className="text-end p-2.5 font-medium">{d.common.articles}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((s) => (
                    <tr key={s.slug} className="border-b border-line last:border-0">
                      <td className="p-2.5"><Link className="font-medium hover:underline" href={`/${l}/sources/${s.slug}`}>{s.name}</Link>
                        {s.name_native && <span className="block text-xs text-muted" dir="auto">{s.name_native}</span>}
                        {s.is_demo && <DemoBadge d={d} />}</td>
                      <td className="p-2.5"><BaseBadge base={s.operating_base} d={d} /></td>
                      <td className="p-2.5 uppercase text-xs">{s.languages.join(" ")}</td>
                      <td className="p-2.5 text-xs">{s.orientation ? <>{s.orientation.simplified.replaceAll("_", " ")} <span className="text-muted">({s.orientation.confidence.toFixed(2)})</span></> : <span className="text-muted">{d.common.unknown}</span>}</td>
                      <td className="p-2.5 text-xs">{s.active ? s.health_status : d.sources.inactive}</td>
                      <td className="p-2.5 text-end num">{fmtNumber(s.articles, l)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </section>
        ))}
      </div>
    </>
  );
}
