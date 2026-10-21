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
              SUM(CASE WHEN p.extraction_status IN ('extracted', 'ocr_extracted') THEN 1 ELSE 0 END) AS extracted_pages,
              SUM(CASE WHEN p.extraction_status = 'needs_ocr' THEN 1 ELSE 0 END) AS ocr_pages,
              SUM(CASE WHEN p.extraction_status = 'ocr_empty' THEN 1 ELSE 0 END) AS empty_pages,
              (
                SELECT COUNT(*)
                FROM stories s
                WHERE s.book_id = b.id AND COALESCE(s.is_active, 1) = 1
              ) AS story_count,
              (
                SELECT COUNT(*)
                FROM stories s
                WHERE s.book_id = b.id
                  AND COALESCE(s.is_active, 1) = 1
                  AND s.correction_status != 'not_started'
              ) AS corrected_story_count
              ,
              (
                SELECT COUNT(*)
                FROM stories s
                WHERE s.book_id = b.id
                  AND COALESCE(s.is_active, 1) = 1
                  AND TRIM(COALESCE(s.content_en, '')) != ''
              ) AS translated_story_count
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
              COALESCE(s.corrected_title_hi, s.title_hi) AS display_title_hi,
              COALESCE(s.corrected_content_hi, s.content_hi) AS display_content_hi,
              c.slug AS category_slug,
              c.name_hi AS category_hi,
              c.name_en AS category_en,
              b.slug AS book_slug,
              b.title_hi AS book_title_hi,
              b.title_en AS book_title_en
            FROM stories s
            LEFT JOIN categories c ON c.id = s.category_id
            JOIN books b ON b.id = s.book_id
            WHERE COALESCE(s.is_active, 1) = 1
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
