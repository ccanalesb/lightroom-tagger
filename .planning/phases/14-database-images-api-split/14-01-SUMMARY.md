---
phase: 14-database-images-api-split
plan: 14-01
subsystem: database
tags: [python, sqlite, refactoring, package-barrel, scaffold]

requires:
  - phase: 13-handlers-split-per-job-family
    provides: Established split/scaffold discipline (Phase 13 handlers package).
provides:
  - lightroom_tagger/core/database/ package with _legacy monolith and explicit barrel __init__.py
  - Ten domain stub modules (db_init … vision_cache) ready for 14-02+ migrations
affects:
  - REFACTOR-02 follow-on plans (14-02 onward)
  - Any documentation or tooling that referenced flat core/database.py path on disk

tech-stack:
  added: []
  patterns:
    - D-12 scaffold — package + _legacy + barrel before per-domain code moves
    - Explicit from ._legacy import (...) barrel (no star re-exports)

key-files:
  created:
    - lightroom_tagger/core/database/__init__.py
    - lightroom_tagger/core/database/db_init.py
    - lightroom_tagger/core/database/catalog.py
    - lightroom_tagger/core/database/instagram.py
    - lightroom_tagger/core/database/matches.py
    - lightroom_tagger/core/database/descriptions.py
    - lightroom_tagger/core/database/scores.py
    - lightroom_tagger/core/database/stacks.py
    - lightroom_tagger/core/database/embeddings.py
    - lightroom_tagger/core/database/similarity.py
    - lightroom_tagger/core/database/vision_cache.py
  modified:
    - lightroom_tagger/core/database/_legacy.py (rename from core/database.py + seed path anchor fix)

key-decisions:
  - Barrel lists 128 module-level symbols from _legacy (124 top-level def/class plus four module-level binds) so import surface matches the former flat module, including VISION_CACHE_OVERSIZED_SENTINEL.

patterns-established:
  - "Database package scaffold: _legacy holds all behavior; __init__.py re-exports via explicit parenthesized imports only."

requirements-completed:
  - REFACTOR-02

duration: ~1 min
completed: 2026-05-06
---

# Phase 14 Plan 14-01 Summary

**Established `lightroom_tagger/core/database/` as a Phase-14 scaffold package: monolith moved to `_legacy.py`, ten one-line stub modules added, and `__init__.py` re-exports the full prior import surface with explicit `from ._legacy import (...)` (no star imports) so downstream `from lightroom_tagger.core.database import …` stays unchanged.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-05-06T14:27:49Z
- **Completed:** 2026-05-06T14:28:47Z
- **Tasks:** 2
- **Files modified:** 12 (package rename + new stubs + barrel)

## Accomplishments

- Recorded baseline top-level `def`/`class` count **124** on the pre-split monolith (`T00`).
- Replaced flat `lightroom_tagger/core/database.py` with package `lightroom_tagger/core/database/` — monolith is now `_legacy.py`; no file/module name collision.
- Added scaffold stub modules aligned with `14-CONTEXT.md` D-01 domain map.
- Generated barrel `__init__.py` via AST walk (top-level `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, `Assign`, `AnnAssign`) totaling **128** exported names.
- `pytest lightroom_tagger/core/` passes (269 tests).

## Task Commits

Each task was committed atomically:

1. **Task 14-01-T00: Confirm top-level symbol count on monolith (baseline)** — `4f3bff7` (chore)
2. **Task 14-01-T01: Create database/ package (move + stubs + barrel)** — `deac067` (feat)

**Plan metadata:** Shipped as `docs(14-01): add 14-01 scaffold plan summary` (alongside this SUMMARY).

## Files Created/Modified

- `lightroom_tagger/core/database/_legacy.py` — former `core/database.py`; default perspectives seed path uses `Path(__file__).resolve().parents[3]` so `prompts/perspectives` resolves from repo root after nesting under `database/`.
- `lightroom_tagger/core/database/__init__.py` — explicit re-export barrel (`__all__` included).
- `lightroom_tagger/core/database/*.py` stubs — single docstring each, no imports or logic.

## Decisions Made

- Export every module-level definable name from `_legacy` (including private module constants) to preserve the exact historical import namespace; tests and jobs only required the public subset but this avoids accidental gaps.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Correctness] Default perspectives seed path broke after package nest**

- **Found during:** Task 14-01-T01 (pytest `lightroom_tagger/core/`)
- **Issue:** `_legacy.py` sits one directory deeper than the old `database.py`; `seed_perspectives_from_prompts_dir` still used `parents[2]`, pointing at `lightroom_tagger/` instead of the repo root → empty `perspectives` table → multiple test failures.
- **Fix:** Updated default resolution to `parents[3]` (code + docstring) only in `seed_perspectives_from_prompts_dir`; no business-logic edits elsewhere.
- **Files modified:** `lightroom_tagger/core/database/_legacy.py`
- **Verification:** `pytest lightroom_tagger/core/` PASS; smoke imports PASS.
- **Committed in:** `deac067` (Task T01 commit)

---

**Total deviations:** 1 auto-fixed (blocking correctness regression from file move).

**Impact on plan:** Necessary scaffold adjustment; aligns with plan allowance for path-relative fixes required by the package layout. No API or schema behavior change intended beyond restoring prior path behavior.

## Issues Encountered

None beyond the perspectives path anchor above (handled as deviation).

## User Setup Required

None.

## Verification log (plan-level)

- `grep -Ec '^(def |class )' lightroom_tagger/core/database/_legacy.py` → **124**
- `test -f lightroom_tagger/core/database/_legacy.py` → PASS
- `test ! -f lightroom_tagger/core/database.py` → PASS
- Stub files (`db_init.py` … `vision_cache.py`) → PASS
- `__init__.py` contains explicit `from ._legacy import (` … `)`, no wildcard → PASS
- `python -c "from lightroom_tagger.core.database import …"` (plan smoke names + `get_cache_stats`, `list_perspectives`) → PASS
- `pytest lightroom_tagger/core/` → PASS (269)

## Self-Check: PASSED

## Next Phase Readiness

- Scaffold complete per D-12; ready for plan **14-02** to migrate the first domain family out of `_legacy.py` into real submodule implementations while keeping imports stable through the barrel.

---
*Phase: 14-database-images-api-split*

*Completed: 2026-05-06*
