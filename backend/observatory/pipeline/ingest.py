"""Stage 1: fetch every active feed, parse, filter, normalise and store new articles.

One failing source never stops the run: errors are recorded in ``pipeline_errors``,
feed/source health is updated, and the loop continues. Re-running is idempotent:
articles are keyed by the SHA-256 of their canonical URL; a changed title/excerpt
creates an ``article_versions`` row and re-queues analysis instead of a duplicate.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from observatory.config import get_settings
from observatory.db import models as m
from observatory.ingest.canonical import canonicalize_url, domain_of, url_hash
from observatory.ingest.feeds import PARSERS, FeedParseError, RawItem
from observatory.ingest.http import Fetcher, FetchError, FetchResult
from observatory.ingest.relevance import RELEVANCE_THRESHOLD, yemen_relevance
from observatory.nlp.language import detect_language
from observatory.nlp.text import content_hash, normalize_for_matching

log = structlog.get_logger()
AGGREGATOR_TYPES = {"google_news_query", "gdelt_query"}


@dataclass
class IngestStats:
    feeds_ok: int = 0
    feeds_failed: int = 0
    feeds_not_modified: int = 0
    items_seen: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    filtered_irrelevant: int = 0
    filtered_old: int = 0
    by_language: Counter = field(default_factory=Counter)

    def as_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "by_language"}
        d["by_language"] = dict(self.by_language)
        return d


def quality_score(item: RawItem, lang_conf: float, title: str, excerpt: str) -> tuple[float, dict]:
    """Technical completeness only. NOT a reliability or credibility score."""
    parts = {
        "has_date": 1.0 if item.published_at else 0.0,
        "has_author": 1.0 if item.author else 0.0,
        "excerpt": min(1.0, len(excerpt) / 200.0),
        "title": 1.0 if 15 <= len(title) <= 300 else 0.5,
        "language_confidence": lang_conf,
    }
    return round(sum(parts.values()) / len(parts), 4), parts


def _health(consecutive_failures: int) -> str:
    if consecutive_failures == 0:
        return "healthy"
    return "degraded" if consecutive_failures < 3 else "failed"


def store_item(
    session: Session,
    item: RawItem,
    feed: m.SourceFeed,
    source: m.Source,
    run_id: int | None,
    domain_map: dict[str, int],
    stats: IngestStats,
    now: dt.datetime,
) -> m.Article | None:
    settings = get_settings()
    stats.items_seen += 1
    published = item.published_at
    if published and published > now + dt.timedelta(hours=6):
        published = now  # feeds sometimes carry future/local-time dates
    if published and published < now - dt.timedelta(days=settings.lookback_days):
        stats.filtered_old += 1
        return None

    relevance = None
    if feed.yemen_filter or feed.feed_type in AGGREGATOR_TYPES:
        relevance = yemen_relevance(item.title, item.summary)
        if relevance < RELEVANCE_THRESHOLD and feed.feed_type not in AGGREGATOR_TYPES:
            stats.filtered_irrelevant += 1
            return None
        if feed.feed_type in AGGREGATOR_TYPES and relevance == 0.0:
            # aggregator queries are already Yemen searches; keep, but score lower
            relevance = 0.6

    source_id = source.id
    if feed.feed_type in AGGREGATOR_TYPES:
        target = domain_map.get(item.publisher_domain or "") or domain_map.get(domain_of(item.url))
        if target:
            source_id = target

    canonical = canonicalize_url(item.url)
    key = url_hash(canonical)
    title_norm = normalize_for_matching(item.title)
    excerpt = item.summary or ""
    chash = content_hash(item.title, excerpt)

    existing = session.scalar(select(m.Article).where(m.Article.url_hash == key))
    if existing is not None:
        if existing.feed_id != feed.id:
            session.merge(m.ArticleSighting(article_id=existing.id, feed_id=feed.id))
        if existing.content_hash == chash:
            stats.unchanged += 1
            return None
        session.add(
            m.ArticleVersion(
                article_id=existing.id,
                content_hash=existing.content_hash,
                title=existing.title,
                excerpt=existing.excerpt,
            )
        )
        existing.title, existing.title_normalized = item.title, title_norm
        existing.excerpt, existing.excerpt_normalized = (
            excerpt or None,
            normalize_for_matching(excerpt) or None,
        )
        existing.content_hash = chash
        existing.processing_status = "new"
        stats.updated += 1
        return existing

    lang = detect_language(f"{item.title}. {excerpt}", hint=item.language_hint)
    q, q_parts = quality_score(item, lang.confidence, item.title, excerpt)
    article = m.Article(
        source_id=source_id,
        feed_id=feed.id,
        publisher_name=item.publisher_name,
        publisher_domain=item.publisher_domain or domain_of(item.url),
        url=item.url,
        canonical_url=canonical,
        url_hash=key,
        title=item.title,
        title_normalized=title_norm,
        author=item.author,
        published_at=published or now,
        published_at_estimated=published is None,
        excerpt=excerpt or None,
        excerpt_normalized=normalize_for_matching(excerpt) or None,
        content_hash=chash,
        language=lang.language,
        language_confidence=lang.confidence,
        script=lang.script,
        is_mixed_language=lang.mixed,
        word_count=len(f"{item.title} {excerpt}".split()),
        yemen_relevance=relevance if relevance is not None else 1.0,
        quality_score=q,
        quality_detail=q_parts,
        raw_metadata={k: v for k, v in item.extra.items() if v} | {"language_method": lang.method},
        processing_status="new",
        pipeline_run_id=run_id,
    )
    session.add(article)
    session.flush()
    stats.inserted += 1
    stats.by_language[lang.language or "unknown"] += 1
    return article


def record_error(
    session: Session,
    run_id: int | None,
    *,
    stage: str,
    error_type: str,
    message: str,
    source_id: int | None = None,
    feed_id: int | None = None,
    retry_count: int = 0,
    article_id: int | None = None,
) -> None:
    session.add(
        m.PipelineError(
            run_id=run_id,
            source_id=source_id,
            feed_id=feed_id,
            article_id=article_id,
            stage=stage,
            error_type=error_type,
            message=message[:2000],
            retry_count=retry_count,
            status="failed",
        )
    )


def run_ingest(
    session: Session, run_id: int | None, fetcher: Fetcher | None = None, feed_ids: list[int] | None = None
) -> IngestStats:
    settings = get_settings()
    stats = IngestStats()
    now = dt.datetime.now(dt.UTC)
    q = (
        select(m.SourceFeed)
        .join(m.Source)
        .where(m.SourceFeed.active.is_(True), m.Source.active.is_(True), m.Source.deleted_at.is_(None))
    )
    if feed_ids:
        q = q.where(m.SourceFeed.id.in_(feed_ids))
    feeds = list(session.scalars(q))
    domain_map = {d: sid for sid, d in session.execute(select(m.Source.id, m.Source.domain)) if d}
    own_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()

    def fetch(feed: m.SourceFeed) -> tuple[m.SourceFeed, FetchResult | FetchError]:
        try:
            # Aggregator APIs and feeds are fetched as feeds; robots.txt is still honoured.
            return feed, fetcher.get(feed.url, etag=feed.etag, last_modified=feed.last_modified)
        except FetchError as exc:
            return feed, exc
        except Exception as exc:  # never let one feed kill the run
            return feed, FetchError(str(exc), error_type=type(exc).__name__, attempts=1)

    try:
        with ThreadPoolExecutor(max_workers=settings.fetch_concurrency) as pool:
            results = list(pool.map(fetch, feeds))
    finally:
        if own_fetcher:
            fetcher.close()

    touched_sources: dict[int, bool] = {}
    for feed, result in results:
        source = feed.source
        feed.last_fetched_at = now
        if isinstance(result, FetchError):
            _fail(session, run_id, feed, source, result.error_type, str(result), result.attempts, now, stats)
            touched_sources.setdefault(source.id, False)
            continue
        if result.not_modified:
            stats.feeds_not_modified += 1
            _succeed(feed, now, 0)
            touched_sources[source.id] = True
            continue
        try:
            items = PARSERS.get(feed.feed_type, PARSERS["rss"])(result.content)
        except FeedParseError as exc:
            _fail(session, run_id, feed, source, "parse_error", str(exc), result.attempts, now, stats)
            touched_sources.setdefault(source.id, False)
            continue
        feed.etag = result.headers.get("etag") or result.headers.get("ETag")
        feed.last_modified = result.headers.get("last-modified") or result.headers.get("Last-Modified")
        for item in items:
            try:
                with session.begin_nested():
                    store_item(session, item, feed, source, run_id, domain_map, stats, now)
            except Exception as exc:
                record_error(
                    session,
                    run_id,
                    stage="store",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    source_id=source.id,
                    feed_id=feed.id,
                )
        _succeed(feed, now, len(items))
        stats.feeds_ok += 1
        touched_sources[source.id] = True
        session.commit()

    for source_id, ok in touched_sources.items():
        src = session.get(m.Source, source_id)
        if ok:
            src.last_success_at, src.consecutive_failures, src.health_status = now, 0, "healthy"
        else:
            src.last_failure_at = now
            src.consecutive_failures += 1
            src.health_status = _health(src.consecutive_failures)
    session.commit()
    log.info("ingest_done", **stats.as_dict())
    return stats


def _succeed(feed: m.SourceFeed, now: dt.datetime, n: int) -> None:
    feed.last_success_at, feed.consecutive_failures, feed.health_status = now, 0, "healthy"
    if n:
        feed.last_item_count = n


def _fail(
    session: Session,
    run_id: int | None,
    feed: m.SourceFeed,
    source: m.Source,
    error_type: str,
    message: str,
    attempts: int,
    now: dt.datetime,
    stats: IngestStats,
) -> None:
    stats.feeds_failed += 1
    feed.last_failure_at = now
    feed.consecutive_failures += 1
    feed.health_status = _health(feed.consecutive_failures)
    record_error(
        session,
        run_id,
        stage="fetch",
        error_type=error_type,
        message=message,
        source_id=source.id,
        feed_id=feed.id,
        retry_count=max(attempts - 1, 0),
    )
    log.warning("feed_failed", source=source.slug, feed=feed.url, error_type=error_type)
    session.commit()
