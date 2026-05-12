---
phase: 17-e2e-harness-bootstrap
plan: "03"
subsystem: testing
tags: [e2e, pytest, flask, vite, subprocess, sqlite]

requires:
  - phase: 17-e2e-harness-bootstrap
    provides: "Plans 17-01 (E2E isolation) and 17-02 (BrowserSession, library_seed.db)"
provides:
  - "VISUALIZER_E2E_STATIC_DIST-gated SPA routes in create_app (_visualizer_e2e_spa, safe_join + send_from_directory)"
  - "fixtures/factory.ensure_writable_fixture_library copying library_seed.db"
  - "Session-scoped viz_e2e_base_url: npm run build, temp jobs+library DBs, Flask Popen on :5099, GET /api/status health gate"
  - "browser_session fixture depending on viz_e2e_base_url + BrowserSession lifecycle"
affects:
  - "17-e2e-harness-bootstrap"
  - "Phase 18 E2E flows"

tech-stack:
  added: []
  patterns:
    - "E2E-only static dist via env gate; API/socket.io paths never served as SPA files (Flask still routes /api/* to blueprints)"
    - "Session fixture teardown: terminate → wait(timeout=5) → kill; then rmtree temp dir"

key-files:
  created:
    - apps/visualizer/backend/tests/e2e/conftest.py
    - apps/visualizer/backend/tests/e2e/fixtures/factory.py
  modified:
    - apps/visualizer/backend/app.py

key-decisions:
  - "Followed plan placement for SPA routes immediately after SocketIO init; Werkzeug routing still prefers concrete /api/* rules over the catch-all."
  - "Health check uses urllib GET http://127.0.0.1:5099/api/status with 60s deadline and 0.25s backoff."

patterns-established:
  - "VITE_BACKEND_PORT=5099 at vite build time; same port for FLASK_PORT and health URL"

requirements-completed: []

duration: 20min
completed: 2026-05-12
---

# Phase 17 Plan 03: E2E stack session fixtures — Summary

**Visualizer backend can serve the built Vite SPA when `VISUALIZER_E2E_STATIC_DIST` is set; E2E tests get a session fixture that builds the frontend, copies the seed library DB, runs Flask on `127.0.0.1:5099`, and polls `/api/status` before yielding the base URL.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-12T15:00:00Z (approx.)
- **Completed:** 2026-05-12T15:20:00Z (approx.)
- **Tasks:** 3
- **Files touched:** 3 (2 created, 1 modified)

## Accomplishments

- Added `_visualizer_e2e_spa` with `safe_join` + `send_from_directory`, skipping static handling for paths starting `api` or `socket.io`.
- Added `ensure_writable_fixture_library` to copy committed `library_seed.db` into a temp writable path.
- Added `viz_e2e_base_url` (session) and `browser_session` fixtures with `FLASK_DEBUG=false`, `proc.wait(timeout=5)` on teardown, and **TEMP COPY** documentation for the library DB copy.

## Task Commits

Each task was committed atomically:

1. **Task T1: SPA gating in `create_app()`** — `9e38cee` (`feat(17-03): gate E2E SPA static serving on VISUALIZER_E2E_STATIC_DIST`)
2. **Task T2: `fixtures/factory.py`** — `238a46d` (`feat(17-03): add E2E fixture library copy helper (library_seed.db)`)
3. **Task T3: `tests/e2e/conftest.py`** — `2f2356d` (`feat(17-03): add E2E session stack fixture (vite build, Flask :5099, health poll)`)

## Files Created/Modified

- `apps/visualizer/backend/app.py` — optional E2E static + SPA fallback behind `VISUALIZER_E2E_STATIC_DIST`.
- `apps/visualizer/backend/tests/e2e/fixtures/factory.py` — `SEED_LIBRARY_DB` + `ensure_writable_fixture_library`.
- `apps/visualizer/backend/tests/e2e/conftest.py` — path bootstrap, `viz_e2e_base_url`, `browser_session`.

## Verification

- `python -m compileall apps/visualizer/backend/app.py apps/visualizer/backend/tests/e2e/conftest.py apps/visualizer/backend/tests/e2e/fixtures/factory.py -q` → exit 0.
- Plan acceptance `rg` checks for tasks T1–T3 → PASS.

## Decisions Made

None beyond the plan — implementation matches `17-03-PLAN.md`, `17-CONTEXT.md` D-11–D-14, and `17-PATTERNS.md` path/bootstrap notes.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None for code paths; running the session fixture requires **Node/npm** for `npm run build` and **browser-harness** on PATH when tests use `browser_session` (from plan 17-02).

## Next Phase Readiness

- Plan **17-04** can add the smoke test and full E2E invocation verification.
- **TEST-03** remains open until the phase smoke harness is proven end-to-end.

---
*Phase: 17-e2e-harness-bootstrap*
*Completed: 2026-05-12*
