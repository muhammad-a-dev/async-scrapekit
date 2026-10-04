"""Tests for max_response_bytes enforcement."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapekit.client import AsyncScrapeClient, ResponseTooLargeError
from scrapekit.config import Settings, get_settings


def _fast_settings(**kwargs: object) -> Settings:
    base = dict(
        user_agent="test-bot/0.1",
        max_concurrency_per_host=2,
        requests_per_second=100.0,
        max_retries=1,
        backoff_base=0.001,
        backoff_cap=0.01,
        timeout=5.0,
        respect_robots=True,
        allow_disallowed=False,
        log_level="WARNING",
        max_response_bytes=64,
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_rejects_oversized_content_length() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://example.com/huge").mock(
        return_value=httpx.Response(
            200,
            content=b"x" * 32,
            headers={"Content-Length": "9999"},
        )
    )
    async with AsyncScrapeClient(_fast_settings(max_response_bytes=64)) as client:
        with pytest.raises(ResponseTooLargeError, match="Content-Length"):
            await client.fetch("https://example.com/huge")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_rejects_oversized_body_without_trusting_header() -> None:
    """Body length is checked even when Content-Length is absent or wrong."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    # No Content-Length: respx/httpx may still set one from content; force small
    # declared length that understates the real body when possible.
    body = b"y" * 128
    respx.get("https://example.com/big").mock(
        return_value=httpx.Response(
            200,
            content=body,
            # Understate Content-Length so the body-length check must fire.
            headers={"Content-Length": "10"},
        )
    )
    async with AsyncScrapeClient(_fast_settings(max_response_bytes=64)) as client:
        with pytest.raises(ResponseTooLargeError, match="body"):
            await client.fetch("https://example.com/big")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_allows_body_within_limit() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://example.com/ok").mock(
        return_value=httpx.Response(200, content=b"small-ok")
    )
    async with AsyncScrapeClient(_fast_settings(max_response_bytes=64)) as client:
        result = await client.fetch("https://example.com/ok")
    assert result.content == b"small-ok"


def test_max_response_bytes_default_and_override() -> None:
    assert Settings().max_response_bytes == 10_485_760
    assert get_settings(max_response_bytes=1024).max_response_bytes == 1024
