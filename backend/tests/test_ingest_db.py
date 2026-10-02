import datetime as dt

import pytest
from sqlalchemy import func, select

from observatory.db import models as m
from observatory.ingest.http import FetchError, FetchResult
from observatory.pipeline.dedup import run_dedup
from observatory.pipeline.ingest import run_ingest

pytestmark = pytest.mark.db


def rss(*items: tuple[str, str, str]) -> bytes:
    when = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><pubDate>{when}</pubDate><description>{d}</description></item>"
        for t, u, d in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{body}</channel></rss>'.encode()


class FakeFetcher:
    """Serves canned responses per feed URL; never touches the network."""

    def __init__(self, responses):
        self.responses = responses

    def get(self, url, etag=None, last_modified=None):
        r = self.responses[url]
        if isinstance(r, Exception):
            raise r
        return FetchResult(url, 200, r, {"etag": '"1"'}, 1)


def make_source(session, slug, domain, feed_url, yemen_filter=False):
    src = m.Source(
        slug=slug,
        name=slug,
        url=f"https://{domain}",
        domain=domain,
        source_type="news_site",
        source_group="test",
        operating_base="unknown",
    )
    src.feeds.append(m.SourceFeed(url=feed_url, feed_type="rss", yemen_filter=yemen_filter))
    session.add(src)
    session.commit()
    return src.feeds[0]


BODY = "Health authorities in Hodeidah reported a rise in suspected cholera cases across three districts."


def test_ingest_is_idempotent_and_failures_are_recorded(session):
    good = make_source(session, "test-good", "good.example", "https://good.example/rss", yemen_filter=True)
    bad = make_source(session, "test-bad", "bad.example", "https://bad.example/rss")
    fetcher = FakeFetcher(
        {
            good.url: rss(
                ("Cholera cases rise in Yemen's Hodeidah", "https://good.example/a?utm_source=x", BODY),
                ("Football results from Europe", "https://good.example/b", "Late goals decide the match."),
            ),
            bad.url: FetchError(
                "HTTP 403 (access restricted; not bypassed)", error_type="access_restricted", attempts=1
            ),
        }
    )
    stats = run_ingest(session, None, fetcher=fetcher, feed_ids=[good.id, bad.id])
    assert (stats.inserted, stats.filtered_irrelevant, stats.feeds_ok, stats.feeds_failed) == (1, 1, 1, 1)

    again = run_ingest(session, None, fetcher=fetcher, feed_ids=[good.id, bad.id])
    assert (again.inserted, again.unchanged) == (0, 1)
    assert session.scalar(select(func.count(m.Article.id))) == 1

    art = session.scalar(select(m.Article))
    assert art.canonical_url == "https://good.example/a"
    assert art.language == "en"
    err = session.scalar(select(m.PipelineError).where(m.PipelineError.feed_id == bad.id))
    assert err.error_type == "access_restricted"
    session.refresh(bad)
    assert bad.consecutive_failures == 2 and bad.health_status != "healthy"


def test_changed_headline_creates_a_version_not_a_duplicate(session):
    feed = make_source(session, "test-ver", "ver.example", "https://ver.example/rss")
    url = "https://ver.example/story"
    run_ingest(
        session,
        None,
        fetcher=FakeFetcher({feed.url: rss(("Talks in Muscat", url, BODY))}),
        feed_ids=[feed.id],
    )
    stats = run_ingest(
        session,
        None,
        fetcher=FakeFetcher({feed.url: rss(("Talks in Muscat end", url, BODY))}),
        feed_ids=[feed.id],
    )
    assert stats.updated == 1
    assert session.scalar(select(func.count(m.Article.id))) == 1
    assert session.scalar(select(func.count(m.ArticleVersion.id))) == 1


def test_dedup_separates_duplicates_from_syndication(session):
    a = make_source(session, "test-wire", "wire.example", "https://wire.example/rss")
    b = make_source(session, "test-copy", "copy.example", "https://copy.example/rss")
    title = "UN envoy meets officials in Muscat to discuss prisoner exchange"
    fetcher = FakeFetcher(
        {
            a.url: rss(
                (title, "https://wire.example/1", BODY),
                (title + " - update", "https://wire.example/1-repost", BODY),
            ),
            b.url: rss((title, "https://copy.example/9", BODY)),
        }
    )
    run_ingest(session, None, fetcher=fetcher, feed_ids=[a.id, b.id])
    stats = run_dedup(session)
    assert stats["new"] == 3
    rels = {r.relation_type for r in session.scalars(select(m.ArticleRelation))}
    assert {"duplicate", "syndicated_from"} <= rels
    arts = list(session.scalars(select(m.Article)))
    assert sum(1 for x in arts if x.duplicate_of_id) == 1
    assert sum(1 for x in arts if x.is_syndicated) == 1
    clusters = {x.story_cluster_id for x in arts}
    assert len(clusters) == 1 and None not in clusters
