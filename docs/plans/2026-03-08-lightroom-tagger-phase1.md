# Lightroom Tagger Phase 1 - Implementation Plan

**Project:** lightroom-tagger  
**Goal:** Read Lightroom catalog, index metadata, store in TinyDB  
**Date:** 2026-03-08

## Prerequisites

- NAS path: `\\nas\ccanales\Lightroom Server\FinalCatalog-v13-3.lrcat`
- WSL drvfs mount: `/mnt/nas`
- TinyDB path: `~/lightroom_tagger/library.db`
- Python dependencies: `sqlite3`, `tinydb`, `python-dotenv`

## Tasks

### Task 1: Config + NAS Mount Setup
**File:** `lightroom_tagger/config.py`

Create config module that:
- Loads config from `config.yaml` or environment variables
- Resolves NAS paths (e.g., `//nas/...` → `/mnt/nas/...`)
- Supports custom mount points
- Provides defaults for all settings

**Verification:**
- Create `config.yaml` with test values
- Verify path resolution works

---

### Task 2: Schema Exploration
**File:** `lightroom_tagger/schema_explorer.py`

Explore Lightroom catalog schema:
- Connect to `.lrcat` SQLite database
- List all tables
- Show schema for key tables: `Adobe_images`, `AgLibraryFile`, `AgLibraryFolder`, `AgLibraryKeyword`, `AgLibraryKeywordImage`, `AgHarvestedExifMetadata`, `AgLibraryIPTC`
- Output schema as JSON for reference

**Verification:**
- Run against real catalog (if available)
- Print summary of key tables and columns

---

### Task 3: Catalog Reader
**File:** `lightroom_tagger/catalog_reader.py`

Read from Lightroom catalog:
- Query `AgLibraryFile` + `AgLibraryFolder` for file paths
- Join with `Adobe_images` for ratings, pick flag, color label
- Join with `AgLibraryKeywordImage` + `AgLibraryKeyword` for keywords
- Join with `AgHarvestedExifMetadata` for EXIF (camera, lens, date, GPS)
- Join with `AgLibraryIPTC` for title, caption, copyright
- Return list of image records with all metadata

**Verification:**
- Print sample record for testing

---

### Task 4: TinyDB Operations
**File:** `lightroom_tagger/database.py`

TinyDB storage:
- Initialize TinyDB at configured path
- Store image records with unique key: `{date_taken}_{filename}`
- Support upsert (update if exists)
- Query by keyword, rating, date range, etc.
- Index commonly searched fields

**Verification:**
- Store test record, retrieve it

---

### Task 5: CLI Parser
**File:** `lightroom_tagger/cli.py`

CLI with argparse:
- `scan` - Scan catalog, index all images
- `search` - Search indexed images (by keyword, rating, date)
- `export` - Export to JSON/CSV
- `--catalog` - Path to .lrcat file
- `--db` - Path to TinyDB
- `--workers` - Parallel workers (default: 4)
- `--ai-model` - AI model for classification (optional)
- `--skip-ai` - Skip AI classification
- `--verbose` - Enable verbose output

**Verification:**
- `python -m lightroom_tagger.cli --help`

---

### Task 6: Main Entry Point
**File:** `lightroom_tagger/tagger.py`

Main entry point:
- Load config
- Parse CLI args
- Dispatch to appropriate command

**Verification:**
- `python -m lightroom_tagger.taggerscan --help`

---

### Task 7: Exporter
**File:** `lightroom_tagger/exporter.py`

Export functionality:
- Export to JSON (full record)
- Export to CSV (flattened)
- Support filtering by keyword, rating, date

**Verification:**
- Export sample data

---

### Task 8: Test with Real Catalog
**Verify end-to-end:**

1. Mount NAS: `sudo mount -t drvfs '\\\\nas\\ccanales' /mnt/nas`
2. Run scan: `python -m lightroom_tagger scan --catalog "/mnt/nas/ccanales/Lightroom Server/FinalCatalog-v13-3.lrcat"`
3. Verify images indexed in TinyDB
4. Search test: `python -m lightroom_tagger search --keyword "landscape"`
5. Export test: `python -m lightroom_tagger export --format csv --output export.csv`

---

## Notes

- Lightroom stores data in `.lrcat` SQLite database (not XMP by default)
- Key tables: `Adobe_images` (ratings, pick flag), `AgLibraryFile` (file paths), `AgLibraryKeyword` (keywords)
- Use parallel processing with `concurrent.futures` for 20k+ images
- Handle network failures with retry logic
