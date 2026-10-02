"""Daily descriptive summary in English and Arabic.

The summary is generated from aggregates with fixed templates: it reports what was
published and how coverage changed, never what is true, who is right, or what
anyone should think. Every figure in the text is also stored in ``data`` so the
frontend can link each claim back to the numbers behind it.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from hudhud.analytics.trends import compute_trends
from hudhud.db import models as m

BASE_LABELS = {
    "sanaa_controlled": ("outlets based in Sana'a-controlled areas", "منافذ في مناطق سيطرة صنعاء"),
    "government_controlled": ("outlets based in government-controlled areas", "منافذ في مناطق سيطرة الحكومة"),
    "stc_controlled": ("outlets based in STC-controlled areas", "منافذ في مناطق سيطرة الانتقالي"),
    "outside_yemen": ("outlets based outside Yemen", "منافذ خارج اليمن"),
}


def _data(session: Session, day: dt.date) -> dict:
    dm = session.get(m.DailyMetric, day)
    p = {
        "d": dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC),
        "d1": dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=dt.UTC),
    }
    bases = dict(
        session.execute(
            text("""SELECT s.operating_base, count(*) FROM articles a JOIN sources s ON s.id=a.source_id
        WHERE a.deleted_at IS NULL AND a.duplicate_of_id IS NULL AND a.published_at >= :d AND a.published_at < :d1
        GROUP BY 1"""),
            p,
        ).all()
    )
    demo = (
        session.scalar(
            text("""SELECT count(*) FROM articles a WHERE a.is_demo AND a.duplicate_of_id IS NULL
        AND a.published_at >= :d AND a.published_at < :d1"""),
            p,
        )
        or 0
    )
    top_level = {cid for cid in session.scalars(select(m.Category.id).where(m.Category.parent_id.is_(None)))}
    trends = [t for t in compute_trends(session, "category", day) if t.ref_id in top_level]
    cats = {
        c.id: c
        for c in session.scalars(select(m.Category).where(m.Category.id.in_([t.ref_id for t in trends])))
    }
    ents = session.execute(
        select(m.Entity.name_en, m.Entity.name_ar, m.EntityMetric.article_count, m.EntityMetric.source_count)
        .join(m.EntityMetric, m.EntityMetric.entity_id == m.Entity.id)
        .where(m.EntityMetric.day == day, m.Entity.entity_type != "location")
        .order_by(m.EntityMetric.article_count.desc())
        .limit(5)
    ).all()
    return {
        "articles": dm.articles if dm else 0,
        "unique_stories": dm.unique_stories if dm else 0,
        "sources_active": dm.sources_active if dm else 0,
        "languages": dm.language_distribution if dm else {},
        "operating_base": bases,
        "demo_articles": int(demo),
        "top_categories": [
            {
                "id": t.ref_id,
                "slug": cats[t.ref_id].slug,
                "name_en": cats[t.ref_id].name_en,
                "name_ar": cats[t.ref_id].name_ar,
                "articles_7d": t.frequency,
                "growth_rate": t.growth_rate,
                "status": t.status,
            }
            for t in trends[:5]
        ],
        "emerging": [
            {
                "slug": cats[t.ref_id].slug,
                "name_en": cats[t.ref_id].name_en,
                "name_ar": cats[t.ref_id].name_ar,
                "growth_rate": t.growth_rate,
            }
            for t in trends
            # with no earlier coverage to compare against, "grew markedly" would be meaningless
            if t.status == "emerging" and t.previous > 0
        ][:3],
        "top_actors": [
            {"name_en": e[0], "name_ar": e[1] or e[0], "articles": e[2], "sources": e[3]} for e in ents
        ],
    }


def render_en(day: dt.date, d: dict) -> str:
    if not d["articles"]:
        return f"No Yemen-related articles were recorded for {day.isoformat()}."
    lines = [
        f"On {day.isoformat()} Hudhud recorded {d['articles']} Yemen-related articles "
        f"({d['unique_stories']} distinct stories) from {d['sources_active']} outlets in "
        f"{len(d['languages'])} languages."
    ]
    if d["top_categories"]:
        cats = ", ".join(f"{c['name_en']} ({c['articles_7d']} in 7 days)" for c in d["top_categories"][:3])
        lines.append(f"The most covered themes over the past week were {cats}.")
    if d["emerging"]:
        lines.append("Coverage grew markedly for " + ", ".join(e["name_en"] for e in d["emerging"]) + ".")
    if d["top_actors"]:
        lines.append(
            "The most mentioned actors were "
            + ", ".join(
                f"{a['name_en']} ({a['articles']} articles, {a['sources']} outlets)"
                for a in d["top_actors"][:3]
            )
            + "."
        )
    split = [
        f"{n} from {BASE_LABELS[k][0]}"
        for k, n in sorted(d["operating_base"].items(), key=lambda x: -x[1])
        if k in BASE_LABELS
    ]
    if split:
        lines.append("By newsroom location: " + "; ".join(split) + ".")
    if d["demo_articles"]:
        lines.append(
            f"DEMO DATA: {d['demo_articles']} of these articles are synthetic demonstration records."
        )
    lines.append(
        "Counts describe coverage volume only; they do not indicate importance, accuracy or public opinion."
    )
    return " ".join(lines)


def render_ar(day: dt.date, d: dict) -> str:
    if not d["articles"]:
        return f"لم تُسجَّل مقالات متعلقة باليمن بتاريخ {day.isoformat()}."
    lines = [
        f"في {day.isoformat()} سجّل هدهد {d['articles']} مقالاً متعلقاً باليمن "
        f"({d['unique_stories']} قصة مختلفة) من {d['sources_active']} منفذاً إعلامياً بـ{len(d['languages'])} لغات."
    ]
    if d["top_categories"]:
        cats = "، ".join(
            f"{c['name_ar'] or c['name_en']} ({c['articles_7d']} خلال 7 أيام)"
            for c in d["top_categories"][:3]
        )
        lines.append(f"أكثر المواضيع تغطية خلال الأسبوع: {cats}.")
    if d["emerging"]:
        lines.append(
            "ارتفعت التغطية بشكل ملحوظ لـ: "
            + "، ".join(e["name_ar"] or e["name_en"] for e in d["emerging"])
            + "."
        )
    if d["top_actors"]:
        lines.append(
            "أكثر الفاعلين ذكراً: "
            + "، ".join(
                f"{a['name_ar']} ({a['articles']} مقالاً، {a['sources']} منافذ)" for a in d["top_actors"][:3]
            )
            + "."
        )
    split = [
        f"{n} من {BASE_LABELS[k][1]}"
        for k, n in sorted(d["operating_base"].items(), key=lambda x: -x[1])
        if k in BASE_LABELS
    ]
    if split:
        lines.append("حسب موقع غرفة الأخبار: " + "؛ ".join(split) + ".")
    if d["demo_articles"]:
        lines.append(
            f"بيانات تجريبية (DEMO DATA): {d['demo_articles']} من هذه المقالات سجلات تجريبية مُصطنعة."
        )
    lines.append("تصف الأرقام حجم التغطية فقط، ولا تدل على الأهمية أو الدقة أو الرأي العام.")
    return " ".join(lines)


def build_daily_summary(session: Session, day: dt.date) -> dict:
    d = _data(session, day)
    session.execute(delete(m.DailySummary).where(m.DailySummary.day == day))
    for lang, body in (("en", render_en(day, d)), ("ar", render_ar(day, d))):
        session.add(m.DailySummary(day=day, language=lang, content=body, data=d, method="template"))
    session.flush()
    return d
