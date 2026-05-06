---
phase: 15-service-modules-boundary-policy
plan: 15-03
subsystem: api
tags: [python, refactoring, package-barrel, ADR-0001]

requires:
  - phase: 15-02
    provides: model getters on config; analyzer re-import surface
provides:
  - lightroom_tagger/core/analyzer/ package scaffold (_legacy monolith + four ADR stub modules + explicit barrel)
affects:
  - Later analyzer splits (15-04+); tests that patch analyzer internals

tech-stack:
  added: []
  patterns:
    - "Analyzer package scaffold (Phase 14 parity): behavior in `_legacy`; `__init__` barrel with explicit `from ._legacy import (` … `)` + matching `__all__`."
    - "unittest patches on implementation globals use `lightroom_tagger.core.analyzer._legacy` after the barrel split."

key-files:
  created:
    - lightroom_tagger/core/analyzer/__init__.py
    - lightroom_tagger/core/analyzer/image_prep.py
    - lightroom_tagger/core/analyzer/image_inspect.py
    - lightroom_tagger/core/analyzer/vision_compare.py
    - lightroom_tagger/core/analyzer/description.py
  modified:
    - lightroom_tagger/core/analyzer/_legacy.py (rename from flat analyzer.py)
    - lightroom_tagger/core/test_analyzer.py

key-decisions:
  - "Barrel export list excludes `typing.Any`; include `ImportFrom` bindings only from `lightroom_tagger.*` plus all module-level defs and assign/ann-assign targets (30 names), matching historical `dir()` expectations for symbols callers use."
  - "Env-driven `VISION_*` constants reload test now runs `importlib.reload` on `_legacy` then the package so module-level `int(os.environ.get(...))` re-executes."

patterns-established:
  - "ADR-0001 filenames exist under `analyzer/` as docstring-only stubs; logic remains in `_legacy` until follow-on plans."

requirements-completed: [REFACTOR-04]

duration: 2min
completed: 2026-05-06
---

# Phase 15 Plan 03: analyzer/ package scaffold Summary

**Flat `core/analyzer.py` is now package `core/analyzer/` with the monolith in `_legacy.py`, four ADR-0001 stub submodules, and an explicit barrel preserving 30 top-level symbols (including config re-exports and `ContextLengthError`).**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-06T18:43:44Z
- **Completed:** 2026-05-06T18:45:07Z
- **Tasks:** 2
- **Files touched:** 8 (1 rename, 5 new under `analyzer/`, 1 test file)

## Accomplishments

- Baseline export list recorded (T01) via AST + constrained `ImportFrom` extraction; committed in `docs(15-03)… (T01)`.
- Package layout: `analyzer/_legacy.py` + `image_prep.py`, `image_inspect.py`, `vision_compare.py`, `description.py` (docstring stubs) + `__init__.py` barrel / `__all__` in lockstep.
- `_legacy` retains no `__file__` usages; `pytest lightroom_tagger/core/` remains green (269 tests).

## Task Commits

Each task was committed atomically:

1. **Task T01: Baseline top-level definable symbols** — `50bafaa` (docs)
2. **Task T02: analyzer/ package (_legacy + stubs + barrel) + test alignment** — `8f37ece` (feat)

## Files Created/Modified

- `lightroom_tagger/core/analyzer/_legacy.py` — former `analyzer.py` implementation (unchanged logic).
- `lightroom_tagger/core/analyzer/__init__.py` — explicit re-exports + `__all__` (ruff `I001` suppressed file-wide; order matches contract).
- `lightroom_tagger/core/analyzer/image_{prep,inspect}.py`, `vision_compare.py`, `description.py` — ADR-0001-aligned stubs.
- `lightroom_tagger/core/test_analyzer.py` — patch paths and env reload sequence updated for package + `_legacy`.

## Decisions Made

- Kept `typing.Any` off the barrel list (not part of intentional analyzer API; avoids `from analyzer import Any`).
- Barrel name order follows `sorted()` over the export set (underscore-prefixed names after uppercase constant names; see `__init__.py`).

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — correctness] `unittest.mock.patch` targets after barrel split**

- **Found during:** T02 acceptance (`pytest lightroom_tagger/core/test_analyzer.py`).
- **Issue:** Patching `lightroom_tagger.core.analyzer.foo` does not affect globals used inside `_legacy.analyze_image` / `compare_with_vision` (implementations resolve names in `_legacy`’s dict).
- **Fix:** Patches use `lightroom_tagger.core.analyzer._legacy.<symbol>`; env-var test reloads `_legacy` then the package.
- **Files modified:** `lightroom_tagger/core/test_analyzer.py`.
- **Verification:** `pytest lightroom_tagger/core/test_analyzer.py`, `pytest lightroom_tagger/core/` — PASS.
- **Committed in:** `8f37ece`.

---

**Total deviations:** 1 auto-fixed (test / patch resolution).
**Impact on plan:** No production API change beyond the scaffold; tests match where implementations bind names after the Phase-14-style package layout.

## Issues Encountered

None aside from the patch-path adjustment above.

## User Setup Required

None.

## Next Phase Readiness

- Import path `from lightroom_tagger.core.analyzer import …` unchanged for callers.
- All four ADR-0001 filenames exist under `analyzer/` as stubs.

## Verification log (plan-level)

| Check | Result |
|-------|--------|
| `test -d …/analyzer && test -f …/analyzer/__init__.py && test -f …/analyzer/_legacy.py` | PASS |
| `test ! -e …/analyzer.py` | PASS |
| `python -c "from lightroom_tagger.core.analyzer import compress_image, compute_phash, compare_with_vision, describe_image, get_vision_model"` | PASS |
| `pytest lightroom_tagger/core/test_analyzer.py -x -q` | PASS |
| `pytest lightroom_tagger/core/ -x -q` | PASS (269 passed) |
| `python -c "import lightroom_tagger.core.analyzer as a; assert hasattr(a, 'compress_image')"` | PASS |
| `rg '__file__' lightroom_tagger/core/analyzer/_legacy.py` | PASS (empty) |
| `python -c "from lightroom_tagger.core.vision_client import compare_images_batch"` | PASS |

### Manual smoke (plan checklist)

- [x] `compare_images_batch` import from `vision_client` — exercised via CLI smoke above.

## Self-Check: PASSED

## Orchestrator note

`STATE.md` and `ROADMAP.md` were **not** updated in this run (executor objective).

---
*Phase: 15-service-modules-boundary-policy*  
*Completed: 2026-05-06*
