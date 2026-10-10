"""Dev helper: dump OCR text for bill images into work/<bill_id>/ocr.txt."""

import sys
from pathlib import Path

from bill_decoder.ocr import ocr_image

for p in sys.argv[2:]:
    path = Path(p)
    rows, text = ocr_image(path, Path(sys.argv[1]) / path.stem)
    print(f"{path.name}: {len(rows)} rows")
