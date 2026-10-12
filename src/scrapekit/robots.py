"""robots.txt fetching and evaluation using urllib.robotparser."""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

#: RFC 9309 section 2.5: crawlers must parse at least 500 KiB of robots.txt
#: and may ignore anything past their limit. We read at most this many bytes.
MAX_ROBOTS_BYTES = 500 * 1024


async def _read_capped_text(response: httpx.Response, limit: int = MAX_ROBOTS_BYTES) -> str:
    """Stream at most *limit* bytes of *response* and decode them as text.

    Bytes past the limit are never buffered. When the body is truncated the
    trailing partial line is dropped so a half-read rule is not evaluated.
    """
    buf = bytearray()
    truncated = False
    async for chunk in response.aiter_bytes():
        buf.extend(chunk)
        if len(buf) > limit:
            truncated = True
            del buf[limit:]
            break
    body = bytes(buf)
    if truncated:
        logger.warning(
            "robots.txt from %s exceeds %d bytes; ignoring the rest", response.url, limit
        )
        cut = body.rfind(b"\n")
        body = body[: cut + 1] if cut != -1 else b""
    return body.decode(response.encoding or "utf-8", errors="replace")


class RobotsChecker:
    """Cache and evaluate robots.txt rules per origin.

    By default, disallowed URLs are blocked. Callers may only bypass this
    by setting ``allow_disallowed=True`` explicitly on the client/settings.
    """

    def __init__(self, user_agent: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._user_agent = user_agent
        self._client = client
        self._parsers: dict[str, RobotFileParser] = {}
        self._failed_origins: set[str] = set()

    @staticmethod
    def origin_of(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"URL must include scheme and host: {url!r}")
        return f"{parsed.scheme}://{parsed.netloc}"

    async def can_fetch(self, url: str, *, allow_disallowed: bool = False) -> bool:
        """Return True if *url* may be fetched under current policy."""
        if allow_disallowed:
            logger.warning(
                "allow_disallowed=True: skipping robots.txt enforcement for %s",
                url,
            )
            return True

        origin = self.origin_of(url)
        parser = await self._get_parser(origin)
        if parser is None:
            # Fail open only when robots.txt could not be retrieved;
            # rate limits and other politeness controls still apply.
            logger.info("No robots.txt available for %s; allowing with caution", origin)
            return True

        allowed = parser.can_fetch(self._user_agent, url)
        if not allowed:
            logger.info("robots.txt disallows %s for UA %r", url, self._user_agent)
        return allowed

    async def crawl_delay(self, url: str) -> float | None:
        """Return crawl-delay (seconds) for the origin, if declared.

        Note: ``urllib.robotparser`` only parses integer Crawl-delay values.
        """
        origin = self.origin_of(url)
        parser = await self._get_parser(origin)
        if parser is None:
            return None
        delay = parser.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None

    async def _get_parser(self, origin: str) -> RobotFileParser | None:
        if origin in self._parsers:
            return self._parsers[origin]
        if origin in self._failed_origins:
            return None

        robots_url = urljoin(origin + "/", "robots.txt")
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            if self._client is not None:
                lines = await self._fetch_lines(self._client, robots_url)
            else:
                async with httpx.AsyncClient(timeout=10.0) as tmp:
                    lines = await self._fetch_lines(tmp, robots_url)
            if lines is None:
                self._failed_origins.add(origin)
                return None
            parser.parse(lines)
        except httpx.HTTPError as exc:
            logger.warning("Error fetching robots.txt from %s: %s", robots_url, exc)
            self._failed_origins.add(origin)
            return None

        self._parsers[origin] = parser
        return parser

    @staticmethod
    async def _fetch_lines(client: httpx.AsyncClient, robots_url: str) -> list[str] | None:
        """Return robots.txt lines, ``[]`` for 404, or ``None`` on other HTTP errors."""
        async with client.stream("GET", robots_url) as response:
            if response.status_code == 404:
                return []
            if response.status_code >= 400:
                logger.warning(
                    "Failed to fetch robots.txt from %s (%s)",
                    robots_url,
                    response.status_code,
                )
                return None
            text = await _read_capped_text(response)
        return text.splitlines()
