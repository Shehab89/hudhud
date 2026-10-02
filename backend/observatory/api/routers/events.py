"""Events extracted from coverage, and the geography view."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from observatory.api.deps import DB, F, Page, apply_filters
from observatory.api.util import article_summaries
from observatory.db import models as m

router = APIRouter(tags=["events"])

EVENT_NOTE = (
    "Events are reported incidents detected in news coverage (a trigger word and a known place in "
    "the same sentence). They are not verified incident data; for casualty figures use dedicated "
    "datasets such as ACLED or the Yemen Data Project."
)


@router.get("/events", summary="Reported events detected in coverage")
def list_events(
    db: DB,
    f: F,
    page: Page,
    event_type: Annotated[str | None, Query()] = None,
    location: Annotated[str | None, Query(description="Location entity slug, e.g. gov-taiz")] = None,
) -> dict:
    ids = apply_filters(select(m.Article.id), f).subquery()
    E, L = m.Event, m.Entity
    q = (
        select(E, L.slug, L.name_en, L.name_ar, m.Location.lat, m.Location.lon)
        .outerjoin(L, L.id == E.location_entity_id)
        .outerjoin(m.Location, m.Location.entity_id == L.id)
        .where(
            E.event_date >= f.date_from,
            E.event_date <= f.date_to,
            E.id.in_(select(m.EventMention.event_id).where(m.EventMention.article_id.in_(select(ids.c.id)))),
        )
    )
    if event_type:
        q = q.where(E.event_type == event_type)
    if location:
        q = q.where(L.slug == location)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    limit, offset = page
    rows = db.execute(
        q.order_by(E.event_date.desc(), E.report_count.desc()).limit(limit).offset(offset)
    ).all()
    types = dict(
        db.execute(
            select(E.event_type, func.count())
            .where(E.event_date >= f.date_from, E.event_date <= f.date_to)
            .group_by(E.event_type)
        ).all()
    )
    return {
        "note": EVENT_NOTE,
        "total": total,
        "limit": limit,
        "offset": offset,
        "types": types,
        "items": [
            {
                "id": e.id,
                "type": e.event_type,
                "date": e.event_date,
                "title": e.title,
                "confidence": e.confidence,
                "method": e.method,
                "reports": e.report_count,
                "sources": e.source_count,
                "location": {"slug": s, "name_en": n, "name_ar": na, "lat": lat, "lon": lon} if s else None,
            }
            for e, s, n, na, lat, lon in rows
        ],
    }


@router.get("/events/{event_id}", summary="One event with the reports and actors linked to it")
def get_event(db: DB, event_id: int) -> dict:
    e = db.get(m.Event, event_id)
    if e is None:
        raise HTTPException(404, "event not found")
    loc = db.get(m.Entity, e.location_entity_id) if e.location_entity_id else None
    mentions = db.execute(
        select(m.EventMention, m.Article)
        .join(m.Article, m.Article.id == m.EventMention.article_id)
        .where(m.EventMention.event_id == e.id)
        .order_by(m.Article.published_at)
    ).all()
    actors = db.execute(
        select(m.Entity.slug, m.Entity.name_en, m.Entity.name_ar, m.EventActor.mention_count)
        .join(m.EventActor, m.EventActor.entity_id == m.Entity.id)
        .where(m.EventActor.event_id == e.id)
        .order_by(m.EventActor.mention_count.desc())
    ).all()
    summaries = {s.id: s for s in article_summaries(db, [a for _, a in mentions])}
    return {
        "note": EVENT_NOTE,
        "id": e.id,
        "type": e.event_type,
        "date": e.event_date,
        "title": e.title,
        "confidence": e.confidence,
        "method": e.method,
        "reports": e.report_count,
        "sources": e.source_count,
        "location": {"slug": loc.slug, "name_en": loc.name_en, "name_ar": loc.name_ar} if loc else None,
        "actors": [{"slug": r[0], "name_en": r[1], "name_ar": r[2], "mentions": r[3]} for r in actors],
        "reports_list": [
            {
                "article": summaries[a.id],
                "evidence_sentence": em.evidence_sentence,
                "trigger": em.trigger,
                "confidence": em.confidence,
            }
            for em, a in mentions
        ],
    }


@router.get("/geography", summary="Coverage and reported events per governorate and named place")
def geography(db: DB, f: F) -> dict:
    ids = apply_filters(select(m.Article.id), f).subquery()
    L, Loc = m.Entity, m.Location
    # mentions of a place count toward the place and, through governorate_entity_id, its governorate
    rows = db.execute(
        select(
            L.id,
            L.slug,
            L.name_en,
            L.name_ar,
            Loc.location_type,
            Loc.admin_code,
            Loc.lat,
            Loc.lon,
            Loc.governorate_entity_id,
            func.count(func.distinct(m.EntityMention.article_id)),
        )
        .join(Loc, Loc.entity_id == L.id)
        .outerjoin(
            m.EntityMention,
            (m.EntityMention.entity_id == L.id) & m.EntityMention.article_id.in_(select(ids.c.id)),
        )
        .group_by(L.id, Loc.entity_id)
    ).all()
    ev = dict(
        db.execute(
            select(m.Event.location_entity_id, func.count())
            .where(
                m.Event.event_date >= f.date_from,
                m.Event.event_date <= f.date_to,
                m.Event.id.in_(
                    select(m.EventMention.event_id).where(m.EventMention.article_id.in_(select(ids.c.id)))
                ),
            )
            .group_by(m.Event.location_entity_id)
        ).all()
    )
    ev_types = db.execute(
        select(m.Event.location_entity_id, m.Event.event_type, func.count())
        .where(m.Event.event_date >= f.date_from, m.Event.event_date <= f.date_to)
        .group_by(m.Event.location_entity_id, m.Event.event_type)
    ).all()
    types: dict[int, dict[str, int]] = {}
    for lid, t, n in ev_types:
        types.setdefault(lid, {})[t] = n
    places = [
        {
            "slug": r[1],
            "name_en": r[2],
            "name_ar": r[3],
            "type": r[4],
            "admin_code": r[5],
            "lat": r[6],
            "lon": r[7],
            "articles": r[9],
            "events": ev.get(r[0], 0),
            "event_types": types.get(r[0], {}),
            "_id": r[0],
            "_gov": r[8],
        }
        for r in rows
    ]
    by_id = {p["_id"]: p for p in places}
    for p in places:
        p["articles_including_places"] = p["articles"]
    for p in places:
        if p["_gov"] and p["_gov"] in by_id:
            by_id[p["_gov"]]["articles_including_places"] += p["articles"]
    for p in places:
        p.pop("_id"), p.pop("_gov")
    return {
        "note": EVENT_NOTE,
        "governorates": [p for p in places if p["type"] == "governorate"],
        "places": [p for p in places if p["type"] != "governorate"],
    }
