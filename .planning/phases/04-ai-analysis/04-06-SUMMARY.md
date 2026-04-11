---
phase: 04-ai-analysis
plan: 06
subsystem: api
tags: [vision, raw, sr2, cache, batch-api, sqlite]

requires:
  - phase: 04-ai-analysis
    provides: Vision matching and cache infrastructure from earlier Phase 4 work
provides:
  - ".sr2 in RAW_EXTENSIONS for rawpy conversion before vision"
  - "512KB max cached image size with __oversized__ DB sentinel"
  - "Batch candidate prep skips None cache paths with per-image log line"
  - "Automatic invalidation of stale RAW cache rows (original path or oversized sentinel)"
affects:
  - vision_match
  - batch vision scoring
  - vision_cache table

tech-stack:
  added: []
  patterns:
    - "Oversized vision assets use a DB sentinel instead of re-compressing every run"
    - "RAW extension list drives cache invalidation when converter support changes"

key-files:
  created:
    - lightroom_tagger/core/test_vision_cache.py
  modified:
    - lightroom_tagger/core/analyzer.py
    - lightroom_tagger/core/database.py
    - lightroom_tagger/core/vision_cache.py
    - lightroom_tagger/core/matcher.py
    - lightroom_tagger/core/test_matcher.py

key-decisions:
  - "512KB MAX_CACHED_IMAGE_KB distinguishes failed compression (~20MB originals) from normal ~50–135KB cache JPEGs"
  - "RAW files with compressed_path equal to original or __oversized__ always invalidate so SR2 and similar can re-run after extension support changes"

patterns-established:
  - "Batch vision pipeline never falls back to raw filesystem paths when cache returns None"

requirements-completed:
  - AI-03

duration: 25min
completed: 2026-04-11
---

# Phase 4 Plan 06: Vision pipeline safety nets Summary

**SR2 RAW conversion, 512KB vision cache ceiling with `__oversized__` sentinel, batch pre-filter for unusable candidates, and automatic invalidation of stale RAW cache rows.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-11T16:28:00Z
- **Completed:** 2026-04-11T16:53:00Z
- **Tasks:** 5
- **Files modified:** 6 (plus new test module)

## Accomplishments

- Added Sony `.sr2` to `RAW_EXTENSIONS` so files convert through rawpy like other RAW formats.
- Capped cached vision JPEGs at 512KB; failures persist `__oversized__` in `vision_cache` to avoid repeat work.
- Batch candidate preparation skips `None` cache paths and logs a single info line per Instagram image when any are skipped.
- `is_vision_cache_valid` forces re-processing for RAW originals previously cached as full-size paths or oversized sentinels.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add `.sr2` to RAW_EXTENSIONS** — `8578323` (fix)
2. **Task 2: Max size validation for vision cache** — `ea27fe7` (feat)
3. **Task 3: Pre-flight size filtering in batch prep** — `8849ce0` (feat)
4. **Task 4: Invalidate stale RAW cache entries** — `ca96bbf` (fix)
5. **Task 5: Tests** — `c463962` (test)
6. **Plan docs** — `docs(04-06)` commit on `master` (SUMMARY, STATE, ROADMAP, REQUIREMENTS, PLAN tracked)

## Files Created/Modified

- `lightroom_tagger/core/analyzer.py` — `.sr2` in `RAW_EXTENSIONS`
- `lightroom_tagger/core/database.py` — `VISION_CACHE_OVERSIZED_SENTINEL`, extended `is_vision_cache_valid`
- `lightroom_tagger/core/vision_cache.py` — `MAX_CACHED_IMAGE_KB`, oversized handling, sentinel short-circuit on cache hit
- `lightroom_tagger/core/matcher.py` — `skipped_oversized` in batch candidate loop
- `lightroom_tagger/core/test_vision_cache.py` — cache size and invalidation tests
- `lightroom_tagger/core/test_matcher.py` — batch skip test; `get_vision_model` patch on cache-hit test

## Decisions Made

- Used a string sentinel stored in `compressed_path` rather than NULL so existing queries and types stay simple; validity for sentinel rows is mtime-based without a filesystem file.
- Invalidation for `compressed_path == original_path` is limited to `RAW_EXTENSIONS` so non-RAW “cache equals original” behavior stays unchanged.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Task 1 initially committed unrelated `analyzer.py` WIP; fixed with `git reset`, restored WIP copy, and re-committed a one-line `RAW_EXTENSIONS` change only.
- Full `pytest lightroom_tagger` reports failures in analyzer/fallback/provider tests on this branch due to other uncommitted WIP; `pytest lightroom_tagger/core/test_vision_cache.py lightroom_tagger/core/test_matcher.py` passes (12 tests) on both committed matcher and local batch-chunk WIP matcher.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Remaining Phase 4 plans (04-01 … 04-05) can proceed on top of a safer vision pipeline; SR2 and oversized paths no longer spam batch 413 retries.

## Self-Check: PASSED

- [x] `04-06-SUMMARY.md` exists
- [x] `git log --oneline --grep="04-06"` shows task and docs commits

---
*Phase: 04-ai-analysis · Completed: 2026-04-11*
