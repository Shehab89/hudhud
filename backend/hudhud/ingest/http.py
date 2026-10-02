"""Polite HTTP fetching: robots.txt, identifying user agent, conditional GET, retries.

Never bypasses paywalls, logins, CAPTCHAs or anti-bot protections: a 401/403/429 or a
robots.txt disallow is recorded and the fetch is skipped, not retried with tricks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urlsplit

import httpx
import structlog

from hudhud.config import get_settings

log = structlog.get_logger()


class FetchError(Exception):
    def __init__(self, message: str, *, error_type: str, attempts: int, status: int | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.attempts = attempts
        self.status = status


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    headers: dict[str, str]
    attempts: int
    not_modified: bool = False


@dataclass
class RobotsCache:
    _parsers: dict[str, robotparser.RobotFileParser | None] = field(default_factory=dict)

    def allowed(self, client: httpx.Client, url: str, user_agent: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._parsers:
            parser = robotparser.RobotFileParser()
            try:
                resp = client.get(f"{base}/robots.txt", timeout=10)
                if resp.status_code in (401, 403):
                    parser.disallow_all = True
                elif resp.status_code >= 400:
                    parser.allow_all = True
                else:
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError:
                # robots.txt unreachable (network error): treat as allowed, as RFC 9309
                # does for unavailable files; the feed request itself will then fail or not.
                parser = None
            self._parsers[base] = parser
        parser = self._parsers[base]
        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)


class Fetcher:
    RETRYABLE = {408, 425, 500, 502, 503, 504}
    BLOCKING = {401, 402, 403, 407, 451}

    def __init__(self, client: httpx.Client | None = None, sleep=time.sleep):
        self.settings = get_settings()
        self.client = client or httpx.Client(
            headers={"User-Agent": self.settings.user_agent, "Accept": "*/*"},
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=True,
        )
        self.robots = RobotsCache()
        self.sleep = sleep

    def close(self) -> None:
        self.client.close()

    def get(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        check_robots: bool = True,
    ) -> FetchResult:
        if check_robots and not self.robots.allowed(self.client, url, self.settings.user_agent):
            raise FetchError("disallowed by robots.txt", error_type="robots_disallowed", attempts=0)
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        attempts = 0
        max_attempts = self.settings.fetch_max_attempts
        last_exc: Exception | None = None
        while attempts < max_attempts:
            attempts += 1
            try:
                resp = self.client.get(url, headers=headers)
            except httpx.HTTPError as exc:  # network error: retry with backoff
                last_exc = exc
                log.info("fetch_retry", url=url, attempt=attempts, error=type(exc).__name__)
            else:
                if resp.status_code == 304:
                    return FetchResult(url, 304, b"", dict(resp.headers), attempts, not_modified=True)
                if resp.status_code < 400:
                    return FetchResult(
                        str(resp.url), resp.status_code, resp.content, dict(resp.headers), attempts
                    )
                if resp.status_code in self.BLOCKING:
                    raise FetchError(
                        f"HTTP {resp.status_code} (access restricted; not bypassed)",
                        error_type="access_restricted",
                        attempts=attempts,
                        status=resp.status_code,
                    )
                if resp.status_code == 429:
                    raise FetchError(
                        "HTTP 429 rate limited", error_type="rate_limited", attempts=attempts, status=429
                    )
                if resp.status_code not in self.RETRYABLE:
                    raise FetchError(
                        f"HTTP {resp.status_code}",
                        error_type="http_error",
                        attempts=attempts,
                        status=resp.status_code,
                    )
                last_exc = FetchError(
                    f"HTTP {resp.status_code}",
                    error_type="http_error",
                    attempts=attempts,
                    status=resp.status_code,
                )
            if attempts < max_attempts:
                self.sleep(self.settings.fetch_backoff_base_seconds * (2 ** (attempts - 1)))
        error_type = getattr(last_exc, "error_type", "network_error")
        raise FetchError(
            str(last_exc), error_type=error_type, attempts=attempts, status=getattr(last_exc, "status", None)
        )
