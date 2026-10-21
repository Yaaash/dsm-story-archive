from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from db import ROOT


SEGMENT_RE = re.compile(
    r"^###\s+(?P<number>[०-९0-9]+)\.\s+(?P<title>.*?)\s+\[pdf-pages\s+(?P<start>\d+)-(?P<end>\d+)\]\n(?P<body>.*?)(?=^###\s+|\Z)",
    re.M | re.S,
)
NOISE_LINE_RE = re.compile(r"^[\s\d०-९|/\\.,:;!?\-–—_]+$")
MULTI_HEADING_RE = re.compile(r"[०-९0-9]{1,4}\s*[\.,।)]\s+")


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = line.replace(" - ", " - ")
    return line


def clean_body(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = clean_line(raw)
        if not line or NOISE_LINE_RE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def should_skip(title: str, body: str) -> bool:
    if "सूची" in title:
        return True
    if len(body) < 90:
        return True
    # Index/table-of-contents lines often contain multiple story numbers in one title.
    if len(MULTI_HEADING_RE.findall(title)) >= 2:
        return True
    if len(title) > 95:
        return True
    return False


def make_slug(book_slug: str, index: int) -> str:
    return f"{book_slug}-story-{index:03d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create correction JSON from split OCR segment text.")
    parser.add_argument("segments_path")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--status", default="bulk_cleaned_draft")
    args = parser.parse_args()

    segments_path = Path(args.segments_path)
    if not segments_path.is_absolute():
        segments_path = ROOT / segments_path
    text = segments_path.read_text(encoding="utf-8")

    stories: list[dict] = []
    story_index = args.start_index
    skipped = 0
    for match in SEGMENT_RE.finditer(text):
        title = clean_line(match.group("title"))
        body = clean_body(match.group("body"))
        if should_skip(title, body):
            skipped += 1
            continue
        story = {
            "slug": make_slug(args.book_slug, story_index),
            "corrected_title_hi": title,
            "corrected_content_hi": body,
            "correction_status": args.status,
            "review_status": "needs_review",
            "start_page": int(match.group("start")),
            "end_page": int(match.group("end")),
            "sort_order": story_index,
            "create_if_missing": True,
        }
        stories.append(story)
        story_index += 1

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"book_slug": args.book_slug, "stories": stories}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(stories)} stories to {output_path.relative_to(ROOT)}; skipped {skipped}.")


if __name__ == "__main__":
    main()
