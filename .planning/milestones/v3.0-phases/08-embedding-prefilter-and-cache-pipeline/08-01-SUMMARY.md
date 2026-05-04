---
phase: 08-embedding-prefilter-and-cache-pipeline
plan: 1
subsystem: matching
tags:
  - clip
  - sqlite-vec
  - vision_match
  - MATCH-02

requires:
  - phase: 07-stacks-in-matching-pin-similarity
    provides: representative-only catalog candidates before matcher scoring
provides:
  - shortlist_catalog_candidates_by_clip KNN intersect helper in clip_similarity
  - match_dump_media clip_top_k wiring before score_candidates_with_vision (D-03)
  - Regression test asserting scorer argument cardinality ≤ clip_top_k
affects:
  - 08-02-plan vision_match plumbing
  - MATCH-02 verification

tech-stack:
  added: []
  patterns:
    - "Over-fetch KNN + intersect with allowed keys (same spirit as list_pin_similarity_candidate_keys)"

key-files:
  created: []
  modified:
    - lightroom_tagger/core/clip_similarity.py
    - lightroom_tagger/core/test_clip_similarity.py
    - lightroom_tagger/scripts/match_instagram_dump.py
    - apps/visualizer/backend/tests/test_handlers_single_match.py
    - apps/visualizer/backend/tests/test_stack_matching_integration.py
    - lightroom_tagger/core/test_description_service.py

key-decisions:
  - "Honored D-03: shortlist replaces candidates before vision_candidates build so phash/description/vision see only shortlisted rows."
  - "Empty Instagram CLIP embedding → shortlist returns [] → existing skip path (no MATCH-03 fallback)."

patterns-established:
  - "Tests without IG embeddings patch shortlist_catalog_candidates_by_clip passthrough (keys[:top_k]) to preserve legacy scenarios."

requirements-completed:
  - MATCH-02

duration: 25min
completed: 2026-04-27
---

# Phase 8 Plan 1: CLIP shortlist core Summary

**CLIP cosine shortlist intersects Phase-7 representative date-window keys before any phash/description/vision scoring; `match_dump_media` exposes `clip_top_k` (default 50) with `clip_shortlist_applied` observability.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-27 (executor session)
- **Completed:** 2026-04-27
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `shortlist_catalog_candidates_by_clip` with `KNN_K_MAX`-aligned top-k clamp and pin-flow over-fetch constants; missing seed embedding returns `[]`.
- Inserted shortlist after representative-only filter in `match_dump_media`; rebuilt `candidates` in shortlist order before `vision_candidates` / `score_candidates_with_vision`.
- Added `test_shortlist_gates_score_candidates_with_vision` plus passthrough mocks where integration tests lack Instagram CLIP rows.

## Task Commits

1. **Task 1: Add CLIP shortlist helper** — `396a20a` (feat)
2. **Task 2: Wire shortlist into match_dump_media (D-03)** — `fbc0250` (feat)
3. **Task 3: D-03 gating regression test** — `ba72f02` (test)

## Files Created/Modified

- `lightroom_tagger/core/clip_similarity.py` — shortlist helper
- `lightroom_tagger/core/test_clip_similarity.py` — shortlist unit tests (mocked `knn_clip_catalog_keys`)
- `lightroom_tagger/scripts/match_instagram_dump.py` — `clip_top_k`, stats, debug log, candidate reorder
- `apps/visualizer/backend/tests/test_handlers_single_match.py` — passthrough mocks + D-03 regression
- `apps/visualizer/backend/tests/test_stack_matching_integration.py` — shortlist passthrough for real handler path
- `lightroom_tagger/core/test_description_service.py` — shortlist passthrough for mocked `match_dump_media` flows

## Decisions Made

- Followed locked Phase 8 CONTEXT (no MATCH-03, no FAISS/migrations/LLM endpoints).
- Used `stats['clip_shortlist_applied']` once per media row after running the shortlist step.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Existing tests without Instagram CLIP embeddings received empty shortlists once shortlisting went live; fixed by patching `shortlist_catalog_candidates_by_clip` with `keys[:top_k]` passthrough at those callsites (documented pattern).

## User Setup Required

None.

## Next Phase Readiness

- Ready for **08-02** (`vision_match` plumbing: clamp `clip_top_k`, handler/Fingerprint wiring, D-07 throttled logs).

## Verification

- `python -m pytest lightroom_tagger/core/test_clip_similarity.py apps/visualizer/backend/tests/test_handlers_single_match.py -q --tb=short` — PASS (16 tests).

---

## Self-Check: PASSED

- SUMMARY.md written at `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-01-SUMMARY.md`.
- Task verify commands from PLAN ran successfully for tasks 1–3.
- Acceptance greps satisfied (`shortlist_catalog_candidates_by_clip`, `clip_top_k` default 50, shortlist lines before `score_candidates_with_vision`, regression test name/collector `-k shortlist`).

---
*Phase: 08-embedding-prefilter-and-cache-pipeline · Completed: 2026-04-27*
