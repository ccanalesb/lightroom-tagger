---
phase: 15-service-modules-boundary-policy
plan: 15-06
subsystem: api
tags: [python, refactoring, identity, sqlite, ADR-0001]

requires:
  - phase: 15-service-modules-boundary-policy
    provides: matcher package split (15-05) and barrel patterns
provides:
  - lightroom_tagger/core/identity_service/ package (aggregates, style_fingerprint, ranking, suggest_post)
  - Stable `from lightroom_tagger.core.identity_service import …` for API and tests
  - No _legacy shim; submodules stay ≤400 lines each
affects:
  - Consumers of identity_service barrel (api/identity.py, api/images/catalog.py, core tests)

tech-stack:
  added: []
  patterns:
    - "Four focused modules plus explicit __init__ barrel re-export mirroring Phase 14/15 splits."
    - "suggest_post imports _image_meta_map from ranking; get_posting_frequency stays only in suggest_post (posting_analytics edge)."

key-files:
  created:
    - lightroom_tagger/core/identity_service/aggregates.py
    - lightroom_tagger/core/identity_service/style_fingerprint.py
    - lightroom_tagger/core/identity_service/ranking.py
    - lightroom_tagger/core/identity_service/suggest_post.py
  modified:
    - lightroom_tagger/core/identity_service/__init__.py

key-decisions:
  - "Kept `_image_meta_map` in `ranking.py` so `suggest_post` can share catalog/Instagram metadata lookups without pulling ranking into aggregates."
  - "Removed `_legacy.py` after the final move so the package matches the matcher split style (no long-lived shim)."

patterns-established:
  - "Identity barrel lists `__all__` and delegates to aggregates, style_fingerprint, ranking, and suggest_post only."

requirements-completed: [REFACTOR-04]

duration: ~42min
completed: 2026-05-06
---

# Phase 15 Plan 06: identity_service package split Summary

**The flat `identity_service.py` monolith is now a four-module package (`aggregates`, `style_fingerprint`, `ranking`, `suggest_post`) with a single barrel preserving all historical imports.**

## Performance

- **Duration:** ~42 min
- **Started:** 2026-05-06T17:30:00Z (approx.)
- **Completed:** 2026-05-06T18:12:00Z (approx.)
- **Tasks:** 3
- **Files modified:** 5 (package files; flat module removed)

## Accomplishments

- Scaffolded package with `_legacy` + stub submodules, then moved aggregate SQL/helpers and style fingerprint, then ranking + suggestions with `_legacy` deleted.
- `compute_single_image_aggregate_scores` remains available from the package root for `api/images/catalog.py`.
- All `lightroom_tagger/core/` and `apps/visualizer/backend/tests/` pytest suites pass (608 tests).

## Task Commits

Each task was committed atomically:

1. **Task 15-06-T01: Scaffold identity_service package** — `b61e18e` (feat)
2. **Task 15-06-T02: Move aggregates.py and style_fingerprint.py out of _legacy** — `0c77d71` (feat)
3. **Task 15-06-T03: Move ranking.py and suggest_post.py; delete _legacy** — `fbc04c3` (feat)

## Files Created/Modified

- **`lightroom_tagger/core/identity_service/aggregates.py`** — `_SCORES_BASE_SQL`, rationale token helpers, `compute_image_aggregate_scores`, `compute_single_image_aggregate_scores`.
- **`lightroom_tagger/core/identity_service/style_fingerprint.py`** — `_aggregate_histogram`, `build_style_fingerprint`.
- **`lightroom_tagger/core/identity_service/ranking.py`** — stack helpers, `rank_best_photos`, `_image_meta_map`.
- **`lightroom_tagger/core/identity_service/suggest_post.py`** — `_posted_catalog_keys_sql`, `suggest_what_to_post_next` plus `get_posting_frequency`.
- **`lightroom_tagger/core/identity_service/__init__.py`** — explicit barrel; no `_legacy`.

## Decisions Made

- Followed the plan module boundaries; `suggest_post` depends on `ranking` only for `_image_meta_map` to avoid duplicating SQL.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Identity split matches `15-RESEARCH.md` inventory; ready for orchestrator to advance phase bookkeeping.
- **Orchestrator** should update `STATE.md` / `ROADMAP.md` / requirements after the wave (skipped here per executor objective).

## Verification log

| Check | Result |
|-------|--------|
| `test ! -e lightroom_tagger/core/identity_service.py` | PASS |
| `test ! -f lightroom_tagger/core/identity_service/_legacy.py` | PASS |
| `grep ^def compute_image_aggregate_scores aggregates.py` | PASS |
| `grep ^def build_style_fingerprint style_fingerprint.py` | PASS |
| `grep ^def suggest_what_to_post_next suggest_post.py` | PASS |
| `wc -l` aggregates / style_fingerprint / ranking / suggest_post ≤ 400 | PASS |
| `pytest lightroom_tagger/core/test_identity_service.py -x -q` | PASS |
| `pytest lightroom_tagger/core/ apps/visualizer/backend/tests/ -x -q` | PASS (608) |
| `python -c` barrel imports (identity + catalog symbols) | PASS |

## Self-Check: PASSED
