import { NextResponse, type NextRequest } from "next/server";

const LOCALES = ["en", "ar"];

function preferred(req: NextRequest) {
  const header = req.headers.get("accept-language") || "";
  return /^\s*ar\b/i.test(header) || /,\s*ar\b/i.test(header.split(",").slice(0, 2).join(",")) ? "ar" : "en";
}

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`))) return;
  req.nextUrl.pathname = `/${preferred(req)}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(req.nextUrl);
}

export const config = { matcher: ["/((?!_next|geo|favicon.ico|icon.svg|robots.txt|sitemap.xml).*)"] };
