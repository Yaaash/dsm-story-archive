from __future__ import annotations

import argparse
import json
from pathlib import Path

from db import ROOT, connect


def main() -> None:
    parser = argparse.ArgumentParser(description="Import reviewed Hindi story corrections from JSON.")
    parser.add_argument("corrections_path")
    args = parser.parse_args()

    corrections_path = Path(args.corrections_path)
    if not corrections_path.is_absolute():
        corrections_path = ROOT / corrections_path
    if not corrections_path.exists():
        raise SystemExit(f"Corrections file not found: {corrections_path}")

    payload = json.loads(corrections_path.read_text(encoding="utf-8"))
    stories = payload.get("stories", [])
    if not stories:
        raise SystemExit("No stories found in corrections file.")

    with connect() as conn:
        book_slug = payload.get("book_slug")
        book = None
        if book_slug:
            book = conn.execute("SELECT id FROM books WHERE slug = ?", (book_slug,)).fetchone()
            if not book:
                raise SystemExit(f"Unknown book slug in corrections file: {book_slug}")

        categories = {
            row["slug"]: row["id"]
            for row in conn.execute("SELECT id, slug FROM categories").fetchall()
        }
        updated = 0
        for story in stories:
            slug = story["slug"]
            category_slug = story.get("category_slug")
            category_id = categories.get(category_slug) if category_slug else None
            result = conn.execute(
                """
                UPDATE stories
                SET
                  corrected_title_hi = ?,
                  corrected_content_hi = ?,
                  correction_status = ?,
                  review_status = ?,
                  start_page = COALESCE(?, start_page),
                  end_page = COALESCE(?, end_page),
                  sort_order = COALESCE(?, sort_order),
                  category_id = COALESCE(?, category_id),
                  is_active = ?,
                  updated_at = CURRENT_TIMESTAMP
                WHERE slug = ?
                """,
                (
                    story.get("corrected_title_hi"),
                    story.get("corrected_content_hi"),
                    story.get("correction_status", "corrected_draft"),
                    story.get("review_status", "needs_review"),
                    story.get("start_page"),
                    story.get("end_page"),
                    story.get("sort_order"),
                    category_id,
                    1 if story.get("is_active", True) else 0,
                    slug,
                ),
            )
            if result.rowcount == 0 and story.get("create_if_missing"):
                if not book:
                    raise SystemExit("create_if_missing requires top-level book_slug.")
                category_slug = story.get("category_slug", "uncategorized")
                conn.execute(
                    """
                    INSERT INTO stories (
                      book_id,
                      category_id,
                      slug,
                      title_hi,
                      content_hi,
                      raw_title_hi,
                      raw_content_hi,
                      corrected_title_hi,
                      corrected_content_hi,
                      correction_status,
                      review_status,
                      start_page,
                      end_page,
                      sort_order,
                      is_active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book["id"],
                        categories.get(category_slug, categories["uncategorized"]),
                        slug,
                        story.get("raw_title_hi") or story.get("corrected_title_hi") or "",
                        story.get("raw_content_hi") or story.get("corrected_content_hi") or "",
                        story.get("raw_title_hi") or story.get("corrected_title_hi") or "",
                        story.get("raw_content_hi") or story.get("corrected_content_hi") or "",
                        story.get("corrected_title_hi"),
                        story.get("corrected_content_hi"),
                        story.get("correction_status", "corrected_draft"),
                        story.get("review_status", "needs_review"),
                        story.get("start_page"),
                        story.get("end_page"),
                        story.get("sort_order", 0),
                        1 if story.get("is_active", True) else 0,
                    ),
                )
                updated += 1
                continue
            updated += result.rowcount

    print(f"Imported corrections for {updated} stories.")


if __name__ == "__main__":
    main()
