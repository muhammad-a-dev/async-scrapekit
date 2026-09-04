"""Retry helpers with exponential backoff and full jitter."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class RetryExhaustedError(RuntimeError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, *, last_exception: BaseException | None = None) -> None:
        super().__init__(message)
        self.last_exception = last_exception


def compute_backoff(
    attempt: int,
    *,
    base: float = 0.5,
    cap: float = 30.0,
    jitter: bool = True,
) -> float:
    """Compute delay for *attempt* (0-based) using exponential backoff + jitter.

    Uses "full jitter" (AWS style): ``random.uniform(0, min(cap, base * 2**attempt))``.
    """
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    ceiling = min(cap, base * (2**attempt))
    if jitter:
        return random.uniform(0.0, ceiling)
    return ceiling


def is_transient_response(response: httpx.Response) -> bool:
    return response.status_code in TRANSIENT_STATUS_CODES


def is_transient_exception(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ),
    )


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base: float = 0.5,
    cap: float = 30.0,
    should_retry_result: Callable[[T], bool] | None = None,
    on_retry: Callable[[int, float, BaseException | None], None] | None = None,
) -> T:
    """Execute *operation*, retrying transient failures with backoff."""
    last_exc: BaseException | None = None
    attempts = max_retries + 1

    for attempt in range(attempts):
        try:
            result = await operation()
        except Exception as exc:
            last_exc = exc
            if not is_transient_exception(exc) or attempt >= max_retries:
                if attempt >= max_retries and is_transient_exception(exc):
                    raise RetryExhaustedError(
                        f"Exhausted {max_retries} retries",
                        last_exception=exc,
                    ) from exc
                raise
            delay = compute_backoff(attempt, base=base, cap=cap)
            logger.warning(
                "Transient error on attempt %s/%s: %s; sleeping %.3fs",
                attempt + 1,
                attempts,
                exc,
                delay,
            )
            if on_retry:
                on_retry(attempt, delay, exc)
            await asyncio.sleep(delay)
            continue

        if should_retry_result and should_retry_result(result) and attempt < max_retries:
            delay = compute_backoff(attempt, base=base, cap=cap)
            logger.warning(
                "Retryable result on attempt %s/%s; sleeping %.3fs",
                attempt + 1,
                attempts,
                delay,
            )
            if on_retry:
                on_retry(attempt, delay, None)
            await asyncio.sleep(delay)
            continue

        return result

    raise RetryExhaustedError(
        f"Exhausted {max_retries} retries",
        last_exception=last_exc,
    )
