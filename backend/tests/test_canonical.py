import pytest

from hudhud.ingest.canonical import canonicalize_url, domain_of, url_hash


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("http://www.Example.com/news/1/?utm_source=x&fbclid=y", "https://example.com/news/1"),
        ("https://m.example.com/news/1#comments", "https://example.com/news/1"),
        ("https://example.com/news/1/amp/", "https://example.com/news/1"),
        ("https://example.com:443/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
        ("https://example.com//a//b/", "https://example.com/a/b"),
    ],
)
def test_equivalent_urls_share_a_canonical_form(a, b):
    assert canonicalize_url(a) == canonicalize_url(b)
    assert url_hash(canonicalize_url(a)) == url_hash(canonicalize_url(b))


def test_meaningful_query_parameters_are_kept():
    assert canonicalize_url("https://example.com/article?id=5") != canonicalize_url(
        "https://example.com/article?id=6"
    )


def test_non_default_port_is_kept_and_domain_strips_prefixes():
    assert canonicalize_url("https://example.com:8443/x") == "https://example.com:8443/x"
    assert domain_of("https://www.sabanew.net/story") == "sabanew.net"
