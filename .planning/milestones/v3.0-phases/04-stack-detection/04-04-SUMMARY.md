---
phase: 04-stack-detection
plan: "04-04"
subsystem: testing
tags: [pytest, batch_stack_detect, checkpoint, flask, STACK-01]

requires:
  - phase: 04-01
    provides: image_stacks schema
  - phase: 04-02
    provides: stack-detection config API and defaults
  - phase: 04-03
    provides: handle_batch_stack_detect, fingerprint_batch_stack_detect
provides:
  - Extended catalog-job and health tests for batch_stack_detect
  - Config API tests for GET/PUT /api/config/stack-detection
  - Fingerprint unit tests (permutation, delta_ms, full vs preserve_edited)
  - test_handlers_batch_stack_detect (zero work, burst, no-date skip, incremental, force rebuild, checkpoint resume)
affects:
  - Future stack UI and job clients (tests lock behavior)

tech-stack:
  added: []
  patterns:
    - "Checkpoint resume test: inject v1 checkpoint + matching fingerprint, assert only remaining burst inserts"

key-files:
  created:
    - apps/visualizer/backend/tests/test_handlers_batch_stack_detect.py
  modified:
    - apps/visualizer/backend/tests/test_library_db.py
    - apps/visualizer/backend/tests/test_jobs_api.py
    - apps/visualizer/backend/tests/test_lt_config_api.py
    - apps/visualizer/backend/tests/test_job_checkpoint.py
    - apps/visualizer/backend/jobs/handlers.py

key-decisions:
  - "Resume test seeds processed_image_keys for first burst without persisting stacks; handler treats them as done and only builds the second burst"

patterns-established: []

requirements-completed: ["STACK-01"]

duration: 35min
completed: 2026-04-24
---

# Phase 4 Plan 04-04: Tests for stack schema, config API, checkpoint, and batch_stack_detect Summary

**Automated tests for `batch_stack_detect`, `fingerprint_batch_stack_detect`, health/config registration, and stack-detection routes; one production fix for `image_stacks` INSERT bind count found while exercising the handler.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-24T16:00:00Z
- **Completed:** 2026-04-24T16:35:00Z
- **Tasks:** 5
- **Files modified/created:** 6

## Accomplishments

- `JOB_TYPES_REQUIRING_CATALOG` and `/api/jobs/health` tests include `batch_stack_detect`.
- `test_lt_config_api` covers GET default, PUT persistence, and 400 for non-positive `stack_burst_delta_ms`.
- `fingerprint_batch_stack_detect` tests cover sorted-key invariance, `delta_ms`, and `full` vs `preserve_edited` distinctness.
- New `test_handlers_batch_stack_detect.py`: zero-work result shape, burst + representative, no-date skip + log, incremental empty work list, force rebuild, and **checkpoint resume** via injected v1 checkpoint so only the second burst inserts rows.
- Fixed `INSERT INTO image_stacks` to use three `?` placeholders for `(representative_key, stack_size, user_modified)` so bindings match SQLite.

## Task Commits

Each task was committed atomically:

1. **Task T1: Extend test_library_db and test_jobs_api** — `d64ca16` (test)
2. **Task T2: test_lt_config_api stack-detection routes** — `a68bd09` (test)
3. **Task T3: test_job_checkpoint fingerprint_batch_stack_detect** — `a834f81` (test)
4. **Task T4: New test_handlers_batch_stack_detect.py** — `9574708` (fix) then `c058909` (test)
5. **Task T5: Checkpoint resume test** — `3024ab7` (test)

## Files Created/Modified

- `apps/visualizer/backend/tests/test_library_db.py` — `batch_stack_detect` in frozenset assertion
- `apps/visualizer/backend/tests/test_jobs_api.py` — health `jobs_requiring_catalog`
- `apps/visualizer/backend/tests/test_lt_config_api.py` — stack-detection GET/PUT/400
- `apps/visualizer/backend/tests/test_job_checkpoint.py` — fingerprint tests
- `apps/visualizer/backend/tests/test_handlers_batch_stack_detect.py` — handler scenarios + resume
- `apps/visualizer/backend/jobs/handlers.py` — `image_stacks` INSERT placeholder fix

## Decisions Made

- Resume coverage uses a synthetic checkpoint (processed keys for burst one) and matching fingerprint so the handler skips the first segment and inserts only the second stack—no reliance on cancel timing.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — bug] `image_stacks` INSERT had two `?` but three bound values**

- **Found during:** Task T4 (burst test); `complete_job` never called; `fail_job` reported SQLite binding mismatch.
- **Issue:** `VALUES (?, ?, 0)` has two placeholders; tuple was `(rep, n, 0)`.
- **Fix:** Use `VALUES (?, ?, ?)` with `(rep, n, 0)`.
- **Files modified:** `apps/visualizer/backend/jobs/handlers.py`
- **Verification:** `pytest tests/test_handlers_batch_stack_detect.py` passes; full 04-04 suite 56 passed.
- **Committed in:** `9574708` (precedes T4 test commit)

---

**Total deviations:** 1 auto-fixed (correctness)

**Impact on plan:** Required for any real stack insert; tests now lock the contract.

## Issues Encountered

None beyond the binding bug above.

## User Setup Required

None - no external service configuration required.

## Verification (plan-level)

```text
cd apps/visualizer/backend && python -m pytest \
  tests/test_handlers_batch_stack_detect.py \
  tests/test_job_checkpoint.py \
  tests/test_lt_config_api.py \
  tests/test_library_db.py \
  tests/test_jobs_api.py -q --tb=short
```

**Result:** 56 passed (2026-04-24).

## Self-Check: PASSED

## Next Phase Readiness

- Stack job behavior and config routes are covered by automated tests; ready for any follow-on UI or API work in later phases.

---
*Phase: 04-stack-detection*
*Completed: 2026-04-24*
