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

Start a local server from the repo root:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/web/
```

