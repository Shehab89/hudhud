"""Synthetic DEMO DATA for local development, screenshots and tests.

Nothing generated here is real news. Every demo source and article carries
``is_demo = true``, demo URLs use the reserved ``.invalid`` top-level domain (RFC 2606)
so they can never resolve, the author field reads "DEMO DATA", and the API and
frontend label these records "DEMO DATA" wherever they appear.

The generator is deterministic (seeded) and idempotent: re-running it inserts only
what is missing. The six demo outlets differ in newsroom location and in the
terminology they use for the same actors, so the terminology, framing and
source-comparison views have something to show. Their names are invented and do
not refer to any real outlet.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from hudhud.db import models as m
from hudhud.ingest.canonical import canonicalize_url, url_hash
from hudhud.nlp.text import content_hash, normalize_for_matching

DEMO_DOMAIN = "demo.invalid"


@dataclass(frozen=True)
class Voice:
    slug: str
    name: str
    language: str
    operating_base: str
    houthi: str
    coalition: str
    gov: str
    opener: str = ""
    closer: str = ""


VOICES = [
    Voice(
        "demo-outlet-north",
        "DEMO Outlet North (Arabic, Sana'a-based)",
        "ar",
        "sanaa_controlled",
        "أنصار الله",
        "تحالف العدوان",
        "حكومة المرتزقة",
        "صنعاء – متابعات خاصة: ",
        " وتابع مراسلنا تطورات الوضع من صنعاء أولاً بأول.",
    ),
    Voice(
        "demo-outlet-aden",
        "DEMO Outlet Aden (Arabic, government areas)",
        "ar",
        "government_controlled",
        "ميليشيا الحوثي",
        "تحالف دعم الشرعية",
        "الحكومة الشرعية",
        "عدن – خاص: ",
        " وأكد مسؤولون حكوميون أنهم يتابعون الوضع عن كثب.",
    ),
    Voice(
        "demo-outlet-south",
        "DEMO Outlet South (Arabic, STC areas)",
        "ar",
        "stc_controlled",
        "الحوثيين",
        "التحالف العربي",
        "الحكومة اليمنية",
        "تقرير ميداني – ",
        " ونقل مراسلنا في المحافظات الجنوبية تفاصيل إضافية.",
    ),
    Voice(
        "demo-outlet-gulf",
        "DEMO Outlet Gulf (Arabic, outside Yemen)",
        "ar",
        "outside_yemen",
        "جماعة الحوثي",
        "التحالف العربي",
        "الحكومة المعترف بها دوليا",
        "وكالات – ",
        " وتتابع العواصم الخليجية هذه التطورات باهتمام.",
    ),
    Voice(
        "demo-wire",
        "DEMO Wire (English, outside Yemen)",
        "en",
        "outside_yemen",
        "Houthi rebels",
        "Saudi-led coalition",
        "internationally recognised government",
    ),
    Voice(
        "demo-outlet-intl",
        "DEMO Outlet International (English, outside Yemen)",
        "en",
        "outside_yemen",
        "Houthis",
        "Saudi-led coalition",
        "Presidential Leadership Council",
    ),
]

# Each story type: governorate pool, English title/excerpt variants, Arabic title/excerpt.
# {loc}/{loc_ar} are governorates; {h}/{c}/{g} are the outlet's own terms for the
# Houthi movement, the coalition and the government.
STORIES = {
    "airstrikes": {
        "locs": ["saada", "al-hudaydah", "amanat-al-asimah", "marib", "al-jawf"],
        "en": [
            (
                "Airstrikes reported in {loc} as fighting continues",
                "Several airstrikes hit areas of {loc} governorate, local officials said. Residents reported civilians "
                "killed and houses destroyed; the {c} did not comment.",
            ),
            (
                "Air raids hit {loc}, civilian casualties reported",
                "Air raids struck {loc} overnight. Medical sources said at least four civilians were killed and "
                "dozens wounded, and called for an independent investigation.",
            ),
        ],
        "ar": (
            "غارات جوية على محافظة {loc_ar}",
            "شنّ طيران {c} غارات على مناطق في محافظة {loc_ar}، وأفادت مصادر محلية بسقوط قتلى وجرحى مدنيين "
            "وتدمير منازل.",
        ),
    },
    "frontline": {
        "locs": ["marib", "taiz", "al-dhale", "al-bayda", "shabwah"],
        "en": [
            (
                "Clashes erupt on {loc} front lines",
                "Heavy clashes broke out between government forces and the {h} on several fronts in {loc}, "
                "military sources said, with casualties on both sides.",
            ),
            (
                "Fighting escalates in {loc}",
                "Fighting escalated in {loc} after the {h} launched an offensive on government positions, "
                "according to military sources.",
            ),
        ],
        "ar": (
            "مواجهات عنيفة في جبهات {loc_ar}",
            "اندلعت مواجهات عنيفة بين قوات {g} و{h} في عدة جبهات بمحافظة {loc_ar}، وسط سقوط قتلى وجرحى من الطرفين.",
        ),
    },
    "red_sea": {
        "locs": ["al-hudaydah", "taiz"],
        "en": [
            (
                "{h} claim attack on commercial vessel in the Red Sea",
                "The {h} said they targeted a commercial vessel in the Red Sea near Bab al-Mandab. Shipping "
                "companies reported further diversions away from the route, raising insurance costs.",
            ),
            (
                "Ship reports incident off Yemen coast in Red Sea",
                "A merchant ship reported an explosion near its hull off the coast of Hodeidah in the Red Sea, "
                "maritime security agencies said. The crew was reported safe.",
            ),
        ],
        "ar": (
            "استهداف سفينة تجارية في البحر الأحمر",
            "أعلن {h} استهداف سفينة تجارية في البحر الأحمر قرب باب المندب، فيما أعلنت شركات شحن تحويل مسار سفنها.",
        ),
    },
    "humanitarian": {
        "locs": ["hajjah", "al-hudaydah", "taiz", "ibb", "lahj"],
        "en": [
            (
                "UN warns of worsening food insecurity in {loc}",
                "The World Food Programme warned that food insecurity is worsening in {loc}, where families face "
                "hunger and malnutrition amid funding cuts to humanitarian aid.",
            ),
            (
                "Aid agencies say funding gap threatens assistance in Yemen",
                "OCHA said the humanitarian response is severely underfunded, putting food assistance for "
                "displaced families in {loc} at risk.",
            ),
        ],
        "ar": (
            "تحذيرات أممية من تفاقم انعدام الأمن الغذائي في {loc_ar}",
            "حذّر برنامج الأغذية العالمي من تفاقم الجوع وسوء التغذية في محافظة {loc_ar} مع تراجع تمويل المساعدات الإنسانية.",
        ),
    },
    "cholera": {
        "locs": ["amanat-al-asimah", "ibb", "al-hudaydah", "taiz", "aden"],
        "en": [
            (
                "Cholera cases rise in {loc}, health officials say",
                "Health officials recorded a rise in suspected cholera cases in {loc}. The World Health Organization "
                "said hospitals are overwhelmed and clean water is scarce.",
            ),
            (
                "WHO warns of cholera outbreak in {loc}",
                "The World Health Organization warned of a cholera outbreak in {loc}, urging support for "
                "treatment centres.",
            ),
        ],
        "ar": (
            "ارتفاع حالات الكوليرا في {loc_ar}",
            "سجّلت السلطات الصحية ارتفاعاً في حالات الاشتباه بالكوليرا في {loc_ar}، وسط ضغط كبير على المستشفيات وشح المياه النظيفة.",
        ),
    },
    "currency": {
        "locs": ["aden"],
        "en": [
            (
                "Yemeni rial hits new low in Aden",
                "The Yemeni rial fell to a new low against the US dollar in Aden, traders said, pushing up food "
                "prices. The Central Bank in Aden announced new measures.",
            ),
            (
                "Rial slide deepens economic crisis in government areas",
                "The rial continued to slide in Aden, deepening the economic crisis as prices of basic goods rose.",
            ),
        ],
        "ar": (
            "انهيار جديد للريال اليمني في عدن",
            "تراجع الريال اليمني إلى مستوى قياسي أمام الدولار في عدن، ما أدى إلى ارتفاع أسعار المواد الغذائية، "
            "وأعلن البنك المركزي في عدن إجراءات جديدة.",
        ),
    },
    "talks": {
        "locs": ["amanat-al-asimah"],
        "en": [
            (
                "UN envoy Hans Grundberg holds talks in Muscat on Yemen truce",
                "UN envoy Hans Grundberg met negotiators in Muscat to discuss extending the truce and a roadmap for "
                "peace talks, his office said. Oman is mediating.",
            ),
            (
                "Diplomatic push for Yemen roadmap continues in Muscat",
                "Diplomats in Muscat continued talks on a UN roadmap including salary payments and a ceasefire, "
                "according to the Special Envoy for Yemen.",
            ),
        ],
        "ar": (
            "المبعوث الأممي غروندبرغ يجري مباحثات في مسقط",
            "التقى المبعوث الأممي هانس غروندبرغ في مسقط بمفاوضين لبحث تمديد الهدنة وخارطة الطريق للسلام، "
            "بوساطة سلطنة عمان.",
        ),
    },
    "prisoners": {
        "locs": ["amanat-al-asimah", "marib"],
        "en": [
            (
                "Prisoner exchange talks resume under UN and ICRC auspices",
                "Representatives of the {g} and the {h} resumed talks on a prisoner exchange, the ICRC said, "
                "expressing hope that detainees will be released.",
            ),
            (
                "Families await news of detainees as exchange talks continue",
                "Families of detainees called for the release of prisoners as talks between the parties continued "
                "with ICRC support.",
            ),
        ],
        "ar": (
            "استئناف مفاوضات تبادل الأسرى برعاية أممية",
            "استؤنفت المفاوضات بين {g} و{h} بشأن تبادل الأسرى والمحتجزين، بمشاركة اللجنة الدولية للصليب الأحمر.",
        ),
    },
    "floods": {
        "locs": ["hadramawt", "al-mahrah", "hajjah", "al-hudaydah"],
        "en": [
            (
                "Flash floods displace families in {loc}",
                "Flash floods swept through parts of {loc} after heavy rains, displacing hundreds of families and "
                "damaging roads, local authorities said.",
            ),
            (
                "Heavy rains cause flooding in {loc}",
                "Heavy rains caused flooding in {loc}; IOM said displaced families need shelter and clean water.",
            ),
        ],
        "ar": (
            "سيول جارفة تشرد أسراً في {loc_ar}",
            "تسببت السيول الناجمة عن الأمطار الغزيرة في نزوح مئات الأسر وتضرر الطرق في محافظة {loc_ar}.",
        ),
    },
    "salaries": {
        "locs": ["aden", "amanat-al-asimah"],
        "en": [
            (
                "Public sector salaries delayed again in Yemen",
                "Public sector employees in {loc} protested unpaid salaries, as the economic crisis and the split "
                "between central banks in Aden and Sanaa continue.",
            ),
            (
                "Unpaid salaries spark protests in {loc}",
                "Teachers and civil servants protested in {loc} over months of unpaid salaries.",
            ),
        ],
        "ar": (
            "احتجاجات على تأخر صرف المرتبات في {loc_ar}",
            "نظّم موظفون حكوميون في {loc_ar} وقفات احتجاجية للمطالبة بصرف المرتبات المتأخرة في ظل الأزمة الاقتصادية.",
        ),
    },
    "landmines": {
        "locs": ["al-hudaydah", "taiz", "marib", "al-jawf"],
        "en": [
            (
                "Landmine explosion kills children in {loc}",
                "A landmine exploded in {loc}, killing two children and injuring others, according to medical sources. "
                "Demining teams called for more support.",
            ),
            (
                "Demining teams clear explosives in {loc}",
                "Demining teams removed hundreds of landmines and unexploded ordnance in {loc} this month.",
            ),
        ],
        "ar": (
            "مقتل أطفال بانفجار لغم في {loc_ar}",
            "قُتل طفلان وأصيب آخرون بانفجار لغم أرضي في محافظة {loc_ar}، بحسب مصادر طبية.",
        ),
    },
    "southern_politics": {
        "locs": ["aden", "hadramawt", "shabwah"],
        "en": [
            (
                "Southern Transitional Council holds rally in {loc}",
                "Supporters of the Southern Transitional Council rallied in {loc}, renewing calls for southern "
                "self-determination. Aidarous al-Zubaidi addressed the crowd.",
            ),
            (
                "STC and government officials meet amid tensions in {loc}",
                "Officials from the STC and the {g} met in {loc} to ease tensions over local administration.",
            ),
        ],
        "ar": (
            "المجلس الانتقالي الجنوبي ينظم فعالية جماهيرية في {loc_ar}",
            "نظّم المجلس الانتقالي الجنوبي فعالية جماهيرية في {loc_ar} جدد فيها المشاركون المطالبة باستعادة الدولة الجنوبية.",
        ),
    },
}

# Relative weights over time: (weight in the older window, weight in the last 7 days).
# Red Sea coverage surges and cholera fades so trend detection has something to find.
EXTRA_EN = [
    "Witnesses described the situation as tense.",
    "Officials gave no further details.",
    "The information could not be independently verified.",
    "Further updates are expected later in the day.",
    "Residents said communications were disrupted.",
    "Local media published photos of the scene.",
]
EXTRA_AR = [
    "ووصف شهود عيان الوضع بالمتوتر.",
    "ولم يقدّم المسؤولون مزيداً من التفاصيل.",
    "ولم يتسنَّ التحقق من هذه المعلومات بشكل مستقل.",
    "ومن المتوقع صدور مزيد من المعلومات لاحقاً.",
    "وأفاد سكان بانقطاع الاتصالات.",
    "ونشرت وسائل إعلام محلية صوراً من الموقع.",
]

TREND = {"red_sea": (0.6, 3.0), "cholera": (1.4, 0.3), "airstrikes": (1.0, 1.2), "humanitarian": (1.2, 1.0)}


def _loc_names(session: Session) -> dict[str, tuple[str, str]]:
    rows = session.execute(
        select(m.Entity.slug, m.Entity.name_en, m.Entity.name_ar).join(
            m.Location, m.Entity.id == m.Location.entity_id
        )
    ).all()
    out = {}
    for slug, en, ar in rows:
        key = slug.removeprefix("gov-")
        out[key] = (en.split(" (")[0], ar or en)
    out["amanat-al-asimah"] = ("Sanaa", "صنعاء")
    return out


# Registry attributes of the synthetic outlets, so comparison views can be tried on DEMO
# DATA. They describe the synthetic voices above, not any real organisation.
DEMO_PROFILE = {
    "demo-outlet-north": ("yemen", "ansar_allah"),
    "demo-outlet-aden": ("yemen", "plc_government"),
    "demo-outlet-south": ("yemen", "stc"),
    "demo-outlet-gulf": ("gulf", "unknown"),
    "demo-wire": ("global", "unknown"),
    "demo-outlet-intl": ("europe", "unknown"),
}


def ensure_demo_sources(session: Session) -> dict[str, m.Source]:
    out = {}
    for v in VOICES:
        src = session.scalar(select(m.Source).where(m.Source.slug == v.slug))
        if src is None:
            src = m.Source(
                slug=v.slug,
                name=v.name,
                url=f"https://{v.slug}.{DEMO_DOMAIN}/",
                domain=f"{v.slug}.{DEMO_DOMAIN}",
                source_type="demo",
                source_group="demo",
                geographic_focus=["yemen"],
                yemen_coverage="primary",
                operating_base=v.operating_base,
                access_policy="metadata_only",
                active=False,
                is_demo=True,
                health_status="inactive",
                notes="DEMO DATA. Synthetic outlet for development; not a real organisation.",
            )
            session.add(src)
            session.flush()
            session.merge(m.SourceLanguage(source_id=src.id, language_code=v.language))
        region, alignment = DEMO_PROFILE.get(v.slug, (None, "unknown"))
        src.category, src.tier, src.region, src.content_type = "MEDIA", "A", region, "journalism"
        src.yemen_political_alignment = alignment
        out[v.slug] = src
    return out


def generate(
    session: Session,
    days: int = 45,
    stories_per_day: int = 7,
    seed: int = 20261002,
    end: dt.date | None = None,
) -> dict:
    rng = random.Random(seed)
    end = end or dt.datetime.now(dt.UTC).date()
    sources = ensure_demo_sources(session)
    locs = _loc_names(session)
    voices = {v.slug: v for v in VOICES}
    inserted = skipped = 0
    for day_offset in range(days - 1, -1, -1):
        day = end - dt.timedelta(days=day_offset)
        recent = day_offset < 7
        kinds = list(STORIES)
        weights = [TREND.get(k, (1.0, 1.0))[1 if recent else 0] for k in kinds]
        todays = []  # weighted sample without replacement: one story per kind per day
        while len(todays) < min(stories_per_day, len(kinds)):
            k = rng.choices(kinds, weights)[0]
            i = kinds.index(k)
            kinds.pop(i)
            weights.pop(i)
            todays.append(k)
        for n, kind in enumerate(todays):
            spec = STORIES[kind]
            loc = rng.choice(spec["locs"])
            loc_en, loc_ar = locs.get(loc, (loc.title(), loc))
            base_time = dt.datetime.combine(
                day, dt.time(rng.randint(5, 20), rng.randint(0, 59)), tzinfo=dt.UTC
            )
            outlets = rng.sample(list(voices), k=rng.randint(2, 5))
            en_variant = rng.randrange(len(spec["en"]))
            wire_text = None
            num = rng.choice([12, 30, 45, 60, 85, 120, 150, 230, 400, 700]) + rng.randint(0, 9)
            k = rng.randrange(len(EXTRA_EN))
            detail_en = f" {EXTRA_EN[k]} Local sources put the number of people affected at about {num}."
            detail_ar = f" {EXTRA_AR[k]} وقدّرت مصادر محلية عدد المتضررين بنحو {num}."
            for i, slug in enumerate(sorted(outlets, key=lambda s: s != "demo-wire")):
                v = voices[slug]
                fill = {"loc": loc_en, "loc_ar": loc_ar, "h": v.houthi, "c": v.coalition, "g": v.gov}
                if v.language == "en":
                    if slug == "demo-outlet-intl" and wire_text and rng.random() < 0.5:
                        title, excerpt = wire_text  # verbatim syndication of the wire copy
                    else:
                        t, e = spec["en"][
                            en_variant if slug == "demo-wire" else (en_variant + 1) % len(spec["en"])
                        ]
                        title, excerpt = t.format(**fill), e.format(**fill) + detail_en
                        if slug == "demo-wire":
                            wire_text = (title, excerpt)
                    title = title[0].upper() + title[1:]
                else:
                    title, excerpt = (
                        spec["ar"][0].format(**fill),
                        v.opener + spec["ar"][1].format(**fill) + detail_ar + v.closer,
                    )
                url = f"https://{slug}.{DEMO_DOMAIN}/{day.isoformat()}/{kind}-{n}"
                key = url_hash(canonicalize_url(url))
                if session.scalar(select(m.Article.id).where(m.Article.url_hash == key)) is not None:
                    skipped += 1
                    continue
                session.add(
                    m.Article(
                        source_id=sources[slug].id,
                        is_demo=True,
                        url=url,
                        canonical_url=canonicalize_url(url),
                        url_hash=key,
                        title=title,
                        title_normalized=normalize_for_matching(title),
                        author="DEMO DATA",
                        published_at=base_time + dt.timedelta(minutes=17 * i + rng.randint(0, 30)),
                        excerpt=excerpt,
                        excerpt_normalized=normalize_for_matching(excerpt),
                        content_hash=content_hash(title, excerpt),
                        language=v.language,
                        language_confidence=1.0,
                        script="arabic" if v.language == "ar" else "latin",
                        word_count=len(f"{title} {excerpt}".split()),
                        yemen_relevance=1.0,
                        quality_score=None,
                        quality_detail={},
                        raw_metadata={"demo": True, "story_kind": kind, "language_method": "demo_fixed"},
                        processing_status="new",
                    )
                )
                inserted += 1
        session.flush()
    session.commit()
    return {"inserted": inserted, "skipped_existing": skipped, "demo_sources": len(sources)}


def purge(session: Session) -> dict:
    """Remove every demo record (sources, articles and everything derived from them)."""
    ids = "SELECT id FROM articles WHERE is_demo"
    srcs = "SELECT id FROM sources WHERE is_demo"
    stmts = [
        f"UPDATE articles SET duplicate_of_id = NULL, canonical_article_id = NULL WHERE duplicate_of_id IN ({ids}) OR canonical_article_id IN ({ids})",
        f"UPDATE article_story_clusters SET representative_article_id = NULL WHERE representative_article_id IN ({ids})",
        f"DELETE FROM source_metrics WHERE source_id IN ({srcs})",
        f"DELETE FROM terminology_variants WHERE source_id IN ({srcs})",
        f"DELETE FROM pipeline_errors WHERE source_id IN ({srcs})",
        "DELETE FROM articles WHERE is_demo",
        "DELETE FROM article_story_clusters c WHERE NOT EXISTS (SELECT 1 FROM articles a WHERE a.story_cluster_id = c.id)",
        f"DELETE FROM source_languages WHERE source_id IN ({srcs})",
        "DELETE FROM sources WHERE is_demo",
    ]
    n = session.scalar(text("SELECT count(*) FROM articles WHERE is_demo"))
    for s in stmts:
        session.execute(text(s))
    session.commit()
    return {"articles_deleted": n}
