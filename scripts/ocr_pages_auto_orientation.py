from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from db import ROOT, connect


DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
NOISE_RE = re.compile(r"[#%/<>\\[\\]{}_=+]{2,}")


def ocr_image(image_path: Path, lang: str, psm: int) -> str:
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", lang, "--psm", str(psm)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def score_text(text: str) -> int:
    devanagari = len(DEVANAGARI_RE.findall(text))
    words = len(re.findall(r"[\u0900-\u097F]{2,}", text))
    noise = len(NOISE_RE.findall(text))
    return devanagari + (words * 4) - (noise * 20)


def rotated_temp(image: Image.Image, degrees: int) -> Path:
    rotated = image.rotate(degrees, expand=True)
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    path = Path(handle.name)
    handle.close()
    rotated.save(path)
    return path


def best_ocr(image_path: Path, lang: str, psm: int, rotations: list[int]) -> tuple[str, int]:
    image = Image.open(image_path)
    candidates: list[tuple[int, str, int]] = []
    temp_paths: list[Path] = []
    try:
        for degrees in rotations:
            if degrees == 0:
                candidate_path = image_path
            else:
                candidate_path = rotated_temp(image, degrees)
                temp_paths.append(candidate_path)
            text = ocr_image(candidate_path, lang, psm)
            candidates.append((score_text(text), text, degrees))
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)

    score, text, degrees = max(candidates, key=lambda item: item[0])
    return text, degrees


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR pages, choosing the best orientation for each page image.")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--lang", default="hin")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--rotations",
        default="0,270",
        help="Comma-separated rotation degrees to try. Use 0,90,270 for mixed scans.",
    )
    args = parser.parse_args()

    if not shutil.which("tesseract"):
        raise SystemExit("Tesseract is not installed. On macOS, run: brew install tesseract tesseract-lang")

    rotations = [int(part.strip()) for part in args.rotations.split(",") if part.strip()]

    with connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")

        end = args.end or book["total_pages"]
        pages = conn.execute(
            """
            SELECT page_number, raw_text, image_path
            FROM pages
            WHERE book_id = ?
              AND page_number >= ?
              AND page_number <= ?
              AND image_path IS NOT NULL
            ORDER BY page_number
            """,
            (book["id"], args.start, end),
        ).fetchall()

        for page in pages:
            if page["raw_text"] and not args.force:
                print(f"Skipping page {page['page_number']}: already has text")
                continue
            image_path = ROOT / page["image_path"]
            text, degrees = best_ocr(image_path, args.lang, args.psm, rotations)
            status = "ocr_extracted" if text else "ocr_empty"
            conn.execute(
                """
                UPDATE pages
                SET raw_text = ?,
                    extraction_method = ?,
                    extraction_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE book_id = ? AND page_number = ?
                """,
                (
                    text,
                    f"tesseract:{args.lang}:psm{args.psm}:auto-rot{degrees}",
                    status,
                    book["id"],
                    page["page_number"],
                ),
            )
            conn.commit()
            print(f"OCR page {page['page_number']}: {len(text)} chars ({status}, rot={degrees})")


if __name__ == "__main__":
    main()
