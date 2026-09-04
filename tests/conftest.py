"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from scrapekit.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        user_agent="async-scrapekit-test/0.1",
        max_concurrency_per_host=2,
        requests_per_second=100.0,  # fast for tests
        max_retries=2,
        backoff_base=0.01,
        backoff_cap=0.05,
        timeout=5.0,
        respect_robots=True,
        allow_disallowed=False,
        log_level="WARNING",
    )
