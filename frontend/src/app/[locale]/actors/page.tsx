import Link from "next/link";
import FilterBar from "@/components/FilterBar";
import { Bar, Empty, PageHeader, Panel } from "@/components/ui";
import { filterQuery, tryApi } from "@/lib/api";
import { fmtNumber, pick } from "@/lib/i18n";
import { one, setup, type PageProps } from "@/lib/page";

export const metadata = { title: "Actors" };
const TYPES = ["political_actor", "person", "country", "igo", "ngo", "organization"];

export default async function ActorsPage(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const type = one(sp.entity_type);
  const data = await tryApi<{ items: { slug: string; name_en: string; name_ar: string | null; entity_type: string; subtype: string | null; articles: number }[] }>(
    `/actors${filterQuery(sp, { entity_type: type, limit: 200 })}`);
  const max = Math.max(1, ...(data?.items ?? []).map((a) => a.articles));
  return (
    <>
      <PageHeader title={d.actors.title} intro={d.actors.intro}>
        <nav className="flex flex-wrap gap-2 text-sm">
          <Link href="?" className={`rounded-full border px-3 py-0.5 ${!type ? "border-accent" : "border-line"}`}>{d.common.all}</Link>
          {TYPES.map((t) => <Link key={t} href={`?entity_type=${t}`} className={`rounded-full border px-3 py-0.5 ${type === t ? "border-accent" : "border-line"}`}>{t.replaceAll("_", " ")}</Link>)}
        </nav>
      </PageHeader>
      <FilterBar d={d} sp={sp} keep={["entity_type"]} />
      <Panel>
        {data?.items.length ? (
          <ul className="grid gap-x-8 gap-y-3 md:grid-cols-2">
            {data.items.map((a) => (
              <li key={a.slug} className="flex flex-col gap-1">
                <div className="flex justify-between gap-2">
                  <Link href={`/${l}/actors/${a.slug}`} className="hover:underline">{pick(l, a.name_en, a.name_ar)}</Link>
                  <span className="text-xs text-muted num">{a.entity_type.replaceAll("_", " ")} · {fmtNumber(a.articles, l)}</span>
                </div>
                <Bar value={a.articles} max={max} color="var(--accent)" />
              </li>
            ))}
          </ul>
        ) : <Empty d={d} />}
      </Panel>
    </>
  );
}
