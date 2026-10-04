import type { Locale } from "./i18n";

type T = { en: string; ar: string };
export interface Tab { href: string; label: T }
export interface Module { n: number; key: string; href: string; title: T; blurb: T; tabs: Tab[] }

export const MODULES: Module[] = [
  { n: 1, key: "coverage", href: "/coverage",
    title: { en: "Coverage monitor", ar: "رصد التغطية" },
    blurb: { en: "Volume, languages and tone of coverage over time, and every article with its analysis and provenance.", ar: "حجم التغطية ولغاتها ونبرتها عبر الزمن، وكل مقال مع تحليله ومصدره." },
    tabs: [{ href: "/coverage", label: { en: "Overview", ar: "نظرة عامة" } }, { href: "/news", label: { en: "News feed", ar: "الأخبار" } }] },
  { n: 2, key: "sources", href: "/sources",
    title: { en: "Source registry", ar: "سجل المصادر" },
    blurb: { en: "A curated set of top sources: media, official and diplomatic voices, international institutions and public figures, each with the evidence for why it was selected.", ar: "مجموعة منتقاة من أهم المصادر: وسائل الإعلام والجهات الرسمية والدبلوماسية والمؤسسات الدولية والشخصيات العامة، مع أدلة اختيار كل منها." },
    tabs: [{ href: "/sources", label: { en: "Registry", ar: "السجل" } }, { href: "/sources/compare", label: { en: "Compare sources", ar: "مقارنة المصادر" } }] },
  { n: 3, key: "topics", href: "/topics",
    title: { en: "Topics and trends", ar: "المواضيع والاتجاهات" },
    blurb: { en: "Curated categories and data-driven topics, with what is rising or fading.", ar: "فئات منسقة ومواضيع مستخرجة من البيانات، وما يتصاعد أو يتراجع." },
    tabs: [{ href: "/topics", label: { en: "Topics", ar: "المواضيع" } }] },
  { n: 4, key: "actors", href: "/actors",
    title: { en: "Actors and terminology", ar: "الأطراف والمصطلحات" },
    blurb: { en: "Public actors, the names outlets use for them, and how sentences that name them read.", ar: "الأطراف العامة والأسماء التي تستخدمها المنافذ لوصفها، وكيف تُقرأ الجمل التي تذكرها." },
    tabs: [{ href: "/actors", label: { en: "Actors", ar: "الأطراف" } }] },
  { n: 5, key: "events", href: "/events",
    title: { en: "Events and geography", ar: "الأحداث والجغرافيا" },
    blurb: { en: "Incidents reported in coverage, on a timeline and a governorate map.", ar: "الحوادث المذكورة في التغطية على خط زمني وخريطة للمحافظات." },
    tabs: [{ href: "/events", label: { en: "Events", ar: "الأحداث" } }, { href: "/geography", label: { en: "Geography", ar: "الجغرافيا" } }] },
  { n: 6, key: "narratives", href: "/compare",
    title: { en: "Narrative comparison", ar: "مقارنة السرديات" },
    blurb: { en: "Media against official statements, Government against Houthi against STC, Saudi against UAE against Iran against the US and UK: how each group tells the same stories.", ar: "الإعلام مقابل البيانات الرسمية، والحكومة مقابل الحوثيين مقابل الانتقالي، والسعودية مقابل الإمارات وإيران والولايات المتحدة وبريطانيا: كيف تروي كل مجموعة القصص نفسها." },
    tabs: [{ href: "/compare", label: { en: "Compare voices", ar: "مقارنة الأصوات" } }, { href: "/media-landscape", label: { en: "Media landscape", ar: "المشهد الإعلامي" } }] },
  { n: 7, key: "research", href: "/research",
    title: { en: "Research workspace", ar: "مساحة البحث" },
    blurb: { en: "Search in any language, compare, cite and export, with the data-quality report behind every number.", ar: "بحث بأي لغة ومقارنة واقتباس وتصدير، مع تقرير جودة البيانات خلف كل رقم." },
    tabs: [{ href: "/research", label: { en: "Search and export", ar: "البحث والتصدير" } }, { href: "/quality", label: { en: "Data quality", ar: "جودة البيانات" } }] },
];

