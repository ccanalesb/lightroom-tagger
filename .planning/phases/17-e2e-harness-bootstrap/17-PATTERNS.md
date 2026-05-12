# Phase 17 — Pattern mapping (E2E harness bootstrap)

Maps **files to create or modify** (from `17-CONTEXT.md` + `17-RESEARCH.md`) to **roles**, **data flow**, **closest codebase analogs**, and **verbatim excerpts** so planners can replicate existing patterns without rediscovering them.

---

## File manifest (create / modify)

| Path (under `apps/visualizer/backend/` unless noted) | Role | Primary data flow |
|-----------------------------------------------------|------|-------------------|
| `tests/e2e/conftest.py` | Pytest bootstrap + **session fixtures** | Imports → `sys.path` → temp dirs → env → **subprocess** backend → **`yield base_url`** → teardown |
| `tests/e2e/pytest.ini` | **Isolation**: dedicated discovery / markers | pytest reads ini only when `-c …` or cwd is `tests/e2e` — avoids `pytest tests/` collecting E2E |
| `tests/e2e/pytest.toml` *(optional alternate to ini)* | Same as ini | `[tool.pytest.ini_options]` if project standard prefers pyproject segment |
| `tests/e2e/harness/browser_session.py` | **CDP façade** (`BrowserSession`) | Test/fixture → thin methods (`navigate`, `click`, `wait_for`, `get_text`) → `js(...)` / `cdp(...)` / harness primitives — **no Playwright shell** |
| `tests/e2e/harness/__init__.py` | Package marker | Enables clean imports |
| `tests/e2e/fixtures/catalog.lrcat` | **Committed catalog slice** (5–10 images) | Read-only artifact; Lightroom export → repo; subprocess may reference for catalog ops |
| `tests/e2e/fixtures/library_seed.db` | **Seeded SQLite** for `LIBRARY_DB` | Copied into session temp (`shutil.copy`) → writable isolated DB → child process env |
| `tests/e2e/fixtures/export_fixture.py` | One-shot export helper | Maintainer runs manually → emits/updates committed fixtures |
| `tests/e2e/test_smoke.py` | First E2E | `base_url` + `BrowserSession` → GET page → assert DOM/title/API readiness |
| `apps/visualizer/frontend/dist/` *(gitignored)* | Built SPA | `vite build` output — consumed by Flask static route or separate static server *(planner chooses D-14)* |
| `apps/visualizer/backend/app.py` *(possible)* | Static + SPA fallback | Only if planner chooses Flask-served `dist/` *(RESEARCH: not present today)* |
| `apps/visualizer/frontend` build env | `VITE_*` at build time | E2E port (e.g. 5099) may need bake-in if API origin is not same-host relative |

---

## 1. `tests/e2e/conftest.py` — path setup, subprocess backend, fixtures

**Analog A — parent `tests/conftest.py` (prepend backend to `sys.path`):**

```1:7:apps/visualizer/backend/tests/conftest.py
import os
import sys

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
```

**E2E note:** For `tests/e2e/conftest.py`, `backend_dir` must use **three** `dirname` hops (…/tests/e2e → tests → backend), or resolve relative to file the same way with one extra parent.

**Analog B — in-process readiness / endpoint contract** (reuse URL shape in health poll or urllib before browser):

```13:24:apps/visualizer/backend/tests/test_app.py
def test_app_has_required_endpoints():
    app = create_app()
    client = app.test_client()

    response = client.get('/api/status')
    assert response.status_code == 200

    catalog_status = client.get('/api/catalog/status')
    assert catalog_status.status_code == 200
    payload = catalog_status.get_json()
    assert 'cached' in payload
    assert isinstance(payload['cached'], bool)
```

**Analog C — tempfile + real DB lifecycle** (`init_db` pattern; E2E should **copy** seeded file instead of only `init_db`, but directory + absolute paths align):

```11:28:apps/visualizer/backend/tests/test_orphan_recovery.py
def test_recover_running_job_with_checkpoint_requeues_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "jobs.db")
        db = init_db(db_path)
        job_id = create_job(db, "batch_describe", {})
        meta = {
            "checkpoint": {
                "checkpoint_version": 1,
                "job_type": "batch_describe",
                "fingerprint": "x",
                "processed_pairs": [],
            }
        }
        db.execute(
            "UPDATE jobs SET status = ?, metadata = ?, started_at = ? WHERE id = ?",
            ("running", json.dumps(meta), datetime.now().isoformat(), job_id),
        )
        db.commit()
```

