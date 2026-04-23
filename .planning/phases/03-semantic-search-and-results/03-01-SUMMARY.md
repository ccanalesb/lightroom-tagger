---
phase: 3
plan: "03-01"
requirements: [NLS-03]
key-files.created: []
key-files.modified:
  - pyproject.toml
  - uv.lock
  - lightroom_tagger/core/database.py
  - lightroom_tagger/core/test_database.py
key-decisions:
  - "Pinned sqlite-vec 0.1.9 and sentence-transformers>=3.0.0 in root dependencies (not optional)."
  - "Extension load via _ensure_sqlite_vec_loaded immediately after row_factory; failures propagate."
  - "vec0 table image_text_embeddings: float[768] cosine + image_key TEXT; migration gated PRAGMA user_version 3→4, mirrors FTS migration error handling."
---

# Phase 3 Plan 01: sqlite-vec Extension + vec0 Migration Summary

**One-liner:** Library DB initialization now loads **sqlite-vec** on every `init_database` connection and migrates **`PRAGMA user_version` to 4** with an idempotent **`image_text_embeddings`** `vec0` virtual table (768-dim cosine + `image_key`), plus pinned runtime deps and a pytest smoke test.

## Task completion

| Task | Title | Commit |
|------|--------|--------|
| 03-01-T1 | Add Python dependencies | `3221ff1` |
| 03-01-T2 | Load sqlite-vec on init_database connections | `fe665ff` |
| 03-01-T3 | Migrate user_version 3→4: CREATE vec0 table | `214c25e` |
| 03-01-T4 | Smoke: vec_version and vec0 table exist | `cfe16c2` |

## Deviations

- **None.** `uv.lock` was regenerated with `uv lock` when adding dependencies (expected for reproducible installs; not listed in plan frontmatter `files_modified`).

## Self-Check

- [x] `grep -n 'sqlite-vec==0.1.9' pyproject.toml` exits 0
- [x] `grep -n 'sentence-transformers' pyproject.toml` exits 0
- [x] `image_text_embeddings` vec0 table created via migration in `database.py`
- [x] Extension loaded on every `init_database` connection (`_ensure_sqlite_vec_loaded`)
- [x] `PRAGMA user_version` bumped 3 → 4 after successful migration
- [x] Per-task acceptance criteria (grep / pytest `-k vec`) passed
- [x] `python -c "import sqlite_vec; print('sqlite_vec ok')"` succeeds under `uv run`

## Self-Check: PASSED
