/** Labels for the curated source registry (database/seeds/sources/SCHEMA.md), in English and Arabic. */
import type { Locale } from "./i18n";

type T = { en: string; ar: string };
const lab = (table: Record<string, T>, key: string | null | undefined, l: Locale) =>
  key ? (table[key]?.[l] ?? key.replaceAll("_", " ")) : "";

export const CATEGORY: Record<string, T> = {
  MEDIA: { en: "Media", ar: "وسائل إعلام" },
  OFFICIAL_GOVERNMENT: { en: "Official government", ar: "جهات حكومية رسمية" },
  DIPLOMATIC_MISSION: { en: "Diplomatic missions", ar: "بعثات دبلوماسية" },
  INTERNATIONAL_INSTITUTION: { en: "International institutions", ar: "مؤسسات دولية" },
  POLITICAL_ORGANIZATION: { en: "Political organisations", ar: "تنظيمات سياسية" },
  SOCIAL_ACCOUNT: { en: "Social accounts", ar: "حسابات التواصل" },
  THINK_TANK: { en: "Think tanks", ar: "مراكز تفكير" },
  RESEARCH_ORGANIZATION: { en: "Research organisations", ar: "منظمات بحثية" },
};
export const CATEGORY_ORDER = Object.keys(CATEGORY);

export const CONTENT_TYPE: Record<string, T> = {
  journalism: { en: "Journalism", ar: "عمل صحفي" },
  official_statement: { en: "Official statement", ar: "بيان رسمي" },
  institutional_publication: { en: "Institutional publication", ar: "منشور مؤسسي" },
  political_statement: { en: "Political statement", ar: "بيان سياسي" },
  social_post: { en: "Social post", ar: "منشور على التواصل" },
  analysis: { en: "Analysis", ar: "تحليل" },
};

export const TIER: Record<string, T> = {
  A: { en: "Tier A · selected for audience and influence", ar: "الفئة أ · مختار لجمهوره وتأثيره" },
  B: { en: "Tier B · selected for institutional importance", ar: "الفئة ب · مختار لأهميته المؤسسية" },
};
export const TIER_SHORT: Record<string, T> = {
  A: { en: "Tier A · influence", ar: "الفئة أ · التأثير" },
  B: { en: "Tier B · institutional", ar: "الفئة ب · مؤسسي" },
};

export const REGION: Record<string, T> = {
  yemen: { en: "Yemen", ar: "اليمن" }, gulf: { en: "Gulf", ar: "الخليج" }, iraq: { en: "Iraq", ar: "العراق" },
  levant: { en: "Levant", ar: "المشرق" }, egypt: { en: "Egypt", ar: "مصر" }, maghreb: { en: "Maghreb", ar: "المغرب العربي" },
  iran: { en: "Iran", ar: "إيران" }, turkey: { en: "Turkey", ar: "تركيا" }, europe: { en: "Europe", ar: "أوروبا" },
  north_america: { en: "North America", ar: "أمريكا الشمالية" }, russia: { en: "Russia", ar: "روسيا" }, asia: { en: "Asia", ar: "آسيا" },
  africa: { en: "Africa", ar: "أفريقيا" }, global: { en: "International", ar: "دولي" },
};

export const YEMEN_ALIGNMENT: Record<string, T> = {
  plc_government: { en: "Government / PLC", ar: "الحكومة / مجلس القيادة" },
  ansar_allah: { en: "Ansar Allah (Houthi)", ar: "أنصار الله (الحوثيون)" },
  stc: { en: "Southern Transitional Council", ar: "المجلس الانتقالي الجنوبي" },
  islah: { en: "Islah", ar: "الإصلاح" },
  gpc_sanaa: { en: "GPC (Sanaa)", ar: "المؤتمر الشعبي (صنعاء)" },
  gpc_plc: { en: "GPC (PLC-aligned)", ar: "المؤتمر الشعبي (مع مجلس القيادة)" },
  national_resistance: { en: "National Resistance", ar: "المقاومة الوطنية" },
  hadramawt: { en: "Hadramawt bodies", ar: "مكونات حضرموت" },
  southern_other: { en: "Other southern bodies", ar: "مكونات جنوبية أخرى" },
  independent: { en: "Independent", ar: "مستقل" },
  mixed: { en: "Mixed", ar: "مختلط" },
  none_documented: { en: "None documented", ar: "لا انحياز موثق" },
  not_applicable: { en: "Not applicable", ar: "لا ينطبق" },
  unknown: { en: "Not assessed", ar: "غير مقيَّم" },
};

