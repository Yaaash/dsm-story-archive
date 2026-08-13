from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader

from db import ROOT, connect


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def extract_page_text(page) -> str:
    try:
        return (page.extract_text() or "").strip()
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a source PDF and ingest page text when available.")
    parser.add_argument("pdf_path")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title-hi", required=True)
    parser.add_argument("--title-en", default="")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_absolute():
        pdf_path = ROOT / pdf_path
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    source_path = relative_to_root(pdf_path)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO books (slug, title_hi, title_en, source_pdf_path, total_pages, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
              title_hi=excluded.title_hi,
              title_en=excluded.title_en,
              source_pdf_path=excluded.source_pdf_path,
              total_pages=excluded.total_pages,
              status=excluded.status,
              updated_at=CURRENT_TIMESTAMP
            """,
            (args.slug, args.title_hi, args.title_en, source_path, total_pages, "ingested"),
        )
        book_id = conn.execute("SELECT id FROM books WHERE slug = ?", (args.slug,)).fetchone()["id"]

        text_pages = 0
        for index, page in enumerate(reader.pages, start=1):
            text = extract_page_text(page)
            if text:
                status = "extracted"
                method = "pypdf"
                text_pages += 1
            else:
                status = "needs_ocr"
                method = "none"

            conn.execute(
                """
                INSERT INTO pages
                  (book_id, page_number, raw_text, extraction_method, extraction_status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(book_id, page_number) DO UPDATE SET
                  raw_text=excluded.raw_text,
                  extraction_method=excluded.extraction_method,
                  extraction_status=excluded.extraction_status,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (book_id, index, text, method, status),
            )

    print(f"Ingested {total_pages} pages for {args.slug}")
    print(f"Selectable text pages: {text_pages}")
    if text_pages == 0:
        print("All pages need OCR before story segmentation.")


if __name__ == "__main__":
    main()

