---
plan: "01-01"
title: "Schema, description_search_document, and FTS5 sync in store_image_description"
status: complete
completed: "2026-04-23"
---

## What Was Built

Added nullable `dominant_colors`, `mood_tags`, `has_repetition`, and `description_search_document` on `image_descriptions`, plus a standalone SQLite FTS5 table `image_descriptions_fts` with `tokenize='porter unicode61'`. A one-time migration backfills `description_search_document` for existing catalog rows and seeds the FTS index with explicit `INSERT` rows (rowids aligned with `image_descriptions`). `store_image_description` now builds the search document from normalized `summary` plus flattened `subjects`, persists the new columns, and maintains the FTS index with `DELETE` + `INSERT` for catalog rows with non-empty documents (non-catalog rows leave the column null and remove any FTS row).

**Note:** The first task used an external-content FTS5 definition; that was replaced with a **standalone** FTS5 table in T02. External-content FTS mirrors content on `SELECT`, so an unconditional `DELETE` from the FTS after only writing the main table could corrupt the index (`database disk image is malformed`). Standalone FTS keeps Python-only maintenance (D-04) and stable `DELETE`/`INSERT` semantics; `bm25()` still applies to the FTS table for NLS-02.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| T01 | Columns, FTS DDL/migration path, legacy catalog API test (D-17) | f81cb02 |
| T02 | `build_description_search_document`, `store_image_description`, `_coerce_has_repetition`, `_visual_attr_json`, standalone FTS + migration backfill | 736a957 |
| T03 | `test_database` FTS `MATCH` + non-catalog assertions | a3541c5 |

## Key Files Modified

- `lightroom_tagger/core/database.py` — New columns on `image_descriptions` (including in base `CREATE TABLE`); `build_description_search_document`; `_migrate_image_descriptions_fts` (drop/create standalone `image_descriptions_fts`, backfill text, populate FTS); extended `store_image_description` with JSON/bool fields and FTS maintenance.
- `lightroom_tagger/core/test_database.py` — `has_repetition` string coercion tests; catalog FTS + visual fields test; Instagram-type row has no FTS entry.
- `apps/visualizer/backend/tests/test_images_catalog_api.py` — `test_catalog_legacy_image_descriptions_missing_visual_columns_returns_200` for legacy schema without `dominant_colors`.

## Issues Encountered

- **External-content FTS5:** `DELETE FROM image_descriptions_fts` after upserting only `image_descriptions` failed with `database disk image is malformed` once a row existed in content; `SELECT` on the FTS can appear to “see” external rows, so delete semantics differ from a normal table. Resolved by switching to **standalone** FTS5 (no `content=` / `content_rowid=`). One-shot `INSERT INTO ... VALUES('rebuild')` was replaced with per-row `INSERT INTO image_descriptions_fts(rowid, description_search_document)` after backfill (same practical effect for indexing existing catalog text; D-05).
- **`ruff check lightroom_tagger/core/database.py`** reports pre-existing issues (whitespace, zip strict, etc.); not introduced by this plan.

## Self-Check

- [x] All tasks executed
- [x] Each task committed individually
- [x] Tests pass (or documented if failing)
- [x] SUMMARY.md created
