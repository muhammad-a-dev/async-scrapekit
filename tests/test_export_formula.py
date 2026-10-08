"""CSV formula-injection guard for scraped text."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scrapekit.export import to_csv


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize(
    "payload",
    [
        '=HYPERLINK("http://evil.example","click")',
        "+1+1",
        "-2+3",
        "@SUM(A1:A2)",
        "\t=1+1",
        "\r=1+1",
    ],
)
def test_to_csv_escapes_formula_prefixes(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "out.csv"
    to_csv([{"url": "https://a.example", "title": payload}], path)
    rows = _read_rows(path)
    assert rows[0]["title"] == "'" + payload
    assert rows[0]["url"] == "https://a.example"


def test_to_csv_leaves_numbers_and_plain_text_alone(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    to_csv([{"title": "Normal title", "delta": -5, "ratio": -0.5, "ok": True}], path)
    row = _read_rows(path)[0]
    assert row == {"title": "Normal title", "delta": "-5", "ratio": "-0.5", "ok": "True"}


def test_to_csv_escape_formulas_opt_out(tmp_path: Path) -> None:
    path = tmp_path / "raw.csv"
    to_csv([{"title": "=1+1"}], path, escape_formulas=False)
    assert _read_rows(path)[0]["title"] == "=1+1"
