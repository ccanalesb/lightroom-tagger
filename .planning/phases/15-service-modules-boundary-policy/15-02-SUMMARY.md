---
phase: 15-service-modules-boundary-policy
plan: 15-02
subsystem: api
tags: [python, refactoring, config, ADR-0001]

requires:
  - phase: 15-01
    provides: exceptions package layout
provides:
  - `get_vision_model` / `get_description_model` on `lightroom_tagger.core.config` with same env/YAML precedence as before
  - Call sites (matcher, scoring, description script) import model getters from config; analyzer re-exports for compatibility
affects:
  - Later phase-15 service-boundary plans

tech-stack:
  added: []
  patterns:
    - "Vision/description model resolution lives on `config`; avoid duplicating getters in `analyzer`."

key-files:
  created: []
  modified:
    - lightroom_tagger/core/config.py
    - lightroom_tagger/core/analyzer.py
    - lightroom_tagger/core/scoring_service.py
    - lightroom_tagger/core/description_service.py
    - lightroom_tagger/core/matcher.py
    - lightroom_tagger/scripts/match_instagram_dump.py
    - lightroom_tagger/core/test_matcher.py

key-decisions:
  - "Matcher tests patch `lightroom_tagger.core.matcher.get_vision_model` (not `config.get_vision_model`) because matcher binds the getter at import time; patching the config attribute does not replace the imported reference."

patterns-established:
  - "Prefer importing `get_vision_model` from `core.config` in new code; `from analyzer import get_vision_model` remains valid via re-export."

requirements-completed: [REFACTOR-04]

duration: 8min
completed: 2026-05-06
---

# Phase 15 Plan 02: Model config helpers Summary

**`get_vision_model` and `get_description_model` now live on `core.config`; matcher, scoring, description services, and the Instagram dump script read models from config while analyzer re-exports the same objects.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-06T18:34:11Z (approx.)
- **Completed:** 2026-05-06T18:42:11Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Centralized env/config precedence for vision and description models in `config.py`.
- Removed duplicate definitions from `analyzer.py`; kept stable `from analyzer import get_vision_model` via imports.
- Updated production imports and matcher unit tests so mocks target the matcher-bound symbol.

## Task Commits

Each task was committed atomically:

1. **Task T01: Implement getters in config.py** — `fad4ba2` (feat)
2. **Task T02: Point services, matcher, and scripts at config getters** — `c22a68b` (feat)

## Files Created/Modified

- `lightroom_tagger/core/config.py` — `get_vision_model`, `get_description_model`.
- `lightroom_tagger/core/analyzer.py` — delegates to config imports; removes `VISION_MODEL` constant and local defs.
- `lightroom_tagger/core/scoring_service.py` — `get_description_model` from config.
- `lightroom_tagger/core/description_service.py` — splits analyzer vs config imports.
- `lightroom_tagger/core/matcher.py` — module-level `get_vision_model` from config.
- `lightroom_tagger/scripts/match_instagram_dump.py` — `get_vision_model` from config.
- `lightroom_tagger/core/test_matcher.py` — patches `matcher.get_vision_model`.

## Decisions Made

- Chose matcher-scoped patch paths in tests so `unittest.mock.patch` observes the callable actually invoked (import-bound getter on `matcher`).

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — correctness] Patch target for matcher tests**

- **Found during:** Task T02 (acceptance pytest)
- **Issue:** Plan text said to patch `lightroom_tagger.core.config.get_vision_model`; matcher uses `from …config import get_vision_model`, so patching the config attribute does not replace matcher's bound reference — cache test called real `get_vision_model`.
- **Fix:** Patches use `lightroom_tagger.core.matcher.get_vision_model` instead.
- **Files modified:** `lightroom_tagger/core/test_matcher.py`
- **Verification:** `pytest lightroom_tagger/core/test_matcher.py …` — PASS
- **Committed in:** `c22a68b`

---

**Total deviations:** 1 auto-fixed (correctness / test mock target)  
**Impact on plan:** Behavior and production imports match the plan; only the test patch string differs from the plan’s literal (still satisfies “no `core.analyzer.get_vision_model` in tests”).

## Issues Encountered

None beyond the patch-target adjustment above.

## User Setup Required

None.

## Next Phase Readiness

- `pytest lightroom_tagger/core/ -x -q` — 269 passed.
- `python -c` identity check: analyzer re-export `is` config getter — PASS.
- `python -c "from lightroom_tagger.scripts.match_instagram_dump import main"` — PASS.

## Self-Check: PASSED

- T01 acceptance greps + import identity — PASS.
- T02 acceptance greps + pytest subset — PASS; full core pytest — PASS.
- Plan automated checks — PASS.

## Orchestrator note

`STATE.md` and `ROADMAP.md` were **not** updated in this run (per executor objective).

---
*Phase: 15-service-modules-boundary-policy*  
*Completed: 2026-05-06*
