import zipfile
from pathlib import Path

root = Path(__file__).parent
skip_dirs = {".venv", "__pycache__", ".pytest_cache", ".streamlit_cache"}
skip_files = {".env"}
out = root / "submission.zip"
if out.exists():
    out.unlink()
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for top in ("output", "source", "demo"):
        if not (root / top).exists():
            continue
        for p in sorted((root / top).rglob("*")):
            if p.is_dir() or skip_dirs & set(p.relative_to(root).parts) or p.name in skip_files:
                continue
            z.write(p, p.relative_to(root).as_posix())
print(out, round(out.stat().st_size / 1e6, 2), "MB")
with zipfile.ZipFile(out) as z:
    names = z.namelist()
    print(len(names), "files; .env present:", any(n.endswith(".env") for n in names))
