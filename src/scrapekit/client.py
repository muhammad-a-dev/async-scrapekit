"""Async scraping client with robots, rate limits, and retries."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

import httpx

from scrapekit.config import Settings, get_settings
from scrapekit.extract import ExtractedPage, extract_page
from scrapekit.rate_limit import HostRateLimiter
from scrapekit.retry import is_transient_response, with_retries
from scrapekit.robots import RobotsChecker

logger = logging.getLogger(__name__)


class RobotsDisallowedError(PermissionError):
    """Raised when robots.txt forbids a URL and allow_disallowed is False."""


@dataclass(slots=True, frozen=True)
class FetchResult:
    """Normalized fetch outcome."""

    url: str
    status_code: int
    headers: httpx.Headers
    content: bytes
    text: str
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "headers": dict(self.headers),
            "text": self.text,
            "elapsed_ms": self.elapsed_ms,
        }


class AsyncScrapeClient:
    """Polite async HTTP fetcher built on :class:`httpx.AsyncClient`.

    Defaults emphasize ethical scraping:
    - robots.txt is respected unless ``allow_disallowed=True``
    - per-host concurrency and RPS limits are enforced
    - transient errors are retried with exponential backoff + jitter
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        **setting_overrides: Any,
    ) -> None:
        self.settings = settings or get_settings(**setting_overrides)
        self._owns_client = client is None
        headers = {"User-Agent": self.settings.user_agent}
        self._client = client or httpx.AsyncClient(
            headers=headers,
            timeout=self.settings.timeout,
            follow_redirects=True,
        )
        if client is not None and "User-Agent" not in client.headers:
            self._client.headers["User-Agent"] = self.settings.user_agent

        self._robots = RobotsChecker(self.settings.user_agent, client=self._client)
        self._limiter = HostRateLimiter(
            max_concurrency=self.settings.max_concurrency_per_host,
            requests_per_second=self.settings.requests_per_second,
        )
        self._configure_logging()

    def _configure_logging(self) -> None:
        root = logging.getLogger("scrapekit")
        if not root.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
            )
            root.addHandler(handler)
        root.setLevel(self.settings.log_level.upper())

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _host_of(url: str) -> str:
        host = urlparse(url).netloc
        if not host:
            raise ValueError(f"URL missing host: {url!r}")
        return host

    async def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        allow_disallowed: bool | None = None,
        headers: dict[str, str] | None = None,
        **request_kwargs: Any,
    ) -> FetchResult:
        """Fetch *url* with robots checks, rate limiting, and retries."""
        bypass = (
            self.settings.allow_disallowed if allow_disallowed is None else allow_disallowed
        )
        if self.settings.respect_robots:
            allowed = await self._robots.can_fetch(url, allow_disallowed=bypass)
            if not allowed:
                raise RobotsDisallowedError(
                    f"robots.txt disallows fetching {url}. "
                    "Only set allow_disallowed=True if you are authorized to ignore robots.txt."
                )

        crawl_delay = await self._robots.crawl_delay(url) if self.settings.respect_robots else None
        if crawl_delay and crawl_delay > 0:
            # Prefer the stricter of configured RPS vs robots crawl-delay.
            effective_rps = min(self.settings.requests_per_second, 1.0 / crawl_delay)
            if effective_rps < self.settings.requests_per_second:
                logger.debug(
                    "Applying robots crawl-delay %.2fs for %s",
                    crawl_delay,
                    self._host_of(url),
                )

        host = self._host_of(url)

        async def _do_request() -> httpx.Response:
            async with self._limiter.limit(host):
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    **request_kwargs,
                )
                return response

        response = await with_retries(
            _do_request,
            max_retries=self.settings.max_retries,
            base=self.settings.backoff_base,
            cap=self.settings.backoff_cap,
            should_retry_result=is_transient_response,
        )

        elapsed_ms = response.elapsed.total_seconds() * 1000.0 if response.elapsed else 0.0
        logger.info("Fetched %s -> %s (%.1fms)", url, response.status_code, elapsed_ms)
        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            text=response.text,
            elapsed_ms=elapsed_ms,
        )

    async def fetch_many(
        self,
        urls: list[str],
        *,
        allow_disallowed: bool | None = None,
        **request_kwargs: Any,
    ) -> list[FetchResult | BaseException]:
        """Fetch many URLs concurrently (still per-host limited).

        Returns a list aligned with *urls*; exceptions are returned, not raised.
        """
        import asyncio

        async def _one(u: str) -> FetchResult:
            return await self.fetch(u, allow_disallowed=allow_disallowed, **request_kwargs)

        return list(await asyncio.gather(*[_one(u) for u in urls], return_exceptions=True))

    async def scrape(
        self,
        url: str,
        *,
        css_fields: dict[str, str] | None = None,
        allow_disallowed: bool | None = None,
        **request_kwargs: Any,
    ) -> ExtractedPage:
        """Fetch *url* and return a structured :class:`ExtractedPage`."""
        result = await self.fetch(url, allow_disallowed=allow_disallowed, **request_kwargs)
        return extract_page(
            result.text,
            url=result.url,
            css_fields=css_fields,
        )
