---
phase: 15-service-modules-boundary-policy
plan: 15-07
subsystem: infra
tags: [architecture, ruff, pytest, bash, layering, sqlite]

requires:
  - phase: 15-service-modules-boundary-policy
    provides: identity_service split (15-06) and prior Phase 15 refactors
provides:
  - docs/architecture.md boundary policy (layers, 400-line budget, import rules)
  - scripts/check_core_file_sizes.sh and make check-core-sizes
  - lightroom_tagger/core/test_architecture.py (line budget + apps import + api sibling import guards)
  - Shared apps/visualizer/backend/utils/pagination.py and utils/perspective_slug.py (no sibling api imports)
  - catalog_query split (catalog_query_filters + catalog_query) under 400 lines; db_init wired to library_bootstrap_schema + db_init_migrations
affects:
  - Future CI when .github/workflows exists
  - Contributors running make check-core-sizes before push

tech-stack:
  added: []
  patterns:
    - "Shell wc -l gate mirrored by pytest for regression safety."
    - "API modules use utils/* for cross-cutting helpers instead of importing sibling api.* packages."

key-files:
  created:
    - docs/architecture.md
    - scripts/check_core_file_sizes.sh
    - lightroom_tagger/core/test_architecture.py
    - lightroom_tagger/core/database/catalog_query_filters.py
    - apps/visualizer/backend/utils/pagination.py
    - apps/visualizer/backend/utils/perspective_slug.py
  modified:
    - pyproject.toml
    - Makefile
    - lightroom_tagger/core/database/catalog_query.py
    - lightroom_tagger/core/database/catalog.py
    - lightroom_tagger/core/database/db_init.py
    - lightroom_tagger/core/database/catalog_write.py
    - apps/visualizer/backend/api/images/common.py
    - apps/visualizer/backend/api/identity.py
    - apps/visualizer/backend/api/analytics.py
    - apps/visualizer/backend/api/perspectives.py
    - apps/visualizer/backend/api/scores.py

key-decisions:
  - "Bundled catalog_query split, db_init/schema/migrations wiring, and catalog_write cleanup in the same commit as the size script so every non-test core file stays ≤400 physical lines and imports stay consistent."
  - "Moved `_clamp_pagination` and perspective slug regex into `utils/` so identity/analytics/scores do not import sibling `api.*` modules, satisfying D-06 while keeping helpers single-sourced."

patterns-established:
  - "Enforce handler → service → database layering in docs; machine checks: bash script + pytest mirror."

requirements-completed: [REFACTOR-04, REFACTOR-05]

duration: ~35min
completed: 2026-05-06
---

# Phase 15 Plan 07: Boundary documentation + CI-sized enforcement Summary

**Published `docs/architecture.md` with a mermaid layer diagram and import rules, linked it from `pyproject.toml`, shipped a `wc -l`-based core size script with a matching pytest module, and routed cross-API helpers through `utils/` so sibling `api/*` imports stay forbidden-by-test.**

## Performance

- **Duration:** ~35 min (executor window; T01–T02 completed earlier on branch)
- **Started:** 2026-05-06T19:00:00Z (approx.)
- **Completed:** 2026-05-06T19:20:00Z (approx.)
- **Tasks:** 5 (`15-07-T01` … `15-07-T05`)
- **Files touched:** 16+ (see frontmatter)

## Accomplishments

- Documented layers, 400-line physical budget, and D-05/D-06 import rules in `docs/architecture.md` (T01; committed earlier as `856c667`).
- Added Ruff-adjacent pointer comment in `pyproject.toml` (T02; `736a239`).
- Implemented `scripts/check_core_file_sizes.sh`, split `catalog_query` + finished split `db_init` wiring so all scanned core files respect the budget (T03).
- Added `test_architecture.py` with stdlib AST checks for `apps` imports and sibling `api.*` usage (T04).
- Added `make check-core-sizes` phony target (T05).

## Task Commits

Earlier on branch (this plan):

1. **Task 15-07-T01:** Create `docs/architecture.md` — `856c667` (docs)
2. **Task 15-07-T02:** Link policy in `pyproject.toml` — `736a239` (chore)
3. **Task 15-07-T03:** Size script + catalog/db split to satisfy gate — `a9bf9ff` (feat)
4. **Task 15-07-T04:** `test_architecture.py` + utils + api import decoupling — `505e4eb` (feat)
5. **Task 15-07-T05:** Makefile `check-core-sizes` — `7c86369` (feat)

## Files Created/Modified

