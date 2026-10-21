# DSM Story Archive

A review-first archive for Hindi spiritual story books. The workflow stores source PDFs,
extracted pages, segmented stories, categories, and English translations in SQLite, then
exports review data for a small local web page.

## Current Book

- Book 1: `source/books/book-01-drishtant-sarovar.pdf`

## Local Review

Initialize and ingest the first book:

```bash
python3 scripts/init_db.py
python3 scripts/ingest_pdf.py source/books/book-01-drishtant-sarovar.pdf \
  --title-hi "दृष्टांत सरोवर" \
  --title-en "Drishtant Sarovar" \
  --slug book-01-drishtant-sarovar
python3 scripts/export_review_data.py
```

For image-only PDFs, OCR the pages before segmentation:

```bash
python3 scripts/ocr_pages_tesseract.py --book-slug book-01-drishtant-sarovar
python3 scripts/segment_from_layout.py --book-slug book-01-drishtant-sarovar --start-page 8
python3 scripts/categorize_stories.py --book-slug book-01-drishtant-sarovar
python3 scripts/export_review_data.py
```

Import reviewed Hindi corrections:

```bash
python3 scripts/import_story_corrections.py data/corrections/book-01-hi-corrections.json
python3 scripts/export_review_data.py
```

Translate reviewed stories into English in resumable batches:

```bash
export OPENAI_API_KEY="your_api_key_here"
python3 scripts/translate_stories_en.py --book-slug book-01-drishtant-sarovar --limit 10
python3 scripts/export_review_data.py
```

Repeat the command with a higher `--limit` or no `--book-slug` to continue translating the
remaining archive. Existing English translations are skipped unless `--overwrite` is passed.

The OCR script requires Tesseract with Hindi language data:

```bash
brew install tesseract tesseract-lang
```

Start a local server from the repo root:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/web/
```