export const t = (x: T, l: Locale) => x[l];
export const num2 = (n: number, l: Locale) => new Intl.NumberFormat(l === "ar" ? "ar-u-nu-arab" : "en", { minimumIntegerDigits: 2 }).format(n);

/** Strip the locale prefix, then find the module (and tab) a pathname belongs to. */
export function locate(pathname: string) {
  const rest = "/" + pathname.split("/").slice(2).join("/");
  const mod = MODULES.find((m) => m.tabs.some((x) => rest === x.href || rest.startsWith(x.href + "/")));
  if (!mod) return null;
  const tab = [...mod.tabs].sort((a, b) => b.href.length - a.href.length).find((x) => rest === x.href || rest.startsWith(x.href + "/"));
  return { mod, tab: tab!, rest };
}

export const GROUP_LABELS: Record<string, T> = {
  yemen_independent: { en: "Yemen: independent", ar: "يمني مستقل" },
  yemen_local: { en: "Yemen: local", ar: "يمني محلي" },
  yemen_state_irg: { en: "Yemen: government-run", ar: "يمني حكومي (الشرعية)" },
  yemen_state_sanaa: { en: "Yemen: Sana'a authorities", ar: "يمني (سلطات صنعاء)" },
  yemen_actor_affiliated: { en: "Yemen: actor-affiliated", ar: "يمني تابع لأحد الأطراف" },
  arab_gulf: { en: "Arab: Gulf", ar: "عربي: الخليج" },
  arab_levant: { en: "Arab: Levant", ar: "عربي: بلاد الشام" },
  arab_egypt: { en: "Arab: Egypt", ar: "عربي: مصر" },
  arab_maghreb: { en: "Arab: Maghreb", ar: "عربي: المغرب العربي" },
  arab_iraq: { en: "Arab: Iraq", ar: "عربي: العراق" },
  arab_pan: { en: "Pan-Arab", ar: "عربي عام" },
  iran: { en: "Iran", ar: "إيران" },
  turkey: { en: "Turkey", ar: "تركيا" },
  international_newspaper: { en: "International press", ar: "صحافة دولية" },
  international_broadcaster: { en: "International broadcasters", ar: "هيئات بث دولية" },
  international_arabic_service: { en: "Arabic services of foreign media", ar: "خدمات عربية لإعلام أجنبي" },
  international_wire: { en: "News agencies", ar: "وكالات أنباء" },
  international_humanitarian: { en: "Humanitarian and UN", ar: "إنساني وأممي" },
  think_tank_research: { en: "Think tanks and research", ar: "مراكز بحث" },
  aggregator: { en: "Aggregators", ar: "مجمّعات أخبار" },
  demo: { en: "Demo", ar: "تجريبي" },
};

export const ORIENT_LABELS: Record<string, T> = {
  state_aligned: { en: "State-aligned", ar: "قريب من الدولة" },
  state_funded: { en: "State-funded", ar: "ممول حكوميًا" },
  movement_aligned: { en: "Movement-aligned", ar: "قريب من حركة" },
  opposition_aligned: { en: "Opposition-aligned", ar: "قريب من المعارضة" },
  public_service: { en: "Public service", ar: "خدمة عامة" },
  intergovernmental: { en: "Intergovernmental", ar: "حكومي دولي" },
  independent: { en: "Independent", ar: "مستقل" },
  unknown: { en: "Not assessed", ar: "غير مقيَّم" },
};

export const LANG_NAMES: Record<string, T> = {
  ar: { en: "Arabic", ar: "العربية" }, en: { en: "English", ar: "الإنجليزية" }, fr: { en: "French", ar: "الفرنسية" },
  fa: { en: "Persian", ar: "الفارسية" }, de: { en: "German", ar: "الألمانية" }, ru: { en: "Russian", ar: "الروسية" },
  es: { en: "Spanish", ar: "الإسبانية" }, tr: { en: "Turkish", ar: "التركية" }, it: { en: "Italian", ar: "الإيطالية" },
  zh: { en: "Chinese", ar: "الصينية" }, he: { en: "Hebrew", ar: "العبرية" }, ur: { en: "Urdu", ar: "الأردية" },
};
