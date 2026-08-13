from __future__ import annotations

import json
from pathlib import Path

from db import ROOT, connect, row_to_dict


EXPORT_PATH = ROOT / "data" / "exports" / "review-data.json"


def fetch_all(conn, query: str, params: tuple = ()) -> list[dict]:
    return [row_to_dict(row) for row in conn.execute(query, params).fetchall()]


def main() -> None:
    with connect() as conn:
        books = fetch_all(
            conn,
            """
            SELECT
              b.*,
              COUNT(p.id) AS page_count,
              SUM(CASE WHEN p.extraction_status = 'extracted' THEN 1 ELSE 0 END) AS extracted_pages,
              SUM(CASE WHEN p.extraction_status = 'needs_ocr' THEN 1 ELSE 0 END) AS ocr_pages
            FROM books b
            LEFT JOIN pages p ON p.book_id = b.id
            GROUP BY b.id
            ORDER BY b.id
            """,
        )
        categories = fetch_all(conn, "SELECT * FROM categories ORDER BY sort_order, name_en")
        stories = fetch_all(
            conn,
            """
            SELECT
              s.*,
              c.slug AS category_slug,
              c.name_hi AS category_hi,
              c.name_en AS category_en,
              b.slug AS book_slug,
              b.title_hi AS book_title_hi,
              b.title_en AS book_title_en
            FROM stories s
            LEFT JOIN categories c ON c.id = s.category_id
            JOIN books b ON b.id = s.book_id
            ORDER BY COALESCE(c.sort_order, 999), s.sort_order, s.id
            """,
        )
        page_samples = fetch_all(
            conn,
            """
            SELECT p.*, b.slug AS book_slug
            FROM pages p
            JOIN books b ON b.id = p.book_id
            WHERE p.page_number <= 5
            ORDER BY b.id, p.page_number
            """,
        )

    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text(
        json.dumps(
            {
                "books": books,
                "categories": categories,
                "stories": stories,
                "page_samples": page_samples,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Exported {EXPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

