"""SSRF host blocking for AsyncScrapeClient (offline)."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapekit.client import AsyncScrapeClient
from scrapekit.config import Settings
from scrapekit.ssrf import BlockedURLError, assert_http_url_allowed, is_blocked_url_host


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


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
        "169.254.169.254",
        "10.0.0.1",
        "192.168.1.1",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
        "foo.localhost",
    ],
)
def test_is_blocked_url_host(host: str) -> None:
    assert is_blocked_url_host(host)


def test_public_host_not_blocked() -> None:
    assert not is_blocked_url_host("example.com")
    assert not is_blocked_url_host("httpbin.org")


def test_assert_http_url_allowed_rejects_schemes_and_null() -> None:
    with pytest.raises(BlockedURLError, match="scheme"):
        assert_http_url_allowed("file:///etc/passwd")
    with pytest.raises(BlockedURLError, match="null"):
        assert_http_url_allowed("https://example.com\x00/")
    assert_http_url_allowed("https://example.com/ok")


def test_assert_http_url_allowed_rejects_userinfo_and_ipv6_loopback() -> None:
    with pytest.raises(BlockedURLError, match="userinfo"):
        assert_http_url_allowed("https://user:pass@example.com/")
    with pytest.raises(BlockedURLError, match="userinfo"):
        assert_http_url_allowed("https://user@example.com/path")
    with pytest.raises(BlockedURLError, match="::1"):
        assert_http_url_allowed("http://[::1]/")


@pytest.mark.asyncio
async def test_fetch_blocks_loopback_before_network() -> None:
    async with AsyncScrapeClient(_fast_settings()) as client:
        with pytest.raises(BlockedURLError, match="127.0.0.1"):
            await client.fetch("http://127.0.0.1/secret")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_blocks_redirect_to_metadata() -> None:
    respx.get("https://example.com/go").mock(
        return_value=httpx.Response(
            302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
        )
    )
    async with AsyncScrapeClient(_fast_settings()) as client:
        with pytest.raises(BlockedURLError, match="169.254.169.254"):
            await client.fetch("https://example.com/go")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_allows_private_when_opted_out() -> None:
    respx.get("http://10.0.0.5/page").mock(
        return_value=httpx.Response(200, text="intranet")
    )
    async with AsyncScrapeClient(_fast_settings(block_private_hosts=False)) as client:
        result = await client.fetch("http://10.0.0.5/page")
        assert result.text == "intranet"
