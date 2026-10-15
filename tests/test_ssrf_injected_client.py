"""SSRF redirect checks for caller-supplied httpx clients (offline)."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapekit.client import AsyncScrapeClient
from scrapekit.config import Settings
from scrapekit.ssrf import BlockedURLError, ssrf_request_hook


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
        block_private_hosts=True,
        log_level="WARNING",
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
@respx.mock
async def test_injected_client_blocks_redirect_to_metadata() -> None:
    """A follow_redirects client must not be bounced into the metadata IP."""
    start = respx.get("https://example.com/go").mock(
        return_value=httpx.Response(
            302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
        )
    )
    async with (
        httpx.AsyncClient(follow_redirects=True) as raw,
        AsyncScrapeClient(_fast_settings(), client=raw) as client,
    ):
        with pytest.raises(BlockedURLError, match="169.254.169.254"):
            await client.fetch("https://example.com/go")
    assert start.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_injected_client_still_follows_public_redirect() -> None:
    respx.get("https://example.com/old").mock(
        return_value=httpx.Response(301, headers={"Location": "https://example.com/new"})
    )
    respx.get("https://example.com/new").mock(
        return_value=httpx.Response(200, text="moved")
    )
    async with (
        httpx.AsyncClient(follow_redirects=True) as raw,
        AsyncScrapeClient(_fast_settings(), client=raw) as client,
    ):
        result = await client.fetch("https://example.com/old")
    assert result.text == "moved"
    assert result.url == "https://example.com/new"


@pytest.mark.asyncio
async def test_injected_client_hook_added_once_after_user_hooks() -> None:
    async def user_hook(request: httpx.Request) -> None:
        return None

    async with httpx.AsyncClient(event_hooks={"request": [user_hook]}) as raw:
        AsyncScrapeClient(_fast_settings(), client=raw)
        AsyncScrapeClient(_fast_settings(), client=raw)
        assert raw.event_hooks["request"] == [user_hook, ssrf_request_hook]


@pytest.mark.asyncio
async def test_injected_client_untouched_when_opted_out() -> None:
    async with httpx.AsyncClient() as raw:
        AsyncScrapeClient(_fast_settings(block_private_hosts=False), client=raw)
        assert ssrf_request_hook not in raw.event_hooks["request"]


@pytest.mark.asyncio
async def test_ssrf_request_hook_checks_request_url() -> None:
    with pytest.raises(BlockedURLError, match="10.0.0.1"):
        await ssrf_request_hook(httpx.Request("GET", "http://10.0.0.1/admin"))
    await ssrf_request_hook(httpx.Request("GET", "https://example.com/"))