- `docs/architecture.md` — Layer diagram (mermaid), file budget, import rules (`must not import sibling api modules`, no `apps` from core).
- `scripts/check_core_file_sizes.sh` — fails with `FAIL <lines> <path>` when any non-`test_*` file under `lightroom_tagger/core/` exceeds 400 lines.
- `lightroom_tagger/core/test_architecture.py` — line budget loop, `apps` top-level import ban in core, api sibling `api.<first>` consistency.
- `apps/visualizer/backend/utils/pagination.py` / `perspective_slug.py` — shared helpers to avoid `identity`/`analytics` importing `api.images` and `scores` importing `api.perspectives`.
- `lightroom_tagger/core/database/catalog_query_filters.py` + slim `catalog_query.py` — keeps query SQL builders under the line cap.
- `Makefile` — `.PHONY: dev dev-down check-core-sizes` and `check-core-sizes` target.

## Decisions Made

- Chose to re-home cross-route helpers under `utils/` rather than weakening the sibling-import test; matches architecture.md guidance to couple through non-`api` shared code or services.

## Deviations from Plan

### Auto-fixed / scope alignment

**1. [Rule 2 - Missing critical] T03 commit included database split wiring, not only the shell script**
- **Found during:** Task 15-07-T03 (`bash scripts/check_core_file_sizes.sh` and import health)
- **Issue:** `catalog_query.py` exceeded 400 lines; `db_init.py` on the working tree referenced `library_bootstrap_schema` / `db_init_migrations` without imports; `catalog_write.py` had a duplicate `__future__` header. Pytest collection for `test_architecture` requires a working `lightroom_tagger.core` import graph.
- **Fix:** Split `catalog_query_filters.py`, repair `db_init.py` imports from `db_init_migrations`, normalize `catalog_write.py`, commit schema/migration modules with T03.
- **Files modified:** `lightroom_tagger/core/database/*` (see commit `a9bf9ff`)
- **Verification:** `bash scripts/check_core_file_sizes.sh` exit 0; `pytest lightroom_tagger/core/test_architecture.py -x -q` exit 0
- **Committed in:** `a9bf9ff`

**2. [Rule 1 - Correctness] Moved shared helpers to `utils/` so D-06 test passes**
- **Found during:** Task 15-07-T04 (writing `test_api_modules_do_not_import_sibling_api_modules`)
- **Issue:** Existing `identity.py` / `analytics.py` imported `api.images.common`; `scores.py` imported `api.perspectives`.
- **Fix:** Added `utils/pagination.py` and `utils/perspective_slug.py`; updated callers and `api/images/common.py` to reuse `utils.pagination`.
- **Verification:** Same pytest module + `pytest lightroom_tagger/core/ apps/visualizer/backend/tests/` (611 passed)
- **Committed in:** `505e4eb`

---

**Total deviations:** 2 (both necessary for AC + import hygiene)
**Impact:** Slightly broader T03/T04 diffs than the literal “script-only” / “test-only” wording; behavior matches plan intent (enforcement + D-06).

## Issues Encountered

None blocking after db/catalog wiring and utils extraction.

## User Setup Required

None.

## Next Phase Readiness

- Automated gates documented in `15-VALIDATION.md` can run locally: `bash scripts/check_core_file_sizes.sh`, `pytest lightroom_tagger/core/test_architecture.py -x -q`, broader `pytest lightroom_tagger/core/ apps/visualizer/backend/tests/`.
- GitHub Actions wiring remains deferred per plan.
- **Orchestrator** updates `STATE.md` / `ROADMAP.md` / requirements (skipped here per executor objective).

## Verification log

| Check | Result |
|-------|--------|
| `test -f docs/architecture.md` | PASS (pre-existing commit) |
| `grep` AC lines in `docs/architecture.md` | PASS |
| `grep` / `awk` pyproject boundary comment before `[tool.ruff]` | PASS (`736a239`) |
| `test -x scripts/check_core_file_sizes.sh` | PASS |
| `bash scripts/check_core_file_sizes.sh` | PASS |
| `pytest lightroom_tagger/core/test_architecture.py -x -q` | PASS |
| `grep` test function defs in `test_architecture.py` | PASS |
| Makefile `check-core-sizes` | PASS |
| `pytest lightroom_tagger/core/ apps/visualizer/backend/tests/` | PASS (611) |

## Self-Check: PASSED

---
*Phase: 15-service-modules-boundary-policy · Plan: 15-07 · Completed: 2026-05-06*
