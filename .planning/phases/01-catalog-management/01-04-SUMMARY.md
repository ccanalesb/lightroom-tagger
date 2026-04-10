# Plan 01-04 — Execution summary

**Objective:** Unify `generate_key` with `lightroom.reader.generate_record_key`, migrate existing library SQLite keys and dependent tables, refresh `images.id` on upsert, and ship an idempotent one-time migration with backup.

## Commits (newest last)

| Task | Hash | Message |
|------|------|---------|
| 1 | `e10f9bb` | feat(01-04): unify generate_key with reader date truncation |
| 2 | `584ee3a` | test(01-04): extend test_generate_key for ISO datetime |
| 3 | `11bccdb` | feat(01-04): refresh images.id on store_image upsert |
| 4 | `12c52d4` | feat(01-04): migrate library DB composite keys with backup |
| Summary | — | docs(01-04): add 01-04 execution summary (this file) |

## What changed

- **`generate_key`:** Uses `date_taken[:10]` when `date_taken` is truthy, else `unknown`, matching the reader’s composite key format.
- **`store_image`:** `ON CONFLICT(key) DO UPDATE SET` now includes `id=excluded.id` so rescans update stored Lightroom `id_local`.
- **Migration:** `_migrate_unified_image_keys` runs from `init_database` before the final commit. It is gated by `PRAGMA user_version` (skip if `>= 1`), copies `library.db` to `*.pre-key-migration.bak` once before first migration, updates `matches`, `rejected_matches`, `vision_cache`, `vision_comparisons`, `image_descriptions` (catalog rows only), `instagram_dump_media`, then `images.key`. Collisions raise `RuntimeError` containing `migrate_unified_image_keys: key collision`.
- **Public API:** `migrate_unified_image_keys(conn)` delegates to `_migrate_unified_image_keys(conn)` (caller commits when not using `init_database`).

## Verification

- **Automated:** `uv run pytest lightroom_tagger/core/test_database.py -q` — **38 passed** (repo root).

- **Manual (real `library.db` copy):** After one app start against that file, `sqlite3` should show `PRAGMA user_version;` → `1`, and sample `SELECT key, date_taken FROM images LIMIT 5` should show `YYYY-MM-DD_filename` keys where legacy keys had a time portion. *(Not run in this environment.)*

## Deviations

- None. The public `migrate_unified_image_keys` wrapper performs **no** `commit()` so `init_database`’s single final `commit()` persists `user_version` and key updates; tests call `commit()` after `migrate_unified_image_keys`.
