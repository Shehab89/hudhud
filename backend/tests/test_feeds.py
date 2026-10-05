import json

import pytest

from hudhud.ingest.feeds import (
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


def test_hand_made_feed_with_html_entities_is_repaired():
    # Seen live: feeds that use &nbsp; or bare & are not XML, and the strict parser drops them.
    feed = (
        '<?xml version="1.0" encoding="windows-1256"?><rss version="2.0"><channel><title>T</title>'
        "<item><title>\u0627\u0644\u064a\u0645\u0646&nbsp;\u0627\u0644\u064a\u0648\u0645 & \u0639\u062f\u0646\x0b</title>"
        "<link>https://example.org/a?x=1&y=2</link></item></channel></rss>"
    ).encode("windows-1256")
    items = parse_rss(feed)
    assert len(items) == 1
    assert (
        items[0].title == "\u0627\u0644\u064a\u0645\u0646 \u0627\u0644\u064a\u0648\u0645 & \u0639\u062f\u0646"
    )
    assert items[0].url == "https://example.org/a?x=1&y=2"


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


TELEGRAM = """<html><body>
<div class="tgme_channel_info"><div class="tgme_channel_info_header_title">Example channel</div></div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
 <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="examplechan/101">
  <a class="tgme_widget_message_reply" href="https://t.me/examplechan/99">
   <div class="tgme_widget_message_text js-message_reply_text">Quoted earlier post</div></a>
  <div class="tgme_widget_message_text js-message_text" dir="auto">بيان صحفي حول الوضع في الحديدة<br/>نص البيان الكامل هنا</div>
  <div class="tgme_widget_message_footer"><span class="tgme_widget_message_meta">
   <a class="tgme_widget_message_date" href="https://t.me/examplechan/101"><time datetime="2026-10-01T08:00:00+00:00" class="time">08:00</time></a>
  </span></div>
 </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
 <div class="tgme_widget_message js-widget_message" data-post="examplechan/102">
  <div class="tgme_widget_message_photo_wrap"></div>
  <a class="tgme_widget_message_date" href="https://t.me/examplechan/102"><time datetime="2026-10-01T09:00:00+00:00"></time></a>
 </div>
</div>
</body></html>""".encode()


def test_parse_telegram_preview_takes_text_posts_only():
    from hudhud.ingest.feeds import parse_telegram_preview

    items = parse_telegram_preview(TELEGRAM)
    assert len(items) == 1  # the photo-only post is skipped
    item = items[0]
    assert item.url == "https://t.me/examplechan/101"
    assert item.title == "بيان صحفي حول الوضع في الحديدة"  # first line, not the quoted reply
    assert "نص البيان الكامل" in item.summary
    assert item.published_at.isoformat() == "2026-10-01T08:00:00+00:00"


def test_parse_telegram_preview_rejects_other_pages():
    from hudhud.ingest.feeds import parse_telegram_preview

    with pytest.raises(FeedParseError):
        parse_telegram_preview(b"<html><body><p>Log in to continue</p></body></html>")


YOUTUBE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Example Channel</title>
 <entry><id>yt:video:abc</id><title>Press briefing on Yemen</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=abc"/>
  <published>2026-10-01T08:00:00+00:00</published>
  <media:group><media:description>Briefing on the humanitarian situation.</media:description></media:group>
 </entry>
</feed>"""


def test_youtube_channel_feed_parses_as_atom():
    from hudhud.ingest.feeds import PARSERS

    items = PARSERS["youtube"](YOUTUBE)
    assert items[0].url == "https://www.youtube.com/watch?v=abc"
    assert items[0].title == "Press briefing on Yemen"
