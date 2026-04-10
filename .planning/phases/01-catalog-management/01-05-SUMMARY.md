---
phase: 1
plan: 05
subsystem: catalog-api
tags: [bugfix, gap-closure, uat, visualizer, sqlite]
key-files:
  - lightroom_tagger/core/database.py
  - apps/visualizer/backend/tests/test_images_catalog_api.py
  - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
  - apps/visualizer/frontend/src/services/api.ts
key-decisions:
  - Run `_migrate_images_schema` before creating indexes on `images` so legacy tables without columns such as `image_hash` do not break `CREATE INDEX` during `executescript`.
  - Treat “empty database” only after a successful catalog fetch (`catalogFetchSucceeded`), never when `loadError` is set or before the first success.
requirements-completed: [CAT-02, CAT-03, CAT-04]
---

# Plan 01-05 — Gap closure: catalog API 500 + Catalog tab filter UX

**One-liner:** Legacy `library.db` files with an older `images` table no longer trip `init_database` (missing columns / premature indexes), so `GET /api/images/catalog` returns 200 with `images` and `total`; the Catalog tab always shows the settings panel and filter row, with separate UI for load failure, true empty DB, and filtered-to-zero.

## Performance

- No hot-path query changes beyond successful `init_database` completing instead of failing; one extra `PRAGMA table_info` pass per column on first open until the schema matches (idempotent, negligible vs I/O).

## Accomplishments

- **Task 1:** Added `_migrate_images_schema` to `ALTER TABLE images` for every column in the current canonical schema when missing; moved the four `images` indexes to run **after** that migration so `CREATE INDEX … (image_hash)` does not run against a legacy table that still lacks `image_hash`. Key-migration backup now logs and continues if `shutil.copy2` raises `OSError`. Regression test builds a minimal legacy `images` table and asserts `GET /api/images/catalog` returns 200.
- **Task 2:** Refactored `CatalogTab` so `CatalogSettingsPanel` and the full filter row are always mounted; introduced `loadError` and `catalogFetchSucceeded` to separate API failure from empty DB vs active filters with zero rows. `request()` in `api.ts` surfaces JSON `{ error: string }` from failed responses when present.

## Task commits

| Task | Hash | Message |
|------|------|---------|
| 1 | `b34c16b` | fix(01-05): legacy images schema migration and index order for catalog API |
| 2 | `8650f21` | fix(01-05): Catalog tab always shows filters; distinct error and empty states |
| 3 | — | Verification only (no code commit) |

The summary document itself is committed as the final step; see `git log -1 --oneline -- .planning/phases/01-catalog-management/01-05-SUMMARY.md` for that hash.

## Files created / modified

| File | Role |
|------|------|
| `lightroom_tagger/core/database.py` | `_migrate_images_schema`, index ordering, resilient key-migration backup |
| `apps/visualizer/backend/tests/test_images_catalog_api.py` | `test_catalog_legacy_db_missing_columns_returns_200` |
| `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` | Always-visible filters; error / empty / filtered states |
| `apps/visualizer/frontend/src/services/api.ts` | Richer `Error` message from JSON `error` on non-OK responses |

## Decisions

- Kept `_migrate_unified_image_keys` collision behavior as a hard `RuntimeError` (no automatic merge); this plan targets the missing-column / index-order 500 path called out in UAT. [Rule 1 - Bug]

## Deviations

- **Full backend suite:** `python3 -m pytest apps/visualizer/backend/tests/` reported **6 failures** (e.g. `test_app_has_required_endpoints`, provider/fallback expectations, batch describe call counts) that appear **environment or fixture/config related**, not regressions from these edits. **Catalog-focused verification** passed:  
  `pytest apps/visualizer/backend/tests/test_images_catalog_api.py apps/visualizer/backend/tests/test_db_utils.py lightroom_tagger/core/test_database.py` → **46 passed**.

## Issues / follow-ups

- **Manual curl (dev server running with valid `LIBRARY_DB`):**  
  `curl -sS "http://localhost:5000/api/images/catalog?limit=50&offset=0"` — expect HTTP 200 and JSON with `images` (array) and `total` (number). Adjust host/port if your Flask config differs.
- **`create_app()` NAS auto-detect** still calls `init_database` on the configured real `library.db`; if key migration throws (e.g. collision), that path logs and continues — unchanged from prior behavior.
