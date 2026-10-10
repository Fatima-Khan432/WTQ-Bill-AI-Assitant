"""Template reading and CSV writing (UTF-8, csv module, one JSON object per cell)."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def read_template(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (column names, rows) from a CSV template, preserving row order."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        return fields, [dict(r) for r in reader]


def write_csv(path: str | Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def to_json_line(obj: dict) -> str:
    """One-line JSON; the csv module doubles the inner quotation marks."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
