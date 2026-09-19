"""Tests for CLI helpers (no live network)."""

from __future__ import annotations

import pytest

from scrapekit.cli import (
    DEFAULT_ALLOWLIST,
    _host_allowed,
    _parse_css_fields,
    _resolve_format,
    build_parser,
)


def test_default_allowlist_contains_httpbin() -> None:
    assert "httpbin.org" in DEFAULT_ALLOWLIST
    assert "example.com" in DEFAULT_ALLOWLIST


def test_host_allowed() -> None:
    assert _host_allowed("https://httpbin.org/get", DEFAULT_ALLOWLIST)
    assert _host_allowed("https://httpbin.org:443/get", DEFAULT_ALLOWLIST)
    assert _host_allowed("http://example.com/", DEFAULT_ALLOWLIST)
    assert not _host_allowed("https://evil.example/x", DEFAULT_ALLOWLIST)
    assert not _host_allowed("https://httpbin.org.evil.example/", DEFAULT_ALLOWLIST)


def test_host_allowed_rejects_unsafe_schemes_and_null_bytes() -> None:
    assert not _host_allowed("file://httpbin.org/etc/passwd", DEFAULT_ALLOWLIST)
    assert not _host_allowed("ftp://httpbin.org/pub", DEFAULT_ALLOWLIST)
    assert not _host_allowed("javascript:alert(1)", DEFAULT_ALLOWLIST)
    assert not _host_allowed("https://httpbin.org\x00.evil.example/", DEFAULT_ALLOWLIST)
    assert not _host_allowed("not-a-url", DEFAULT_ALLOWLIST)
    assert not _host_allowed("", DEFAULT_ALLOWLIST)


def test_parse_css_fields() -> None:
    assert _parse_css_fields(["title=h1", "links=a"]) == {"title": "h1", "links": "a"}


def test_parse_css_fields_invalid() -> None:
    with pytest.raises(SystemExit):
        _parse_css_fields(["bad"])


def test_resolve_format() -> None:
    assert _resolve_format("out.csv", None) == "csv"
    assert _resolve_format("out.jsonl", None) == "jsonl"
    assert _resolve_format("out.dat", "csv") == "csv"


def test_build_parser_help() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "authorized" in help_text.lower() or "robots" in help_text.lower()
