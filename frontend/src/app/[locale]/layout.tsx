import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import "../globals.css";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import { themeScript } from "@/components/ThemeToggle";
import { dirOf, getDict, hasLocale, locales } from "@/lib/i18n";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(locale)) return {};
  const d = getDict(locale);
  const site = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  return {
    metadataBase: new URL(site),
    title: { default: d.site.name, template: `%s · ${d.site.name}` },
    description: d.site.tagline,
    alternates: { languages: { en: "/en", ar: "/ar" } },
    openGraph: { title: d.site.name, description: d.site.tagline, type: "website", locale: locale === "ar" ? "ar_YE" : "en_GB" },
    robots: { index: true, follow: true },
  };
}

export default async function LocaleLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!hasLocale(locale)) notFound();
  const d = getDict(locale);
  return (
    <html lang={locale} dir={dirOf(locale)} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" />
      </head>
      <body className="min-h-screen flex flex-col">
        <a href="#main" className="skip-link">{d.site.skip}</a>
        <Header l={locale} d={d} />
        <main id="main" className="flex-1 mx-auto w-full max-w-7xl px-4 py-8">{children}</main>
        <Footer l={locale} d={d} />
      </body>
    </html>
  );
}
