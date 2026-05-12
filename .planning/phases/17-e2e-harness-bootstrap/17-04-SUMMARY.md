---
phase: 17-e2e-harness-bootstrap
plan: "04"
subsystem: testing
tags: [e2e, pytest, browser-harness, cdp, smoke]

requires:
  - phase: 17-e2e-harness-bootstrap
    provides: "Plans 17-01 (e2e isolation), 17-02 (BrowserSession), 17-03 (viz_e2e_base_url + browser_session)"
provides:
  - "pytest.mark.e2e smoke test test_e2e_visualizer_homepage_smoke: navigate /, wait_for h1, assert APP_TITLE substring in h1 text"
affects:
  - "17-e2e-harness-bootstrap"
  - "Phase 18 critical user flows E2E"

tech-stack:
  added: []
  patterns:
    - "Default pytest tests/ collect_ignore keeps e2e out; explicit pytest -c tests/e2e/pytest.ini tests/e2e/ collects smoke test"

key-files:
  created:
    - apps/visualizer/backend/tests/e2e/test_smoke.py
  modified: []

key-decisions:
  - "Matched strings.ts APP_TITLE literal Lightroom Tagger in TITLE constant; no optional document.title assertion per exact plan snippet."

patterns-established:
  - "Homepage smoke: browser_session + viz_e2e_base_url, rstrip('/') before /, 60s wait_for on h1"

requirements-completed:
  - TEST-03

duration: 12min
completed: 2026-05-12
---

# Phase 17 Plan 04: E2E smoke test — homepage title + Layout h1 via CDP stack — Summary

**Marked e2e smoke test opens the visualizer root URL on the session stack, waits for the layout `h1`, and asserts the visible title contains `Lightroom Tagger` (parity with `APP_TITLE` in the frontend constants).**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-12T16:10:00Z (approx.)
- **Completed:** 2026-05-12T16:22:00Z (approx.)
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- Added `tests/e2e/test_smoke.py` with `pytestmark = pytest.mark.e2e`, `TITLE = "Lightroom Tagger"`, and `test_e2e_visualizer_homepage_smoke(browser_session, viz_e2e_base_url)`.
- Confirmed default `pytest tests/` collection does not surface the e2e smoke node id; e2e config collects it explicitly.

## Task Commits

Each task was committed atomically:

1. **Task 17-04-T1: Create `tests/e2e/test_smoke.py`** — `c9ff25a` (`test(17-04): add E2E homepage smoke test (h1 APP_TITLE)`)

**Plan metadata:** same git commit as this `17-04-SUMMARY.md` file (bundled `.planning/` updates).

## Files Created/Modified

- `apps/visualizer/backend/tests/e2e/test_smoke.py` — e2e homepage smoke: `navigate`, `wait_for("h1")`, `get_text("h1")` vs `TITLE`.

## Decisions Made

None beyond plan text — used the exact Python snippet from `17-04-PLAN.md` (no extra `document.title` assertion).

## Deviations from Plan

None — plan executed exactly as written.

Machine verification used **collection only** for the e2e suite (no full run against live Chrome / browser-harness), per executor instructions.

## Issues Encountered

None

## User Setup Required

None for this plan artifact. **Preconditions for actually running** `test_e2e_visualizer_homepage_smoke` (documented for operators):

- Python environment consistent with repo (e.g. `.venv`) for `pytest` / `npm`.
- `browser-harness` on `PATH` with a healthy `browser-harness --doctor` per `~/.cursor/skills/browser-harness/SKILL.md`.
- Google Chrome available for CDP in the maintainer’s harness workflow.

## Verification

### 1. Default suite collect-ignore guardrail

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/backend && python -m pytest tests/ --collect-only -q 2>&1
```

- **Exit code:** 0
- **`test_e2e_visualizer_homepage_smoke` in output:** **no** (grep count 0 on captured log)
- **Sample tail:** `347 tests collected in 2.50s`

### 2. E2E config collects smoke test

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/backend && python -m pytest tests/e2e/ -c tests/e2e/pytest.ini --collect-only -q
```

- **Exit code:** 0
- **Collected:** `test_smoke.py::test_e2e_visualizer_homepage_smoke` (1 test)
- **Note:** Exit code **5** would also be acceptable for “no tests collected” in other misconfigurations; here collection succeeded with exit 0.

### Plan acceptance (`rg` / `test -f`)

All criteria from `17-04-PLAN.md` task **17-04-T1** `<acceptance_criteria>` — **PASS**.

## Next Phase Readiness

Phase **17** harness bootstrap is complete (4/4 plans). **Phase 18** can add critical-path E2E flows on top of the same stack and markers.

## Self-Check: PASSED

---

*Phase: 17-e2e-harness-bootstrap*
*Completed: 2026-05-12*
