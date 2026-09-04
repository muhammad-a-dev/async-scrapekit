"""Tests for settings / config."""

from __future__ import annotations

import os
from unittest import mock

from scrapekit.config import Settings, get_settings


def test_defaults() -> None:
    s = Settings()
    assert s.respect_robots is True
    assert s.allow_disallowed is False
    assert s.max_concurrency_per_host >= 1
    assert "async-scrapekit" in s.user_agent


def test_env_override() -> None:
    with mock.patch.dict(os.environ, {"SCRAPEKIT_USER_AGENT": "EnvBot/1.0"}, clear=False):
        s = Settings()
        assert s.user_agent == "EnvBot/1.0"


def test_get_settings_overrides() -> None:
    s = get_settings(requests_per_second=5.0, max_retries=1)
    assert s.requests_per_second == 5.0
    assert s.max_retries == 1
