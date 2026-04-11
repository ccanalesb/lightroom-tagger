---
phase: 04-ai-analysis
plan: 04
subsystem: jobs
tags: [batch_describe, sqlite, catalog, react, pytest]

requires:
  - phase: 04-ai-analysis
    provides: image_descriptions, batch_describe job, catalog query patterns from 04-01/04-06
provides:
  - "12-month date_filter for batch_describe (months=12)"
  - "Optional min_rating on catalog selection (unanalyzed + force SQL paths)"
  - "DescriptionsTab UI sends min_rating in job metadata"
  - "Handler tests for 12months and min_rating; stable mocks for add_job_log and runner.is_cancelled"
affects:
  - batch description jobs
  - processing UI

tech-stack:
  added: []
  patterns:
    - "Catalog-only min_rating; Instagram branch ignores it (including both)"

key-files:
  created: []
  modified:
    - lightroom_tagger/core/database.py
    - apps/visualizer/backend/jobs/handlers.py
    - apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx
    - apps/visualizer/backend/tests/test_handlers_batch_describe.py

key-decisions:
  - "Invalid min_rating metadata coerces to None via try/except so the job does not fail on bad input"
  - "Batch handler tests patch jobs.handlers.add_job_log because handlers binds add_job_log at import time"

patterns-established:
  - "Force-catalog SQL builds WHERE clauses for date window and rating with shared parameter list"

requirements-completed:
  - AI-03

duration: 2min
completed: 2026-04-11
---

# Phase 4 Plan 04: Batch describe 12-month window, min_rating, and SQL alignment Summary

**Batch describe honors `12months`, filters catalog candidates by optional `min_rating` in SQL and job metadata, and the Processing UI exposes a catalog minimum-rating control with tests covering the handler contract.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-11T16:38:25Z
- **Completed:** 2026-04-11T16:40:13Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Extended `get_undescribed_catalog_images` with optional `min_rating` and `AND i.rating >= ?` when set.
- Wired `handle_batch_describe` to map `12months`, parse `min_rating`, and apply rating filter for catalog force and unanalyzed paths only.
- Added **Minimum rating (catalog)** select on `DescriptionsTab` with helper text for catalog vs Instagram-only behavior.
- Strengthened `test_handlers_batch_describe` with 12-month and min_rating assertions and reliable mocks.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend undescribed catalog query for min_rating** — `a0e6f83` (feat)
2. **Task 2: Batch handler months map and min_rating filtering** — `6cd74bc` (feat)
3. **Task 3: DescriptionsTab UI and job metadata** — `29c1948` (feat)
4. **Task 4: Handler tests for 12months and min_rating** — `ecd3f89` (test)

**Plan metadata:** `docs(04-04): complete batch describe scope plan` (same commit as this SUMMARY on `master`)

## Files Created/Modified

- `lightroom_tagger/core/database.py` — `get_undescribed_catalog_images(months, min_rating)` filter clause.
- `apps/visualizer/backend/jobs/handlers.py` — `12months` map, metadata parsing, catalog SQL for force path, `get_undescribed_catalog_images(..., min_rating=...)`.
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` — `batchMinRating` state, select, metadata.
- `apps/visualizer/backend/tests/test_handlers_batch_describe.py` — new tests; `jobs.handlers.add_job_log` patch; `_make_runner()`; related fixes.

## Decisions Made

- Coerce invalid `min_rating` job metadata to `None` with `try/except` so a bad client value does not abort the whole job.
- Patch `jobs.handlers.add_job_log` in batch-describe tests so failure-path logging does not invoke real SQLite against `MagicMock` DB.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Batch describe tests failed under pytest**

- **Found during:** Task 4 (handler tests)
- **Issue:** Tests patched `database.add_job_log`, but `jobs.handlers` holds its own `add_job_log` reference from import; warning logs on failed describes called the real function and raised against a mock DB. Separately, `runner.is_cancelled` defaulted to a truthy `MagicMock`, so the sequential loop exited before describing. A few expectations were out of date (`fail_job` severity, parallel vs sequential stop count, legacy `vision_model` metadata).
- **Fix:** Patch `jobs.handlers.add_job_log`; add `_make_runner()` with `is_cancelled.return_value = False`; use `max_workers: 1` for consecutive-failure test; align `fail_job` and vision-model assertions with current handler behavior.
- **Files modified:** `apps/visualizer/backend/tests/test_handlers_batch_describe.py`
- **Verification:** `pytest apps/visualizer/backend/tests/test_handlers_batch_describe.py -q` passes.
- **Committed in:** `ecd3f89` (Task 4)

---

**Total deviations:** 1 auto-fixed (1 blocking test harness)

**Impact on plan:** No product scope change; tests now match how the handler imports and cancels.

## Issues Encountered

None beyond the test harness issues above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for plan **04-02** (catalog grid AI badges / analyzed filter UI) or the next outstanding AI-analysis plan per roadmap order.

## Self-Check: PASSED

- `04-04-SUMMARY.md` present; `pytest apps/visualizer/backend/tests/test_handlers_batch_describe.py -q` exits 0.

---
*Phase: 04-ai-analysis*  
*Completed: 2026-04-11*
