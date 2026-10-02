"""Research mode: citation-ready exports, saved queries and annotations."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from hudhud.api.deps import DB, CurrentUser, F, apply_filters
from hudhud.db import models as m

router = APIRouter(tags=["research"])
EXPORT_LIMIT = 10_000
EXPORT_FIELDS = [
    "id",
    "is_demo",
    "published_at",
    "source",
    "source_group",
    "operating_base",
    "language",
    "title",
    "url",
    "excerpt",
    "primary_category",
    "sentiment",
    "sentiment_confidence",
    "frames",
    "story_cluster_id",
    "is_syndicated",
]


def _rows(db: DB, f, limit: int) -> list[dict[str, Any]]:
    A = m.Article
    rows = db.execute(
        apply_filters(select(A, m.Source).join(m.Source, m.Source.id == A.source_id), f)
        .order_by(A.published_at.desc())
        .limit(limit)
    ).all()
    ids = [a.id for a, _ in rows]
    cats = dict(
        db.execute(
            select(m.CategoryAssignment.article_id, m.Category.slug)
            .join(m.Category, m.Category.id == m.CategoryAssignment.category_id)
            .where(
                m.CategoryAssignment.article_id.in_(ids),
                m.CategoryAssignment.is_current.is_(True),
                m.CategoryAssignment.rank == "primary",
            )
        ).all()
    )
    sents = {
        r[0]: (r[1], r[2])
        for r in db.execute(
            select(
                m.SentimentAnalysis.article_id, m.SentimentAnalysis.polarity, m.SentimentAnalysis.confidence
            ).where(m.SentimentAnalysis.article_id.in_(ids), m.SentimentAnalysis.is_current.is_(True))
        ).all()
    }
    frames: dict[int, list[str]] = {}
    for aid, slug in db.execute(
        select(m.FramingAnalysis.article_id, m.Frame.slug)
        .join(m.Frame, m.Frame.id == m.FramingAnalysis.frame_id)
        .where(m.FramingAnalysis.article_id.in_(ids), m.FramingAnalysis.is_current.is_(True))
    ).all():
        frames.setdefault(aid, []).append(slug)
    return [
        {
            "id": a.id,
            "is_demo": a.is_demo,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "source": s.name,
            "source_group": s.source_group,
            "operating_base": s.operating_base,
            "language": a.language,
            "title": a.title,
            "url": a.url,
            "excerpt": a.excerpt,
            "primary_category": cats.get(a.id),
            "sentiment": sents.get(a.id, (None, None))[0],
            "sentiment_confidence": sents.get(a.id, (None, None))[1],
            "frames": ";".join(sorted(frames.get(a.id, []))),
            "story_cluster_id": a.story_cluster_id,
            "is_syndicated": a.is_syndicated,
        }
        for a, s in rows
    ]


def _bib_key(r: dict) -> str:
    word = re.sub(r"\W+", "", (r["title"] or "x").split()[0])[:12] or "item"
    return (
        f"{re.sub(r'[^a-z0-9]', '', r['source'].lower())[:15]}{(r['published_at'] or '')[:4]}{word}{r['id']}"
    )


def _bibtex(rows: list[dict]) -> str:
    def esc(s: str | None) -> str:
        return (s or "").replace("{", "\\{").replace("}", "\\}")

    out = []
    for r in rows:
        note = "DEMO DATA (synthetic record)" if r["is_demo"] else "Retrieved via Hudhud"
        out.append(
            f"@misc{{{_bib_key(r)},\n  title = {{{esc(r['title'])}}},\n  howpublished = {{{esc(r['source'])}}},\n"
            f"  year = {{{(r['published_at'] or '')[:4]}}},\n  date = {{{(r['published_at'] or '')[:10]}}},\n"
            f"  url = {{{r['url']}}},\n  language = {{{r['language'] or ''}}},\n"
            f"  urldate = {{{dt.date.today().isoformat()}}},\n  note = {{{note}}}\n}}"
        )
    return "\n\n".join(out) + "\n"


def _ris(rows: list[dict]) -> str:
    out = []
    for r in rows:
        d = (r["published_at"] or "")[:10]
        lines = [
            "TY  - NEWS",
            f"TI  - {r['title']}",
            f"T2  - {r['source']}",
            f"PY  - {d[:4]}",
            f"DA  - {d.replace('-', '/')}",
            f"UR  - {r['url']}",
            f"LA  - {r['language'] or ''}",
            f"Y2  - {dt.date.today().isoformat()}",
        ]
        if r["excerpt"]:
            lines.append(f"AB  - {r['excerpt']}")
        if r["is_demo"]:
            lines.append("N1  - DEMO DATA (synthetic record)")
        out.append("\n".join(lines) + "\nER  - ")
    return "\n".join(out) + "\n"


@router.get(
    "/export/articles",
    summary="Export article metadata and analysis labels (CSV, JSON, BibTeX, RIS)",
    responses={
        200: {
            "content": {
                "text/csv": {},
                "application/json": {},
                "application/x-bibtex": {},
                "application/x-research-info-systems": {},
            }
        }
    },
)
def export_articles(
    db: DB,
    f: F,
    format: Literal["csv", "json", "bibtex", "ris"] = "csv",  # noqa: A002
    limit: Annotated[int, Query(ge=1, le=EXPORT_LIMIT)] = 1000,
) -> Response:
    """Exports contain metadata, short excerpts and labels only, never full article text."""
    rows = _rows(db, f, limit)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d")
    if format == "json":
        body = json.dumps(
            {
                "filters": f.as_dict(),
                "exported_at": dt.datetime.now(dt.UTC).isoformat(),
                "contains_demo": any(r["is_demo"] for r in rows),
                "fields": EXPORT_FIELDS,
                "articles": rows,
            },
            ensure_ascii=False,
            indent=1,
        )
        media, ext = "application/json", "json"
    elif format == "bibtex":
        body, media, ext = _bibtex(rows), "application/x-bibtex", "bib"
    elif format == "ris":
        body, media, ext = _ris(rows), "application/x-research-info-systems", "ris"
    else:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=EXPORT_FIELDS)
        w.writeheader()
        for r in rows:
            # neutralise spreadsheet formula injection
            w.writerow({k: (f"'{v}" if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in r.items()})
        body, media, ext = "﻿" + buf.getvalue(), "text/csv; charset=utf-8", "csv"
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="yemen-hudhud-{stamp}.{ext}"'},
    )


class SavedQueryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["search", "comparison", "collection"] = "search"
    query: dict[str, Any] = Field(default_factory=dict, description="Filter parameters as used by the API.")
    article_ids: list[int] = Field(default_factory=list, max_length=5000)


def _sq(q: m.SavedQuery) -> dict:
    return {
        "id": q.id,
        "name": q.name,
        "kind": q.kind,
        "query": q.query,
        "article_ids": q.article_ids,
        "created_at": q.created_at,
        "updated_at": q.updated_at,
    }


@router.get("/saved-queries", summary="List your saved queries and collections")
def list_saved(db: DB, user: CurrentUser) -> list[dict]:
    return [
        _sq(q)
        for q in db.scalars(
            select(m.SavedQuery)
            .where(m.SavedQuery.user_id == user.id)
            .order_by(m.SavedQuery.updated_at.desc())
        )
    ]


@router.post("/saved-queries", status_code=201, summary="Save a query or a collection of articles")
def create_saved(db: DB, user: CurrentUser, body: SavedQueryIn) -> dict:
    if len(json.dumps(body.query)) > 10_000:
        raise HTTPException(422, "query too large")
    q = m.SavedQuery(user_id=user.id, **body.model_dump())
    db.add(q)
    db.commit()
    return _sq(q)


@router.delete("/saved-queries/{query_id}", status_code=204, summary="Delete a saved query")
def delete_saved(db: DB, user: CurrentUser, query_id: int) -> Response:
    q = db.get(m.SavedQuery, query_id)
    if q is None or q.user_id != user.id:
        raise HTTPException(404, "not found")
    db.delete(q)
    db.commit()
    return Response(status_code=204)


class AnnotationIn(BaseModel):
    article_id: int | None = None
    source_id: int | None = None
    target_type: Literal[
        "category",
        "topic",
        "sentiment",
        "frame",
        "entity",
        "targeted_sentiment",
        "event",
        "source_orientation",
        "duplicate",
    ]
    target_id: int | None = None
    original_value: dict[str, Any] = Field(default_factory=dict)
    corrected_value: dict[str, Any]
    note: str | None = Field(None, max_length=2000)


@router.post(
    "/annotations", status_code=201, summary="Submit a correction to a model output (human-in-the-loop)"
)
def create_annotation(db: DB, user: CurrentUser, body: AnnotationIn) -> dict:
    if user.role not in ("annotator", "admin", "researcher"):
        raise HTTPException(403, "not allowed")
    if body.article_id is None and body.source_id is None:
        raise HTTPException(422, "article_id or source_id is required")
    if body.article_id is not None and db.get(m.Article, body.article_id) is None:
        raise HTTPException(404, "article not found")
    a = m.Annotation(user_id=user.id, **body.model_dump())
    db.add(a)
    db.commit()
    return {"id": a.id, "status": a.status}
