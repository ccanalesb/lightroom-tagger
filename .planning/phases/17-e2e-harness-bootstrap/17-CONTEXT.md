# Phase 17: E2E Harness Bootstrap (CDP + fixture) — Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Bootstrap a minimal E2E test framework that runs against a live local stack. No new user-facing features. This is the scaffolding Phase 18's critical-flow tests build on. Requirement: TEST-03.

Deliverables:
1. `tests/e2e/` directory with its own pytest config (excluded from unit test run)
2. `BrowserSession` CDP helper class + pytest fixture
3. Committed catalog fixture (real slice export) + fixture DB factory
4. Suite-managed stack spin-up/teardown (isolated port, temp DB)
5. One smoke test proving the harness works end-to-end

</domain>

<decisions>
## Implementation Decisions

### Test runner & file layout

- **D-01:** E2E tests live under `apps/visualizer/backend/tests/e2e/` — a subdirectory of the existing tests tree
- **D-02:** `tests/e2e/` has its own `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) so `pytest tests/` never picks up E2E tests — two completely separate invocations
- **D-03:** E2E suite is invoked explicitly: `pytest tests/e2e/` — no accidental inclusion in the unit test CI step

### Browser harness

- **D-04:** A `BrowserSession` class wraps the CDP connection — methods: `navigate(url)`, `click(selector)`, `wait_for(selector)`, `get_text(selector)` at minimum
- **D-05:** A pytest fixture in `tests/e2e/conftest.py` yields an instance of `BrowserSession`, handles open/close lifecycle
- **D-06:** Tests can call CDP directly if they need something `BrowserSession` doesn't expose — the class is a convenience layer, not a sealed abstraction
- **D-07:** Project policy: use the `browser-harness` CDP skill — raw Playwright shell commands are blocked

### Catalog fixture

- **D-08:** A one-time export script produces a minimal real `.lrcat` slice (5–10 images) committed to the repo under `tests/e2e/fixtures/`
- **D-09:** The fixture also includes a seeded library DB snapshot (or factory function) so tests have predictable image keys, descriptions, and scores
- **D-10:** The committed fixture is the canonical "real catalog" for all E2E tests — Phase 18 tests build on the same fixture

### Stack spin-up / teardown

- **D-11:** The E2E suite spins up its own backend instance on a separate port (e.g. `:5099`) — the dev stack on `:5001` is never touched
- **D-12:** Suite uses a temp copy of the fixture DB (not the dev library DB) — written to a `tmp/` dir, deleted after the session
- **D-13:** A session-scoped pytest fixture handles backend start (subprocess, pointed at test port + temp DB via env overrides), waits for it to be healthy, and kills it on teardown
- **D-14:** Frontend: `vite build` produces static assets once; the test backend serves them (or a simple static server does) — no Vite dev server required at E2E test time
- **D-15:** Phase 17 scope stops at one passing smoke test (e.g. load the app homepage, assert the page title or a known element is present) — full user-flow coverage is Phase 18

### Claude's Discretion

- Exact port number for the test backend (`:5099` suggested, planner may choose any free port)
- Whether the static frontend assets are served by Flask or a separate `http.server` subprocess
- Internal structure of `BrowserSession` (sync vs async CDP calls)
- Whether fixture export script is a standalone `.py` or a `pytest --fixtures` helper
- How the temp DB copy is created (Python `shutil.copy` is fine)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing test infrastructure
- `apps/visualizer/backend/tests/conftest.py` — current path-setup pattern
- `apps/visualizer/backend/tests/test_app.py` — Flask in-process test pattern (reference for subprocess alternative)
- `apps/visualizer/backend/tests/test_orphan_recovery.py` — real `init_db` + tempfile pattern

### Production code integration points
- `apps/visualizer/backend/app.py` — Flask app entry point, env vars controlling DB path and port
- `apps/visualizer/backend/.env` / `.env.example` — env var names for DB path, library path, port

### Browser harness
- `.cursor/skills/browser-harness/SKILL.md` — CDP connection skill; project policy mandates this over raw Playwright shell commands

### Requirements
- `.planning/REQUIREMENTS.md` — TEST-03 definition (E2E harness bootstrapped, real catalog fixture, framework in place)
- `.planning/REQUIREMENTS.md` — E2E-01..E2E-06 (what Phase 18 will test — Phase 17 must not couple to these flows, just enable them)

### Frontend build
- `apps/visualizer/frontend/package.json` — vite build command
- `apps/visualizer/frontend/` — frontend root for static asset output path

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` — minimal sys.path setup; E2E conftest should extend this pattern
- `test_orphan_recovery.py` — `tempfile.TemporaryDirectory` + real `init_db(db_path)` pattern; same approach for temp fixture DB copy
- `app.py` — Flask app is importable; can be started as subprocess with env overrides for port and DB path

### Established Patterns
- All tests use `MagicMock` + `@patch` for unit isolation — E2E tests deliberately bypass this (they hit the real stack)
- `pytest` with standard discovery; `conftest.py` at `tests/` level adds backend dir to sys.path
- Backend reads `LIBRARY_DB_PATH` (and similar) from env — easy to override for the isolated test instance

### Integration Points
- New `tests/e2e/pytest.ini` must set `testpaths = tests/e2e` and use a custom marker (`@pytest.mark.e2e`) so `pytest tests/` never collects it
- The smoke test connects to the test backend URL (e.g. `http://localhost:5099`) via `BrowserSession`

</code_context>

<specifics>
## Specific Ideas

- Test backend port: `:5099` (far from dev `:5001`, unlikely to collide)
- Temp DB pattern: `shutil.copy(fixture_db_path, tmp_dir / "library.db")` in a session-scoped fixture
- Smoke test target: load `http://localhost:5099`, assert the React app mounts (e.g. nav element or known heading visible)
- Fixture export script: `tests/e2e/fixtures/export_fixture.py` — run once by developer, output committed to `tests/e2e/fixtures/catalog.lrcat` + `tests/e2e/fixtures/library_seed.db`

</specifics>

<deferred>
## Deferred Ideas

- Full user-flow E2E coverage (describe, score, match review, batch flows) — Phase 18
- CI integration (GitHub Actions spin-up) — out of scope for Phase 17 bootstrap
- Parallel E2E test workers — premature for a one-smoke-test phase

</deferred>

---

*Phase: 17-e2e-harness-bootstrap*
*Context gathered: 2026-05-10*
