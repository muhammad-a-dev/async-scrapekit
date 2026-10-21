"""Tests that oversized bodies are aborted while streaming, not after loading."""

from __future__ import annotations

import gzip
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from scrapekit.client import AsyncScrapeClient, ResponseTooLargeError
from scrapekit.config import Settings

ROBOTS_OK = "User-agent: *\nAllow: /\n"


def _settings(**kwargs: object) -> Settings:
    base = dict(
        user_agent="test-bot/0.1",
        requests_per_second=100.0,
        max_retries=2,
        backoff_base=0.001,
        backoff_cap=0.01,
        timeout=5.0,
        log_level="WARNING",
        max_response_bytes=64,
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


class _ChunkStream(httpx.AsyncByteStream):
    """Chunked body with no Content-Length that records how far it was read."""

    def __init__(self, chunk: bytes, count: int) -> None:
        self.chunk = chunk
        self.count = count
        self.sent = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(self.count):
            self.sent += 1
            yield self.chunk

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
@respx.mock
async def test_chunked_body_is_aborted_at_the_cap() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_OK)
    )
    stream = _ChunkStream(b"z" * 32, count=1000)
    route = respx.get("https://example.com/endless").mock(
        return_value=httpx.Response(200, stream=stream)
    )
    async with AsyncScrapeClient(_settings()) as client:
        with pytest.raises(ResponseTooLargeError, match="aborted after 96 bytes"):
            await client.fetch("https://example.com/endless")
    # 64 byte cap, 32 byte chunks: the third chunk trips it and reading stops.
    assert stream.sent == 3
    assert stream.closed
    # ResponseTooLargeError is not transient, so there is no retry.
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_gzip_bomb_is_measured_after_decoding() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_OK)
    )
    packed = gzip.compress(b"a" * 10_000)
    assert len(packed) < 64
    respx.get("https://example.com/bomb").mock(
        return_value=httpx.Response(
            200,
            content=packed,
            headers={"Content-Encoding": "gzip"},
        )
    )
    async with AsyncScrapeClient(_settings()) as client:
        with pytest.raises(ResponseTooLargeError, match="max_response_bytes=64"):
            await client.fetch("https://example.com/bomb")


@pytest.mark.asyncio
@respx.mock
async def test_body_exactly_at_cap_is_allowed_and_decoded() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_OK)
    )
    body = "é".encode() * 32  # 64 bytes
    respx.get("https://example.com/edge").mock(
        return_value=httpx.Response(
            200,
            stream=_ChunkStream(body[:32], count=1),
        )
    )
    respx.get("https://example.com/full").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
    )
    async with AsyncScrapeClient(_settings()) as client:
        result = await client.fetch("https://example.com/full")
        assert result.content == body
        assert result.text == "é" * 32
        partial = await client.fetch("https://example.com/edge")
        assert partial.content == body[:32]


@pytest.mark.asyncio
@respx.mock
async def test_transient_status_is_still_retried_with_streaming() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_OK)
    )
    route = respx.get("https://example.com/flaky").mock(
        side_effect=[
            httpx.Response(503, text="busy"),
            httpx.Response(200, text="ok"),
        ]
    )
    async with AsyncScrapeClient(_settings()) as client:
        result = await client.fetch("https://example.com/flaky")
    assert result.status_code == 200
    assert result.text == "ok"
    assert route.call_count == 2
