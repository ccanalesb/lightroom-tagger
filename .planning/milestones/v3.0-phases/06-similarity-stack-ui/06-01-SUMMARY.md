---
phase: 06-similarity-stack-ui
plan: 1
subsystem: database
tags: [sqlite, stacks, catalog, identity, STACK-03]

requires:
  - phase: 04-stack-detection
    provides: image_stacks / image_stack_members schema and representative_key
provides:
  - Collapsed catalog and best-photos primary lists with stack_id, stack_member_count, is_stack_representative
  - catalog_key_is_primary_grid_row for downstream similar-search filtering
affects:
  - visualizer catalog API consumers
  - Best Photos / identity API responses

tech-stack:
  added: []
  patterns:
    - "LEFT JOIN stacks + SQL collapse clause (m_st NULL OR i.key = representative_key)"
    - "rank_best_photos removes non-reps then enriches remaining keys in two batched queries"

key-files:
  created:
    - lightroom_tagger/core/test_database_stack_collapse.py
  modified:
    - lightroom_tagger/core/database.py
    - lightroom_tagger/core/identity_service.py

key-decisions:
  - "Optional stack fields on non-stacked rows: stack_id and stack_member_count null, is_stack_representative false"
  - "rank_best_photos applies stack drop before posted filter and existing sort (per plan)"

patterns-established:
  - "Primary grid / best-photos lists show at most one row per burst stack (representative or solo)"

requirements-completed: [STACK-03]

duration: 15min
completed: 2026-04-25
---

# Phase 6 Plan 1: STACK-03 data layer Summary

**Catalog and Best Photos primary lists now collapse non-representative stack members and expose stack_id, stack_member_count, and is_stack_representative for representative (or solo) rows, with pytest coverage.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2
- **Files modified:** 3 (2 code + 1 test module)

## Accomplishments

- `query_catalog_images` and `query_catalog_images_by_keys` JOIN `image_stack_members` / `image_stacks`, filter with `(m_st.image_key IS NULL OR i.key = st.representative_key)`, and SELECT stack metadata aligned with D-04 naming.
- `catalog_key_is_primary_grid_row` shortcut for “would this key show on the default catalog grid?”.
- `rank_best_photos` drops keys that are non-representative members, then attaches stack fields in batch; `is_stack_representative` is only true when the key equals `image_stacks.representative_key`.

## Task Commits

1. **Task 1: Collapse + stack metadata in query_catalog_images / by_keys** — `a558152` (feat)
2. **Task 2: rank_best_photos — drop non-reps + stack fields** — `2fd73af` (feat)

## Files Created/Modified

- `lightroom_tagger/core/database.py` — stack JOINs, collapse WHERE, extra SELECT columns, `catalog_key_is_primary_grid_row`, `is_stack_representative` bool in `_deserialize_row`.
- `lightroom_tagger/core/identity_service.py` — `_stack_non_representative_keys`, `_stack_fields_for_image_keys`, `rank_best_photos` integration.
- `lightroom_tagger/core/test_database_stack_collapse.py` — three tests (catalog only-rep, count with solo, best-photos excludes high-scoring non-rep).

## Decisions Made

- Followed plan SQL strings exactly for the collapse predicate; stack size surfaced as `stack_member_count` from `image_stacks.stack_size`.
- None beyond plan; optional helper included for later similar-search work.

## Deviations from Plan

None - plan executed as written. (Task 2 was tagged TDD in the plan; implementation and tests were delivered together in one feature commit after Task 1 tests were green—no separate RED-only commit.)

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Data layer ready for CLIP similar API and UI to consume consistent stack badges and grid cardinality.

## TDD Gate Compliance

Plan subtask 2 specified `tdd="true"`; the suite was added alongside the `rank_best_photos` change in a single feature commit after Task 1. No separate `test(` RED-only commit.

## Self-Check: PASSED

- `lightroom_tagger/core/test_database_stack_collapse.py` exists; `.venv/bin/python -m pytest lightroom_tagger/core/test_database_stack_collapse.py` passes (3 tests).
- Commits `a558152`, `2fd73af` on branch.

---
*Phase: 06-similarity-stack-ui*
*Completed: 2026-04-25*
