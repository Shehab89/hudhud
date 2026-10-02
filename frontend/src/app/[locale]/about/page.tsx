import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { PUBLIC_API_URL } from "@/lib/api";
import { setup, type PageProps } from "@/lib/page";

export const metadata = { title: "About" };

const TEXT = {
  en: {
    p: [
      "This is an open-source research platform for monitoring and analysing how Yemen is covered by Yemeni, regional and international media. It is built for researchers, journalists, NGOs and anyone studying the information environment around the conflict and the humanitarian crisis.",
      "It is a measurement tool, not an advocacy project. It does not rank political actors, recommend positions, or claim to know what is true. It shows what was published, by whom, how it was worded, and how confident the automated analysis is.",
      "The design takes cues from ACAPS' Yemen Analysis Hub (YETI) in presenting a split country: wherever it helps, coverage is compared by where newsrooms operate.",
    ],
    rules: "What the platform will not do",
    list: ["profile private individuals or infer protected attributes", "bypass paywalls, logins or robots.txt", "republish full articles", "rank parties or recommend candidates", "present sentiment as truth", "show synthetic data without a DEMO DATA label"],
    api: "Data access",
    apiText: "All data shown is available through the public API, with exports in CSV, JSON, BibTeX and RIS.",
  },
  ar: {
    p: [
      "منصة بحثية مفتوحة المصدر لرصد وتحليل تغطية وسائل الإعلام اليمنية والإقليمية والدولية لليمن. صُممت للباحثين والصحفيين والمنظمات غير الحكومية وكل من يدرس البيئة الإعلامية المحيطة بالنزاع والأزمة الإنسانية.",
      "إنها أداة قياس لا مشروع مناصرة. لا ترتّب الفاعلين السياسيين ولا توصي بمواقف ولا تدّعي معرفة الحقيقة. تُظهر ما نُشر ومن نشره وكيف صيغ ومدى ثقة التحليل الآلي.",
      "يستلهم التصميم مركز تحليل اليمن لدى ACAPS (YETI) في عرض بلد منقسم: حيثما يفيد ذلك، تُقارن التغطية بحسب أماكن عمل غرف الأخبار.",
    ],
    rules: "ما لن تفعله المنصة",
    list: ["إنشاء ملفات عن أفراد عاديين أو استنتاج سماتهم المحمية", "تجاوز جدران الدفع أو تسجيل الدخول أو robots.txt", "إعادة نشر المقالات كاملة", "ترتيب الأحزاب أو التوصية بمرشحين", "تقديم المشاعر على أنها حقيقة", "عرض بيانات مُصطنعة دون وسم «بيانات تجريبية»"],
    api: "الوصول إلى البيانات",
    apiText: "كل البيانات المعروضة متاحة عبر الواجهة البرمجية العامة، مع تصدير بصيغ CSV وJSON وBibTeX وRIS.",
  },
};

export default async function About(props: PageProps) {
  const { l, d } = await setup(props);
  const t = TEXT[l];
  return (
    <div className="max-w-[68ch]">
      <PageHeader title={d.nav.about} intro={d.site.tagline} />
      <div className="flex flex-col gap-4 leading-relaxed">
        {t.p.map((x, i) => <p key={i}>{x}</p>)}
        <h2 className="text-xl font-semibold mt-4">{t.rules}</h2>
        <ul className="list-disc ps-6 flex flex-col gap-1">{t.list.map((x) => <li key={x}>{x}</li>)}</ul>
        <h2 className="text-xl font-semibold mt-4">{t.api}</h2>
        <p>{t.apiText} <a className="text-accent-2 underline" href={`${PUBLIC_API_URL}/docs`}>{PUBLIC_API_URL}/docs</a></p>
        <p><Link className="text-accent-2 underline" href={`/${l}/methodology`}>{d.nav.methodology} →</Link></p>
      </div>
    </div>
  );
}
