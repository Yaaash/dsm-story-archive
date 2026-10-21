from __future__ import annotations

import argparse
import csv
import re
import subprocess
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from db import ROOT, connect


PAGE_MARK_RE = re.compile(r"^[\s()०-९0-9|.,:;!\\-]+$")
SKIP_TITLE_RE = re.compile(r"(दृष्टान्त\s+सरोवर|रस\s+|सज्जनो|बन्धुओ|मित्रो|प्रिय\s+पाठ)")


@dataclass
class Line:
    page_number: int
    left: int
    top: int
    width: int
    height: int
    text: str


def clean_text(value: str) -> str:
    return re.sub(r"\\s+", " ", value.replace("_", " ")).strip()


def line_key(row: dict) -> tuple[str, str, str]:
    return (row["block_num"], row["par_num"], row["line_num"])


def tsv_lines(image_path: Path, page_number: int, lang: str, psm: int) -> list[Line]:
    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", lang, "--psm", str(psm), "tsv"],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = list(csv.DictReader(StringIO(result.stdout), delimiter="\t"))
    boxes = {}
    words = {}

    for row in rows:
        level = row.get("level")
        if level == "4":
            boxes[line_key(row)] = (
                int(float(row["left"])),
                int(float(row["top"])),
                int(float(row["width"])),
                int(float(row["height"])),
            )
        elif level == "5":
            text = clean_text(row.get("text") or "")
            if text:
                words.setdefault(line_key(row), []).append(text)

    lines: list[Line] = []
    for key, parts in words.items():
        if key not in boxes:
            continue
        text = clean_text(" ".join(parts))
        if not text:
            continue
        left, top, width, height = boxes[key]
        lines.append(Line(page_number, left, top, width, height, text))

    return sorted(lines, key=lambda line: (line.top, line.left))


def is_verse(line: Line) -> bool:
    text = line.text
    return ("।" in text or "॥" in text) and 160 <= line.left <= 360 and line.width <= 620


def is_title(lines: list[Line], index: int) -> bool:
    line = lines[index]
    text = line.text.strip()
    if PAGE_MARK_RE.match(text):
        return False
    if SKIP_TITLE_RE.search(text):
        return False
    if len(text) < 4 or len(text) > 64:
        return False
    if len(text.split()) > 8:
        return False
    if "," in text or "，" in text:
        return False
    if "।" in text or "॥" in text:
        return False
    if line.left < 300 or line.width > 540:
        return False

    next_lines = lines[index + 1 : index + 3]
    return any(is_verse(next_line) for next_line in next_lines)


def page_text_from_lines(lines: list[Line]) -> str:
    return "\n".join(line.text for line in lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Segment scanned stories using OCR line layout.")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--lang", default="hin")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--clear-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")

        page_rows = conn.execute(
            """
            SELECT page_number, image_path
            FROM pages
            WHERE book_id = ?
              AND page_number >= ?
              AND page_number <= ?
              AND image_path IS NOT NULL
            ORDER BY page_number
            """,
            (book["id"], args.start_page, args.end_page or book["total_pages"]),
        ).fetchall()

        all_lines: list[Line] = []
        for page in page_rows:
            image_path = ROOT / page["image_path"]
            all_lines.extend(tsv_lines(image_path, page["page_number"], args.lang, args.psm))

        boundaries = [i for i in range(len(all_lines)) if is_title(all_lines, i)]
        if args.dry_run:
            for number, index in enumerate(boundaries, start=1):
                line = all_lines[index]
                print(f"{number:03d}. p{line.page_number}: {line.text}")
            return

        if args.clear_existing:
            conn.execute("DELETE FROM stories WHERE book_id = ?", (book["id"],))

        category = conn.execute("SELECT id FROM categories WHERE slug = 'uncategorized'").fetchone()
        created = 0
        for story_index, start_index in enumerate(boundaries, start=1):
            end_index = boundaries[story_index] if story_index < len(boundaries) else len(all_lines)
            story_lines = all_lines[start_index:end_index]
            if not story_lines:
                continue

            title = story_lines[0].text
            content = page_text_from_lines(story_lines)
            if len(content) < 180:
                continue

            slug = f"{args.book_slug}-story-{story_index:03d}"
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
                  sort_order=excluded.sort_order,
                  updated_at=CURRENT_TIMESTAMP
                """,
                (
                    book["id"],
                    category["id"],
                    slug,
                    title,
                    content,
                    story_lines[0].page_number,
                    story_lines[-1].page_number,
                    story_index,
                ),
            )
            created += 1

    print(f"Created/updated {created} layout-segmented draft story rows.")


if __name__ == "__main__":
    main()
