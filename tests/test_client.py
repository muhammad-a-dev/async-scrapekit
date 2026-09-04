"""Tests for AsyncScrapeClient (mocked network via respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapekit.client import AsyncScrapeClient, RobotsDisallowedError
from scrapekit.config import Settings
from scrapekit.retry import RetryExhaustedError


def _fast_settings(**kwargs: object) -> Settings:
    base = dict(
        user_agent="test-bot/0.1",
        max_concurrency_per_host=2,
        requests_per_second=100.0,
        max_retries=2,
        backoff_base=0.001,
        backoff_cap=0.01,
        timeout=5.0,
        respect_robots=True,
        allow_disallowed=False,
        log_level="WARNING",
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_success() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html><title>Hi</title></html>")
    )
    async with AsyncScrapeClient(_fast_settings()) as client:
        result = await client.fetch("https://example.com/page")
    assert result.status_code == 200
    assert "Hi" in result.text


@pytest.mark.asyncio
@respx.mock
async def test_fetch_blocked_by_robots() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /secret\n")
    )
    async with AsyncScrapeClient(_fast_settings()) as client:
        with pytest.raises(RobotsDisallowedError):
            await client.fetch("https://example.com/secret")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_allow_disallowed_opt_in() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /secret\n")
    )
    respx.get("https://example.com/secret").mock(
        return_value=httpx.Response(200, text="ok")
    )
    async with AsyncScrapeClient(_fast_settings()) as client:
        result = await client.fetch("https://example.com/secret", allow_disallowed=True)
    assert result.text == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_scrape_extracts_page() -> None:
    html = "<html><head><title>T</title></head><body><h1>H</h1></body></html>"
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    async with AsyncScrapeClient(_fast_settings()) as client:
        page = await client.scrape("https://example.com/", css_fields={"h": "h1"})
    assert page.title == "T"
    assert page.selected["h"] == ["H"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_retries_on_503() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    route = respx.get("https://example.com/flaky")
    route.side_effect = [
        httpx.Response(503, text="no"),
        httpx.Response(200, text="yes"),
    ]
    async with AsyncScrapeClient(_fast_settings(max_retries=2)) as client:
        result = await client.fetch("https://example.com/flaky")
    assert result.text == "yes"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_fetch_retry_exhaustion_raises() -> None:
    """Persistent 503s should surface RetryExhaustedError after max_retries."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    route = respx.get("https://example.com/down").mock(
        return_value=httpx.Response(503, text="unavailable")
    )
    async with AsyncScrapeClient(_fast_settings(max_retries=2)) as client:
        with pytest.raises(RetryExhaustedError):
            await client.fetch("https://example.com/down")
    # initial attempt + 2 retries
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_fetch_many_returns_aligned_results() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://example.com/a").mock(return_value=httpx.Response(200, text="a"))
    respx.get("https://example.com/b").mock(return_value=httpx.Response(200, text="b"))
    async with AsyncScrapeClient(_fast_settings()) as client:
        results = await client.fetch_many(
            ["https://example.com/a", "https://example.com/b"]
        )
    assert [r.text for r in results if not isinstance(r, BaseException)] == ["a", "b"]


@pytest.mark.asyncio
@respx.mock
async def test_custom_user_agent_header() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    route = respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="ok")
    )
    async with AsyncScrapeClient(_fast_settings(user_agent="PortfolioBot/9.9")) as client:
        await client.fetch("https://example.com/")
    assert route.calls[0].request.headers["User-Agent"] == "PortfolioBot/9.9"
