from __future__ import annotations

import argparse
import re

from db import connect


CATEGORY_KEYWORDS = {
    "bhakti": [
        "भक्ति",
        "भगवान",
        "परमेश्वर",
        "ईश्वर",
        "राम",
        "गणेश",
        "विष्णु",
        "पूज",
        "माधव",
        "नारायण",
    ],
    "gyan": [
        "ज्ञान",
        "अनुभव",
        "विद्या",
        "बुद्धि",
        "पण्डित",
        "पंडित",
        "अर्थ",
        "शिक्ष",
        "विचार",
        "सत्ता",
    ],
    "seva": [
        "सेवा",
        "परोपकार",
        "उपकार",
        "दान",
        "दानी",
        "रन्तिदेव",
    ],
    "guru": [
        "गुरु",
        "महात्मा",
        "साधु",
        "सन्यासी",
        "सन्‍्यास",
        "उपदेश",
    ],
    "karuna": [
        "करुणा",
        "दया",
        "पीड़ा",
        "दुख",
        "दुःख",
        "प्राणी",
        "बचाइ",
    ],
    "vairagya": [
        "वैराग",
        "त्याग",
        "विषय",
        "इन्द्रिय",
        "इंद्रिय",
        "काम",
        "मोह",
        "माया",
        "धन",
        "घरबार",
    ],
    "chamatkar": [
        "चमत्कार",
        "भूत",
        "अद्भुत",
        "डिबिया",
        "माया",
    ],
    "dharma": [
        "धर्म",
        "सत्य",
        "सती",
        "पालन",
        "कल्याण",
        "कर्म",
        "नियोग",
    ],
    "niti": [
        "नीति",
        "सच्चाई",
        "चालाकी",
        "झूठ",
        "सच",
        "दुर्जन",
        "परिणाम",
        "अवसर",
        "जिद्द",
        "ज़िद्द",
    ],
    "samaj": [
        "समाज",
        "नव",
        "बाबू",
        "अंग्रेजी",
        "विलायत",
        "सरकार",
        "डिप्टी",
        "तरक्की",
        "गृहस्थ",
        "सभा",
    ],
    "sadhana": [
        "साधना",
        "मन",
        "ध्यान",
        "नाम",
        "जप",
        "इन्द्रियों",
        "इंद्रियों",
        "दमन",
    ],
}


TITLE_BOOST = 4


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def score_story(title: str, content: str) -> tuple[str, int]:
    title_text = normalize(title)
    body_text = normalize(content)
    scores = {}
    for slug, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            score += body_text.count(keyword)
            if keyword in title_text:
                score += TITLE_BOOST
        scores[slug] = score

    slug, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return "uncategorized", 0
    return slug, score


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign draft categories to stories with keyword scoring.")
    parser.add_argument("--book-slug", required=True)
    args = parser.parse_args()

    with connect() as conn:
        book = conn.execute("SELECT id FROM books WHERE slug = ?", (args.book_slug,)).fetchone()
        if not book:
            raise SystemExit(f"Unknown book slug: {args.book_slug}")

        categories = {
            row["slug"]: row["id"]
            for row in conn.execute("SELECT id, slug FROM categories").fetchall()
        }
        stories = conn.execute(
            """
            SELECT
              id,
              COALESCE(corrected_title_hi, title_hi) AS title_hi,
              COALESCE(corrected_content_hi, content_hi) AS content_hi
            FROM stories
            WHERE book_id = ?
            ORDER BY sort_order
            """,
            (book["id"],),
        ).fetchall()

        counts: dict[str, int] = {}
        for story in stories:
            category_slug, score = score_story(story["title_hi"], story["content_hi"])
            conn.execute(
                """
                UPDATE stories
                SET category_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (categories[category_slug], story["id"]),
            )
            counts[category_slug] = counts.get(category_slug, 0) + 1
            print(f"{story['id']}: {category_slug} ({score}) - {story['title_hi']}")

    print("Assigned draft categories:")
    for slug, count in sorted(counts.items()):
        print(f"  {slug}: {count}")


if __name__ == "__main__":
    main()
