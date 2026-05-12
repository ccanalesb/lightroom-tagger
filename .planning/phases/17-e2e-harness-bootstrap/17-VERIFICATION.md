---
phase: 17
status: passed
checked: 2026-05-12
must_haves_total: 14
must_haves_verified: 14
---

## Verification Report

Phase **17** delivers the E2E harness described in plans **17-01–17-04**: isolated pytest entry for `tests/e2e/`, `BrowserSession` over `browser-harness` stdin (no Playwright), committed `library_seed.db`, optional `catalog.lrcat` flow via `export_fixture.py --catalog-from`, Flask SPA serving behind `VISUALIZER_E2E_STATIC_DIST`, session stack fixture with Vite build + subprocess Flask + library copy + `/api/status` health gate, and a marked smoke test for the homepage `h1`.

**Traceability (TEST-03):** `.planning/REQUIREMENTS.md` marks **TEST-03** complete and says *“real catalog fixture used”*. The repo has **`library_seed.db`** (five `e2e_cat_*` rows) but **no** `catalog.lrcat` under `tests/e2e/fixtures/` (consistent with **17-02-T3** developer-gated catalog). Consider a small doc tweak so TEST-03 wording matches artifacts; this does not block the phase implementation goals above.

**Dynamic port:** `viz_e2e_base_url` uses `_find_free_port()` for `flask run --port` and health-checks `{base_url}/api/status`, while `npm run build` still sets `VITE_BACKEND_PORT=5099`. Production frontend uses relative `API_DEFAULT_URL` (`/api`), so same-origin API calls stay correct on the dynamic port.

**Live smoke:** This verification is static (file + collection + sqlite). A full `test_e2e_visualizer_homepage_smoke` run still depends on **browser-harness**, Chrome/CDP, and **npm** as documented in plan summaries.

## Must-Haves Check

| # | Item | Status |
|---|------|--------|
| 1 | `pytest.ini` exists with `testpaths = .` and `e2e:` marker line | PASS |
| 2 | `harness/__init__.py` and `fixtures/README.md` under `tests/e2e/` | PASS |
| 3 | Parent `tests/conftest.py`: `collect_ignore = ["e2e"]` + comment with `pytest -c tests/e2e/pytest.ini tests/e2e/` | PASS |
| 4 | Only `test_smoke.py` as `test_*.py` under `tests/e2e/` (no extras) | PASS |
| 5 | `BrowserSession`: `navigate`/`click`/`wait_for`/`get_text` via stdin (`new_tab`, `wait_for_load`, `js`, `click(x,y)`); no `playwright` in file | PASS |
| 6 | `export_fixture.py --library` + committed `fixtures/library_seed.db` with five `e2e_cat_*` keys | PASS |
| 7 | `export_fixture.py` supports `--catalog-from`; `catalog.lrcat` not committed (developer-gated — OK) | PASS |
| 8 | `browser_session` fixture: parameter `viz_e2e_base_url` + body line `_ = viz_e2e_base_url` | PASS |
| 9 | `app.py`: `VISUALIZER_E2E_STATIC_DIST`, `_visualizer_e2e_spa`; `path` starting `api` or `socket.io` → `abort(404)` | PASS |
| 10 | `factory.ensure_writable_fixture_library` copies committed `library_seed.db` | PASS |
| 11 | `viz_e2e_base_url`: `VITE_BACKEND_PORT=5099` at build, Flask on dynamic port, `FLASK_DEBUG=false`, GET `/api/status` gate, `Popen`, teardown `terminate` / `wait(timeout=5)` / `kill` | PASS |
| 12 | `test_smoke.py`: `pytestmark = pytest.mark.e2e` | PASS |
| 13 | Smoke: `navigate`, `wait_for("h1")`, assert `Lightroom Tagger` in `get_text("h1")` | PASS |
| 14 | `pytest tests/` `--collect-only` does not surface `test_smoke` / e2e smoke | PASS |

## Shell Verification Results

1. **Default collection vs `test_smoke`:**  
   `cd .../apps/visualizer/backend && ./../../../.venv/bin/python -m pytest tests/ --collect-only -q 2>&1 | grep -c "test_smoke" || echo "0 matches (good)"`  
   → **`0`** matches (grep exit 1 → fallback echoed); e2e smoke not collected by default tree.

2. **E2E config collection (tail):**  
   `pytest tests/e2e/ -c tests/e2e/pytest.ini --collect-only -q`  
   → Ends with `test_smoke.py::test_e2e_visualizer_homepage_smoke` and **`1 test collected`**.

3. **`collect_ignore`:**  
   `rg -n "collect_ignore" apps/visualizer/backend/tests/conftest.py`  
   → `9:collect_ignore = ["e2e"]`

4. **`VISUALIZER_E2E_STATIC_DIST`:**  
   `rg -n "VISUALIZER_E2E_STATIC_DIST" apps/visualizer/backend/app.py`  
   → `119:    raw_root = os.environ.get("VISUALIZER_E2E_STATIC_DIST", "").strip()`

5. **`pytestmark`:**  
   `rg -n "pytestmark = pytest.mark.e2e" apps/visualizer/backend/tests/e2e/test_smoke.py`  
   → `3:pytestmark = pytest.mark.e2e`

6. **`library_seed.db` row count:**  
   `sqlite3 .../fixtures/library_seed.db "SELECT COUNT(*) FROM images;"`  
   → **`5`** (keys `e2e_cat_001` … `e2e_cat_005` verified separately).

## Summary

All **14** enumerated must-haves match the codebase and shell checks. Phase **17** goal (bootstrap E2E harness + smoke contract + default pytest isolation) is **achieved**. Optional follow-up: align **TEST-03** prose in `REQUIREMENTS.md` with the developer-gated **`catalog.lrcat`** policy so traceability matches committed files.
