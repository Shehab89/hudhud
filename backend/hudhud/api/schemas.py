"""Response models (the OpenAPI contract the frontend is typed against)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Paged(BaseModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: list[T]
    contains_demo: bool = Field(False, description="True if any item is synthetic DEMO DATA.")


class Provenance(BaseModel):
    method: str
    model: str | None = None
    model_version: str | None = None
    confidence: float | None = None
    analysis_version: str | None = None


class SourceRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    source_group: str
    operating_base: str
    country: str | None = None
    is_demo: bool = False
    category: str = "MEDIA"
    tier: str | None = None
    region: str | None = None
    # journalism | official_statement | institutional_publication | political_statement |
    # social_post | analysis: official text is labelled, never presented as reporting.
    content_type: str = "journalism"


class ArticleSummary(BaseModel):
    id: int
    title: str
    url: str
    published_at: dt.datetime | None
    language: str | None
    excerpt: str | None
    source: SourceRef
    publisher_name: str | None = None
    is_demo: bool
    is_syndicated: bool
    story_cluster_id: int | None
    primary_category: str | None = None
    sentiment: str | None = None


class TrendOut(BaseModel):
    id: int
    slug: str | None = None
    label: str
    label_ar: str | None = None
    frequency: int
    previous: int
    growth_rate: float
    acceleration: float
    source_count: int
    source_diversity: float | None
    language_count: int
    status: str
    series: list[tuple[str, int]]


class SeriesPoint(BaseModel):
    day: dt.date
    values: dict[str, Any]


class EntityRef(BaseModel):
    slug: str
    name_en: str
    name_ar: str | None
    entity_type: str
