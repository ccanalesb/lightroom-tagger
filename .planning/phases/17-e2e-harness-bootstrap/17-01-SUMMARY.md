---
phase: 17-e2e-harness-bootstrap
plan: 17-01
subsystem: testing
tags: [pytest, e2e, visualizer-backend]

requires: []
provides:
  - Dedicated `tests/e2e/pytest.ini` with `e2e` marker and local `testpaths`
  - `tests/e2e/harness/` package marker and `fixtures/README.md` for future committed artifacts
  - Parent `tests/conftest.py` `collect_ignore` so `pytest tests/` never collects E2E paths before they exist
affects:
  - 17-02
  - Phase 18 E2E flows

tech-stack:
  added: []
  patterns:
    - "Two pytest entry points: default tree ignores `e2e/`; E2E runs with `pytest -c tests/e2e/pytest.ini tests/e2e/`"

key-files:
  created:
    - apps/visualizer/backend/tests/e2e/pytest.ini
    - apps/visualizer/backend/tests/e2e/harness/__init__.py
    - apps/visualizer/backend/tests/e2e/fixtures/README.md
  modified:
    - apps/visualizer/backend/tests/conftest.py

key-decisions:
  - "Use `collect_ignore = [\"e2e\"]` in parent conftest so accidental `test_*.py` under `tests/e2e/` never enters default CI collection."
  - "Keep E2E `pytest.ini` at `tests/e2e/` with `testpaths = .` so `-c` invocation scopes discovery to that subtree."

patterns-established:
  - "Document fixture regeneration via `export_fixture.py --library` and `--catalog-from` in fixtures README; runtime uses `shutil.copy` for `library_seed.db` into temp dirs."

requirements-completed: []

duration: 10 min
completed: 2026-05-12
---

# Phase 17 Plan 01: E2E pytest isolation and directory scaffold — Summary

**Visualizer backend gained a dedicated E2E pytest config, harness/fixture placeholders, and parent `collect_ignore` so unit runs never collect `tests/e2e/`.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-12T14:10:00Z (approx.)
- **Completed:** 2026-05-12T14:25:00Z (approx.)
- **Tasks:** 3
- **Files touched:** 4 (3 created, 1 modified)

## Accomplishments

- Added `tests/e2e/pytest.ini` with `testpaths = .`, `e2e` marker, and `-ra` defaults.
- Scaffolded `harness/__init__.py` and documented `fixtures/` (`catalog.lrcat`, `library_seed.db`, export commands, `shutil.copy` temp-DB pattern).
- Appended `collect_ignore = ["e2e"]` plus the canonical E2E invocation in a comment on `tests/conftest.py`.

## Task Commits

Each task was committed atomically:

1. **Task T1: `tests/e2e/pytest.ini`** — `2860fab` (`test(17-01): add dedicated pytest.ini for e2e suite`)
2. **Task T2: harness + fixtures README** — `6dbe45b` (`test(17-01): scaffold e2e harness package and fixtures README`)
3. **Task T3: `collect_ignore`** — `e218797` (`test(17-01): ignore e2e subtree in default pytest collection`)

**Docs:** `docs(17-01): complete e2e pytest isolation scaffold plan` — locate with `git log --oneline --grep='docs(17-01)'` (includes this file, `STATE.md`, `ROADMAP.md`).

## Files Created/Modified

- `apps/visualizer/backend/tests/e2e/pytest.ini` — E2E-only pytest config and markers.
- `apps/visualizer/backend/tests/e2e/harness/__init__.py` — package marker for future CDP helpers.
- `apps/visualizer/backend/tests/e2e/fixtures/README.md` — fixture layout and regeneration notes.
- `apps/visualizer/backend/tests/conftest.py` — excludes `e2e` directory from default collection.

## Decisions Made

- Followed plan verbatim for ini contents and `collect_ignore` placement after `sys.path.insert`.
- Left **TEST-03** unchecked at the requirement level: this plan only scaffolds; real fixture files and smoke coverage land in later 17-xx plans.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `gsd-sdk query state.advance-plan` reported a parse error against `STATE.md` (`Current Plan` / `Total Plans`). Progress was updated manually in `STATE.md` (plan counts + current focus table).

## User Setup Required

None — no external service configuration required.

## Verification (plan-level)

| Check | Result |
|-------|--------|
| `test -f .../tests/e2e/pytest.ini` && `test -f .../tests/e2e/harness/__init__.py` | **PASS** |
| `cd apps/visualizer/backend && python -m pytest tests/e2e/ -c tests/e2e/pytest.ini --collect-only -q` | **Exit code 5** (“no tests collected”) — expected with zero `test_*.py` |
| `python -m pytest tests/ --collect-only -q` output must not contain `tests/e2e/` | **PASS** (asserted with `rg -q`) |

## Self-Check: PASSED

## Next Phase Readiness

- Ready for **17-02** (harness implementation): parent tree will keep ignoring E2E until tests are added; invoke E2E with `pytest -c tests/e2e/pytest.ini tests/e2e/`.

---
*Phase: 17-e2e-harness-bootstrap · Completed: 2026-05-12*
