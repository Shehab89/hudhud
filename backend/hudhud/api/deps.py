"""Shared API dependencies: database session, common filters, authentication."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from hudhud.config import get_settings
from hudhud.db import models as m
from hudhud.db.session import get_db

DB = Annotated[Session, Depends(get_db)]
MAX_RANGE_DAYS = 366


@dataclass
class Filters:
    date_from: dt.date
    date_to: dt.date
    languages: list[str]
    sources: list[str]
    source_groups: list[str]
    operating_bases: list[str]
    category: str | None
    entity: str | None
    demo: str
    source_categories: list[str] = field(default_factory=list)
    source_tiers: list[str] = field(default_factory=list)
    source_regions: list[str] = field(default_factory=list)
    source_countries: list[str] = field(default_factory=list)
    yemen_alignments: list[str] = field(default_factory=list)
    regional_alignments: list[str] = field(default_factory=list)
    content_types: list[str] = field(default_factory=list)

    def source_filtered(self) -> bool:
        return bool(
            self.sources
            or self.source_groups
            or self.operating_bases
            or self.source_categories
            or self.source_tiers
            or self.source_regions
            or self.source_countries
            or self.yemen_alignments
            or self.regional_alignments
            or self.content_types
        )

    @property
    def start(self) -> dt.datetime:
        return dt.datetime.combine(self.date_from, dt.time.min, tzinfo=dt.UTC)

    @property
    def end(self) -> dt.datetime:
        return dt.datetime.combine(self.date_to + dt.timedelta(days=1), dt.time.min, tzinfo=dt.UTC)

    def as_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in self.__dict__.items()}


def _split(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        out += [x.strip() for x in v.split(",") if x.strip()]
    return out


def filters(
    date_from: Annotated[
        dt.date | None, Query(description="Start date (inclusive). Default: 30 days ago.")
    ] = None,
    date_to: Annotated[
        dt.date | None, Query(description="End date (inclusive). Default: today (UTC).")
    ] = None,
    language: Annotated[
        list[str] | None, Query(description="ISO 639-1 codes; repeat or comma-separate.")
    ] = None,
    source: Annotated[list[str] | None, Query(description="Source slugs.")] = None,
    source_group: Annotated[list[str] | None, Query(description="Source groups, e.g. yemen_media.")] = None,
    operating_base: Annotated[
        list[str] | None,
        Query(
            description="Newsroom location: sanaa_controlled, government_controlled, stc_controlled, outside_yemen, unknown."
        ),
    ] = None,
    category: Annotated[str | None, Query(description="Taxonomy slug (includes its sub-categories).")] = None,
    entity: Annotated[str | None, Query(description="Actor/entity slug mentioned in the article.")] = None,
    demo: Annotated[
        Literal["include", "exclude", "only"], Query(description="Synthetic DEMO DATA handling.")
    ] = "include",
    source_category: Annotated[
        list[str] | None,
        Query(description="Source category: MEDIA, OFFICIAL_GOVERNMENT, DIPLOMATIC_MISSION, ..."),
    ] = None,
    source_tier: Annotated[list[str] | None, Query(description="A (influence) or B (institutional).")] = None,
    source_region: Annotated[list[str] | None, Query(description="yemen, gulf, iran, europe, ...")] = None,
    source_country: Annotated[list[str] | None, Query(description="ISO country of the source.")] = None,
    yemen_alignment: Annotated[
        list[str] | None, Query(description="plc_government, ansar_allah, stc, islah, ...")
    ] = None,
    regional_alignment: Annotated[list[str] | None, Query(description="saudi, uae, iran_axis, ...")] = None,
    content_type: Annotated[
        list[str] | None,
        Query(description="journalism, official_statement, institutional_publication, ..."),
    ] = None,
) -> Filters:
    today = dt.datetime.now(dt.UTC).date()
    date_to = date_to or today
    date_from = date_from or (date_to - dt.timedelta(days=29))
    if date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(422, f"date range is limited to {MAX_RANGE_DAYS} days")
    return Filters(
        date_from,
        date_to,
        _split(language),
        _split(source),
        _split(source_group),
        _split(operating_base),
        category,
        entity,
        demo,
        [c.upper() for c in _split(source_category)],
        [t.upper() for t in _split(source_tier)],
        _split(source_region),
        [c.upper() for c in _split(source_country)],
        _split(yemen_alignment),
        _split(regional_alignment),
        _split(content_type),
    )


F = Annotated[Filters, Depends(filters)]


def apply_filters(stmt: Select, f: Filters, *, dedupe: bool = True) -> Select:
    """Restrict an article query (which must already select from ``m.Article``)."""
    A = m.Article
    stmt = stmt.where(A.deleted_at.is_(None), A.published_at >= f.start, A.published_at < f.end)
    if dedupe:
        stmt = stmt.where(A.duplicate_of_id.is_(None))
    if f.languages:
        stmt = stmt.where(A.language.in_(f.languages))
    if f.demo == "exclude":
        stmt = stmt.where(A.is_demo.is_(False))
    elif f.demo == "only":
        stmt = stmt.where(A.is_demo.is_(True))
    if f.source_filtered():
        stmt = stmt.where(A.source_id.in_(source_id_query(f)))
    if f.category:
        root = select(m.Category.id).where(m.Category.slug == f.category).scalar_subquery()
        cats = select(m.Category.id).where((m.Category.id == root) | (m.Category.parent_id == root))
        stmt = stmt.where(
            A.id.in_(
                select(m.CategoryAssignment.article_id).where(
                    m.CategoryAssignment.is_current.is_(True), m.CategoryAssignment.category_id.in_(cats)
                )
            )
        )
    if f.entity:
        ent = select(m.Entity.id).where(m.Entity.slug == f.entity).scalar_subquery()
        stmt = stmt.where(
            A.id.in_(select(m.EntityMention.article_id).where(m.EntityMention.entity_id == ent))
        )
    return stmt


def source_id_query(f: Filters) -> Select:
    """Source ids matching the source-level filters (registry attributes)."""
    S = m.Source
    src = select(S.id)
    for values, col in (
        (f.sources, S.slug),
        (f.source_groups, S.source_group),
        (f.operating_bases, S.operating_base),
        (f.source_categories, S.category),
        (f.source_tiers, S.tier),
        (f.source_regions, S.region),
        (f.source_countries, S.country),
        (f.yemen_alignments, S.yemen_political_alignment),
        (f.regional_alignments, S.regional_alignment),
        (f.content_types, S.content_type),
    ):
        if values:
            src = src.where(col.in_(values))
    return src


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(503, "Admin API disabled: set ADMIN_TOKEN (REQUIRES CONFIGURATION)")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "invalid admin token")


def require_user(db: DB, x_api_key: Annotated[str | None, Header()] = None) -> m.User:
    if not x_api_key:
        raise HTTPException(401, "X-API-Key header required (create one with `hudhud create-user`)")
    user = db.scalar(select(m.User).where(m.User.api_key_hash == hash_api_key(x_api_key)))
    if user is None:
        raise HTTPException(401, "invalid API key")
    return user


Admin = Depends(require_admin)
CurrentUser = Annotated[m.User, Depends(require_user)]


def page_params(
    limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0, le=100_000)] = 0
) -> tuple[int, int]:
    return limit, offset


Page = Annotated[tuple[int, int], Depends(page_params)]
