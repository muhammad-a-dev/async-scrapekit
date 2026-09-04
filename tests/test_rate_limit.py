"""Tests for per-host rate limiting."""

from __future__ import annotations

import asyncio
import time

import pytest

from scrapekit.rate_limit import HostRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_enforces_min_interval() -> None:
    limiter = HostRateLimiter(max_concurrency=2, requests_per_second=20.0)
    start = time.monotonic()
    for _ in range(3):
        async with limiter.limit("example.com"):
            pass
    elapsed = time.monotonic() - start
    # 3 acquires at 20 rps => ~2 intervals of 0.05s => >= ~0.08s with slack
    assert elapsed >= 0.08


@pytest.mark.asyncio
async def test_rate_limiter_isolates_hosts() -> None:
    limiter = HostRateLimiter(max_concurrency=1, requests_per_second=100.0)

    async def hit(host: str) -> str:
        async with limiter.limit(host):
            await asyncio.sleep(0.05)
            return host

    start = time.monotonic()
    results = await asyncio.gather(hit("a.example"), hit("b.example"))
    elapsed = time.monotonic() - start
    assert set(results) == {"a.example", "b.example"}
    # Parallel across hosts should finish near one sleep, not two.
    assert elapsed < 0.09


def test_rate_limiter_validates_args() -> None:
    with pytest.raises(ValueError):
        HostRateLimiter(max_concurrency=0)
    with pytest.raises(ValueError):
        HostRateLimiter(requests_per_second=0)
