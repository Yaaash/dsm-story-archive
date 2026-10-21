from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import pypdfium2 as pdfium

from db import ROOT, connect


def render_page(pdf: pdfium.PdfDocument, output_dir: Path, page_number: int, scale: float) -> Path:
    page = pdf[page_number - 1]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page-{page_number:04d}.png"
    image.save(output_path)
    return output_path


def ocr_image(image_path: Path, lang: str, psm: int) -> str:
    command = [
        "tesseract",
        str(image_path),
        "stdout",
        "-l",
        lang,
        "--psm",
        str(psm),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR image-only PDF pages with Tesseract.")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--lang", default="hin")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not shutil.which("tesseract"):
        raise SystemExit("Tesseract is not installed. On macOS, run: brew install tesseract tesseract-lang")

    with connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")

        pdf_path = ROOT / book["source_pdf_path"]
        output_dir = ROOT / "data" / "page-images" / args.book_slug
        end = args.end or book["total_pages"]

        pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            for page_number in range(args.start, end + 1):
                page_row = conn.execute(
                    """
                    SELECT raw_text, image_path FROM pages
                    WHERE book_id = ? AND page_number = ?
                    """,
                    (book["id"], page_number),
                ).fetchone()
                if page_row and page_row["raw_text"] and not args.force:
                    print(f"Skipping page {page_number}: already has text")
                    continue

                image_path = output_dir / f"page-{page_number:04d}.png"
                if not image_path.exists() or args.force:
                    image_path = render_page(pdf, output_dir, page_number, args.scale)

                text = ocr_image(image_path, args.lang, args.psm)
                rel_image_path = str(image_path.relative_to(ROOT))
                status = "ocr_extracted" if text else "ocr_empty"

                conn.execute(
                    """
                    UPDATE pages
                    SET
                      raw_text = ?,
                      extraction_method = ?,
                      extraction_status = ?,
                      image_path = ?,
                      updated_at = CURRENT_TIMESTAMP
                    WHERE book_id = ? AND page_number = ?
                    """,
                    (text, f"tesseract:{args.lang}:psm{args.psm}", status, rel_image_path, book["id"], page_number),
                )
                conn.commit()
                print(f"OCR page {page_number}: {len(text)} chars ({status})")
        finally:
            pdf.close()


if __name__ == "__main__":
    main()

