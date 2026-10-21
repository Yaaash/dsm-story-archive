from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

from db import connect


HEADING_RE = re.compile(r"^\s*(?:[०-९0-9]+[.)।-]\s*)?(.{3,80})\s*$")


@dataclass
class Candidate:
    title: str
    start_page: int
    end_page: int
    content: str


def looks_like_heading(line: str) -> bool:
    clean = line.strip()
    if not clean:
        return False
    if len(clean) > 80:
        return False
    if clean.endswith(("।", "?", "!", ":")):
        return False
    if len(clean.split()) > 10:
        return False
    return bool(HEADING_RE.match(clean))


def make_slug(book_slug: str, index: int) -> str:
    return f"{book_slug}-story-{index:03d}"


def find_candidates(pages) -> list[Candidate]:
    candidates: list[Candidate] = []
    current_title = ""
    current_start = 0
    current_lines: list[str] = []

    for page in pages:
        page_number = page["page_number"]
        lines = [line.strip() for line in (page["raw_text"] or "").splitlines()]
        for line in lines:
            if looks_like_heading(line) and current_lines:
                candidates.append(
                    Candidate(
                        title=current_title or f"Story {len(candidates) + 1}",
                        start_page=current_start,
                        end_page=page_number,
                        content="\n".join(current_lines).strip(),
                    )
                )
                current_title = line
                current_start = page_number
                current_lines = []
            elif looks_like_heading(line) and not current_lines and not current_title:
                current_title = line
                current_start = page_number
            else:
                if line:
                    if not current_start:
                        current_start = page_number
                    current_lines.append(line)

    if current_lines:
        candidates.append(
            Candidate(
                title=current_title or f"Story {len(candidates) + 1}",
                start_page=current_start,
                end_page=pages[-1]["page_number"],
                content="\n".join(current_lines).strip(),
            )
        )
    return [item for item in candidates if len(item.content) >= 100]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create draft story rows from OCR page text.")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--clear-existing", action="store_true")
    args = parser.parse_args()

    with connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")

        category = conn.execute("SELECT id FROM categories WHERE slug = 'uncategorized'").fetchone()
        if args.clear_existing:
            conn.execute("DELETE FROM stories WHERE book_id = ?", (book["id"],))

        where = "book_id = ? AND raw_text <> '' AND page_number >= ?"
        params: list = [book["id"], args.start_page]
        if args.end_page:
            where += " AND page_number <= ?"
            params.append(args.end_page)

        pages = conn.execute(
            """
            SELECT * FROM pages
            WHERE """ + where + """
            ORDER BY page_number
            """,
            params,
        ).fetchall()

        if not pages:
            raise SystemExit("No OCR/page text available yet.")

        candidates = find_candidates(pages)
        if args.limit:
            candidates = candidates[: args.limit]

        for index, candidate in enumerate(candidates, start=1):
            slug = make_slug(args.book_slug, index)
            conn.execute(
                """
                INSERT INTO stories
                  (book_id, category_id, slug, title_hi, content_hi, start_page, end_page, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                  title_hi=excluded.title_hi,
                  content_hi=excluded.content_hi,
                  start_page=excluded.start_page,
                  end_page=excluded.end_page,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (
                    book["id"],
                    category["id"],
                    slug,
                    candidate.title,
                    candidate.content,
                    candidate.start_page,
                    candidate.end_page,
                    index,
                ),
            )

    print(f"Created/updated {len(candidates)} draft story rows.")


if __name__ == "__main__":
    main()
