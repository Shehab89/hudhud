import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20 flex flex-col gap-3">
      <h1 className="text-2xl font-semibold">404</h1>
      <p className="text-muted">Not found · غير موجود</p>
      <Link className="text-accent-2" href="/">←</Link>
    </div>
  );
}
