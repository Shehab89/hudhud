import type { Dict } from "@/lib/i18n";

export default function DemoBanner({ d, show }: { d: Dict; show: boolean }) {
  if (!show) return null;
  return (
    <div role="status" className="mb-6 rounded-md border border-demo/50 bg-demo-bg text-demo px-4 py-2.5 text-sm font-medium">
      {d.site.demoBanner}
    </div>
  );
}
