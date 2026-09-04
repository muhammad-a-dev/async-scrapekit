"""Tests for JSONL / CSV export."""

from __future__ import annotations

from pathlib import Path

from scrapekit.export import records_from_jsonl, to_csv, to_jsonl
from scrapekit.extract import ExtractedPage


def test_to_jsonl_and_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    records = [
        {"url": "https://a.example", "title": "A"},
        ExtractedPage(url="https://b.example", title="B"),
    ]
    count = to_jsonl(records, path)
    assert count == 2
    loaded = records_from_jsonl(path)
    assert loaded[0]["title"] == "A"
    assert loaded[1]["title"] == "B"


def test_to_csv_writes_header_and_rows(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    count = to_csv(
        [{"url": "https://a.example", "status": 200}, {"url": "https://b.example", "status": 404}],
        path,
    )
    assert count == 2
    text = path.read_text(encoding="utf-8")
    assert "url,status" in text.splitlines()[0]
    assert "https://a.example,200" in text


def test_to_csv_empty_with_fieldnames(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    count = to_csv([], path, fieldnames=["url", "title"])
    assert count == 0
    assert path.read_text(encoding="utf-8").startswith("url,title")
