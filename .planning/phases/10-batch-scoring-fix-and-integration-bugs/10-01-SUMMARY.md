---
phase: 10-batch-scoring-fix-and-integration-bugs
plan: "01"
subsystem: jobs
tags: [batch_score, sqlite, pytest, visualizer-backend]

requires:
  - phase: "06"
    provides: "batch_score job handler and scoring pipeline"
provides:
  - "Non-force batch_score selects catalog/Instagram keys with the same SQL as force=True (date/rating filters), then existing logic builds work triplets."
  - "Regression test proving get_undescribed_catalog_images is not invoked from non-force batch_score."
affects:
  - "batch_score operator jobs after bulk describe (unscored-but-described images remain candidates)."

tech-stack:
  added: []
  patterns:
    - "Batch score candidate keys come from the same SELECTs as force rescoring; undescribed helpers stay on the describe path only."

key-files:
  created: []
  modified:
    - "apps/visualizer/backend/jobs/handlers.py"
    - "apps/visualizer/backend/tests/test_handlers_batch_score.py"

key-decisions:
  - "Commits were produced from a HEAD-only slice of handlers.py because the worktree contained unrelated uncommitted handler changes; the working file was restored afterward so local WIP stayed intact."

patterns-established: []

requirements-completed:
  - SCORE-01
  - SCORE-04

duration: 12min
completed: 2026-04-14
---

# Phase 10 Plan 01: Fix `batch_score` non-force image selection — Summary

**Non-force `batch_score` now loads catalog and Instagram candidate keys with the same parameterized SQL as `force=True`, so described-but-unscored images still enter the work queue; tests mock `execute().fetchall()` and assert the undescribed-catalog helper is never used.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-14T18:09:00Z
- **Completed:** 2026-04-14T18:21:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced `get_undescribed_catalog_images` / `get_undescribed_instagram_images` in `handle_batch_score`’s non-force branches with the same `SELECT key FROM images` and `SELECT media_key FROM instagram_dump_media` patterns as the force path.
- Updated unit tests to drive the new SQL path via `mock_db.execute` and added `test_batch_score_non_force_never_calls_get_undescribed_catalog_images`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace non-force catalog/Instagram selection in `handle_batch_score`** — `7cc7c8c` (fix)
2. **Task 2: Update batch score handler tests** — `d618030` (test)

**Plan documentation:** `docs(10-01): add plan 10-01 execution summary` (see `git log --oneline -5`)

## Files Created/Modified

- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_score` non-force catalog/Instagram selection aligned with force SQL; undescribed imports removed from that handler block only.
- `apps/visualizer/backend/tests/test_handlers_batch_score.py` — Mocks for catalog `SELECT`; new regression test with a spy on `get_undescribed_catalog_images`.

## Decisions Made

- **Isolated handler commit:** The repository had large unrelated edits in `handlers.py`. For a plan-only diff, the committed `handle_batch_score` change was applied on top of `HEAD`, committed, then the prior working copy of `handlers.py` was copied back so uncommitted work stayed in the tree. The two commits on `master` contain only the plan’s handler hunk; the restored file may again include additional local changes beyond `HEAD`.

## Deviations from Plan

### Execution note (not a behavior change)

**Isolated commit against `HEAD` for `handlers.py`** — Found during: Task 1 | Issue: `handlers.py` mixed this plan with other uncommitted batch job edits | Fix: Snapshot mixed file, reset `handlers.py` from `HEAD`, re-applied only the plan’s `handle_batch_score` edit for `git commit`, then restored the snapshot | Files: `apps/visualizer/backend/jobs/handlers.py` (working tree after restore) | Verification: `uv run pytest apps/visualizer/backend/tests/test_handlers_batch_score.py -q` passes after restore | Committed in: `7cc7c8c` (handler hunk matches plan; full mixed file was not committed).

---

**Total deviations:** 1 workflow workaround (not a product change)  
**Impact on plan:** Delivered behavior and tests per plan; orchestrator should know `HEAD` handlers may differ from current working tree until other WIP is committed.

## Issues Encountered

None — tests pass after handler fix and test updates.

## User Setup Required

None.

## Next Phase Readiness

- Plan **10-01** complete; ready for the next plan in phase 10 or orchestrator STATE/ROADMAP updates.

## Self-Check: PASSED

- `10-01-SUMMARY.md` present at `.planning/phases/10-batch-scoring-fix-and-integration-bugs/10-01-SUMMARY.md`
- `git log --oneline --grep=10-01` lists the fix, test, and docs commits for this plan

---
*Phase: 10-batch-scoring-fix-and-integration-bugs*  
*Completed: 2026-04-14*
