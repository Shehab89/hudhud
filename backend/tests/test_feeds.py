import json

import pytest

from observatory.ingest.feeds import (
    EXCERPT_MAX_CHARS,
    FeedParseError,
    parse_gdelt,
    parse_google_news,
    parse_rss,
)

RSS = (
    b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title>
<item><title>Cholera cases rise in Hodeidah</title><link>https://example.org/a?utm_source=rss</link>
<pubDate>Thu, 01 Oct 2026 08:00:00 GMT</pubDate><description>&lt;p&gt;Health officials in &lt;b&gt;Hodeidah&lt;/b&gt; said.&lt;/p&gt;</description>
<author>desk@example.org (Desk)</author></item>
<item><title>No link item</title></item>
<item><title>Long</title><link>https://example.org/b</link><description>"""
    + b"word " * 400
    + b"""</description></item>
</channel></rss>"""
)


def test_parse_rss_extracts_items_and_strips_html():
    items = parse_rss(RSS)
    assert [i.url for i in items] == ["https://example.org/a?utm_source=rss", "https://example.org/b"]
    first = items[0]
    assert first.title == "Cholera cases rise in Hodeidah"
    assert first.summary == "Health officials in Hodeidah said."
    assert first.published_at.isoformat() == "2026-10-01T08:00:00+00:00"
    assert len(items[1].summary) <= EXCERPT_MAX_CHARS + 2  # excerpts only, never full text


def test_malformed_feed_raises_parse_error():
    with pytest.raises(FeedParseError):
        parse_rss(b"<html><body>Access denied</body")


GOOGLE_NEWS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Talks resume in Muscat - Example Times</title>
<link>https://news.google.com/rss/articles/abc</link>
<pubDate>Thu, 01 Oct 2026 10:00:00 GMT</pubDate>
<source url="https://www.exampletimes.com">Example Times</source></item>
</channel></rss>"""


def test_google_news_publisher_is_taken_from_source_element():
    [item] = parse_google_news(GOOGLE_NEWS)
    assert item.title == "Talks resume in Muscat"
    assert item.publisher_name == "Example Times"
    assert item.publisher_domain == "exampletimes.com"
    assert item.extra["aggregator"] == "google_news"
    assert item.summary == ""


def test_gdelt_articles_and_bad_json():
    payload = {
        "articles": [
            {
                "url": "https://www.example.net/x",
                "title": "Yemen talks",
                "seendate": "20261001T101500Z",
                "domain": "www.example.net",
                "language": "Arabic",
            },
            {"url": "", "title": "skipped"},
        ]
    }
    [item] = parse_gdelt(json.dumps(payload).encode())
    assert item.language_hint == "ar"
    assert item.publisher_domain == "example.net"
    assert item.extra["published_at_is_seen_date"] is True
    with pytest.raises(FeedParseError):
        parse_gdelt(b"<html>rate limited</html>")