export const REGIONAL_ALIGNMENT: Record<string, T> = {
  saudi: { en: "Saudi Arabia", ar: "السعودية" }, uae: { en: "UAE", ar: "الإمارات" }, qatar: { en: "Qatar", ar: "قطر" },
  oman: { en: "Oman", ar: "عُمان" }, kuwait: { en: "Kuwait", ar: "الكويت" }, iran_axis: { en: "Iran and allies", ar: "إيران وحلفاؤها" },
  turkey: { en: "Turkey", ar: "تركيا" }, egypt: { en: "Egypt", ar: "مصر" }, israel: { en: "Israel", ar: "إسرائيل" }, us: { en: "United States", ar: "الولايات المتحدة" },
  uk: { en: "United Kingdom", ar: "المملكة المتحدة" }, eu: { en: "European Union", ar: "الاتحاد الأوروبي" },
  russia: { en: "Russia", ar: "روسيا" }, china: { en: "China", ar: "الصين" },
  none_documented: { en: "None documented", ar: "لا انحياز موثق" }, not_applicable: { en: "Not applicable", ar: "لا ينطبق" },
  unknown: { en: "Not assessed", ar: "غير مقيَّم" },
};

export const LEVEL: Record<string, T> = {
  high: { en: "High", ar: "عالية" }, medium: { en: "Medium", ar: "متوسطة" }, low: { en: "Low", ar: "منخفضة" }, none: { en: "None", ar: "لا توجد" },
};

export const FREQUENCY: Record<string, T> = {
  daily: { en: "Daily", ar: "يومية" }, weekly: { en: "Weekly", ar: "أسبوعية" }, monthly: { en: "Monthly", ar: "شهرية" }, occasional: { en: "Occasional", ar: "متقطعة" },
};

export const METRIC: Record<string, T> = {
  x_followers: { en: "X followers", ar: "متابعو إكس" }, youtube_subscribers: { en: "YouTube subscribers", ar: "مشتركو يوتيوب" },
  facebook_followers: { en: "Facebook followers", ar: "متابعو فيسبوك" }, telegram_subscribers: { en: "Telegram subscribers", ar: "مشتركو تيليغرام" },
  instagram_followers: { en: "Instagram followers", ar: "متابعو إنستغرام" }, tiktok_followers: { en: "TikTok followers", ar: "متابعو تيك توك" },
  monthly_visits: { en: "Monthly visits", ar: "الزيارات الشهرية" }, tv_reach: { en: "TV reach", ar: "انتشار تلفزيوني" },
  print_circulation: { en: "Print circulation", ar: "التوزيع المطبوع" },
};

export const PLATFORM: Record<string, T> = {
  website: { en: "Website", ar: "موقع" }, x: { en: "X", ar: "إكس" }, telegram: { en: "Telegram", ar: "تيليغرام" },
  youtube: { en: "YouTube", ar: "يوتيوب" }, facebook: { en: "Facebook", ar: "فيسبوك" }, instagram: { en: "Instagram", ar: "إنستغرام" },
  tiktok: { en: "TikTok", ar: "تيك توك" }, tv: { en: "TV", ar: "تلفزيون" }, radio: { en: "Radio", ar: "إذاعة" }, wire: { en: "Wire", ar: "وكالة" },
};

/** Which account platforms the pipeline can collect. X needs the paid API: REQUIRES CONFIGURATION. */
export const COLLECTABLE = new Set(["telegram", "youtube", "website"]);

export const L = {
  category: (k: string | null | undefined, l: Locale) => lab(CATEGORY, k, l),
  contentType: (k: string | null | undefined, l: Locale) => lab(CONTENT_TYPE, k, l),
  region: (k: string | null | undefined, l: Locale) => lab(REGION, k, l),
  yemen: (k: string | null | undefined, l: Locale) => lab(YEMEN_ALIGNMENT, k, l),
  regional: (k: string | null | undefined, l: Locale) => lab(REGIONAL_ALIGNMENT, k, l),
  level: (k: string | null | undefined, l: Locale) => lab(LEVEL, k, l),
  frequency: (k: string | null | undefined, l: Locale) => lab(FREQUENCY, k, l),
  metric: (k: string | null | undefined, l: Locale) => lab(METRIC, k, l),
  platform: (k: string | null | undefined, l: Locale) => lab(PLATFORM, k, l),
  tier: (k: string | null | undefined, l: Locale) => lab(TIER_SHORT, k, l),
};

export const SCORE_TEXT = {
  en: {
    influence: "Influence", institutional: "Institutional importance", reliability: "Reliability", notAssessed: "Not assessed",
    notScored: "Not scored: too little evidence", outOf: "/ 100",
    note: "Influence is measured from audience and Yemen-coverage evidence. Institutional importance is a separate attribute: an embassy can matter a great deal with a small audience. Official status raises neither score, and no source is rated more reliable for being official.",
  },
  ar: {
    influence: "التأثير", institutional: "الأهمية المؤسسية", reliability: "الموثوقية", notAssessed: "غير مقيَّمة",
    notScored: "بلا درجة: الأدلة غير كافية", outOf: "/ ١٠٠",
    note: "يُقاس التأثير من أدلة الجمهور وتواتر تغطية اليمن. الأهمية المؤسسية صفة منفصلة: قد تكون سفارةٌ مهمة جدًا بجمهور صغير. الصفة الرسمية لا ترفع أيًّا من الدرجتين، ولا يُعدّ أي مصدر أكثر موثوقية لكونه رسميًا.",
  },
};
