---
phase: 14-database-images-api-split
plan: "04"
subsystem: testing
tags: [pytest, sqlite, unittest, database-barrel]

requires:
  - phase: "14-database-images-api-split"
    provides: Wave 14-03 database package refactor context
provides:
  - Focused core test modules mirroring lightroom_tagger/core/database/* domains
  - Scratch mapping artifact for TestCase routing (14-04-T01)
  - Consolidated stack-collapse tests under test_database_stacks.py
affects:
  - "14-database-images-api-split"
  - core-test-maintenance

tech-stack:
  added: []
  patterns:
    - "Tests import only from lightroom_tagger.core.database barrel (D-02)"
    - "Monolithic TestDatabase split into DbInit / Embeddings / CatalogCrud before physical file split"

key-files:
  created:
    - lightroom_tagger/core/test_database_db_init.py
    - lightroom_tagger/core/test_database_catalog.py
    - lightroom_tagger/core/test_database_instagram.py
    - lightroom_tagger/core/test_database_matches.py
    - lightroom_tagger/core/test_database_descriptions.py
    - lightroom_tagger/core/test_database_embeddings.py
    - lightroom_tagger/core/test_database_similarity.py
    - lightroom_tagger/core/test_database_vision_cache.py
    - lightroom_tagger/core/test_database_stacks.py
    - .planning/phases/14-database-images-api-split/scratch/14-04-T01-test-case-map.txt
  modified: []

key-decisions:
  - "Physical split only: no assertion or test-body edits beyond class split (T01) and hoisting inline barrel imports on Instagram dump tests"
  - "test_database_similarity.py added as an empty placeholder module documenting future similarity job-table coverage (no tests yet in the migrated monolith)"
  - "Executor did not mutate .planning/STATE.md or ROADMAP.md (orchestrator-owned)"

patterns-established:
  - "Per-domain test_database_<area>.py next to legacy test_database_scores.py / test_database_nl_filter_arrays.py"

requirements-completed: [REFACTOR-02]

duration: ~18 min
completed: 2026-05-06
---

# Phase 14 Plan 04: Split monolithic core database tests

**Core DB tests reorganized into `test_database_<domain>.py` modules aligned with `lightroom_tagger/core/database/*`; `test_database_stack_collapse.py` merged into `test_database_stacks.py` with unchanged bodies and barrel-only imports.**

## Performance

- **Duration:** ~18 min
- **Started:** (approximate execution window same calendar day as completed)
- **Completed:** 2026-05-06
- **Tasks:** 2 (T01 inventory + T02 moves)
- **Files touched:** 11 (2 commits: map/split-class + file split/absorb)

## Accomplishments

- Replaced single `test_database.py` with nine focused modules plus placeholder `test_database_similarity.py`
- Moved stack collapse integration tests verbatim into `test_database_stacks.py` and deleted the old filename
- Preserved barrel import rule: production surface `from lightroom_tagger.core.database import …` in all migrated tests

## Task Commits

Each task committed atomically:

1. **Task T01:** Inventory mapping + split `TestDatabase` into `TestDatabaseDbInit`, `TestDatabaseEmbeddings`, `TestDatabaseCatalogCrud` — `3e9c5b4` (test)
2. **Task T02:** Create per-domain files, delete monolith, absorb stack collapse — `00c795d` (test)

**Plan metadata:** `git log --oneline --grep docs(14-04)` — summary commit on branch head at completion time

## Files Created/Modified

- `scratch/14-04-T01-test-case-map.txt` — one row per `unittest.TestCase` mapping to target module
- `test_database_db_init.py` — init, sqlite-vec schema smoke, `migrate_unified_image_keys`
- `test_database_catalog.py` — CRUD + `query_catalog_images` filters
- `test_database_instagram.py` — Instagram status + dump media (inline imports hoisted to module top)
- `test_database_matches.py` — `test_store_match_with_rank` (pytest)
- `test_database_descriptions.py` — descriptions + FTS builder
- `test_database_embeddings.py` — CLIP vec0 round-trip
- `test_database_similarity.py` — placeholder docstring only
- `test_database_vision_cache.py` — vision comparison cache
- `test_database_stacks.py` — former `test_database_stack_collapse.py` content unchanged
- Removed: `test_database.py`, `test_database_stack_collapse.py`

## Decisions Made

- Split the old `TestDatabase` class in T01 so each `TestCase` subclass maps to a single domain file without duplicating methods
- Left `test_database_nl_filter_arrays.py` and `test_database_scores.py` untouched (per D-06)

## Deviations from Plan

None — plan executed as written. (Minor: `test_database_similarity.py` has no collected tests yet; mirrors empty production coverage in the migrated monolith.)

## Issues Encountered

None

## User Setup Required

None

## Next Phase Readiness

- `pytest lightroom_tagger/core/` green (269 passed at completion)
- Ready for orchestrator to advance STATE/ROADMAP if applicable

## Self-Check: PASSED

- `test ! -f lightroom_tagger/core/test_database_stack_collapse.py` — OK
- `test ! -f lightroom_tagger/core/test_database.py` — OK
- Required new module paths — all `test -f` OK
- `grep -l "test_database_stack_collapse" lightroom_tagger/core/*.py` — no matches
- `pytest lightroom_tagger/core/` — 269 passed

---
*Phase: 14-database-images-api-split*
