---
phase: 15-service-modules-boundary-policy
plan: 15-01
subsystem: api
tags: [python, exceptions, refactoring, ADR-0004]

requires:
  - phase: (none — ADR-0004 baseline)
    provides: documented exception layout
provides:
  - Canonical `lightroom_tagger.core.exceptions` import root for provider and DB errors
  - `StackMutationError` in `exceptions/db_errors.py` with stable `database` barrel re-exports
affects:
  - Later phase-15 plans (service module boundaries)

tech-stack:
  added: []
  patterns:
    - "Import provider/DB domain errors only from `lightroom_tagger.core.exceptions`"

key-files:
  created:
    - lightroom_tagger/core/exceptions/__init__.py
    - lightroom_tagger/core/exceptions/provider_errors.py
    - lightroom_tagger/core/exceptions/db_errors.py
  modified:
    - lightroom_tagger/core/database/stacks.py
    - lightroom_tagger/core/database/__init__.py
    - lightroom_tagger/core/analyzer.py
    - lightroom_tagger/core/fallback.py
    - lightroom_tagger/core/matcher.py
    - lightroom_tagger/core/nl_catalog_search.py
    - lightroom_tagger/core/retry.py
    - lightroom_tagger/core/scoring_service.py
    - lightroom_tagger/core/vision_client.py
    - lightroom_tagger/core/test_*.py (provider/fallback/retry/vision_client)
    - apps/visualizer/backend/api/descriptions.py
    - apps/visualizer/backend/api/images/search.py
    - apps/visualizer/backend/jobs/handlers/common.py
    - apps/visualizer/backend/tests/test_descriptions_api.py

key-decisions:
  - "Re-export `StackMutationError` from both `core.exceptions` and `core.database` so existing `from …database import StackMutationError` call sites remain valid."

patterns-established:
  - "ADR-0004: add new domain errors under `core/exceptions/`; barrel `__init__.py` is the only public entry for imports."

requirements-completed: [REFACTOR-04]

duration: 1 min
completed: 2026-05-06
---

# Phase 15 Plan 01: `exceptions/` package Summary

**`lightroom_tagger.core.exceptions` is now the single import root for vision-provider errors and `StackMutationError`; legacy `core/provider_errors.py` is removed.**

## Performance

- **Duration:** ~1 min (commit window 2026-05-06 14:39:05–14:39:34 -0400)
- **Started:** 2026-05-06T18:39:05Z
- **Completed:** 2026-05-06T18:39:34Z
- **Tasks:** 3
- **Files touched:** 19 (3 new, 1 deleted, 15 modified in T03 batch)

## Accomplishments

- Added `core/exceptions/` with `provider_errors` module (parity with former `core/provider_errors.py`).
- Moved `StackMutationError` into `exceptions/db_errors.py`; `database/stacks.py` imports from the package root.
- Bulk-migrated all `lightroom_tagger/` and `apps/visualizer/` imports to `core.exceptions`; deleted `provider_errors.py`.

## Task Commits

Each task was committed atomically:

1. **Task T01: Create exceptions package with provider_errors module** — `aed7915` (feat)
2. **Task T02: Add db_errors.StackMutationError and wire database/stacks** — `4a3e8b7` (feat)
3. **Task T03: Bulk-migrate imports to exceptions and delete provider_errors module** — `f412d07` (refactor)

## Files Created/Modified

- `lightroom_tagger/core/exceptions/__init__.py` — public re-exports and `__all__`.
- `lightroom_tagger/core/exceptions/provider_errors.py` — provider error hierarchy and retry sets.
- `lightroom_tagger/core/exceptions/db_errors.py` — `StackMutationError`.
- `lightroom_tagger/core/database/stacks.py` — imports `StackMutationError` from exceptions package.
- `lightroom_tagger/core/database/__init__.py` — imports `StackMutationError` from exceptions; keeps barrel API.
- Migrated imports in analyzer, matcher, nl_catalog_search, retry, fallback, scoring_service, vision_client, visualizer API/job/test modules; tests now import from `core.exceptions`.

## Decisions Made

- Used package-root `from lightroom_tagger.core.exceptions import StackMutationError` in `stacks.py` per ADR preference over deep `db_errors` imports.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Wave-1 baseline checks satisfied: `pytest lightroom_tagger/core/ -x -q` passed (269 tests).
- Architecture/size scripts for this phase land in plan **15-07** per phase validation doc.

## Self-Check: PASSED

- T01 acceptance: file presence, `ProviderError` / `RETRYABLE_ERRORS` in `exceptions/provider_errors.py`, import smoke — PASS.
- T02: no `StackMutationError` class in `stacks.py`; class in `db_errors.py`; identity `database` vs `exceptions` — PASS; `pytest lightroom_tagger/core/test_database_stacks.py` — PASS.
- T03: `rg` shows zero `core.provider_errors` imports; `provider_errors.py` absent; `vision_client` uses `core.exceptions` — PASS; targeted + full core pytest — PASS.
- Plan-level: `python -c` imports for `StackMutationError`, `ProviderError`, `RETRYABLE_ERRORS`, and `from lightroom_tagger.core.database import StackMutationError` — PASS.

## Orchestrator note

`STATE.md` and `ROADMAP.md` were **not** updated in this run (per executor objective); the parent wave should advance position and roadmap.

---
*Phase: 15-service-modules-boundary-policy*  
*Completed: 2026-05-06*
