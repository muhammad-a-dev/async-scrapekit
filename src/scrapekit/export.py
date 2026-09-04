"""Structured export helpers for JSONL and CSV."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def _normalize_record(record: Mapping[str, Any] | Any) -> dict[str, Any]:
    if hasattr(record, "to_dict") and callable(record.to_dict):
        data = record.to_dict()
        if isinstance(data, dict):
            return data
    if isinstance(record, Mapping):
        return dict(record)
    raise TypeError(f"Cannot export record of type {type(record)!r}")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def to_jsonl(
    records: Iterable[Mapping[str, Any] | Any],
    path: str | Path,
    *,
    append: bool = False,
) -> int:
    """Write records as JSON Lines. Returns the number of rows written."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    count = 0
    with destination.open(mode, encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(_normalize_record(record), ensure_ascii=False, default=str))
            handle.write("\n")
            count += 1
    return count


def to_csv(
    records: Iterable[Mapping[str, Any] | Any],
    path: str | Path,
    *,
    fieldnames: Sequence[str] | None = None,
    append: bool = False,
) -> int:
    """Write records as CSV. Nested values are JSON-encoded.

    When *fieldnames* is omitted, columns are inferred from the first record
    and any additional keys discovered later are appended.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    normalized = [_normalize_record(r) for r in records]
    if not normalized:
        if fieldnames:
            mode = "a" if append else "w"
            with destination.open(mode, encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
                if not append or destination.stat().st_size == 0:
                    writer.writeheader()
        return 0

    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in normalized:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        fieldnames = keys

    mode = "a" if append else "w"
    write_header = not append or not destination.exists() or destination.stat().st_size == 0
    with destination.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in normalized:
            writer.writerow({k: _stringify(row.get(k)) for k in fieldnames})
    return len(normalized)


def records_from_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load JSONL records from disk (utility for tests/examples)."""
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
