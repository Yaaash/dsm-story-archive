from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

from db import connect


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")


SYSTEM_PROMPT = """You translate Hindi spiritual teaching stories into clear, faithful English.

Rules:
- Preserve the meaning, sequence, and teaching of the original.
- Keep names, spiritual terms, and book-specific concepts accurate.
- Translate dohas/verses naturally; do not invent new teachings.
- If OCR noise appears, infer conservatively from context and keep uncertain fragments simple.
- Return only valid JSON matching the requested schema."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate Hindi stories into English in resumable batches.")
    parser.add_argument("--book-slug", help="Translate only one book slug.")
    parser.add_argument("--story-id", type=int, help="Translate one story id.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum stories to translate in this run.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing English title/content.")
    parser.add_argument("--dry-run", action="store_true", help="Show the stories that would be translated.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to wait between API calls.")
    return parser.parse_args()


def story_rows(conn, args: argparse.Namespace) -> list:
    where = ["COALESCE(s.is_active, 1) = 1"]
    params: list[object] = []
    if not args.overwrite:
        where.append("(TRIM(COALESCE(s.title_en, '')) = '' OR TRIM(COALESCE(s.content_en, '')) = '')")
    if args.book_slug:
        where.append("b.slug = ?")
        params.append(args.book_slug)
    if args.story_id:
        where.append("s.id = ?")
        params.append(args.story_id)
    params.append(args.limit)
    return conn.execute(
        f"""
        SELECT
          s.id,
          s.sort_order,
          b.slug AS book_slug,
          COALESCE(s.corrected_title_hi, s.title_hi) AS title_hi,
          COALESCE(s.corrected_content_hi, s.content_hi) AS content_hi,
          s.title_en,
          s.content_en
        FROM stories s
        JOIN books b ON b.id = s.book_id
        WHERE {" AND ".join(where)}
        ORDER BY b.id, s.sort_order, s.id
        LIMIT ?
        """,
        params,
    ).fetchall()


def response_text(payload: dict) -> str:
    if payload.get("output_text"):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "".join(chunks)


def translate_story(row, model: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Export it first, then rerun this script.")

    user_prompt = {
        "story_id": row["id"],
        "hindi_title": row["title_hi"],
        "hindi_story": row["content_hi"],
    }
    body = {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Translate this story to English and return JSON:\n"
                        + json.dumps(user_prompt, ensure_ascii=False),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "story_translation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title_en": {"type": "string"},
                        "content_en": {"type": "string"},
                    },
                    "required": ["title_en", "content_en"],
                },
            }
        },
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {error.code}: {detail}") from error

    text = response_text(payload).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Model did not return valid JSON for story {row['id']}: {text[:500]}") from error


def main() -> None:
    args = parse_args()
    with connect() as conn:
        rows = story_rows(conn, args)
        if args.dry_run:
            for row in rows:
                print(f"{row['id']}: {row['book_slug']} #{row['sort_order']} {row['title_hi']}")
            print(f"Dry run: {len(rows)} story/stories selected.")
            return

        translated = 0
        for row in rows:
            print(f"Translating {row['id']}: {row['book_slug']} #{row['sort_order']} {row['title_hi']}")
            result = translate_story(row, args.model)
            title_en = result["title_en"].strip()
            content_en = result["content_en"].strip()
            if not title_en or not content_en:
                raise RuntimeError(f"Empty translation returned for story {row['id']}")
            conn.execute(
                """
                UPDATE stories
                SET title_en = ?,
                    content_en = ?,
                    translation_status = 'translated',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title_en, content_en, row["id"]),
            )
            conn.commit()
            translated += 1
            time.sleep(args.sleep)

    print(f"Translated {translated} story/stories.")


if __name__ == "__main__":
    main()
