"""Import posts that a member pasted into a file (CSV or JSON), for accounts we cannot collect.

X needs a paid API (REQUIRES CONFIGURATION), so the posts of public figures on X reach the
platform only when someone supplies them. Nothing is fetched from X here. Each row is checked
before it is stored:

* the source must be a curated, non-demo record of the registry;
* the post URL must belong to one of that source's registered accounts (platform and handle)
  or to the source's own website, so a post cannot be filed under the wrong person;
* the post needs a date (never estimated) and text; text is cut to the same excerpt length
  as feed items, so the platform stores excerpts, not full copies.

Rows are stored like any other item (same URL key, versions on change) and are analysed by
the next pipeline run. The source's content type (e.g. social post) labels them in the UI.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from hudhud.db import models as m
from hudhud.ingest.canonical import domain_of
from hudhud.ingest.feeds import RawItem, _excerpt, _first_line
from hudhud.pipeline.ingest import IngestStats, store_item

FIELDS = ("source", "url", "posted_at", "text", "language")
PLATFORM_HOSTS = {
    "x": {"x.com", "twitter.com", "mobile.twitter.com"},
    "telegram": {"t.me"},
    "facebook": {"facebook.com", "m.facebook.com"},
    "instagram": {"instagram.com"},
    "tiktok": {"tiktok.com"},
    "youtube": {"youtube.com", "m.youtube.com"},
}
HANDLE_FROM_PATH = {
    # /<handle>/status/<id> on X; /<channel>/<id> or /s/<channel>/<id> on Telegram
    "x": re.compile(r"^/(?P<handle>[A-Za-z0-9_]{1,15})/status/\d+"),
    "telegram": re.compile(r"^/(?:s/)?(?P<handle>[A-Za-z][A-Za-z0-9_]{3,31})/\d+"),
}
MANUAL_FEED_TYPE = "manual_import"


@dataclass
class ImportResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "rejected": self.rejected,
        }


def read_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        rows = json.loads(text)
        if not isinstance(rows, list):
            raise ValueError("a JSON import file must hold a list of posts")
        return rows
    return list(csv.DictReader(text.splitlines()))


def _parse_when(value: str) -> dt.datetime | None:
    try:
        when = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.UTC)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.").lower()


def url_belongs_to(source: m.Source, url: str) -> str | None:
    """Platform of the account (or 'website') the URL belongs to, or None."""
    host = _host(url)
    social = set().union(*PLATFORM_HOSTS.values())
    # A social account's own URL is on a platform host shared by everyone, so only a real
    # website (an outlet, a ministry) vouches for URLs on its domain.
    if host and host == domain_of(source.url) and host not in social:
        return "website"
    for acc in source.accounts or []:
        platform = acc.get("platform")
        if host not in PLATFORM_HOSTS.get(platform, set()):
            continue
        rx = HANDLE_FROM_PATH.get(platform)
        handle = rx.match(urlsplit(url).path) if rx else None
        if handle and handle["handle"].lower() == str(acc.get("handle", "")).lower().lstrip("@"):
            return platform
    return None


def _manual_feed(session: Session, source: m.Source) -> m.SourceFeed:
    url = f"manual-import:{source.slug}"
    feed = session.scalar(select(m.SourceFeed).where(m.SourceFeed.url == url))
    if feed is None:
        feed = m.SourceFeed(
            source_id=source.id,
            url=url,
            feed_type=MANUAL_FEED_TYPE,
            active=False,  # never fetched: posts arrive only from imported files
            notes="Posts pasted by a member from an account the platform cannot collect.",
        )
        session.add(feed)
        session.flush()
    return feed


def import_posts(
    session: Session, rows: list[dict], *, now: dt.datetime | None = None, dry_run: bool = False
) -> ImportResult:
    now = now or dt.datetime.now(dt.UTC)
    result = ImportResult()
    stats = IngestStats()
    sources: dict[str, m.Source | None] = {}
    for n, row in enumerate(rows, start=1):
        slug = str(row.get("source") or "").strip()
        url = str(row.get("url") or "").strip()

        def reject(reason: str, n: int = n, slug: str = slug, url: str = url) -> None:
            result.rejected.append({"row": n, "source": slug, "url": url, "reason": reason})

        if slug not in sources:
            sources[slug] = session.scalar(
                select(m.Source).where(
                    m.Source.slug == slug, m.Source.registry_status == "curated", m.Source.is_demo.is_(False)
                )
            )
        source = sources[slug]
        text = str(row.get("text") or "").strip()
        when = _parse_when(row.get("posted_at") or "")
        if source is None:
            reject("source is not a curated record of the registry")
        elif not url or not text:
            reject("url and text are required")
        elif when is None:
            reject("posted_at must be an ISO date or datetime; dates are never estimated")
        elif when > now + dt.timedelta(hours=6):
            reject("posted_at is in the future")
        elif url_belongs_to(source, url) is None:
            reject("url does not belong to a registered account or the website of this source")
        else:
            if dry_run:
                result.inserted += 1
                continue
            item = RawItem(
                url=url,
                title=_first_line(text),
                published_at=when,
                summary=_excerpt(text),
                language_hint=(str(row.get("language") or "").strip().lower() or None),
                extra={"imported": True, "platform": url_belongs_to(source, url)},
            )
            before = (stats.inserted, stats.updated, stats.unchanged)
            store_item(
                session,
                item,
                _manual_feed(session, source),
                source,
                None,
                {},
                stats,
                now,
                lookback_days=36500,
            )
            if stats.inserted > before[0]:
                result.inserted += 1
            elif stats.updated > before[1]:
                result.updated += 1
            else:
                result.unchanged += 1
    return result
