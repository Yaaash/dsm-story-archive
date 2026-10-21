from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from db import ROOT, connect


HEADING_RE = re.compile(r"^\s*([०-९0-9]{1,4})\s*[\.,।)]\s*(.{3,90})\s*$")
NOISE_RE = re.compile(r"^[\s\d०-९|/\\.,:;!?\-–—_]+$")


@dataclass
class OcrBlock:
    source_page: int
    side: str
    text: str


@dataclass
class StoryDraft:
    number: int
    title: str
    start_source_page: int
    end_source_page: int
    content: str


def hindi_number(value: str) -> int:
    trans = str.maketrans("०१२३४५६७८९", "0123456789")
    return int(value.translate(trans))


def rotation_from_method(method: str | None) -> int | None:
    if not method:
        return None
    match = re.search(r"rot(0|90|180|270)", method)
    if not match:
        return None
    return int(match.group(1))


def score_text(text: str) -> float:
    devanagari = sum("\u0900" <= ch <= "\u097f" for ch in text)
    latin = sum("a" <= ch.lower() <= "z" for ch in text)
    replacements = text.count("�")
    heading_hits = len(HEADING_RE.findall(text))
    return devanagari + heading_hits * 40 - latin * 0.7 - replacements * 20


def ocr_image(image: Image.Image, lang: str, psm: int) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        image.save(tmp.name)
        result = subprocess.run(
            ["tesseract", tmp.name, "stdout", "-l", lang, "--psm", str(psm)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    return result.stdout.strip()


def choose_rotation(image: Image.Image, lang: str, psm: int, preferred: int | None) -> int:
    candidates = [preferred] if preferred is not None else []
    candidates += [0, 90, 180, 270]
    seen: set[int] = set()
    best_rotation = 0
    best_score = float("-inf")
    for rotation in candidates:
        if rotation is None or rotation in seen:
            continue
        seen.add(rotation)
        rotated = image.rotate(rotation, expand=True) if rotation else image
        sample = rotated
        if rotated.width > 900 and rotated.height > 900:
            # Fast orientation check on the right half; it usually contains body text.
            sample = rotated.crop((rotated.width // 2, 0, rotated.width, rotated.height))
        text = ocr_image(sample, lang, psm)
        score = score_text(text)
        if score > best_score:
            best_score = score
            best_rotation = rotation
    return best_rotation


def split_spread(image: Image.Image) -> list[tuple[str, Image.Image]]:
    if image.width >= image.height:
        mid = image.width // 2
        return [
            ("left", image.crop((0, 0, mid, image.height))),
            ("right", image.crop((mid, 0, image.width, image.height))),
        ]
    mid = image.height // 2
    return [
        ("top", image.crop((0, 0, image.width, mid))),
        ("bottom", image.crop((0, mid, image.width, image.height))),
    ]


def normalize_text(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if NOISE_RE.match(line):
            continue
        line = line.replace("----", " - ").replace("---", " - ")
        lines.append(line)
    return "\n".join(lines)


def looks_like_heading(line: str) -> tuple[int, str] | None:
    match = HEADING_RE.match(line.strip())
    if not match:
        return None
    number = hindi_number(match.group(1))
    title = match.group(2).strip()
    if number <= 0 or number > 900:
        return None
    if len(title.split()) > 12:
        return None
    return number, title


def segment_blocks(blocks: list[OcrBlock]) -> list[StoryDraft]:
    stories: list[StoryDraft] = []
    current_number: int | None = None
    current_title = ""
    current_start = 0
    current_end = 0
    current_lines: list[str] = []

    for block in blocks:
        for line in normalize_text(block.text).splitlines():
            heading = looks_like_heading(line)
            if heading:
                if current_number is not None and len("\n".join(current_lines)) >= 60:
                    stories.append(
                        StoryDraft(
                            number=current_number,
                            title=current_title,
                            start_source_page=current_start,
                            end_source_page=current_end,
                            content="\n".join(current_lines).strip(),
                        )
                    )
                current_number, current_title = heading
                current_start = block.source_page
                current_end = block.source_page
                current_lines = [line]
            elif current_number is not None:
                current_end = block.source_page
                current_lines.append(line)

    if current_number is not None and len("\n".join(current_lines)) >= 60:
        stories.append(
            StoryDraft(
                number=current_number,
                title=current_title,
                start_source_page=current_start,
                end_source_page=current_end,
                content="\n".join(current_lines).strip(),
            )
        )
    return stories


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR split book spreads and segment by numbered story headings.")
    parser.add_argument("--book-slug", required=True)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--start-story", type=int, default=1)
    parser.add_argument("--lang", default="hin")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trust-db-rotation", action="store_true")
    args = parser.parse_args()

    with connect() as conn:
        book = conn.execute("SELECT * FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")
        pages = conn.execute(
            """
            SELECT page_number, image_path, extraction_method
            FROM pages
            WHERE book_id = ?
              AND page_number >= ?
              AND page_number <= ?
              AND image_path IS NOT NULL
            ORDER BY page_number
            """,
            (book["id"], args.start_page, args.end_page or book["total_pages"]),
        ).fetchall()

    blocks: list[OcrBlock] = []
    for page in pages:
        image_path = ROOT / page["image_path"]
        image = Image.open(image_path).convert("L")
        preferred = rotation_from_method(page["extraction_method"])
        rotation = preferred if args.trust_db_rotation and preferred is not None else choose_rotation(image, args.lang, args.psm, preferred)
        rotated = image.rotate(rotation, expand=True) if rotation else image
        for side, half in split_spread(rotated):
            text = ocr_image(half, args.lang, args.psm)
            blocks.append(OcrBlock(page["page_number"], side, text))
        print(f"OCR split page {page['page_number']}: rot={rotation}")

    stories = [story for story in segment_blocks(blocks) if story.number >= args.start_story]
    out = args.output or ROOT / "data" / "exports" / f"{args.book_slug}-split-segments.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for story in stories:
            handle.write(
                f"### {story.number}. {story.title} "
                f"[pdf-pages {story.start_source_page}-{story.end_source_page}]\n"
            )
            handle.write(story.content)
            handle.write("\n\n")
    try:
        display_path = out.relative_to(ROOT)
    except ValueError:
        display_path = out
    print(f"Wrote {len(stories)} segmented stories to {display_path}")


if __name__ == "__main__":
    main()