**Analog D — Flask entry, port guard, subprocess env targets** (`create_app` uses `config.DATABASE_PATH` beside `app.py`; `__main__` uses `socketio.run` + `_refuse_if_port_in_use`):

```115:118:apps/visualizer/backend/app.py
    CORS(app, origins=config.FRONTEND_URL.split(','))
    socketio = SocketIO(app, cors_allowed_origins="*")

    db_path = os.path.join(os.path.dirname(__file__), config.DATABASE_PATH)
```

```360:397:apps/visualizer/backend/app.py
def _refuse_if_port_in_use(host: str, port: int) -> None:
    """Exit early if another backend is already bound to host:port.
    ...
    """
    if os.environ.get('WERKZEUG_RUN_MAIN'):
        return
    ...
```

```394:397:apps/visualizer/backend/app.py
if __name__ == '__main__':
    _refuse_if_port_in_use(config.FLASK_HOST, config.FLASK_PORT)
    app = create_app()
    socketio.run(app, host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, allow_unsafe_werkzeug=True)
```

**Config env knobs** (child process should set absolute paths + non-reloader debug):

```1:17:apps/visualizer/backend/config.py
import os

from dotenv import load_dotenv

load_dotenv()

FLASK_HOST = os.getenv('FLASK_HOST', 'localhost')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173,http://localhost:5174')
# Library DB path - must be absolute or relative to working directory
# Use environment variable LIBRARY_DB to specify absolute path
# Falls back to library.db in current working directory

DATABASE_PATH = os.getenv('DATABASE_PATH', '../visualizer.db')
LIBRARY_DB = os.getenv('LIBRARY_DB', 'library.db')
```

**Session fixture sketch (behavioral checklist, not prescriptive implementation):**

1. `TemporaryDirectory` (session-scoped): jobs DB + copied `library_seed.db`.
2. `Popen([python, "app.py"], cwd=<backend_abs>, env={**os.environ, "FLASK_PORT": "5099", "FLASK_DEBUG": "false", "DATABASE_PATH": <abs jobs sqlite>, "LIBRARY_DB": <abs copied library>, "FRONTEND_URL": <origins incl. test origin>, …})`.
3. Poll `GET http://127.0.0.1:5099/api/status` until 200 or timeout.
4. `yield` base URL to tests.
5. `terminate()` → `wait(timeout=…)` → `kill()` if needed; delete temp dirs.

---

## 2. `tests/e2e/pytest.ini` — test isolation config

**Goal:** Default `pytest tests/` from backend **never** collects E2E; E2E is explicit: `pytest -c tests/e2e/pytest.ini tests/e2e/` or `cd tests/e2e && pytest`.

**Suggested `pytest.ini` contents** (adapt paths if invocation cwd differs):

```ini
[pytest]
testpaths = .
python_files = test_*.py
python_functions = test_*
markers =
    e2e: tests that spin up browser + stack (slow; not for unit CI)
addopts =
    -ra
```

**Notes:**

- `testpaths = .` limits collection to the ini’s directory tree when pytest’s rootdir is `tests/e2e`.
- Register `e2e` marker to avoid “unknown marker” warnings and document intent (`17-CONTEXT.md` D-03).
- Optional strictness (if team wants failures on unknown markers in this suite only): `addopts = --strict-markers` (ensure all markers declared in this file).

---

## 3. `tests/e2e/harness/browser_session.py` — CDP wrapper; browser-harness skill API

**Project policy:** Use **browser-harness** (daemon-mediated CDP to **already-running Chrome**). Do not spawn Playwright from tests (`17-CONTEXT.md` D-07).

**Invocation shape** (stdin Python; helpers pre-imported):

```bash
browser-harness <<'PY'
new_tab("https://example.com")
wait_for_load()
print(page_info())
PY
```

**First navigation rule:** **`new_tab(url)`** — not `goto` — so the active tab is not clobbered (`17-RESEARCH.md`, skill).

**Primitives to wrap or delegate** (skill contract):

