"""Run Level 1 then Level 2 and print a per-bill summary.

    python -m bill_decoder.run_all --bills test/bills --csv-dir test/csv --out output --work work
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import level1, level2


def run(bills: Path, csv_dir: Path, out: Path, work: Path, force: bool = False) -> int:
    failed1 = set(level1.run(bills, csv_dir / "level1.csv", out / "level1.csv", work, reuse_raw=not force))
    status2 = level2.run(bills, csv_dir / "level2.csv", work, out / "level2.csv", force=False)

    print("\nPer-bill summary")
    print(f"{'bill':<14}{'level1':<10}{'level2':<10}")
    bad = 0
    for bill_id, s2 in status2.items():
        s1 = "failed" if bill_id in failed1 else "ok"
        if s1 == "failed" or s2 == "failed":
            bad += 1
        print(f"{bill_id:<14}{s1:<10}{s2:<10}")
    print("(see work/<bill_id>/warnings.txt and l2_warnings.txt for warnings)")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run Level 1 and Level 2")
    ap.add_argument("--bills", required=True, type=Path)
    ap.add_argument("--csv-dir", required=True, type=Path, help="folder with level1.csv and level2.csv templates")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--work", default=Path("work"), type=Path)
    ap.add_argument("--force", action="store_true", help="ignore cached results and re-run the model")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return run(args.bills, args.csv_dir, args.out, args.work, args.force)


if __name__ == "__main__":
    sys.exit(main())
