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


def test_is_transient_response_covers_408_and_425() -> None:
    request = httpx.Request("GET", "https://example.com")
    assert is_transient_response(httpx.Response(408, request=request))
    assert is_transient_response(httpx.Response(425, request=request))
    assert is_transient_response(httpx.Response(502, request=request))
    assert is_transient_response(httpx.Response(504, request=request))


def test_is_transient_exception() -> None:
    assert is_transient_exception(httpx.ConnectTimeout("timeout"))
    assert is_transient_exception(httpx.ConnectError("boom"))
    assert not is_transient_exception(ValueError("nope"))


def test_is_transient_exception_covers_timeout_and_protocol() -> None:
    assert is_transient_exception(httpx.ReadTimeout("slow body"))
    assert is_transient_exception(httpx.WriteTimeout("slow write"))
    assert is_transient_exception(httpx.RemoteProtocolError("server reset"))
    assert not is_transient_exception(httpx.HTTPStatusError(
        "bad request",
        request=httpx.Request("GET", "https://example.com"),
        response=httpx.Response(400, request=httpx.Request("GET", "https://example.com")),
    ))


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

    with pytest.raises(RetryExhaustedError) as exc_info:
        await with_retries(always_fail, max_retries=2, base=0.001, cap=0.01)
    assert isinstance(exc_info.value.last_exception, httpx.ConnectError)


@pytest.mark.asyncio
async def test_with_retries_reraises_non_transient_immediately() -> None:
    calls = {"n": 0}

    async def hard_fail() -> str:
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError, match="not retryable"):
        await with_retries(hard_fail, max_retries=3, base=0.001, cap=0.01)
    assert calls["n"] == 1


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


@pytest.mark.asyncio
async def test_with_retries_exhausted_on_persistent_retryable_result() -> None:
    request = httpx.Request("GET", "https://example.com")
    calls = {"n": 0}

    async def always_503() -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, request=request)

    result = await with_retries(
        always_503,
        max_retries=2,
        base=0.001,
        cap=0.01,
        should_retry_result=is_transient_response,
    )
    # Final attempt still returns the retryable response rather than raising.
    assert result.status_code == 503
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_with_retries_invokes_on_retry_callback() -> None:
    events: list[tuple[int, float, BaseException | None]] = []
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("temporary")
        return "ok"

    def on_retry(attempt: int, delay: float, exc: BaseException | None) -> None:
        events.append((attempt, delay, exc))

    result = await with_retries(
        flaky,
        max_retries=2,
        base=0.001,
        cap=0.01,
        on_retry=on_retry,
    )
    assert result == "ok"
    assert len(events) == 1
    attempt, delay, exc = events[0]
    assert attempt == 0
    assert delay >= 0.0
    assert isinstance(exc, httpx.ConnectError)
