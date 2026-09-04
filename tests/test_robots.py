"""Tests for robots.txt checker."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapekit.robots import RobotsChecker


@pytest.mark.asyncio
@respx.mock
async def test_robots_allows_when_permitted() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(
            200,
            text="User-agent: *\nDisallow: /private\n",
        )
    )
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        assert await checker.can_fetch("https://example.com/public") is True
        assert await checker.can_fetch("https://example.com/private") is False


@pytest.mark.asyncio
@respx.mock
async def test_allow_disallowed_bypasses_robots() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
    )
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        assert (
            await checker.can_fetch("https://example.com/", allow_disallowed=True) is True
        )


@pytest.mark.asyncio
@respx.mock
async def test_missing_robots_fails_open() -> None:
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        assert await checker.can_fetch("https://example.com/page") is True


@pytest.mark.asyncio
@respx.mock
async def test_crawl_delay_parsed() -> None:
    # urllib.robotparser only accepts integer Crawl-delay values.
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(
            200,
            text="User-agent: *\nCrawl-delay: 3\nDisallow:\n",
        )
    )
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        delay = await checker.crawl_delay("https://example.com/")
        assert delay == 3.0


def test_origin_of_requires_absolute_url() -> None:
    with pytest.raises(ValueError):
        RobotsChecker.origin_of("/relative")
