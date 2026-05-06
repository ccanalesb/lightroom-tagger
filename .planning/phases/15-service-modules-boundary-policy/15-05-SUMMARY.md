---
phase: 15-service-modules-boundary-policy
plan: 15-05
subsystem: api
tags: [python, refactoring, ADR-0001, matcher, path-utils]

requires:
  - phase: 15-service-modules-boundary-policy
    provides: analyzer population (15-04) and established package-barrel patterns
provides:
  - lightroom_tagger/core/matcher/ package replacing flat matcher.py
  - Domain modules candidates, text_scores, description_batch, vision_batch, score_with_vision, matching
  - path_utils.normalize_match_filesystem_path for UNC/mount join + existence gate
affects:
  - Scripts and tests importing lightroom_tagger.core.matcher (barrel surface preserved)
  - Future NAS/UNC path handling can reuse normalize_match_filesystem_path

tech-stack:
  added: []
  patterns:
    - "Matcher orchestration calls sibling APIs via lazy import lightroom_tagger.core.matcher so unittest patches on the package keep working after the package split."
    - "Vision batch path: compressed catalog entries built in vision_batch; summary logging tail co-located there to keep score_with_vision under the 400-line budget."

key-files:
  created:
    - lightroom_tagger/core/matcher/candidates.py
    - lightroom_tagger/core/matcher/text_scores.py
    - lightroom_tagger/core/matcher/description_batch.py
    - lightroom_tagger/core/matcher/vision_batch.py
    - lightroom_tagger/core/matcher/score_with_vision.py
    - lightroom_tagger/core/matcher/matching.py
  modified:
    - lightroom_tagger/core/matcher/__init__.py
    - lightroom_tagger/core/path_utils.py

key-decisions:
  - "Kept lazy package-level dispatch (import matcher as _matcher inside hot paths) so existing tests that patch lightroom_tagger.core.matcher.* remain valid."
  - "Placed batch candidate path preparation and comparison tail logging in vision_batch.py so score_with_vision.py stays ≤400 lines without adding unplanned top-level modules."

patterns-established:
  - "Matcher barrel re-exports the same historical module-level names (including config/database/vision_cache imports) as the former flat matcher.py."
  - "Catalog batch path normalization for matching lives in path_utils.normalize_match_filesystem_path next to resolve_catalog_path."

requirements-completed: [REFACTOR-04]

duration: ~55min
completed: 2026-05-06
---

# Phase 15 Plan 05: matcher package + path helper Summary

**The 747-line `core/matcher.py` monolith is now a `matcher/` package with six focused modules, `normalize_match_filesystem_path` in `path_utils.py`, and no `_legacy` shim — public imports from `lightroom_tagger.core.matcher` stay stable.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-05-06T00:00:00Z (approx.)
- **Completed:** 2026-05-06
- **Tasks:** 5
- **Files touched:** 8 (package + path_utils)

## Accomplishments

- Scaffold → split candidates/text scores → description + vision batch helpers → `score_with_vision` + path helper → `matching` + delete `_legacy`.
- Batch UNC / `mount_point` / exists prelude centralized in `path_utils.normalize_match_filesystem_path`.
- Full `pytest lightroom_tagger/core/` green (267 tests); matcher-only tests 15/15.

## Task Commits

Each task was committed atomically:

1. **Task 15-05-T01: Scaffold matcher package (_legacy + barrel + stubs)** — `1deadac`
2. **Task 15-05-T02: Populate candidates.py and text_scores.py; rewire barrel** — `09b328e`
3. **Task 15-05-T03: Populate description_batch.py and vision_batch.py** — `d3fd4cf`
4. **Task 15-05-T04: path_utils helper + score_with_vision.py** — `c88a777`
5. **Task 15-05-T05: matching.py + delete _legacy.py** — `60421d0`

## Files Created/Modified

