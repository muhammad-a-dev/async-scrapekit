"""Per-host concurrency and request-rate limiting."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _HostState:
    semaphore: asyncio.Semaphore
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_allowed_at: float = 0.0


class HostRateLimiter:
    """Limit concurrency and steady-state RPS independently per host."""

    def __init__(self, *, max_concurrency: int = 2, requests_per_second: float = 1.0) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        self._max_concurrency = max_concurrency
        self._min_interval = 1.0 / requests_per_second
        self._hosts: dict[str, _HostState] = defaultdict(
            lambda: _HostState(semaphore=asyncio.Semaphore(self._max_concurrency))
        )

    def host_key(self, host: str) -> str:
        return host.lower()

    async def acquire(self, host: str) -> None:
        """Block until a slot is available for *host* under both limits."""
        state = self._hosts[self.host_key(host)]
        await state.semaphore.acquire()
        try:
            async with state.lock:
                now = time.monotonic()
                wait = state.next_allowed_at - now
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                state.next_allowed_at = now + self._min_interval
        except Exception:
            state.semaphore.release()
            raise

    def release(self, host: str) -> None:
        """Release a concurrency slot for *host*."""
        state = self._hosts[self.host_key(host)]
        state.semaphore.release()

    async def __aenter__(self) -> None:  # pragma: no cover - not used directly
        raise TypeError("Use acquire/release or the limit() context manager")

    def limit(self, host: str) -> _LimitContext:
        return _LimitContext(self, host)


class _LimitContext:
    def __init__(self, limiter: HostRateLimiter, host: str) -> None:
        self._limiter = limiter
        self._host = host

    async def __aenter__(self) -> None:
        await self._limiter.acquire(self._host)

    async def __aexit__(self, *exc: object) -> None:
        self._limiter.release(self._host)
