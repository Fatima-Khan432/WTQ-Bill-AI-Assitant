"""Level 1 CLI: read every bill in a folder and fill the json column of level1.csv.

    python -m bill_decoder.level1 --bills test/bills --template test/csv/level1.csv \
        --out output/level1.csv --work work
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .assemble import assemble
from .config import Config, load_config
from .csv_io import read_template, to_json_line, write_csv
from .llm import ExtractionFormatError, GeminiClient, LLMError
from .ocr import ocr_image
from .provider import detect_layout, detect_provider, provider_from_filename
from .schema import RAW_SCHEMA_VERSION, RawBill, fallback_bill
from .validate import hard_check, soft_check

log = logging.getLogger("bill_decoder")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")


def find_image(bills_dir: Path, bill_id: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = bills_dir / f"{bill_id}{ext}"
        if p.exists():
            return p
    return None


def extract_raw(
    client: GeminiClient, image: Path, ocr_text: str, provider: str, cfg: Config,
    warnings: list[str], layout: str | None = None,
) -> RawBill:
    """One LLM extraction plus up to ``max_retries`` retries on hard-check failures."""
    error: str | None = None
    raw: RawBill | None = None
    for attempt in range(cfg.max_retries + 1):
        try:
            raw = client.extract(image, ocr_text, provider, previous_error=error, layout=layout)
        except ExtractionFormatError as exc:
            error, raw = str(exc), None
            warnings.append(f"attempt {attempt + 1}: {error}")
            continue
        problems = hard_check(raw)
        if not problems:
            return raw
        error = "\n".join(problems)
        warnings.append(f"attempt {attempt + 1}: hard check failed: {error}")
    if raw is None:
        raise ExtractionFormatError(error or "no valid response")
    return raw  # unparseable amounts become null in assemble(), with warnings


def _raw_version_ok(meta_path: Path) -> bool:
    """A cached raw.json is reusable only if it was written with the current schema version."""
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("version") == RAW_SCHEMA_VERSION
    except (OSError, ValueError):
        return False


def load_cached_level1(work_dir: Path) -> tuple[dict, dict, str | None, list[str]] | None:
    """Return (final, raw, provider, warnings) from work/<bill_id>/ if a complete, current cache exists."""
    try:
        if not _raw_version_ok(work_dir / "raw.meta.json"):
            return None
        final = json.loads((work_dir / "final.json").read_text(encoding="utf-8"))
        raw = json.loads((work_dir / "raw.json").read_text(encoding="utf-8"))
        meta = json.loads((work_dir / "raw.meta.json").read_text(encoding="utf-8"))
        wp = work_dir / "warnings.txt"
        warnings = wp.read_text(encoding="utf-8").splitlines() if wp.exists() else []
        return final, raw, meta.get("provider"), warnings
    except (OSError, ValueError):
        return None


def process_bill(
    image: Path, work_dir: Path, client: GeminiClient | None, cfg: Config, reuse_raw: bool = False
) -> tuple[dict, list[str], bool]:
    """Return (final 18-key object, warnings, ok)."""
    warnings: list[str] = []
    work_dir.mkdir(parents=True, exist_ok=True)
    provider = provider_from_filename(image)
    try:
        _, ocr_text = ocr_image(image, work_dir, cfg.max_image_side)
        provider = detect_provider(ocr_text, image)
        if provider is None and client is not None:
            provider = client.detect_provider(image, ocr_text)
        if provider is None:
            raise RuntimeError("provider could not be determined")

        layout = detect_layout(provider, ocr_text)
        raw_path = work_dir / "raw.json"
        meta_path = work_dir / "raw.meta.json"
        if reuse_raw and raw_path.exists() and _raw_version_ok(meta_path):
            raw = RawBill.model_validate_json(raw_path.read_text(encoding="utf-8"))
        else:
            if client is None:
                raise LLMError("no LLM client available (check API_KEY)")
            raw = extract_raw(client, image, ocr_text, provider, cfg, warnings, layout)
            raw_path.write_text(raw.model_dump_json(indent=2), encoding="utf-8")
            meta_path.write_text(
                json.dumps({"version": RAW_SCHEMA_VERSION, "provider": provider, "layout": layout}),
                encoding="utf-8",
            )

        final = assemble(raw, provider, warnings, layout)
        warnings.extend(soft_check(final))
        ok = True
    except Exception as exc:  # noqa: BLE001 - one bad bill must not stop the run
        log.error("%s failed: %s", image.name, exc)
        warnings.append(f"FAILED: {exc}")
        final = fallback_bill(provider)
        ok = False

    (work_dir / "final.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    (work_dir / "warnings.txt").write_text("\n".join(warnings), encoding="utf-8")
    return final, warnings, ok


def run(
    bills: Path, template: Path, out: Path, work: Path, reuse_raw: bool = False
) -> list[str]:
    cfg = load_config()
    fields, rows = read_template(template)
    if "bill_id" not in fields or "json" not in fields:
        raise SystemExit(f"{template} must have columns bill_id, json (found {fields})")

    client: GeminiClient | None = None
    try:
        client = GeminiClient(cfg)
    except LLMError as exc:
        if not reuse_raw:
            log.error("LLM unavailable: %s", exc)

    failed: list[str] = []
    for row in rows:
        bill_id = row["bill_id"]
        image = find_image(bills, bill_id)
        if image is None:
            log.error("no image for %s in %s", bill_id, bills)
            final, warns, ok = fallback_bill(provider_from_filename(bill_id)), ["image not found"], False
        else:
            log.info("processing %s", bill_id)
            final, warns, ok = process_bill(image, work / bill_id, client, cfg, reuse_raw)
        for w in warns:
            log.warning("%s: %s", bill_id, w)
        if not ok:
            failed.append(bill_id)
        row["json"] = to_json_line(final)

    write_csv(out, fields, rows)
    print(f"Wrote {len(rows)} rows to {out}")
    if failed:
        print(f"FAILED bills (fallback rows written): {', '.join(failed)}")
    return failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Level 1: extract bill details into level1.csv")
    ap.add_argument("--bills", required=True, type=Path, help="folder of bill images")
    ap.add_argument("--template", required=True, type=Path, help="level1.csv template")
    ap.add_argument("--out", required=True, type=Path, help="output level1.csv")
    ap.add_argument("--work", default=Path("work"), type=Path, help="intermediate files folder")
    ap.add_argument("--reuse-raw", action="store_true", help="reuse work/<id>/raw.json, no LLM calls")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args.bills, args.template, args.out, args.work, args.reuse_raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())

