import datetime as dt

import pytest
import yaml
from sqlalchemy import select

pytestmark = pytest.mark.db

NOW = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.UTC)
FIGURE = {
    "id": "test-envoy",
    "name": "Test Envoy",
    "url": "https://x.com/testenvoy",
    "source_type": "person",
    "category": "SOCIAL_ACCOUNT",
    "tier": "B",
    "region": "yemen",
    "country": "YE",
    "languages": ["ar"],
    "platform": "x",
    "holder": {"kind": "person", "role": "Spokesman of a negotiating delegation", "public_figure": True},
    "accounts": [
        {
            "platform": "x",
            "handle": "TestEnvoy",
            "url": "https://x.com/TestEnvoy",
            "handle_evidence": "https://example.org/about",
        },
        {
            "platform": "telegram",
            "handle": "testenvoychannel",
            "url": "https://t.me/testenvoychannel",
            "handle_evidence": "https://example.org/about",
        },
    ],
    "selection": {
        "reason": "Public spokesman of a party to the talks.",
        "institutional_importance": {"level": "high", "note": "Speaks for the delegation."},
        "audience_evidence": [
            {
                "metric": "x_followers",
                "value": 50000,
                "as_of": "2026-09",
                "source_url": "https://example.org/f",
            }
        ],
        "yemen_coverage": {"frequency": "weekly"},
    },
    "alignment": {
        "yemen_political_alignment": "unknown",
        "regional_alignment": "unknown",
    },
    "feeds": [],
}


@pytest.fixture()
def envoy(session, tmp_path):
    from hudhud.registry.seed import seed_sources

    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "f.yaml").write_text(yaml.safe_dump([FIGURE]))
    assert seed_sources(session, tmp_path)["invalid"] == 0


def row(**kw):
    base = {
        "source": "test-envoy",
        "url": "https://x.com/TestEnvoy/status/1900000000000000001",
        "posted_at": "2026-09-20T08:30:00Z",
        "text": "Talks will resume next week. Prisoner lists were exchanged.",
        "language": "en",
    }
    return base | kw


def test_valid_posts_are_stored_as_social_posts_and_not_fetched(session, envoy):
    from hudhud.db import models as m
    from hudhud.ingest.manual import import_posts

    res = import_posts(
        session,
        [row(), row(url="https://t.me/testenvoychannel/77", text="بيان جديد حول المفاوضات", language="ar")],
        now=NOW,
    )
    assert (res.inserted, res.updated, res.unchanged, res.rejected) == (2, 0, 0, [])
    arts = session.scalars(select(m.Article).join(m.Source).where(m.Source.slug == "test-envoy")).all()
    assert {a.raw_metadata["platform"] for a in arts} == {"x", "telegram"}
    assert all(a.raw_metadata["imported"] and a.processing_status == "new" for a in arts)
    # a September post is kept even though it is older than the daily collection window
    assert min(a.published_at for a in arts) == dt.datetime(2026, 9, 20, 8, 30, tzinfo=dt.UTC)
    feed = session.scalar(select(m.SourceFeed).where(m.SourceFeed.url == "manual-import:test-envoy"))
    assert feed.feed_type == "manual_import" and feed.active is False


def test_reimport_is_idempotent_and_edits_become_versions(session, envoy):
    from hudhud.ingest.manual import import_posts

    assert import_posts(session, [row()], now=NOW).inserted == 1
    assert import_posts(session, [row()], now=NOW).unchanged == 1
    assert import_posts(session, [row(text="Talks are postponed.")], now=NOW).updated == 1


@pytest.mark.parametrize(
    "bad, reason",
    [
        ({"source": "nobody"}, "not a curated record"),
        ({"url": "https://x.com/SomeoneElse/status/1900000000000000002"}, "does not belong"),
        ({"url": "https://t.me/otherchannel/5"}, "does not belong"),
        ({"url": "https://example.com/post/1"}, "does not belong"),
        ({"posted_at": ""}, "never estimated"),
        ({"posted_at": "yesterday"}, "never estimated"),
        ({"posted_at": "2026-12-01"}, "in the future"),
        ({"text": ""}, "required"),
    ],
)
def test_rows_that_cannot_be_trusted_are_rejected_with_a_reason(session, envoy, bad, reason):
    from hudhud.ingest.manual import import_posts

    res = import_posts(session, [row(**bad)], now=NOW)
    assert res.inserted == 0
    assert len(res.rejected) == 1 and reason in res.rejected[0]["reason"]


def test_text_is_stored_as_an_excerpt_not_a_full_copy(session, envoy):
    from hudhud.db import models as m
    from hudhud.ingest.feeds import EXCERPT_MAX_CHARS
    from hudhud.ingest.manual import import_posts

    import_posts(session, [row(text="word " * 1000)], now=NOW)
    art = session.scalar(select(m.Article).join(m.Source).where(m.Source.slug == "test-envoy"))
    assert len(art.excerpt) <= EXCERPT_MAX_CHARS + 2


def test_csv_and_json_files_are_read(tmp_path):
    from hudhud.ingest.manual import read_rows

    (tmp_path / "p.csv").write_text(
        "source,url,posted_at,text,language\ntest-envoy,https://x.com/TestEnvoy/status/1,2026-09-20,hello,en\n",
        encoding="utf-8-sig",
    )
    (tmp_path / "p.json").write_text('[{"source": "test-envoy", "url": "u", "posted_at": "d", "text": "t"}]')
    assert read_rows(tmp_path / "p.csv")[0]["text"] == "hello"
    assert read_rows(tmp_path / "p.json")[0]["source"] == "test-envoy"
