from __future__ import annotations

from db import connect


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  title_hi TEXT NOT NULL,
  title_en TEXT,
  language TEXT NOT NULL DEFAULT 'hi',
  source_pdf_path TEXT NOT NULL,
  total_pages INTEGER,
  status TEXT NOT NULL DEFAULT 'registered',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id INTEGER NOT NULL,
  page_number INTEGER NOT NULL,
  raw_text TEXT NOT NULL DEFAULT '',
  extraction_method TEXT NOT NULL DEFAULT 'none',
  extraction_status TEXT NOT NULL DEFAULT 'pending',
  ocr_confidence REAL,
  image_path TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(book_id, page_number),
  FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name_hi TEXT NOT NULL,
  name_en TEXT NOT NULL,
  description_hi TEXT,
  description_en TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id INTEGER NOT NULL,
  category_id INTEGER,
  slug TEXT NOT NULL UNIQUE,
  title_hi TEXT NOT NULL,
  title_en TEXT,
  content_hi TEXT NOT NULL DEFAULT '',
  content_en TEXT NOT NULL DEFAULT '',
  raw_title_hi TEXT,
  raw_content_hi TEXT,
  corrected_title_hi TEXT,
  corrected_content_hi TEXT,
  correction_status TEXT NOT NULL DEFAULT 'not_started',
  is_active INTEGER NOT NULL DEFAULT 1,
  summary_hi TEXT,
  summary_en TEXT,
  start_page INTEGER,
  end_page INTEGER,
  segmentation_status TEXT NOT NULL DEFAULT 'draft',
  translation_status TEXT NOT NULL DEFAULT 'not_started',
  review_status TEXT NOT NULL DEFAULT 'needs_review',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE,
  FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS story_pages (
  story_id INTEGER NOT NULL,
  page_id INTEGER NOT NULL,
  PRIMARY KEY(story_id, page_id),
  FOREIGN KEY(story_id) REFERENCES stories(id) ON DELETE CASCADE,
  FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS story_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  story_id INTEGER NOT NULL,
  note_type TEXT NOT NULL DEFAULT 'general',
  note TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(story_id) REFERENCES stories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pages_book_page ON pages(book_id, page_number);
CREATE INDEX IF NOT EXISTS idx_stories_book ON stories(book_id);
CREATE INDEX IF NOT EXISTS idx_stories_category ON stories(category_id);
"""


STORY_MIGRATIONS = [
    ("raw_title_hi", "TEXT"),
    ("raw_content_hi", "TEXT"),
    ("corrected_title_hi", "TEXT"),
    ("corrected_content_hi", "TEXT"),
    ("correction_status", "TEXT NOT NULL DEFAULT 'not_started'"),
    ("is_active", "INTEGER NOT NULL DEFAULT 1"),
]


SEED_CATEGORIES = [
    ("uncategorized", "अवर्गीकृत", "Uncategorized", "कहानी की श्रेणी अभी तय नहीं हुई है।", "Stories awaiting category review.", 0),
    ("bhakti", "भक्ति", "Devotion", None, None, 10),
    ("gyan", "ज्ञान", "Wisdom", None, None, 20),
    ("seva", "सेवा", "Service", None, None, 30),
    ("guru", "गुरु", "Guru", None, None, 40),
    ("karuna", "करुणा", "Compassion", None, None, 50),
    ("vairagya", "वैराग्य", "Detachment", None, None, 60),
    ("chamatkar", "चमत्कार", "Miracles", None, None, 70),
    ("dharma", "धर्म", "Dharma", None, None, 80),
    ("niti", "नीति", "Ethics", None, None, 90),
    ("samaj", "समाज", "Society", None, None, 100),
    ("sadhana", "साधना", "Spiritual Practice", None, None, 110),
]


def main() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(stories)").fetchall()
        }
        for column, definition in STORY_MIGRATIONS:
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE stories ADD COLUMN {column} {definition}")
        conn.execute(
            """
            UPDATE stories
            SET
              raw_title_hi = COALESCE(raw_title_hi, title_hi),
              raw_content_hi = COALESCE(raw_content_hi, content_hi)
            """
        )
        conn.executemany(
            """
            INSERT INTO categories
              (slug, name_hi, name_en, description_hi, description_en, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
              name_hi=excluded.name_hi,
              name_en=excluded.name_en,
              description_hi=excluded.description_hi,
              description_en=excluded.description_en,
              sort_order=excluded.sort_order
            """,
            SEED_CATEGORIES,
        )
    print("Initialized data/archive.sqlite")


if __name__ == "__main__":
    main()
