"""Relational schema.

Design rules (see docs/architecture.md):
* Source orientation, article sentiment, framing, topic and actor attitude live in
  separate tables and are never combined into one score.
* Every analytical row records how it was produced: model_version_id, method,
  confidence, analysis_version and created_at. New model versions add rows; they
  never overwrite earlier results (``is_current`` marks the latest per article).
* Observed data (articles, sources) is kept apart from inferences.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ProvenanceMixin:
    """Columns every NLP result carries, for reproducibility."""

    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"), index=True)
    method: Mapped[str] = mapped_column(String(40))  # model | lexicon | rule | llm | human | fallback
    confidence: Mapped[float | None] = mapped_column(Float)
    analysis_version: Mapped[str] = mapped_column(String(40), default="1")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- reference


class Language(Base):
    __tablename__ = "languages"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_native: Mapped[str | None] = mapped_column(String(80))
    script: Mapped[str] = mapped_column(String(20))
    rtl: Mapped[bool] = mapped_column(Boolean, default=False)
    supported: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- sources


class Source(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    name_native: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(200), index=True)
    country: Mapped[str | None] = mapped_column(String(2), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_group: Mapped[str] = mapped_column(String(60), index=True)
    geographic_focus: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    yemen_coverage: Mapped[str | None] = mapped_column(String(20))
    # Where the newsroom operates: sanaa_controlled | government_controlled |
    # stc_controlled | outside_yemen | unknown. Used for split views; not an orientation.
    operating_base: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    ownership_description: Mapped[str | None] = mapped_column(Text)
    ownership_evidence_urls: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    access_policy: Mapped[str] = mapped_column(String(30), default="metadata_only")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    # health: healthy | degraded | failed | inactive | unknown
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_success_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    # Synthetic sources created by `observatory demo-data`; everything they own is DEMO DATA.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)

    languages: Mapped[list[SourceLanguage]] = relationship(cascade="all, delete-orphan")
    feeds: Mapped[list[SourceFeed]] = relationship(back_populates="source", cascade="all, delete-orphan")
    orientations: Mapped[list[SourceOrientation]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceLanguage(Base):
    __tablename__ = "source_languages"
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    language_code: Mapped[str] = mapped_column(ForeignKey("languages.code"), primary_key=True)


class SourceFeed(TimestampMixin, Base):
    __tablename__ = "source_feeds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    feed_type: Mapped[str] = mapped_column(
        String(30)
    )  # rss | atom | sitemap | api | google_news_query | gdelt_query
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[dt.date | None] = mapped_column(Date)
    yemen_filter: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    last_fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_item_count: Mapped[int | None] = mapped_column(Integer)

    source: Mapped[Source] = relationship(back_populates="feeds")


class SourceOrientation(Base):
    """Time-aware, evidence-backed orientation profile of an outlet (history table).

    ``simplified`` is optional shorthand; ``dimensions`` holds the multidimensional
    profile. Rows with valid_to IS NULL are current. Orientation is NOT a measure of
    accuracy, quality or reliability.
    """

    __tablename__ = "source_orientation"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    simplified: Mapped[str] = mapped_column(String(40), default="unknown")
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(40), default="unknown")
    valid_from: Mapped[dt.date | None] = mapped_column(Date)
    valid_to: Mapped[dt.date | None] = mapped_column(Date)
    last_reviewed: Mapped[dt.date | None] = mapped_column(Date)
    review_status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="orientations")
    evidence_items: Mapped[list[SourceOrientationEvidence]] = relationship(cascade="all, delete-orphan")


class SourceOrientationEvidence(Base):
    __tablename__ = "source_orientation_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orientation_id: Mapped[int] = mapped_column(
        ForeignKey("source_orientation.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    evidence_type: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)
    accessed_at: Mapped[dt.date | None] = mapped_column(Date)


# ---------------------------------------------------------------- articles


class Article(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    feed_id: Mapped[int | None] = mapped_column(ForeignKey("source_feeds.id"))
    # For aggregator items (Google News, GDELT) the outlet that actually published it.
    publisher_name: Mapped[str | None] = mapped_column(String(300))
    publisher_domain: Mapped[str | None] = mapped_column(String(200), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    title_normalized: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    excerpt: Mapped[str | None] = mapped_column(Text)
    excerpt_normalized: Mapped[str | None] = mapped_column(Text)
    # Full text only when the source's access_policy permits it.
    content_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(8), index=True)
    language_confidence: Mapped[float | None] = mapped_column(Float)
    script: Mapped[str | None] = mapped_column(String(20))
    is_mixed_language: Mapped[bool] = mapped_column(Boolean, default=False)
    translated_title: Mapped[str | None] = mapped_column(Text)
    translation_status: Mapped[str] = mapped_column(String(20), default="none")  # none|machine|human
    word_count: Mapped[int | None] = mapped_column(Integer)
    yemen_relevance: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Dedup / story structure
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), index=True)
    canonical_article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"))
    story_cluster_id: Mapped[int | None] = mapped_column(ForeignKey("article_story_clusters.id"), index=True)
    syndication_cluster_id: Mapped[int | None] = mapped_column(Integer, index=True)
    similarity_score: Mapped[float | None] = mapped_column(Float)
    is_syndicated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Processing state machine: new -> deduped -> analysed ; error states kept per stage
    processing_status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    analysed_content_hash: Mapped[str | None] = mapped_column(String(64))
    pipeline_run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id"))
    search_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', coalesce(title_normalized, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(excerpt_normalized, '')), 'B')",
            persisted=True,
        ),
    )

    source: Mapped[Source] = relationship()

    __table_args__ = (
        Index("ix_articles_search_tsv", "search_tsv", postgresql_using="gin"),
        Index("ix_articles_source_published", "source_id", "published_at"),
    )


class ArticleVersion(Base):
    __tablename__ = "article_versions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArticleSighting(Base):
    """Each time an already-known URL is seen in another feed (e.g. an aggregator)."""

    __tablename__ = "article_sources"
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("source_feeds.id", ondelete="CASCADE"), primary_key=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoryCluster(Base):
    """Group of articles reporting the same story (near-duplicates + syndication + same-story)."""

    __tablename__ = "article_story_clusters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    representative_article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", use_alter=True, name="fk_story_cluster_representative")
    )
    first_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    article_count: Mapped[int] = mapped_column(Integer, default=1)
    source_count: Mapped[int] = mapped_column(Integer, default=1)
    # Outlets that did not merely republish identical wire copy.
    independent_source_count: Mapped[int] = mapped_column(Integer, default=1)
    language_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArticleRelation(Base):
    """Typed article-article edges: duplicate | syndicated_from | same_story | same_event |
    same_topic | similar | contradicts | supports | quotes."""

    __tablename__ = "article_duplicates"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    to_article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(30))
    similarity_score: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(40))  # url | content_hash | title_minhash | embedding | llm
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("from_article_id", "to_article_id", "relation_type"),)


# ---------------------------------------------------------------- model registry


class Model(Base):
    __tablename__ = "models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    provider: Mapped[str] = mapped_column(String(60))  # huggingface | anthropic | internal
    license: Mapped[str | None] = mapped_column(String(80))
    url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id"), index=True)
    version: Mapped[str] = mapped_column(String(80))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model: Mapped[Model] = relationship()
    __table_args__ = (UniqueConstraint("model_id", "version"),)


class ModelTask(Base):
    __tablename__ = "model_tasks"
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), primary_key=True)
    task: Mapped[str] = mapped_column(String(40), primary_key=True)


class ModelLanguage(Base):
    __tablename__ = "model_languages"
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), primary_key=True)
    language_code: Mapped[str] = mapped_column(String(8), primary_key=True)


class ModelBenchmark(Base):
    __tablename__ = "model_benchmarks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), index=True)
    task: Mapped[str] = mapped_column(String(40))
    dataset: Mapped[str] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(8))
    metric: Mapped[str] = mapped_column(String(40))  # accuracy | macro_f1 | coherence | latency_ms | cost_usd
    value: Mapped[float] = mapped_column(Float)
    n: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    measured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(20))
    template: Mapped[str] = mapped_column(Text)
    json_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    model: Mapped[str] = mapped_column(String(80))
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("name", "version"),)


class LLMCall(Base):
    """Cache + audit log of every LLM call (keyed by input hash)."""

    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prompt_template_id: Mapped[int] = mapped_column(ForeignKey("prompt_templates.id"), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(80))
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    valid: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("prompt_template_id", "input_hash", "model"),)


# ---------------------------------------------------------------- embeddings


class ArticleEmbedding(Base):
    __tablename__ = "article_embeddings"
    __table_args__ = (
        Index(
            "ix_article_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- taxonomy & topics


class Category(Base):
    """Curated hierarchical taxonomy (source_categories / topic_hierarchy for curated topics)."""

    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    name_en: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # {lang: [terms]}
    is_emerging: Mapped[bool] = mapped_column(Boolean, default=False)


class CategoryAssignment(ProvenanceMixin, Base):
    __tablename__ = "category_assignments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    rank: Mapped[str] = mapped_column(String(12))  # primary | secondary
    score: Mapped[float] = mapped_column(Float)
    route: Mapped[str | None] = mapped_column(String(20))  # accepted | secondary | llm | uncertain
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class TopicModel(Base):
    __tablename__ = "topic_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    scope: Mapped[str] = mapped_column(String(80))  # global | category:<slug> | language:<code>
    algorithm: Mapped[str] = mapped_column(String(40))  # bertopic | kmeans_ctfidf
    embedding_model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    training_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    training_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # coherence, diversity, outliers
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | superseded
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GlobalTopic(Base):
    """Cross-lingual concept that language/scope-specific topics align to."""

    __tablename__ = "global_topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_en: Mapped[str] = mapped_column(Text)
    label_ar: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    centroid: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_model_id: Mapped[int] = mapped_column(ForeignKey("topic_models.id", ondelete="CASCADE"), index=True)
    topic_index: Mapped[int] = mapped_column(Integer)
    raw_representation: Mapped[list[Any]] = mapped_column(JSONB, default=list)  # [[term, weight], ...]
    label: Mapped[str] = mapped_column(Text)  # human_readable_topic_name
    label_method: Mapped[str] = mapped_column(String(20), default="keywords")  # keywords | llm | human
    llm_description: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer, default=0)
    parent_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    language_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    quality: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    representative_article_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    centroid: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("topic_model_id", "topic_index"),)


class TopicTranslation(Base):
    __tablename__ = "topic_translations"
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    language: Mapped[str] = mapped_column(String(8), primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(20))


class TopicAlignment(Base):
    __tablename__ = "topic_alignments"
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    global_topic_id: Mapped[int] = mapped_column(
        ForeignKey("global_topics.id", ondelete="CASCADE"), primary_key=True
    )
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(30))  # centroid_cosine | llm


class TopicAssignment(Base):
    __tablename__ = "topic_assignments"
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    topic_model_id: Mapped[int] = mapped_column(ForeignKey("topic_models.id", ondelete="CASCADE"), index=True)
    probability: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20), default="fit")  # fit | transform (incremental)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- sentiment / emotion / framing


class SentimentAnalysis(ProvenanceMixin, Base):
    __tablename__ = "sentiment_analysis"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    polarity: Mapped[str] = mapped_column(String(10))  # positive | neutral | negative | uncertain
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    intensity: Mapped[float | None] = mapped_column(Float)


class EmotionAnalysis(ProvenanceMixin, Base):
    """kind='emotion' (anger, fear...) or kind='tone' (accusatory, conciliatory...)."""

    __tablename__ = "emotion_analysis"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dominant: Mapped[str | None] = mapped_column(String(40))


class Frame(Base):
    __tablename__ = "frames"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    cues: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    discovered: Mapped[bool] = mapped_column(Boolean, default=False)


class FramingAnalysis(ProvenanceMixin, Base):
    __tablename__ = "framing_analysis"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    frame_id: Mapped[int] = mapped_column(ForeignKey("frames.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    evidence_sentence: Mapped[str | None] = mapped_column(Text)


class TargetedSentiment(ProvenanceMixin, Base):
    __tablename__ = "targeted_sentiment"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    sentiment: Mapped[str] = mapped_column(String(10))
    score: Mapped[float] = mapped_column(Float)  # -1..1
    evidence_sentence: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------- entities, locations, events


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    # political_actor | armed_group | person | country | igo | ngo | organization | location | media
    subtype: Mapped[str | None] = mapped_column(String(60))
    name_en: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    wikidata_id: Mapped[str | None] = mapped_column(String(20))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"))
    is_public_figure: Mapped[bool] = mapped_column(Boolean, default=True)

    aliases: Mapped[list[EntityAlias]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    location: Mapped[Location | None] = relationship(
        back_populates="entity", uselist=False, foreign_keys="Location.entity_id"
    )


class EntityAlias(Base):
    """Surface forms. Doubles as the terminology-variant catalogue: aliases are NOT
    assumed to be framing-neutral (``alias_type`` / ``framing_note``)."""

    __tablename__ = "entity_aliases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    surface_form: Mapped[str] = mapped_column(String(300))
    normalized_form: Mapped[str] = mapped_column(String(300), index=True)
    language: Mapped[str] = mapped_column(String(8))
    alias_type: Mapped[str] = mapped_column(String(30), default="common")
    # official | self_designation | common | descriptive | critical | transliteration | abbreviation
    framing_note: Mapped[str | None] = mapped_column(Text)
    match: Mapped[bool] = mapped_column(Boolean, default=True)  # use in gazetteer matching
    entity: Mapped[Entity] = relationship(back_populates="aliases")
    __table_args__ = (UniqueConstraint("entity_id", "normalized_form", "language"),)


class Location(Base):
    __tablename__ = "locations"
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    location_type: Mapped[str] = mapped_column(
        String(30)
    )  # governorate|city|district|port|island|strait|border
    governorate_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"))
    admin_code: Mapped[str | None] = mapped_column(String(20))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    entity: Mapped[Entity] = relationship(back_populates="location", foreign_keys=[entity_id])


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), index=True)
    alias_id: Mapped[int | None] = mapped_column(ForeignKey("entity_aliases.id"), index=True)
    surface_form: Mapped[str] = mapped_column(String(300))
    ner_label: Mapped[str | None] = mapped_column(String(20))
    field: Mapped[str] = mapped_column(String(10))  # title | excerpt | body
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    sentence: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(20))  # gazetteer | ner_model
    confidence: Mapped[float | None] = mapped_column(Float)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True)
    location_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20))
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    __table_args__ = (UniqueConstraint("event_type", "event_date", "location_entity_id"),)


class EventActor(Base):
    __tablename__ = "event_actors"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)


class EventMention(Base):
    __tablename__ = "event_mentions"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_sentence: Mapped[str | None] = mapped_column(Text)
    trigger: Mapped[str | None] = mapped_column(String(120))


class Claim(Base):
    """Detected claims. Verification is NOT automated: status starts as 'unverified'."""

    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    claimant_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"))
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    # unverified | corroborated | contradicted | fact-checked | unknown
    fact_check_url: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- aggregates


class TerminologyVariant(Base):
    """terminology_variant x entity x source x day frequency."""

    __tablename__ = "terminology_variants"
    alias_id: Mapped[int] = mapped_column(
        ForeignKey("entity_aliases.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    frequency: Mapped[int] = mapped_column(Integer)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    articles: Mapped[int] = mapped_column(Integer, default=0)
    unique_stories: Mapped[int] = mapped_column(Integer, default=0)
    sources_active: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rate: Mapped[float | None] = mapped_column(Float)
    language_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    group_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sentiment_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    topic_entropy: Mapped[float | None] = mapped_column(Float)
    source_diversity: Mapped[float | None] = mapped_column(Float)
    language_diversity: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CategoryMetric(Base):
    __tablename__ = "topic_metrics"
    # dimension: 'category' or 'topic'
    dimension: Mapped[str] = mapped_column(String(10), primary_key=True)
    ref_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    story_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    language_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_sentiment: Mapped[float | None] = mapped_column(Float)


class SourceMetric(Base):
    __tablename__ = "source_metrics"
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_sentiment: Mapped[float | None] = mapped_column(Float)
    category_distribution: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class EntityMetric(Base):
    __tablename__ = "entity_metrics"
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_targeted_sentiment: Mapped[float | None] = mapped_column(Float)


class DailySummary(Base):
    __tablename__ = "daily_summaries"
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    language: Mapped[str] = mapped_column(String(8), primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    method: Mapped[str] = mapped_column(String(20))  # template | llm
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- operations


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(30))  # daily | ingest | analyse | metrics | topics
    trigger: Mapped[str | None] = mapped_column(String(40))  # schedule | manual | test
    git_sha: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|partial|failed
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class PipelineError(Base):
    __tablename__ = "pipeline_errors"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), index=True)
    feed_id: Mapped[int | None] = mapped_column(ForeignKey("source_feeds.id"))
    article_id: Mapped[int | None] = mapped_column(BigInteger)
    stage: Mapped[str] = mapped_column(String(30))
    error_type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="failed")  # failed | recovered | skipped
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DriftReport(Base):
    __tablename__ = "drift_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"))
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String(60))
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- users & research


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="researcher")  # researcher | annotator | admin
    api_key_hash: Mapped[str | None] = mapped_column(String(128), unique=True)


class SavedQuery(TimestampMixin, Base):
    __tablename__ = "saved_queries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="search")  # search | comparison | collection
    query: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    article_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class Annotation(Base):
    __tablename__ = "annotations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    target_type: Mapped[str] = mapped_column(
        String(30)
    )  # category|topic|sentiment|frame|entity|source_orientation
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    original_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    corrected_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="submitted")  # submitted | accepted | rejected
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
