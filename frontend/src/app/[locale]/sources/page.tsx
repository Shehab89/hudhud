import SourceRegistry, { type Src } from "@/components/SourceRegistry";
import { Empty, PageHeader } from "@/components/ui";
import { tryApi } from "@/lib/api";
import { setup, one, type PageProps } from "@/lib/page";

export const metadata = { title: "Source registry" };

export default async function SourcesPage(props: PageProps) {
  const { l, d, sp } = await setup(props);
  const demo = one(sp.demo) || "exclude";
  const data = await tryApi<{ sources: Src[] }>(`/sources?demo=${demo}`);
  return (
    <>
      <PageHeader title={d.sources.title} intro={d.sources.intro} />
      {data ? <SourceRegistry sources={data.sources} l={l} d={d} /> : <Empty d={d} />}
    </>
  );
}
