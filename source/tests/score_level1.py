"""Compare Level 1 output with hand-checked expected JSON.

Numbers match within +-1, text and dates must match exactly.

    python tests/score_level1.py --csv output/level1.csv
    python tests/score_level1.py --work work
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

EXPECTED_DIR = Path(__file__).parent / "expected"


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare_value(got, want) -> bool:
    if _is_num(got) and _is_num(want):
        return abs(got - want) <= 1.0
    return got == want


def compare_list(got: list, want: list) -> bool:
    if len(got) != len(want):
        return False
    return all(
        g.get("type") == w.get("type") and compare_value(g.get("amount"), w.get("amount"))
        for g, w in zip(got, want)
    )


def score_bill(got: dict, want: dict) -> list[str]:
    """Return a list of mismatch descriptions (empty = identical within tolerance)."""
    problems = []
    if list(got.keys()) != list(want.keys()):
        problems.append(f"keys differ: {list(got.keys())}")
    for key, expected in want.items():
        actual = got.get(key, "<missing>")
        ok = compare_list(actual, expected) if key in {"charges", "taxes"} and isinstance(actual, list) \
            else compare_value(actual, expected)
        if not ok:
            problems.append(f"{key}: got {actual!r}, expected {expected!r}")
    return problems


def load_outputs(args) -> dict[str, dict]:
    outputs: dict[str, dict] = {}
    if args.csv:
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["json"]:
                    outputs[row["bill_id"]] = json.loads(row["json"])
    else:
        for p in Path(args.work).glob("*/final.json"):
            outputs[p.parent.name] = json.loads(p.read_text(encoding="utf-8"))
    return outputs


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--csv", type=Path)
    g.add_argument("--work", type=Path)
    args = ap.parse_args()

    outputs = load_outputs(args)
    failures = 0
    for exp_path in sorted(EXPECTED_DIR.glob("*.json")):
        bill = exp_path.stem
        if bill not in outputs:
            print(f"{bill}: no output")
            continue
        problems = score_bill(outputs[bill], json.loads(exp_path.read_text(encoding="utf-8")))
        if problems:
            failures += 1
            print(f"{bill}: {len(problems)} mismatch(es)")
            for p in problems:
                print(f"   - {p}")
        else:
            print(f"{bill}: OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
