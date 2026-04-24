---
phase: 04-stack-detection
plan: "04-03"
subsystem: jobs
tags: [sqlite, batch jobs, checkpoint, image_stacks, STACK-01]

requires:
  - phase: 04-01
    provides: `image_stacks` / `image_stack_members` schema and `library_write`
  - phase: 04-02
    provides: `stack_burst_delta_ms` on `Config` and metadata override semantics (D-07)
provides:
  - `fingerprint_batch_stack_detect` in `jobs/checkpoint.py` (delta_ms, force_mode, sorted work-list keys)
  - `batch_stack_detect` in `JOB_TYPES_REQUIRING_CATALOG` and `JOB_HANDLERS`
  - `handle_batch_stack_detect` / `_handle_batch_stack_detect_inner` with burst scan, `image_scores`+active `perspectives` representative SQL, checkpoint resume, and five D-11 result keys
affects:
  - Future stack UI (Phase 6) and any job API clients that enqueue `batch_stack_detect`

tech-stack:
  added: []
  patterns:
    - "Stack fingerprint: canonical JSON with resolved `delta_ms`, normalized `force_mode`, and sorted initial `images.key` work list (mirrors `batch_text_embed` resume semantics)"
    - "Burst detection: sort-and-scan on parseable `date_taken` in Python; one representative query per multi-image burst"

key-files:
  created: []
  modified:
    - apps/visualizer/backend/jobs/checkpoint.py
    - apps/visualizer/backend/library_db.py
    - apps/visualizer/backend/jobs/handlers.py

key-decisions:
  - "`images_skipped_already_stacked` is taken as `COUNT(*)` on `image_stack_members` at job start in incremental mode; after `force` rebuild it is 0"
  - "`stacks_updated` is always 0 (no in-place stack updates in this plan)"
  - "Checkpoint `processed_image_keys` includes only keys with parseable `date_taken` that were assigned to a stack or were singleton bursts; bad/missing `date_taken` keys are counted in `images_skipped_no_date` and are not checkpoint entries"

patterns-established: []

requirements-completed: ["STACK-01"]

duration: 12min
completed: 2026-04-24
---

# Phase 4 Plan 04-03: batch_stack_detect handler, fingerprint, job registration Summary

**`batch_stack_detect` job handler: burst grouping by `date_taken`, three-tier SQL representative (`rating` + `image_scores`/`perspectives` + tie-breaks), `fingerprint_batch_stack_detect` for resume, and `JOB_HANDLERS` + catalog job-type registration with five integer result fields.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-24T15:00:00Z
- **Completed:** 2026-04-24T15:12:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Checkpoint module documents `batch_stack_detect` and exposes `fingerprint_batch_stack_detect(metadata, image_keys, resolved_delta_ms=, force_mode=)`.
- `batch_stack_detect` is registered for catalog resolution alongside other library-backed job types.
- Handler mirrors `batch_text_embed` (cancel scope, `delta_ms` with `0` = unset, `force` → full / preserve_edited / incremental, full rebuild via `DELETE FROM image_stacks`, checkpoint `processed_image_keys` capped at 100k, completion log + exact `complete_job` keys).

## Task Commits

Each task was committed atomically:

1. **Task T1: Add fingerprint_batch_stack_detect and module docstring bullet** - `bfa3ebc` (feat)
2. **Task T2: Register batch_stack_detect as catalog job type** - `ef6a97c` (feat)
3. **Task T3: Implement handle_batch_stack_detect inner logic** - `ed1cc04` (feat)

**Plan metadata:** `docs(04-03): add plan completion summary for batch_stack_detect handler` (follows `ed1cc04` — T3)

## Files Created/Modified

- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_batch_stack_detect`; docstring bullet for `batch_stack_detect` checkpoints
- `apps/visualizer/backend/library_db.py` — `JOB_TYPES_REQUIRING_CATALOG` includes `batch_stack_detect`
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_stack_detect`, burst/representative/checkpoint/result/counters, `JOB_HANDLERS` entry

## Decisions Made

- Incremental work list excludes keys already in `image_stack_members`; burst gaps are only among that list (documented; global rebuild uses `force`).
- Missing `images` rows for keys in the work list are treated like absent `date_taken` (synthetic `NULL`) so they accrue to `images_skipped_no_date` and do not stall checkpoint progress.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Verification (plan-level)

- `cd apps/visualizer/backend && python -c "from jobs.handlers import JOB_HANDLERS; assert JOB_HANDLERS.get('batch_stack_detect')"` — **PASS**
- `rg -n "batch_stack_detect" apps/visualizer/backend/jobs/checkpoint.py apps/visualizer/backend/jobs/handlers.py apps/visualizer/backend/library_db.py` — **PASS** (hits in all three)
- `python -m py_compile` on `jobs/handlers.py` and `jobs/checkpoint.py` — **PASS**

## Self-Check: PASSED

- Plan T1–T3 `acceptance_criteria` `rg` checks run successfully during execution.
- Must-haves: job type string `batch_stack_detect`; representative query uses `image_scores` + `perspectives` subquery; `complete_job` uses the five D-11 keys; fingerprint includes resolved `delta_ms`, `force_mode`, sorted keys; `delta_ms: 0` and omission both fall through to config, override validated `>= 1`.

## Next Phase Readiness

- Stack job is registered and implementable for API/queue tests in a follow-up plan; no STATE/ROADMAP edits in this execution (orchestrator-owned).

---
*Phase: 04-stack-detection*
*Completed: 2026-04-24*
