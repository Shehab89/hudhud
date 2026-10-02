import httpx
import pytest
import respx

from observatory.ingest.http import Fetcher, FetchError

FEED = "https://feeds.example.org/rss"
ROBOTS = "https://feeds.example.org/robots.txt"


@pytest.fixture
def fetcher():
    f = Fetcher(client=httpx.Client(), sleep=lambda _s: None)
    yield f
    f.close()


@respx.mock
def test_retries_server_errors_then_succeeds(fetcher):
    respx.get(ROBOTS).respond(404)
    route = respx.get(FEED).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, content=b"<rss/>", headers={"ETag": '"v1"'})]
    )
    result = fetcher.get(FEED)
    assert result.status == 200 and result.attempts == 2
    assert route.call_count == 2


@respx.mock
def test_access_restriction_is_not_retried_or_bypassed(fetcher):
    respx.get(ROBOTS).respond(404)
    route = respx.get(FEED).respond(403)
    with pytest.raises(FetchError) as exc:
        fetcher.get(FEED)
    assert exc.value.error_type == "access_restricted"
    assert route.call_count == 1


@respx.mock
def test_robots_disallow_skips_the_fetch(fetcher):
    respx.get(ROBOTS).respond(200, text="User-agent: *\nDisallow: /")
    route = respx.get(FEED).respond(200, content=b"<rss/>")
    with pytest.raises(FetchError) as exc:
        fetcher.get(FEED)
    assert exc.value.error_type == "robots_disallowed"
    assert route.call_count == 0


@respx.mock
def test_conditional_get_returns_not_modified(fetcher):
    respx.get(ROBOTS).respond(404)
    route = respx.get(FEED).respond(304)
    result = fetcher.get(FEED, etag='"v1"')
    assert result.not_modified
    assert route.calls.last.request.headers["If-None-Match"] == '"v1"'


@respx.mock
def test_gives_up_after_max_attempts(fetcher):
    respx.get(ROBOTS).respond(404)
    respx.get(FEED).respond(502)
    with pytest.raises(FetchError) as exc:
        fetcher.get(FEED)
    assert exc.value.attempts == fetcher.settings.fetch_max_attempts
