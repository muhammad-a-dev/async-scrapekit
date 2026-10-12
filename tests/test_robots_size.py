"""robots.txt bodies are read with a size cap (RFC 9309 section 2.5)."""

from __future__ import annotations

import httpx
import pytest
import respx

from scrapekit.robots import MAX_ROBOTS_BYTES, RobotsChecker


@pytest.mark.asyncio
@respx.mock
async def test_rules_before_cap_are_kept_and_tail_is_ignored() -> None:
    head = "User-agent: *\nDisallow: /private\n"
    padding = "# " + "x" * (MAX_ROBOTS_BYTES) + "\n"
    tail = "Disallow: /late\n"
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=head + padding + tail)
    )
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        assert await checker.can_fetch("https://example.com/private") is False
        # Rule past the cap is not evaluated.
        assert await checker.can_fetch("https://example.com/late") is True


@pytest.mark.asyncio
@respx.mock
async def test_partial_line_at_cap_is_dropped() -> None:
    # Fill up to the cap, then start a rule that gets cut mid-line.
    filler = "User-agent: *\n" + "#" * (MAX_ROBOTS_BYTES - 15 - 14) + "\n"
    body = filler + "Disallow: /cut-me-off-here\n"
    assert len(filler.encode()) < MAX_ROBOTS_BYTES < len(body.encode())
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(200, text=body))
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        # A truncated "Disallow: /cu" must not block /cut... or /cu paths.
        assert await checker.can_fetch("https://example.com/cut-me-off-here") is True
        assert await checker.can_fetch("https://example.com/cu") is True


@pytest.mark.asyncio
@respx.mock
async def test_small_robots_unchanged() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /a")
    )
    async with httpx.AsyncClient() as client:
        checker = RobotsChecker("test-bot", client=client)
        assert await checker.can_fetch("https://example.com/a") is False
        assert await checker.can_fetch("https://example.com/b") is True
