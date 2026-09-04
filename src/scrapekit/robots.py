"""robots.txt fetching and evaluation using urllib.robotparser."""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)


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
                response = await self._client.get(robots_url)
                if response.status_code == 404:
                    parser.parse([])
                elif response.status_code >= 400:
                    logger.warning(
                        "Failed to fetch robots.txt from %s (%s)",
                        robots_url,
                        response.status_code,
                    )
                    self._failed_origins.add(origin)
                    return None
                else:
                    parser.parse(response.text.splitlines())
            else:
                async with httpx.AsyncClient(timeout=10.0) as tmp:
                    response = await tmp.get(robots_url)
                    if response.status_code == 404:
                        parser.parse([])
                    elif response.status_code >= 400:
                        self._failed_origins.add(origin)
                        return None
                    else:
                        parser.parse(response.text.splitlines())
        except httpx.HTTPError as exc:
            logger.warning("Error fetching robots.txt from %s: %s", robots_url, exc)
            self._failed_origins.add(origin)
            return None

        self._parsers[origin] = parser
        return parser