- **`lightroom_tagger/core/matcher/candidates.py`** — `query_by_exif`, `find_candidates_by_date` (with `VIDEO_EXTENSIONS` from analyzer).
- **`lightroom_tagger/core/matcher/text_scores.py`** — `text_similarity`, `score_candidates`.
- **`lightroom_tagger/core/matcher/description_batch.py`** — `_compute_desc_scores_for_candidates`.
- **`lightroom_tagger/core/matcher/vision_batch.py`** — `BATCH_MAX_TOKENS_ESCALATION`, `_call_batch_chunk`, `_build_compressed_batch_entries`, `_log_comparison_tail`.
- **`lightroom_tagger/core/matcher/score_with_vision.py`** — `score_candidates_with_vision` (≤400 lines).
- **`lightroom_tagger/core/matcher/matching.py`** — `match_image`, `match_batch`.
- **`lightroom_tagger/core/matcher/__init__.py`** — Explicit barrel; no `_legacy`.
- **`lightroom_tagger/core/path_utils.py`** — `normalize_match_filesystem_path`.

## Decisions Made

- Preserved test compatibility by resolving patched symbols through `lightroom_tagger.core.matcher` at runtime inside orchestration functions (not only `_legacy` — extended into `matching` and `score_with_vision`).
- Colocated small helpers in `vision_batch.py` to satisfy the per-file line cap for `score_with_vision.py` without introducing another top-level matcher module.

## Deviations from Plan

### Auto-fixed / scope adjustments

**1. [Rule 2 - Test compatibility] Lazy package dispatch after scaffold**

- **Found during:** Task T01 (first `pytest test_matcher` run)
- **Issue:** With `match_image` living in `_legacy`, patches on `lightroom_tagger.core.matcher.query_by_exif` no longer replaced names in `_legacy`’s global namespace.
- **Fix:** Route internal calls through `from lightroom_tagger.core import matcher as _matcher` inside `match_image`, `match_batch`, and `score_candidates_with_vision` (and `compare_descriptions_batch` in description scoring).
- **Files modified:** `_legacy` (then `score_with_vision` / `matching` as code moved)
- **Verification:** `pytest lightroom_tagger/core/test_matcher.py` PASS
- **Committed in:** `1deadac` (scaffold commit; pattern carried through later extractions)

**2. [Rule 3 - Line budget] Helpers in `vision_batch.py` for `score_with_vision` ≤400 lines**

- **Found during:** Task T04 acceptance (`wc -l score_with_vision.py` > 400)
- **Issue:** Plan requires every matcher submodule ≤400 lines; monolithic `score_candidates_with_vision` exceeded the cap in one file.
- **Fix:** Extract `_build_compressed_batch_entries` and `_log_comparison_tail` into `vision_batch.py`; import from `score_with_vision.py`.
- **Files modified:** `vision_batch.py`, `score_with_vision.py`
- **Verification:** `wc -l` on `score_with_vision.py` ≤ 400; `pytest` PASS
- **Committed in:** `c88a777`

---

**Total deviations:** 2 handled (1 blocking test failure, 1 line-budget structural adjustment)  
**Impact on plan:** No behavior change intended; import and logging layout adjusted to keep tests and file-size gates green.

## Issues Encountered

None beyond the items noted under Deviations.

## User Setup Required

None.

## Next Phase Readiness

- Matcher split matches the Phase 15 research inventory; `_legacy.py` removed.
- **Orchestrator** should update `STATE.md` / `ROADMAP.md` / requirements after the wave (skipped here per executor objective).

## Verification log

| Check | Result |
|-------|--------|
| `test ! -f lightroom_tagger/core/matcher.py` | PASS |
| `test ! -f lightroom_tagger/core/matcher/_legacy.py` | PASS |
| `grep _legacy` on `matcher/__init__.py` | PASS (no matches) |
| `wc -l` each `matcher/*.py` ≤ 400 | PASS (max 398 on `score_with_vision.py`) |
| `grep ^def normalize_match_filesystem_path path_utils.py` | PASS |
| `pytest lightroom_tagger/core/test_matcher.py -x -q` | PASS |
| `pytest lightroom_tagger/core/ -x -q` | PASS (267) |
| `python -c "from lightroom_tagger.core.matcher import find_candidates_by_date, match_image, score_candidates_with_vision"` | PASS |
| `python -c "from lightroom_tagger.scripts.match_instagram_dump import main"` | PASS |

## Self-Check: PASSED

## Orchestrator note

`STATE.md` and `ROADMAP.md` were **not** updated in this run (per objective).
