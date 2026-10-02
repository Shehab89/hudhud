"""Parsers that turn feed payloads into RawItems.

Supported: RSS/Atom (feedparser), Google News RSS search feeds, and the GDELT DOC 2.0
article-list API. Malformed feeds raise FeedParseError rather than crashing a run.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from observatory.ingest.canonical import domain_of
from observatory.nlp.text import strip_html

EXCERPT_MAX_CHARS = 600


class FeedParseError(Exception):
    pass


@dataclass
class RawItem:
    url: str
    title: str
    published_at: dt.datetime | None
    summary: str = ""
    author: str | None = None
    publisher_name: str | None = None
    publisher_domain: str | None = None
    language_hint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _to_dt(struct_time: Any) -> dt.datetime | None:
    if not struct_time:
        return None
    try:
        return dt.datetime(*struct_time[:6], tzinfo=dt.UTC)
    except (TypeError, ValueError):
        return None


def _excerpt(text: str) -> str:
    text = strip_html(text)
    if len(text) <= EXCERPT_MAX_CHARS:
        return text
    cut = text[:EXCERPT_MAX_CHARS]
    return cut[: cut.rfind(" ")] + " …" if " " in cut else cut + " …"


def parse_rss(content: bytes) -> list[RawItem]:
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise FeedParseError(f"malformed feed: {getattr(parsed, 'bozo_exception', 'unknown error')}")
    if not parsed.entries and not parsed.get("feed"):
        raise FeedParseError("not a feed")
    feed_lang = (parsed.feed.get("language") or "")[:2].lower() or None
    items = []
    for e in parsed.entries:
        link = e.get("link") or ""
        title = strip_html(e.get("title") or "")
        if not link or not title:
            continue
        summary = e.get("summary") or ""
        if not summary and e.get("content"):
            summary = e["content"][0].get("value", "")
        items.append(
            RawItem(
                url=link,
                title=title,
                published_at=_to_dt(e.get("published_parsed") or e.get("updated_parsed")),
                summary=_excerpt(summary),
                author=strip_html(e.get("author") or "") or None,
                language_hint=feed_lang,
                extra={"tags": [t.get("term") for t in e.get("tags", []) if t.get("term")][:10]},
            )
        )
    return items


_GN_SUFFIX = re.compile(r"\s+-\s+([^-]{2,80})$")


def parse_google_news(content: bytes) -> list[RawItem]:
    """Google News RSS: links are news.google.com redirects; the publisher is in <source>."""
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise FeedParseError(f"malformed feed: {getattr(parsed, 'bozo_exception', 'unknown error')}")
    items = []
    for e in parsed.entries:
        title = strip_html(e.get("title") or "")
        src = e.get("source") or {}
        publisher = src.get("title")
        publisher_url = src.get("href")
        m = _GN_SUFFIX.search(title)
        if m and (not publisher or m.group(1).strip() == publisher):
            publisher = publisher or m.group(1).strip()
            title = title[: m.start()].strip()
        if not e.get("link") or not title:
            continue
        items.append(
            RawItem(
                url=e["link"],
                title=title,
                published_at=_to_dt(e.get("published_parsed")),
                summary="",  # Google News summaries only repeat the headline
                publisher_name=publisher,
                publisher_domain=domain_of(publisher_url) if publisher_url else None,
                extra={"aggregator": "google_news", "publisher_url": publisher_url},
            )
        )
    return items


_GDELT_LANG = {
    "arabic": "ar",
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "turkish": "tr",
    "persian": "fa",
    "russian": "ru",
    "chinese": "zh",
}


def parse_gdelt(content: bytes) -> list[RawItem]:
    try:
        data = json.loads(content.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError as exc:
        raise FeedParseError(f"GDELT returned non-JSON: {exc}") from exc
    items = []
    for a in data.get("articles", []) or []:
        seen = a.get("seendate")
        published = None
        if seen:
            try:
                published = dt.datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC)
            except ValueError:
                published = None
        if not a.get("url") or not a.get("title"):
            continue
        items.append(
            RawItem(
                url=a["url"],
                title=strip_html(a["title"]),
                published_at=published,
                publisher_name=a.get("domain"),
                publisher_domain=(a.get("domain") or "").removeprefix("www.") or None,
                language_hint=_GDELT_LANG.get((a.get("language") or "").lower()),
                extra={
                    "aggregator": "gdelt",
                    "sourcecountry": a.get("sourcecountry"),
                    "published_at_is_seen_date": True,
                },
            )
        )
    return items


def parse_http_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


PARSERS = {
    "rss": parse_rss,
    "atom": parse_rss,
    "google_news_query": parse_google_news,
    "gdelt_query": parse_gdelt,
}
