"""Tests for JSONL / CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_to_jsonl_append_and_rejects_bad_type(tmp_path: Path) -> None:
    path = tmp_path / "append.jsonl"
    assert to_jsonl([{"url": "https://a.example"}], path) == 1
    assert to_jsonl([{"url": "https://b.example"}], path, append=True) == 1
    loaded = records_from_jsonl(path)
    assert [row["url"] for row in loaded] == [
        "https://a.example",
        "https://b.example",
    ]
    with pytest.raises(TypeError, match="Cannot export record"):
        to_jsonl(["not-a-mapping"], path)  # type: ignore[list-item]


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


def test_to_csv_nested_values_and_blank_jsonl_lines(tmp_path: Path) -> None:
    csv_path = tmp_path / "nested.csv"
    count = to_csv(
        [{"url": "https://a.example", "tags": ["x", "y"], "meta": {"k": 1}}],
        csv_path,
        fieldnames=["url", "tags", "meta"],
    )
    assert count == 1
    text = csv_path.read_text(encoding="utf-8")
    assert '["x", "y"]' in text or '["x","y"]' in text
    assert '"k": 1' in text or '"k":1' in text

    jsonl_path = tmp_path / "blank.jsonl"
    jsonl_path.write_text(
        '\n{"url": "https://keep.example"}\n\n',
        encoding="utf-8",
    )
    loaded = records_from_jsonl(jsonl_path)
    assert loaded == [{"url": "https://keep.example"}]
