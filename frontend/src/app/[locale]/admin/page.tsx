import { PageHeader } from "@/components/ui";
import { PUBLIC_API_URL } from "@/lib/api";
import { setup, type PageProps } from "@/lib/page";
import AdminConsole from "./AdminConsole";

export const metadata = { title: "Admin", robots: { index: false } };

export default async function Admin(props: PageProps) {
  const { d } = await setup(props);
  return (
    <>
      <PageHeader title={d.admin.title} intro={d.admin.intro} />
      <AdminConsole apiUrl={PUBLIC_API_URL} t={d.admin} />
    </>
  );
}
