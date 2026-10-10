"""Provider detection from OCR text and the file-name prefix (no LLM)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

PREFIXES = {"KESC": "KE", "KE": "KE", "LESCO": "LESCO", "IESCO": "IESCO"}

_PATTERNS = [
    ("LESCO", re.compile(r"LAHORE\s+ELECTRIC|LESCO", re.I)),
    ("IESCO", re.compile(r"ISLAMABAD\s+ELECTRIC|IESCO", re.I)),
    ("KE", re.compile(r"K[\s\-]?ELECTRIC|KE\s+NTN|KE\s+GST|\bKE\b", re.I)),
]


def provider_from_text(ocr_text: str) -> str | None:
    """Return the provider whose keywords appear most often, else None."""
    scores = {name: len(p.findall(ocr_text)) for name, p in _PATTERNS}
    best = max(scores.values())
    if best == 0:
        return None
    # Ties are resolved by the declaration order above (LESCO, IESCO, KE).
    for name, _ in _PATTERNS:
        if scores[name] == best:
            return name
    return None


_WEB_RE = [re.compile(r"LESCO\s*CHARGES", re.I), re.compile(r"GOVT\.?\s*CHARGES", re.I)]
_DIGITAL_RE = re.compile(r"LOCK\s*OPEN|W\.?\s*E\s*CREDIT|TOTAL\s*FPA", re.I)


def detect_layout(provider: str | None, ocr_text: str) -> str | None:
    """LESCO sub-variants from OCR text: ``web`` | ``digital`` | ``standard``.

    ``web``: itemised "LESCO CHARGES" + "GOVT. CHARGES" bill.
    ``digital``: looks like IESCO (Subsidies, Total FPA, W.E Credit, Lock Open Credit).
    Other providers have a single layout (None).
    """
    if provider != "LESCO":
        return None
    if all(p.search(ocr_text) for p in _WEB_RE):
        return "web"
    if _DIGITAL_RE.search(ocr_text):
        return "digital"
    return "standard"


def provider_from_filename(path: str | Path) -> str | None:
    stem = Path(path).stem.upper()
    prefix = stem.split("_", 1)[0]
    return PREFIXES.get(prefix)


def detect_provider(ocr_text: str, image_path: str | Path) -> str | None:
    """Combine OCR keywords with the file-name prefix.

    Disagreement: the file-name prefix wins and a warning is logged.
    Returns None when neither source gives an answer.
    """
    from_text = provider_from_text(ocr_text)
    from_name = provider_from_filename(image_path)
    if from_text and from_name and from_text != from_name:
        log.warning(
            "provider mismatch for %s: OCR says %s, file name says %s; using file name",
            Path(image_path).name, from_text, from_name,
        )
        return from_name
    return from_name or from_text
