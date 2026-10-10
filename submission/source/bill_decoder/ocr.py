"""RapidOCR wrapper that returns positioned text lines."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageOps

_ENGINE = None


@dataclass
class OcrBox:
    text: str
    x: int
    y: int
    x2: int
    y2: int
    score: float

    @property
    def cy(self) -> float:
        return (self.y + self.y2) / 2

    @property
    def h(self) -> int:
        return max(1, self.y2 - self.y)


@dataclass
class OcrRow:
    y: int
    boxes: list[OcrBox]

    @property
    def text(self) -> str:
        return "   ".join(b.text for b in self.boxes)

    @property
    def x(self) -> int:
        return self.boxes[0].x if self.boxes else 0


def load_image(path: str | Path, max_side: int = 0) -> Image.Image:
    """Open with Pillow, apply EXIF orientation, convert to RGB.

    ``max_side`` > 0 downscales so the longest side is at most that value.
    """
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if max_side and max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    return img


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _ENGINE = RapidOCR()
    return _ENGINE


def run_ocr(img: Image.Image) -> list[OcrBox]:
    """Run RapidOCR and return boxes (axis-aligned) sorted top-to-bottom."""
    import numpy as np

    result, _ = _engine()(np.array(img))
    boxes: list[OcrBox] = []
    for quad, text, score in result or []:
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        boxes.append(
            OcrBox(
                text=str(text).strip(),
                x=int(min(xs)),
                y=int(min(ys)),
                x2=int(max(xs)),
                y2=int(max(ys)),
                score=float(score),
            )
        )
    boxes = [b for b in boxes if b.text]
    boxes.sort(key=lambda b: (b.cy, b.x))
    return boxes


def group_rows(boxes: list[OcrBox]) -> list[OcrRow]:
    """Group boxes whose vertical centres fall within the same text line."""
    rows: list[OcrRow] = []
    for box in sorted(boxes, key=lambda b: (b.cy, b.x)):
        placed = False
        if rows:
            last = rows[-1]
            ref = last.boxes[0]
            tol = max(ref.h, box.h) * 0.5
            if abs(box.cy - sum(b.cy for b in last.boxes) / len(last.boxes)) <= tol:
                last.boxes.append(box)
                placed = True
        if not placed:
            rows.append(OcrRow(y=box.y, boxes=[box]))
    for row in rows:
        row.boxes.sort(key=lambda b: b.x)
        row.y = int(min(b.y for b in row.boxes))
    return rows


def serialize_rows(rows: list[OcrRow]) -> str:
    """One line per row: ``[y=412 x=88] Total Electricity Charges 3,777.49``.

    Boxes in the same row are separated by `` | ``; every box after the first
    carries its own ``@x`` so the model can tell columns apart.
    """
    lines = []
    for row in rows:
        parts = " | ".join(
            b.text if i == 0 else f"{b.text} @x{b.x}" for i, b in enumerate(row.boxes)
        )
        lines.append(f"[y={row.y} x={row.x}] {parts}")
    return "\n".join(lines)


def ocr_image(
    image_path: str | Path, work_dir: Path | None = None, max_side: int = 0
) -> tuple[list[OcrRow], str]:
    """OCR a bill image, caching results in ``work_dir/ocr.json``.

    Returns (rows, serialized text).
    """
    cache = work_dir / "ocr.json" if work_dir else None
    boxes: list[OcrBox] | None = None
    if cache and cache.exists():
        try:
            boxes = [OcrBox(**b) for b in json.loads(cache.read_text(encoding="utf-8"))]
        except (ValueError, TypeError):
            boxes = None
    if boxes is None:
        boxes = run_ocr(load_image(image_path, max_side))
        if cache:
            work_dir.mkdir(parents=True, exist_ok=True)
            cache.write_text(
                json.dumps([asdict(b) for b in boxes], ensure_ascii=False), encoding="utf-8"
            )
    rows = group_rows(boxes)
    text = serialize_rows(rows)
    if work_dir:
        (work_dir / "ocr.txt").write_text(text, encoding="utf-8")
    return rows, text
