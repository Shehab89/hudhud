import { PageHeader } from "@/components/ui";
import { setup, type PageProps } from "@/lib/page";
import { ar, en } from "./content";

export const metadata = { title: "Methodology" };

export default async function Methodology(props: PageProps) {
  const { l, d } = await setup(props);
  const blocks = l === "ar" ? ar : en;
  return (
    <div className="grid gap-10 lg:grid-cols-[14rem_1fr]">
      <nav aria-label={d.nav.methodology} className="hidden lg:block">
        <ul className="sticky top-24 flex flex-col gap-1 text-sm">{blocks.map((b) => <li key={b.id}><a className="text-muted hover:text-ink" href={`#${b.id}`}>{b.title}</a></li>)}</ul>
      </nav>
      <div className="min-w-0">
        <PageHeader title={d.nav.methodology} intro={d.site.disclaimer} />
        <div className="flex flex-col gap-10 max-w-[68ch]">
          {blocks.map((b) => (
            <section key={b.id} id={b.id} className="scroll-mt-24 flex flex-col gap-3">
              <h2 className="text-xl font-semibold">{b.title}</h2>
              {b.body.map((p, i) => <p key={i} className="leading-relaxed">{p}</p>)}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
