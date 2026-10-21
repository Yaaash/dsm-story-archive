from __future__ import annotations

import argparse
from pathlib import Path

import pypdfium2 as pdfium

from db import ROOT, connect


def render_page(pdf_path: Path, output_dir: Path, page_number: int, scale: float) -> Path:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[page_number - 1]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"page-{page_number:04d}.png"
        image.save(output_path)
        return output_path
    finally:
        pdf.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render PDF pages to PNG files for OCR/review.")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--scale", type=float, default=3.0)
    args = parser.parse_args()

    with connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")

        pdf_path = ROOT / book["source_pdf_path"]
        end = args.end or book["total_pages"]
        output_dir = ROOT / "data" / "page-images" / args.book_slug

        for page_number in range(args.start, end + 1):
            output_path = render_page(pdf_path, output_dir, page_number, args.scale)
            rel_path = str(output_path.relative_to(ROOT))
            conn.execute(
                """
                UPDATE pages
                SET image_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE book_id = ? AND page_number = ?
                """,
                (rel_path, book["id"], page_number),
            )
            print(f"Rendered page {page_number}: {rel_path}")


if __name__ == "__main__":
    main()

