"""Tests for the max_redirects cap (offline, respx)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError

from scrapekit.client import AsyncScrapeClient
from scrapekit.config import Settings


def _fast_settings(**kwargs: object) -> Settings:
    base = dict(
        user_agent="test-bot/0.1",
        max_concurrency_per_host=2,
        requests_per_second=100.0,
        max_retries=1,
        backoff_base=0.001,
        backoff_cap=0.01,
        timeout=5.0,
        respect_robots=False,
        allow_disallowed=False,
        log_level="WARNING",
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
@respx.mock
async def test_redirect_loop_stops_at_cap_and_is_not_retried() -> None:
    loop = respx.get("https://example.com/loop").mock(
        return_value=httpx.Response(302, headers={"Location": "https://example.com/loop"})
    )
    async with AsyncScrapeClient(_fast_settings(max_redirects=3)) as client:
        with pytest.raises(httpx.TooManyRedirects):
            await client.fetch("https://example.com/loop")
    # First request plus 3 followed hops. A retry would double this.
    assert loop.call_count == 4


@pytest.mark.asyncio
@respx.mock
async def test_chain_within_cap_is_followed() -> None:
    respx.get("https://example.com/r1").mock(
        return_value=httpx.Response(301, headers={"Location": "https://example.com/r2"})
    )
    respx.get("https://example.com/r2").mock(
        return_value=httpx.Response(302, headers={"Location": "https://example.com/final"})
    )
    respx.get("https://example.com/final").mock(return_value=httpx.Response(200, text="done"))
    async with AsyncScrapeClient(_fast_settings(max_redirects=2)) as client:
        result = await client.fetch("https://example.com/r1")
    assert result.text == "done"
    assert result.url == "https://example.com/final"


@pytest.mark.asyncio
@respx.mock
async def test_zero_disables_redirect_following() -> None:
    start = respx.get("https://example.com/moved").mock(
        return_value=httpx.Response(301, headers={"Location": "https://example.com/new"})
    )
    target = respx.get("https://example.com/new").mock(return_value=httpx.Response(200))
    async with AsyncScrapeClient(_fast_settings(max_redirects=0)) as client:
        with pytest.raises(httpx.TooManyRedirects):
            await client.fetch("https://example.com/moved")
    assert start.call_count == 1
    assert target.call_count == 0


@pytest.mark.asyncio
async def test_owned_client_uses_setting_and_injected_client_is_left_alone() -> None:
    async with AsyncScrapeClient(_fast_settings(max_redirects=4)) as client:
        assert client._client.max_redirects == 4
    async with (
        httpx.AsyncClient(max_redirects=7) as raw,
        AsyncScrapeClient(_fast_settings(max_redirects=4), client=raw),
    ):
        assert raw.max_redirects == 7


def test_max_redirects_default_env_and_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().max_redirects == 10
    monkeypatch.setenv("SCRAPEKIT_MAX_REDIRECTS", "5")
    assert Settings().max_redirects == 5
    for bad in (-1, 31):
        with pytest.raises(ValidationError):
            Settings(max_redirects=bad)
