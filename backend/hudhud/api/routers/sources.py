"""Source registry, evidence-backed orientation profiles, and source and group comparison."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from hudhud.api.deps import DB, F, Filters, apply_filters
from hudhud.api.util import article_summaries
from hudhud.db import models as m

router = APIRouter(tags=["sources"])

ORIENTATION_NOTE = (
    "Orientation describes ownership, funding and stated editorial alignment, documented with "
    "evidence. It is not a measure of accuracy, quality or reliability, and it is separate from "
    "the sentiment, framing and topic of any individual article."
)
SCORES_NOTE = (
    "Influence (audience and weight in Yemen discourse) and institutional importance (speaking "
    "for an institution) are separate attributes. Official status raises neither influence nor "
    "reliability. Reliability is not assessed unless a record cites evidence for it."
)
COMPARISON_NOTE = (
    "Groups are compared on what their sources published: volume, topics, framing, tone, actors "
    "and places. Official statements show what an institution says, not what happened, and no "
    "group is treated as more reliable than another."
)


def _curated(s: m.Source) -> dict:
    sel = s.selection or {}
    return {
        "category": s.category,
        "tier": s.tier,
        "region": s.region,
        "platform": s.platform,
        "content_type": s.content_type,
        "registry_status": s.registry_status,
        "yemen_political_alignment": s.yemen_political_alignment,
        "sub_alignment": s.sub_alignment,
        "regional_alignment": s.regional_alignment,
        "domestic_political_orientation": s.domestic_political_orientation,
        "classification_confidence": s.classification_confidence,
        "assessment_date": s.assessment_date,
        "influence_score": s.influence_score,
        "institutional_importance": s.institutional_importance,
        "reliability_score": s.reliability_score,  # None = not assessed
        "selection_reason": sel.get("reason"),
        "holder": s.holder,
        "accounts": [
            {k: a.get(k) for k in ("platform", "handle", "url", "followers", "followers_as_of")}
            for a in s.accounts or []
        ],
    }


def _orientation(o: m.SourceOrientation | None) -> dict | None:
    if o is None:
        return None
    return {
        "simplified": o.simplified,
        "dimensions": o.dimensions,
        "confidence": o.confidence,
        "evidence": o.evidence,
        "method": o.method,
        "valid_from": o.valid_from,
        "valid_to": o.valid_to,
        "last_reviewed": o.last_reviewed,
        "review_status": o.review_status,
        "evidence_items": [
            {"url": e.url, "type": e.evidence_type, "note": e.note, "accessed_at": e.accessed_at}
            for e in o.evidence_items
        ],
    }


@router.get("/sources", summary="Source registry with orientation, health and article counts")
def list_sources(
    db: DB,
    f: F,
    group: Annotated[str | None, Query()] = None,
    operating_base: Annotated[str | None, Query()] = None,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    active_only: bool = False,
    registry: Annotated[
        Literal["curated", "archived", "all"],
        Query(description="curated = the current source universe; archived = earlier registry."),
    ] = "curated",
) -> dict:
    q = (
        select(m.Source)
        .where(m.Source.deleted_at.is_(None))
        .options(
            selectinload(m.Source.orientations).selectinload(m.SourceOrientation.evidence_items),
            selectinload(m.Source.languages),
            selectinload(m.Source.feeds),
        )
    )
    if group:
        q = q.where(m.Source.source_group == group)
    if operating_base:
        q = q.where(m.Source.operating_base == operating_base)
    if country:
        q = q.where(m.Source.country == country.upper())
    if active_only:
        q = q.where(m.Source.active.is_(True))
    if registry != "all":
        q = q.where((m.Source.registry_status == registry) | m.Source.is_demo.is_(True))
    if f.source_filtered():
        from hudhud.api.deps import source_id_query

        q = q.where(m.Source.id.in_(source_id_query(f)))
    if f.demo == "exclude":
        q = q.where(m.Source.is_demo.is_(False))
    elif f.demo == "only":
        q = q.where(m.Source.is_demo.is_(True))
    counts = dict(
        db.execute(
            apply_filters(select(m.Article.source_id, func.count()), f).group_by(m.Article.source_id)
        ).all()
    )
    out = []
    for s in db.scalars(q.order_by(m.Source.category, m.Source.name)):
        cur = next((o for o in s.orientations if o.valid_to is None), None)
        out.append(
            {
                **_curated(s),
                "slug": s.slug,
                "name": s.name,
                "name_native": s.name_native,
                "url": s.url,
                "country": s.country,
                "source_type": s.source_type,
                "source_group": s.source_group,
                "operating_base": s.operating_base,
                "languages": [lang.language_code for lang in s.languages],
                "active": s.active,
                "is_demo": s.is_demo,
                "access_policy": s.access_policy,
                "health_status": s.health_status,
                "last_success_at": s.last_success_at,
                "feeds": len(s.feeds),
                "orientation": {
                    "simplified": cur.simplified,
                    "confidence": cur.confidence,
                    "method": cur.method,
                    "review_status": cur.review_status,
                    "evidence": cur.evidence,
                    "evidence_items": [{"url": e.url, "type": e.evidence_type} for e in cur.evidence_items],
                }
                if cur
                else None,
                "articles": counts.get(s.id, 0),
            }
        )
    return {"note": ORIENTATION_NOTE, "scores_note": SCORES_NOTE, "count": len(out), "sources": out}


def _profile_stats(db: DB, f: Filters, source_ids: list[int]) -> dict:
    ids = apply_filters(select(m.Article.id), f).where(m.Article.source_id.in_(source_ids)).subquery()
    in_ids = select(ids.c.id)
    day = func.date_trunc("day", m.Article.published_at)
    series = db.execute(
        select(day, func.count()).where(m.Article.id.in_(in_ids)).group_by(day).order_by(day)
    ).all()
    C, P = m.Category, m.Category.__table__.alias("p")
    cats = db.execute(
        select(func.coalesce(P.c.slug, C.slug), func.count())
        .select_from(m.CategoryAssignment)
        .join(C, C.id == m.CategoryAssignment.category_id)
        .outerjoin(P, P.c.id == C.parent_id)
        .where(
            m.CategoryAssignment.is_current.is_(True),
            m.CategoryAssignment.rank == "primary",
            m.CategoryAssignment.article_id.in_(in_ids),
        )
        .group_by(func.coalesce(P.c.slug, C.slug))
        .order_by(func.count().desc())
    ).all()
    sentiment = dict(
        db.execute(
            select(m.SentimentAnalysis.polarity, func.count())
            .where(m.SentimentAnalysis.is_current.is_(True), m.SentimentAnalysis.article_id.in_(in_ids))
            .group_by(m.SentimentAnalysis.polarity)
        ).all()
    )
    tone = db.execute(
        select(m.EmotionAnalysis.dominant, func.count())
        .where(
            m.EmotionAnalysis.is_current.is_(True),
            m.EmotionAnalysis.kind == "tone",
            m.EmotionAnalysis.article_id.in_(in_ids),
        )
        .group_by(m.EmotionAnalysis.dominant)
        .order_by(func.count().desc())
    ).all()
    frames = db.execute(
        select(m.Frame.slug, m.Frame.name_en, m.Frame.name_ar, func.count())
        .join(m.FramingAnalysis, m.FramingAnalysis.frame_id == m.Frame.id)
        .where(m.FramingAnalysis.is_current.is_(True), m.FramingAnalysis.article_id.in_(in_ids))
        .group_by(m.Frame.id)
        .order_by(func.count().desc())
    ).all()
    terms = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.EntityAlias.surface_form,
            m.EntityAlias.alias_type,
            m.EntityAlias.framing_note,
            func.count(),
        )
        .select_from(m.EntityMention)
        .join(m.EntityAlias, m.EntityAlias.id == m.EntityMention.alias_id)
        .join(m.Entity, m.Entity.id == m.EntityMention.entity_id)
        .where(
            m.EntityMention.article_id.in_(in_ids),
            m.Entity.entity_type != "location",
            m.Entity.entity_type != "country",
        )
        .group_by(m.Entity.id, m.EntityAlias.id)
        .order_by(func.count().desc())
        .limit(40)
    ).all()
    actors = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.Entity.name_ar,
            func.count(func.distinct(m.EntityMention.article_id)),
            func.avg(m.TargetedSentiment.score),
        )
        .join(m.EntityMention, m.EntityMention.entity_id == m.Entity.id)
        .outerjoin(
            m.TargetedSentiment,
            (m.TargetedSentiment.entity_id == m.Entity.id)
            & (m.TargetedSentiment.article_id == m.EntityMention.article_id)
            & m.TargetedSentiment.is_current.is_(True),
        )
        .where(m.EntityMention.article_id.in_(in_ids), m.Entity.entity_type != "location")
        .group_by(m.Entity.id)
        .order_by(func.count(func.distinct(m.EntityMention.article_id)).desc())
        .limit(15)
    ).all()
    places = db.execute(
        select(
            m.Entity.slug,
            m.Entity.name_en,
            m.Entity.name_ar,
            func.count(func.distinct(m.EntityMention.article_id)),
        )
        .join(m.EntityMention, m.EntityMention.entity_id == m.Entity.id)
        .where(m.EntityMention.article_id.in_(in_ids), m.Entity.entity_type == "location")
        .group_by(m.Entity.id)
        .order_by(func.count(func.distinct(m.EntityMention.article_id)).desc())
        .limit(12)
    ).all()
    events = db.execute(
        select(m.Event.event_type, func.count(func.distinct(m.Event.id)))
        .join(m.EventMention, m.EventMention.event_id == m.Event.id)
        .where(m.EventMention.article_id.in_(in_ids))
        .group_by(m.Event.event_type)
        .order_by(func.count(func.distinct(m.Event.id)).desc())
    ).all()
    total = db.scalar(select(func.count()).select_from(ids)) or 0
    return {
        "articles": total,
        "places": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "articles": r[3]} for r in places],
        "events": [{"event_type": t, "events": n} for t, n in events],
        "series": [{"day": d.date(), "articles": n} for d, n in series],
        "categories": [{"slug": s, "articles": n} for s, n in cats],
        "sentiment": sentiment,
        "tone": [{"tone": t, "articles": n} for t, n in tone],
        "frames": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "articles": r[3]} for r in frames],
        "terminology": [
            {
                "entity": r[0],
                "entity_name": r[1],
                "term": r[2],
                "alias_type": r[3],
                "framing_note": r[4],
                "mentions": r[5],
            }
            for r in terms
        ],
        "actors": [
            {
                "slug": r[0],
                "name_en": r[1],
                "name_ar": r[2],
                "articles": r[3],
                "mean_targeted_sentiment": round(float(r[4]), 3) if r[4] is not None else None,
            }
            for r in actors
        ],
    }


@router.get(
    "/sources/{slug}", summary="Source profile: registry entry, orientation history, coverage patterns"
)
def get_source(db: DB, f: F, slug: str) -> dict:
    s = db.scalar(
        select(m.Source)
        .where(m.Source.slug == slug)
        .options(
            selectinload(m.Source.orientations).selectinload(m.SourceOrientation.evidence_items),
            selectinload(m.Source.languages),
            selectinload(m.Source.feeds),
        )
    )
    if s is None:
        raise HTTPException(404, "source not found")
    history = sorted(s.orientations, key=lambda o: (o.valid_from is None, o.valid_from), reverse=True)
    recent = article_summaries(
        db,
        db.scalars(
            apply_filters(select(m.Article), f)
            .where(m.Article.source_id == s.id)
            .order_by(m.Article.published_at.desc())
            .limit(15)
        ),
    )
    return {
        "note": ORIENTATION_NOTE,
        "scores_note": SCORES_NOTE,
        **_curated(s),
        "selection": s.selection,
        "accounts": s.accounts,
        "wikidata": s.wikidata,
        "slug": s.slug,
        "name": s.name,
        "name_native": s.name_native,
        "url": s.url,
        "domain": s.domain,
        "country": s.country,
        "source_type": s.source_type,
        "source_group": s.source_group,
        "operating_base": s.operating_base,
        "geographic_focus": s.geographic_focus,
        "yemen_coverage": s.yemen_coverage,
        "languages": [lang.language_code for lang in s.languages],
        "ownership": s.ownership_description,
        "ownership_evidence_urls": s.ownership_evidence_urls,
        "access_policy": s.access_policy,
        "active": s.active,
        "is_demo": s.is_demo,
        "notes": s.notes,
        "health": {
            "status": s.health_status,
            "last_success_at": s.last_success_at,
            "last_failure_at": s.last_failure_at,
            "consecutive_failures": s.consecutive_failures,
        },
        "feeds": [
            {
                "url": fd.url,
                "type": fd.feed_type,
                "verified": fd.verified,
                "verified_at": fd.verified_at,
                "active": fd.active,
                "health_status": fd.health_status,
                "last_success_at": fd.last_success_at,
                "last_item_count": fd.last_item_count,
                "notes": fd.notes,
            }
            for fd in s.feeds
        ],
        "orientation": _orientation(next((o for o in s.orientations if o.valid_to is None), None)),
        "orientation_history": [_orientation(o) for o in history],
        "stats": _profile_stats(db, f, [s.id]),
        "recent_articles": recent,
    }


@router.get("/compare/sources", summary="Side-by-side comparison of 2-6 sources under the same filters")
def compare_sources(
    db: DB, f: F, slugs: Annotated[str, Query(description="Comma-separated source slugs (2-6).")]
) -> dict:
    wanted = [x.strip() for x in slugs.split(",") if x.strip()]
    if not 2 <= len(wanted) <= 6:
        raise HTTPException(422, "provide between 2 and 6 source slugs")
    out = []
    for slug in wanted:
        s = db.scalar(
            select(m.Source).where(m.Source.slug == slug).options(selectinload(m.Source.orientations))
        )
        if s is None:
            raise HTTPException(404, f"source not found: {slug}")
        cur = next((o for o in s.orientations if o.valid_to is None), None)
        out.append(
            {
                "slug": s.slug,
                "name": s.name,
                "operating_base": s.operating_base,
                "source_group": s.source_group,
                "is_demo": s.is_demo,
                "category": s.category,
                "content_type": s.content_type,
                "orientation": {"simplified": cur.simplified, "confidence": cur.confidence} if cur else None,
                **_profile_stats(db, f, [s.id]),
            }
        )
    shared = db.execute(
        select(m.Article.story_cluster_id, func.count(func.distinct(m.Source.slug)))
        .join(m.Source, m.Source.id == m.Article.source_id)
        .where(
            m.Source.slug.in_(wanted),
            m.Article.story_cluster_id.is_not(None),
            m.Article.published_at >= f.start,
            m.Article.published_at < f.end,
        )
        .group_by(m.Article.story_cluster_id)
        .having(func.count(func.distinct(m.Source.slug)) == len(wanted))
    ).all()
    return {
        "filters": f.as_dict(),
        "note": ORIENTATION_NOTE,
        "sources": out,
        "stories_covered_by_all": len(shared),
    }


# ---------------------------------------------------------------- group comparison


class GroupFilter(BaseModel):
    """Sources matching every listed attribute (values within one attribute are alternatives)."""

    category: list[str] = []
    tier: list[str] = []
    region: list[str] = []
    country: list[str] = []
    yemen_alignment: list[str] = []
    regional_alignment: list[str] = []
    content_type: list[str] = []
    slug: list[str] = []
    not_region: list[str] = []
    not_country: list[str] = []


class Group(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_-]{1,40}$")
    label: dict[str, str]
    # A source belongs to the group if it matches ANY of these filters.
    any: list[GroupFilter] = Field(min_length=1, max_length=6)


class GroupComparison(BaseModel):
    groups: list[Group] = Field(min_length=2, max_length=6)


def _g(key: str, en: str, ar: str, *filters: dict[str, Any]) -> dict[str, Any]:
    return {"key": key, "label": {"en": en, "ar": ar}, "any": list(filters)}


_OFFICIAL = ["OFFICIAL_GOVERNMENT", "DIPLOMATIC_MISSION"]


def _state(key: str, en: str, ar: str, country: str) -> dict[str, Any]:
    # A state's official voice: its ministries, its missions and its officials' own accounts.
    return _g(
        key,
        en,
        ar,
        {"category": _OFFICIAL, "country": [country]},
        {"category": ["SOCIAL_ACCOUNT"], "tier": ["B"], "country": [country]},
    )


PRESETS: dict[str, dict[str, Any]] = {
    "saudi-media-vs-government": {
        "title": {"en": "Saudi media vs Saudi government", "ar": "الإعلام السعودي مقابل الحكومة السعودية"},
        "groups": [
            _g(
                "saudi_media",
                "Saudi media",
                "الإعلام السعودي",
                {"category": ["MEDIA"], "regional_alignment": ["saudi"]},
            ),
            _state("saudi_official", "Saudi government and diplomats", "الحكومة والدبلوماسية السعودية", "SA"),
        ],
    },
    "yemeni-camps": {
        "title": {
            "en": "Government / PLC vs Houthi vs STC",
            "ar": "الحكومة / مجلس القيادة مقابل الحوثيين مقابل الانتقالي",
        },
        "groups": [
            _g(
                "plc",
                "Government / PLC",
                "الحكومة / مجلس القيادة",
                {"region": ["yemen"], "yemen_alignment": ["plc_government"]},
            ),
            _g(
                "ansar_allah",
                "Houthi (Ansar Allah)",
                "الحوثيون (أنصار الله)",
                {"region": ["yemen"], "yemen_alignment": ["ansar_allah"]},
            ),
            _g(
                "stc",
                "Southern Transitional Council",
                "المجلس الانتقالي الجنوبي",
                {"region": ["yemen"], "yemen_alignment": ["stc"]},
            ),
        ],
    },
    "foreign-actors": {
        "title": {
            "en": "Saudi vs UAE vs Iran vs US vs UK (official voices)",
            "ar": "السعودية والإمارات وإيران والولايات المتحدة والمملكة المتحدة (المصادر الرسمية)",
        },
        "groups": [
            _state("sa", "Saudi Arabia", "السعودية", "SA"),
            _state("ae", "United Arab Emirates", "الإمارات", "AE"),
            _state("ir", "Iran", "إيران", "IR"),
            _state("us", "United States", "الولايات المتحدة", "US"),
            _state("gb", "United Kingdom", "المملكة المتحدة", "GB"),
        ],
    },
    "media-vs-diplomacy": {
        "title": {
            "en": "International media vs foreign ministries vs embassies",
            "ar": "الإعلام الدولي مقابل وزارات الخارجية مقابل السفارات",
        },
        "groups": [
            _g(
                "intl_media",
                "International media",
                "الإعلام الدولي",
                {"category": ["MEDIA"], "not_region": ["yemen"]},
            ),
            _g(
                "ministries",
                "Foreign governments",
                "الحكومات الأجنبية",
                {"category": ["OFFICIAL_GOVERNMENT"], "not_country": ["YE"]},
            ),
            _g(
                "embassies",
                "Embassies and missions",
                "السفارات والبعثات",
                {"category": ["DIPLOMATIC_MISSION"], "not_country": ["YE"]},
            ),
        ],
    },
    "yemeni-media-vs-official": {
        "title": {
            "en": "Yemeni media vs Yemeni official sources",
            "ar": "الإعلام اليمني مقابل المصادر الرسمية اليمنية",
        },
        "groups": [
            _g("ye_media", "Yemeni media", "الإعلام اليمني", {"category": ["MEDIA"], "region": ["yemen"]}),
            _g(
                "ye_official",
                "Yemeni official sources",
                "المصادر الرسمية اليمنية",
                {"category": _OFFICIAL, "region": ["yemen"]},
            ),
            _g(
                "ye_parties",
                "Yemeni political organisations",
                "التنظيمات السياسية اليمنية",
                {"category": ["POLITICAL_ORGANIZATION"], "region": ["yemen"]},
            ),
        ],
    },
    "institutions-vs-media": {
        "title": {
            "en": "International institutions vs international media",
            "ar": "المؤسسات الدولية مقابل الإعلام الدولي",
        },
        "groups": [
            _g(
                "institutions",
                "International institutions",
                "المؤسسات الدولية",
                {"category": ["INTERNATIONAL_INSTITUTION"]},
            ),
            _g(
                "intl_media",
                "International media",
                "الإعلام الدولي",
                {"category": ["MEDIA"], "not_region": ["yemen"]},
            ),
        ],
    },
}


def _group_sources(gf: GroupFilter, demo: str) -> Select:
    S = m.Source
    q = select(S.id).where(S.deleted_at.is_(None), S.registry_status == "curated")
    if demo == "exclude":
        q = q.where(S.is_demo.is_(False))
    elif demo == "only":
        q = q.where(S.is_demo.is_(True))
    for values, col in (
        (gf.category, S.category),
        (gf.tier, S.tier),
        (gf.region, S.region),
        (gf.country, S.country),
        (gf.yemen_alignment, S.yemen_political_alignment),
        (gf.regional_alignment, S.regional_alignment),
        (gf.content_type, S.content_type),
        (gf.slug, S.slug),
    ):
        if values:
            q = q.where(col.in_(values))
    if gf.not_region:
        q = q.where(S.region.not_in(gf.not_region))
    if gf.not_country:
        q = q.where(S.country.not_in(gf.not_country))
    return q


def _compare_groups(db: DB, f: Filters, groups: list[Group]) -> dict:
    out, members = [], {}
    for g in groups:
        ids: set[int] = set()
        for gf in g.any:
            ids |= set(db.scalars(_group_sources(gf, f.demo)))
        members[g.key] = ids
        srcs = (
            db.scalars(select(m.Source).where(m.Source.id.in_(ids)).order_by(m.Source.name)).all()
            if ids
            else []
        )
        content_types: dict[str, int] = {}
        for s in srcs:
            content_types[s.content_type] = content_types.get(s.content_type, 0) + 1
        out.append(
            {
                "key": g.key,
                "label": g.label,
                "filter": [gf.model_dump(exclude_defaults=True) for gf in g.any],
                "source_count": len(srcs),
                "collected_sources": sum(1 for s in srcs if s.active),
                "content_types": content_types,
                "sources": [
                    {
                        "slug": s.slug,
                        "name": s.name,
                        "category": s.category,
                        "content_type": s.content_type,
                        "active": s.active,
                    }
                    for s in srcs
                ],
                **(_profile_stats(db, f, list(ids)) if ids else {"articles": 0}),
            }
        )
    return {
        "filters": f.as_dict(),
        "note": COMPARISON_NOTE,
        "groups": out,
        "shared_stories": _shared_stories(db, f, members),
    }


def _shared_stories(db: DB, f: Filters, members: dict[str, set[int]], limit: int = 8) -> list[dict]:
    """Story clusters reported by every group, with one headline per group."""
    if any(not ids for ids in members.values()):
        return []
    A = m.Article
    per_group: dict[str, dict[int, m.Article]] = {}
    for key, ids in members.items():
        rows = db.scalars(
            apply_filters(select(A), f, dedupe=False)
            .where(A.source_id.in_(ids), A.story_cluster_id.is_not(None))
            .order_by(A.published_at.desc())
            .limit(2000)
        )
        first: dict[int, m.Article] = {}
        for a in rows:
            first.setdefault(a.story_cluster_id, a)
        per_group[key] = first
    common = set.intersection(*(set(v) for v in per_group.values()))
    latest = sorted(
        common, key=lambda c: max(per_group[k][c].published_at or f.start for k in per_group), reverse=True
    )[:limit]
    stories = []
    for cid in latest:
        heads = {k: per_group[k][cid] for k in per_group}
        summaries = article_summaries(db, heads.values())
        stories.append(
            {
                "story_cluster_id": cid,
                "headlines": {k: s.model_dump() for k, s in zip(heads, summaries, strict=True)},
            }
        )
    return stories


@router.get(
    "/compare/presets", summary="Ready-made group comparisons (media vs official, camps, foreign actors)"
)
def compare_presets() -> dict:
    return {
        "note": COMPARISON_NOTE,
        "presets": [{"key": k, "title": v["title"], "groups": v["groups"]} for k, v in PRESETS.items()],
    }


@router.get("/compare/groups", summary="Compare groups of sources defined by a preset")
def compare_groups_preset(
    db: DB, f: F, preset: Annotated[str, Query(description="Key from /compare/presets.")]
) -> dict:
    if preset not in PRESETS:
        raise HTTPException(404, f"unknown preset: {preset}")
    body = GroupComparison.model_validate({"groups": PRESETS[preset]["groups"]})
    return {"preset": preset, "title": PRESETS[preset]["title"], **_compare_groups(db, f, body.groups)}


@router.post("/compare/groups", summary="Compare 2-6 custom groups of sources")
def compare_groups_custom(db: DB, f: F, body: GroupComparison) -> dict:
    return {"preset": None, **_compare_groups(db, f, body.groups)}
