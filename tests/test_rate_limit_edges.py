"""Additional edge coverage for HostRateLimiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from scrapekit.rate_limit import HostRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_host_key_is_case_insensitive() -> None:
    limiter = HostRateLimiter(max_concurrency=1, requests_per_second=1000.0)
    assert limiter.host_key("Example.COM") == "example.com"

    order: list[str] = []

    async def hit(label: str, host: str) -> None:
        async with limiter.limit(host):
            order.append(f"{label}:enter")
            await asyncio.sleep(0.04)
            order.append(f"{label}:exit")

    # Same host under different casing must serialize under concurrency=1.
    await asyncio.gather(hit("a", "Example.COM"), hit("b", "example.com"))
    assert order[0].endswith(":enter")
    assert order[1].endswith(":exit")
    assert order[2].endswith(":enter")
    assert order[3].endswith(":exit")


@pytest.mark.asyncio
async def test_rate_limiter_enforces_concurrency_cap() -> None:
    limiter = HostRateLimiter(max_concurrency=2, requests_per_second=1000.0)
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal in_flight, peak
        async with limiter.limit("concurrency.example"):
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1

    await asyncio.gather(*(worker() for _ in range(5)))
    assert peak == 2


@pytest.mark.asyncio
async def test_rate_limiter_releases_slot_after_body_error() -> None:
    limiter = HostRateLimiter(max_concurrency=1, requests_per_second=1000.0)

    with pytest.raises(RuntimeError, match="boom"):
        async with limiter.limit("err.example"):
            raise RuntimeError("boom")

    # Slot must be released so a subsequent acquire can proceed promptly.
    start = time.monotonic()
    async with limiter.limit("err.example"):
        pass
    assert time.monotonic() - start < 0.2


@pytest.mark.asyncio
async def test_rate_limiter_zero_wait_when_interval_already_elapsed() -> None:
    limiter = HostRateLimiter(max_concurrency=1, requests_per_second=50.0)
    async with limiter.limit("fast.example"):
        pass
    # Wait longer than min interval so the next acquire should not sleep for spacing.
    await asyncio.sleep(0.03)
    start = time.monotonic()
    async with limiter.limit("fast.example"):
        pass
    assert time.monotonic() - start < 0.02
