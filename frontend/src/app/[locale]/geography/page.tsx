import EChart from "@/components/EChart";
import FilterBar from "@/components/FilterBar";
import { choropleth } from "@/components/charts/options";
import { Empty, PageHeader, Panel, Section } from "@/components/ui";
import { filterQuery, tryApi } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Geography" };

interface Place { slug: string; name_en: string; name_ar: string | null; type: string; admin_code: string | null; lat: number | null; lon: number | null;
  articles: number; articles_including_places: number; events: number; event_types: Record<string, number> }

export default async function Geography(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const g = await tryApi<{ note: string; governorates: Place[]; places: Place[] }>(`/geography${filterQuery(sp)}`);
  const govs = (g?.governorates ?? []).sort((a, b) => b.articles_including_places - a.articles_including_places);
  return (
    <>
      <PageHeader title={d.geography.title} intro={d.geography.intro}><p className="text-sm text-muted">{g?.note}</p></PageHeader>
      <FilterBar d={d} sp={sp} />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Panel>
          {g ? <EChart ariaLabel={d.geography.title} height={520} mapGeoUrl="/geo/yemen-adm1.json"
            option={choropleth(govs.filter((x) => x.admin_code).map((x) => ({ code: x.admin_code as string, name: pick(l, x.name_en, x.name_ar), value: x.articles_including_places })),
              g.places.filter((p) => p.lat !== null && p.lon !== null).map((p) => ({ name: pick(l, p.name_en, p.name_ar), lat: p.lat as number, lon: p.lon as number, value: p.articles })),
              d.geography.articles)} /> : <Empty d={d} />}
          <p className="text-xs text-muted mt-2">Boundaries: Natural Earth (public domain), simplified. Socotra is drawn within Hadramawt in this dataset.</p>
        </Panel>
        <Section title={d.geography.articles}>
          <Panel className="!p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-xs text-muted"><th className="text-start p-2">{d.common.location}</th><th className="text-end p-2">{d.common.articles}</th><th className="text-end p-2">{d.common.events}</th></tr></thead>
              <tbody>{govs.map((x) => (
                <tr key={x.slug} className="border-b border-line last:border-0">
                  <td className="p-2">{pick(l, x.name_en, x.name_ar)}<span className="block text-xs text-muted">{Object.entries(x.event_types).map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`).join(" · ")}</span></td>
                  <td className="p-2 text-end num">{fmtNumber(x.articles_including_places, l)}</td><td className="p-2 text-end num">{fmtNumber(x.events, l)}</td>
                </tr>))}</tbody>
            </table>
          </Panel>
        </Section>
      </div>
    </>
  );
}
