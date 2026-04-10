---
status: issues_found
phase: 01
depth: standard
files_reviewed: 6
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
---

# Code Review: Phase 01 (catalog-management)

## Summary

Catalog querying and API wiring are solid: SQL uses bound parameters, legacy `images` columns are migrated safely, and tests cover pagination and legacy DB behavior. Remaining gaps are mainly operational and security hardening—unbounded request limits, full-table reads for Instagram listing, and thumbnail endpoints that trust paths stored in SQLite.

## Findings

### CR-01: Unbounded `limit` / `offset` on catalog list (warning)
- **File:** lightroom_tagger/core/database.py
- **Line:** 606
- **Issue:** `query_catalog_images` passes `limit` and `offset` straight into `LIMIT`/`OFFSET` with no validation. The Flask handler forwards query params without clamping. Very large `limit` values can cause high memory use; negative values can yield errors or surprising SQLite behavior.
- **Suggestion:** Enforce sane bounds in one place (e.g. `limit = max(1, min(limit, 200))`, `offset = max(0, offset)`) in `query_catalog_images` or in `list_catalog_images` before calling it.

### CR-02: Key migration continues if backup fails (warning)
- **File:** lightroom_tagger/core/database.py
- **Line:** 349
- **Issue:** If copying the DB to `.pre-key-migration.bak` fails, the migration still runs and rewrites primary keys and related tables, increasing exposure if something goes wrong mid-migration.
- **Suggestion:** Fail closed (abort migration and surface a clear error) when backup is required but cannot be created, or document that operators must take an external backup first.

### CR-03: Instagram list loads entire dump table into memory (warning)
- **File:** apps/visualizer/backend/api/images.py
- **Line:** 105
- **Issue:** `list_instagram_images` runs `SELECT * FROM instagram_dump_media` with no server-side filter or pagination, then filters and paginates in Python. Large libraries will scale poorly and spike memory.
- **Suggestion:** Push filters and `LIMIT`/`OFFSET` into SQL (mirroring `query_catalog_images`), or at least select only needed columns.

### CR-04: Thumbnail endpoints trust filesystem paths from the database (warning)
- **File:** apps/visualizer/backend/api/images.py
- **Line:** 191
- **Issue:** `get_instagram_thumbnail` and `get_catalog_thumbnail` resolve paths from DB rows and call `send_file` when the path exists. A poisoned or tampered library DB (or bug writing paths) could expose arbitrary readable files to anything that can call the API.
- **Suggestion:** Restrict paths to expected roots (catalog root, Instagram media dir), reject `..` and absolute paths outside allowlists, or resolve to a canonical path under a trusted base.

### CR-05: `store_catalog_image` does not ensure a non-null `key` (warning)
- **File:** lightroom_tagger/core/database.py
- **Line:** 707
- **Issue:** `key = record.get('key')` can be `None`, unlike `store_image` which always derives a key via `generate_key`. That can cause failed inserts or ambiguous rows depending on SQLite constraints and callers.
- **Suggestion:** Require `key` or compute it the same way as `store_image` / callers’ contract; raise `ValueError` early if missing.

### CR-06: Dead / misleading `success_paginated` call (info)
- **File:** apps/visualizer/backend/api/images.py
- **Line:** 143
- **Issue:** `success_paginated(...)` is invoked and its return value ignored; the handler then builds a manual `jsonify(...)` response. This confuses readers and suggests incomplete refactoring.
- **Suggestion:** Remove the call or use its return value as the actual response.

### CR-07: Keyword search treats `%` and `_` as SQL `LIKE` wildcards (info)
- **File:** lightroom_tagger/core/database.py
- **Line:** 624
- **Issue:** User-supplied keywords are wrapped in `%...%` for `LIKE` without escaping, so literal `%` or `_` in a search string change match semantics.
- **Suggestion:** Escape `LIKE` specials (e.g. escape `\` and use `ESCAPE '\'` in SQLite) or document the behavior.

### CR-08: Thumbnail responses always use `image/jpeg` (info)
- **File:** apps/visualizer/backend/api/images.py
- **Line:** 196
- **Issue:** `send_file(..., mimetype='image/jpeg')` is used even when the underlying file may be PNG, HEIC, or other formats (including the “last resort” original file path).
- **Suggestion:** Sniff extension or use `mimetypes.guess_type`, or omit forcing mimetype and let Flask infer when appropriate.

### CR-09: Broad exceptions return raw `str(e)` to clients (info)
- **File:** apps/visualizer/backend/api/images.py
- **Line:** 157
- **Issue:** `except Exception as e: return error_server_error(str(e))` can leak internal paths, SQL fragments, or implementation details to API consumers.
- **Suggestion:** Log the full exception server-side and return a generic message (or a stable error code) in production.

### CR-10: Duplicate `CREATE INDEX` for the same index (info)
- **File:** lightroom_tagger/core/database.py
- **Line:** 163
- **Issue:** `idx_dump_media_processed_attempted` is created in the initial `executescript` and again after migrations (lines 243–246). Harmless with `IF NOT EXISTS` but redundant noise in schema init.
- **Suggestion:** Keep a single `CREATE INDEX` in one location after all migrations that affect indexed columns.
