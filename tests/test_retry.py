"""Tests for retry / backoff helpers."""

from __future__ import annotations

import httpx
import pytest

from scrapekit.retry import (
    RetryExhaustedError,
    compute_backoff,
    is_transient_exception,
    is_transient_response,
    with_retries,
)


def test_compute_backoff_no_jitter_grows_exponentially() -> None:
    assert compute_backoff(0, base=1.0, cap=100.0, jitter=False) == 1.0
    assert compute_backoff(1, base=1.0, cap=100.0, jitter=False) == 2.0
    assert compute_backoff(2, base=1.0, cap=100.0, jitter=False) == 4.0


def test_compute_backoff_respects_cap() -> None:
    assert compute_backoff(10, base=1.0, cap=5.0, jitter=False) == 5.0


def test_compute_backoff_jitter_within_bounds() -> None:
    for attempt in range(5):
        delay = compute_backoff(attempt, base=0.5, cap=10.0, jitter=True)
        assert 0.0 <= delay <= min(10.0, 0.5 * (2**attempt))


def test_compute_backoff_rejects_negative_attempt() -> None:
    with pytest.raises(ValueError):
        compute_backoff(-1)


def test_is_transient_response() -> None:
    request = httpx.Request("GET", "https://example.com")
    assert is_transient_response(httpx.Response(429, request=request))
    assert is_transient_response(httpx.Response(503, request=request))
    assert not is_transient_response(httpx.Response(200, request=request))
    assert not is_transient_response(httpx.Response(404, request=request))


def test_is_transient_exception() -> None:
    assert is_transient_exception(httpx.ConnectTimeout("timeout"))
    assert is_transient_exception(httpx.ConnectError("boom"))
    assert not is_transient_exception(ValueError("nope"))


@pytest.mark.asyncio
async def test_with_retries_succeeds_after_transient_errors() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("temporary")
        return "ok"

    result = await with_retries(flaky, max_retries=3, base=0.001, cap=0.01)
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_with_retries_exhausted() -> None:
    async def always_fail() -> str:
        raise httpx.ConnectError("down")

    with pytest.raises(RetryExhaustedError):
        await with_retries(always_fail, max_retries=2, base=0.001, cap=0.01)


@pytest.mark.asyncio
async def test_with_retries_on_retryable_result() -> None:
    request = httpx.Request("GET", "https://example.com")
    responses = [
        httpx.Response(503, request=request),
        httpx.Response(200, request=request),
    ]

    async def op() -> httpx.Response:
        return responses.pop(0)

    result = await with_retries(
        op,
        max_retries=2,
        base=0.001,
        cap=0.01,
        should_retry_result=is_transient_response,
    )
    assert result.status_code == 200
