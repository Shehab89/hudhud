import type { MetadataRoute } from "next";

const PAGES = ["", "/news", "/topics", "/sources", "/actors", "/events", "/geography", "/media-landscape", "/research", "/methodology", "/about", "/quality"];

export default function sitemap(): MetadataRoute.Sitemap {
  const site = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  return PAGES.flatMap((p) => ["en", "ar"].map((l) => ({
    url: `${site}/${l}${p}`, changeFrequency: "daily" as const,
    alternates: { languages: { en: `${site}/en${p}`, ar: `${site}/ar${p}` } },
  })));
}
