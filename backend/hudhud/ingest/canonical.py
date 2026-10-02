"""Canonical URLs: the first deduplication key."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = re.compile(
    r"^(utm_\w+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid|ref|ref_src|cmpid|ocid|"
    r"at_medium|at_campaign|at_custom\d|xtor|ns_\w+|smid|_ga|guccounter|output|amp|outputType|"
    r"rss|from|source|s_cid)$",
    re.IGNORECASE,
)
AMP_PATH = re.compile(r"(/amp/?$|/amp/(?=.)|\.amp$|\.amp\.html$)", re.IGNORECASE)


def canonicalize_url(url: str) -> str:
    """Normalise a URL so the same article reached through different links compares equal.

    Lowercases scheme/host, drops "www.", fragments, tracking parameters, default ports,
    AMP suffixes and trailing slashes, and sorts remaining query parameters.
    """
    url = (url or "").strip()
    parts = urlsplit(url)
    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme.lower()
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    path = AMP_PATH.sub("/", parts.path or "/")
    path = re.sub(r"/{2,}", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if not TRACKING_PARAMS.match(k)
    ]
    query.sort()
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def url_hash(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.").removeprefix("m.")