| Primitive | Purpose |
|-----------|---------|
| `new_tab(url)` | Primary navigation for tests |
| `wait_for_load()` | After navigation |
| `page_info()` | Lightweight “alive?” introspection |
| `screenshot()` | Visual verification / debugging |
| `js(...)` | DOM read/write when selectors/text needed (`get_text`, custom waits) |
| `cdp("Domain.method", **params)` | Raw Chrome DevTools when helpers insufficient |
| `http_get(url)` | Bulk static HTTP outside browser (optional; smoke may use `urllib` in pytest instead) |
| `ensure_real_tab()` | Recover stale tab contexts |

**Architecture reference** (skill): `Chrome → CDP WS → daemon → /tmp/bu-<NAME>.sock → run.py`; `BU_NAME` namespaces sockets.

**Planning implications for `BrowserSession`:**

- Either **subprocess `browser-harness`** per operation (heavy) or **import harness Python helpers** in the pytest venv (document install: `browser-harness --doctor`, `uv tool`, etc.).
- Tests may call **raw CDP** alongside the façade (`17-CONTEXT.md` D-06).

---

## 4. `tests/e2e/fixtures/` — DB / catalog factory patterns

**Committed artifacts:** `catalog.lrcat` + `library_seed.db` + optional `export_fixture.py` (`17-CONTEXT.md` D-08..D-10, specifics).

**Runtime pattern:** **`shutil.copy(library_seed.db, tmp_library_path)`** before starting Flask so the subprocess has a **writable** isolated DB (`17-CONTEXT.md` / `17-RESEARCH.md`).

**Closest analog — tempfile + SQLite init** (`test_orphan_recovery.py`): same “under `TemporaryDirectory`, absolute `db_path`” discipline; swap `init_db`+mutate for **copy seed → point `LIBRARY_DB`**.

```11:14:apps/visualizer/backend/tests/test_orphan_recovery.py
def test_recover_running_job_with_checkpoint_requeues_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "jobs.db")
        db = init_db(db_path)
```

**Jobs DB (`DATABASE_PATH`):** Smoke may use **fresh `init_db`** under temp dir (like tests above) unless a committed empty template is preferred (`17-RESEARCH.md`).

---

## 5. `tests/e2e/test_smoke.py` — assertion targets

**Flow:** Fixtures bring up stack → `BrowserSession` opens `http://127.0.0.1:<port>/` (or static server URL) → wait for load → assert stable surface.

### A. Backend / fail-fast (no browser)

Mirror `test_app`: expect **`GET /api/status`** → 200 on the **subprocess** base URL before CDP-heavy steps (`17-RESEARCH.md`).

### B. Document title (static HTML from built SPA)

Built `index.html` template carries:

```7:8:apps/visualizer/frontend/index.html
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Lightroom Tagger</title>
```

### C. React mount — shell `h1` text

`APP_TITLE` is the single source for header copy:

```1:2:apps/visualizer/frontend/src/constants/strings.ts
export const APP_TITLE = 'Lightroom Tagger'
```

```27:31:apps/visualizer/frontend/src/components/Layout.tsx
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-8">
              <h1 className="text-lg font-semibold text-text">{APP_TITLE}</h1>

              <nav className="hidden md:flex items-center space-x-1">
```

**Practical assertions for smoke:**

- **`document.title`** contains **`Lightroom Tagger`** after load, and/or  
- **`h1` text** **`Lightroom Tagger`** visible (via `js(...)` querying `document.querySelector('h1')` or similar — avoid brittle Tailwind class selectors).

---

## Summary for planners

| Deliverable | Replicate |
|-------------|-----------|
| Path injection | Extra `dirname` vs `tests/conftest.py` |
| Temp isolated DB | `TemporaryDirectory` + patterns from `test_orphan_recovery.py`; **copy** `library_seed.db` |
| Health / API | Poll `/api/status` like `test_app.py` |
| Subprocess server | Match `app.py` `__main__` entry; obey `_refuse_if_port_in_use`; set **`FLASK_DEBUG=false`** (`17-RESEARCH.md`) |
| Browser | **browser-harness** primitives: `new_tab`, `wait_for_load`, `js`, `cdp`, `page_info` |
| Smoke assertions | Title + `APP_TITLE` / `Layout` `h1` |

## PATTERN MAPPING COMPLETE
