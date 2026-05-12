# Phase 17 — E2E Harness Bootstrap: Research Notes

**Purpose:** What you need to know to **plan** Phase 17 well (minimal E2E harness + one smoke test), aligned with `17-CONTEXT.md`, TEST-03, and the current backend/frontend codebase.

---

## 1. CDP / browser-harness skill — how `BrowserSession` should relate to project policy

**Canonical doc:** project rules point agents at `~/.cursor/skills/browser-harness/SKILL.md` (the copy under `.cursor/skills/browser-harness/` in-repo may not exist; treat `~/.cursor/skills/` as authoritative). Repo hooks also enforce using `browser-harness` instead of ad-hoc Playwright shell commands.

**What the harness is:** a CLI (`browser-harness`) that runs Python with **daemon-mediated CDP** to an **already-available Chrome** (local profile with remote debugging, or remote Browser Use session). First navigation should use **`new_tab(url)`** (not clobbering the user’s active tab). Common primitives from the skill: `wait_for_load()`, `screenshot()`, `page_info()`, `js(...)`, **`cdp("Domain.method", ...)` for raw Chrome DevTools Protocol**, `http_get` for bulk static HTTP outside the browser.

**Implications for `BrowserSession` (D-04..D-07):**

- **Policy:** Convenience methods (`navigate`, `click`, `wait_for`, `get_text`) should be implemented **in the same spirit** as the harness: thin wrappers over **`js(...)` / raw CDP** rather than spawning Playwright from tests.
- **Implementation options for pytest (planning tradeoff):**
  - **Subprocess delegation:** Run snippets via `browser-harness <<'PY'` from tests — simple but heavy (process + IPC per call) and awkward for granular assertions.
  - **Import helpers inside the pytest venv:** The canonical install can be **`uv tool install`/editable** tooling where top-level modules like `helpers` / `run` / `daemon` **may** resolve from an editable checkout (see finder mapping in local `uv tool` installs). **Risk:** teammates/CI won’t match unless harness is pinned/documented as a dev prerequisite.
  - **Minimal CDP client that talks to the same daemon/socket convention** as `browser-harness` — only if planners confirm the harness’s stable wire protocol is acceptable to depend on.

**Recommendation for PLAN:** State explicitly:

1. **`BrowserSession`** is either a **thin façade** importing from the harness’s Python helpers (with a documented installation path), or a **minimal CDP + daemon attach** copied from harness patterns—not Playwright-driver tests.

2. **CI / unattended machines:** SKILL assumes **interactive Chrome**. Phase 17 `17-CONTEXT.md` already defers CI; document that smoke tests locally require **`browser-harness --doctor`**-clean setup (or remote `BU_*` flow from the SKILL) so Phase 18 does not silently assume CI availability.

---

## 2. pytest isolation — separate config, markers, session-scoped process fixtures

**Goal (D-01..D-03):** `pytest tests/` (from `apps/visualizer/backend`) must **never** collect E2E tests; E2E is **`pytest`** with explicit config/path.

**Why parent tree has no pytest.ini today:** Backend tests rely on **`tests/conftest.py`** only for **`sys.path`** insertion (`backend_dir` = parent of `tests/`). Root `pyproject.toml` does **not** define `[tool.pytest.ini_options]`, so Phase 17 will introduce the **first** dedicated pytest ini for visualizer unless you extend root config.

**Reliable exclusion patterns:**

| Approach | Idea |
|---------|------|
| **Dedicated `pytest.ini`** under `tests/e2e/` with `testpaths = .` | Invoked as `pytest -c tests/e2e/pytest.ini tests/e2e/` from backend dir (paths relative to cwd), or **`cd tests/e2e && pytest`** so only that tree is targeted. |
| **`collect_ignore`** in **`tests/conftest.py`** | `collect_ignore_glob = ["**/e2e/*"]` for default runs risks drift if naming changes—CONTEXT prefers standalone ini + explicit invocation. |
| **`@pytest.mark.e2e`** | Register marker in `tests/e2e/pytest.ini` (`markers = e2e: ...`) even if duplication is discouraged in unit runs (`-m "not e2e"` is a weaker primary guard than separate config). |

**Session-scoped stack fixture (D-13):**

- **Scope `session`** for exactly one backend (and optionally one static server) per pytest process.
- **Order:** Create temp dirs → copy seeded DB → set env → `subprocess.Popen` → poll health → **`yield base_url`** → terminate/kill subprocess → cleanup temp dirs.
- **Safety:** Prefer **timeouts** on health polling and teardown (`proc.wait(timeout=n)`) so a wedged Flask process does not leave port listeners around (see **`_refuse_if_port_in_use`** in `app.py` — collisions must be avoided).

---

## 3. Flask subprocess spin-up — health checks, debug/reloader gotchas, teardown

**Entry point:** `apps/visualizer/backend/app.py` runs with `socketio.run(...)` under `__main__`, reads **`config.FLASK_HOST` / `FLASK_PORT` / `FLASK_DEBUG`** from env via `config.py` (`dotenv`-loaded `.env`, then overridden by subprocess env).

**Health signal:** Unit smoke already uses **`GET /api/status`** (`test_app.py`) — reuse that endpoint for readiness (optionally **`/api/jobs/health`** if you want worker visibility; not required for static smoke).

**Environment variables Phase 17 should plan to set on the child process:**

| Variable | Role |
|---------|------|
| `FLASK_PORT` | Isolated port (e.g. `5099` per CONTEXT) |
| `FLASK_HOST` | `127.0.0.1` avoids `0.0.0.0` ambiguity |
| `FLASK_DEBUG` | Prefer **`false`** for subprocess tests to disable **Werkzeug reloader** (double process, flaky tests). Matches need to skip `_refuse_if_port_in_use` only when reloaders are involved (`WERKZEUG_RUN_MAIN` — see `_refuse_if_port_in_use` docstring). |
| `DATABASE_PATH` | Point **jobs/visualizer.sqlite** copy under session temp (`config.DATABASE_PATH` defaults to `../visualizer.db` relative to config module cwd — **use absolute tempfile paths**). |
| `LIBRARY_DB` | Seeded **`library_seed.db`** copy path (consistent with **`library_db.py`**: env overrides config file). |
| `FRONTEND_URL` | Include origins that match how the SPA is served in E2E (if same-origin on `5099`, add **`http://127.0.0.1:5099`** / `http://localhost:5099` for `CORS` + Socket.IO allowances in `create_app`). |
| Optional catalog/config | Backend may resolve NAS paths via `lightroom_tagger.core.config`; E2E seed should avoid depending on `/tmp` instagram dirs unless the smoke test needs them |

**`_refuse_if_port_in_use`:** Startup **aborts if something listens on `host:port`**. Plan must ensure **exclusive use** of the test port during the session fixture lifetime.

**Teardown:**

1. **`terminate()`** then **`wait(timeout=...)`**.
2. On timeout, **`kill()`** — log stderr if capturing child output aids debugging Phase 18 failures.

**Working directory:** `subprocess.Popen` should **`cwd`** to **`apps/visualizer/backend`** so relative paths in `.env`/defaults behave predictably—or avoid relying on cwd by passing **absolute** paths for all DB env vars.

---

## 4. Fixture DB patterns — seeded library DB, `.lrcat` slice

**Committed artifacts (D-08..D-10):**

- Minimal **real `.lrcat`** (5–10 images) under **`tests/e2e/fixtures/`** — Lightroom Classic is the practical source; there is **no automation in-repo yet** beyond CLI/docs that reference `--catalog`.

- **`library_seed.db`** — authoritative **predictable** SQLite for `LIBRARY_DB` (image keys, descriptions, scores as needed).

**Temp copy pattern (D-12, existing code parallels):**

- **`test_orphan_recovery.py`** / **`test_images_detail_api.py`**: **`tempfile.TemporaryDirectory`**, **`init_db`** or **`init_database`**, then mutate — for E2E you **prefer `shutil.copy(library_seed.db, tmp_library)`** before starting Flask so subprocess gets a writable copy (same idea as CONTEXT `shutil.copy`).

**Visualizer jobs DB:**

- Separate from library DB (`DATABASE_PATH` / `visualizer.db` path in `create_app`). Copy or init an empty **`init_db`**-compatible DB for jobs if Phase 17 smoke avoids job creation; otherwise reuse a trivial committed empty template.

**Lightroom `.lrcat` reality:**

- Files are SQLite; WAL/SMB quirks are documented in project README (`connect_catalog`).
- Fixture export (`export_fixture.py` idea in CONTEXT): plan should either **manual export + scripted copy** into `fixtures/`, or a **documented Lightroom workflow** (“export as catalog” / trimmed folder) plus whatever **path consistency** Phase 18 needs for thumbnails.

---

## 5. Frontend static assets — Vite output, serving strategy

**Build:** `apps/visualizer/frontend/package.json` → `"build": "tsc && vite build"`; default **`outDir`** is **`dist/`** at `apps/visualizer/frontend/dist` (no custom `build.outDir` in `vite.config.ts`).

**Runtime API base:**

- **`vite.config.ts`** uses **`VITE_BACKEND_PORT`** for dev proxy targets (default proxy → `localhost:5001`).
- Production build inlines **`import.meta.env.VITE_*`**. For E2E against **`5099`**, plan **`VITE_BACKEND_PORT=5099` (and host if encoded)** at **build time** unless the SPA is served same-origin behind Flask (then relative `/api` may work).

**Serving options (D-14, planner discretion):**

| Option | Pros | Cons |
|--------|------|------|
| **Flask serves `dist/` + SPA fallback** | Single origin, no CORS split, Socket.IO same host | Requires small **static + `catch_all` → index.html`** route additions (SPA client routes like `/processing`) — **currently missing** from `create_app`; must be scoped to `"e2e" / static root` env flag |
| **`python -m http.server`** (or Node `vite preview`) on second port | No Flask routing changes | Needs **correct API base URL** baked into frontend build; Socket.IO origins must align with **`FRONTEND_URL`** |

**Dev vs prod HTML:** Root `index.html` references **`/src/main.tsx`** — only the **built** artifacts under **`dist/`** are suitable for E2E **without Vite**.

---

## 6. Validation architecture — proving the harness (smoke test)

**Minimal bar (D-15, TEST-03):** One smoke test establishes **live browser → HTTP server → API-capable backend → bundled React**.

**Suggested flow:**

1. Session fixtures up (stack + **`BrowserSession`**).
2. `navigate` to **`http://127.0.0.1:<port>/`** (or static server URL if split).
3. **`wait_for_load`** (harness terminology) **or equivalent** polling until DOM ready.

**Assertions (prefer stable UX surface):**

- Document title **`Lightroom Tagger`** (`frontend/index.html` + constants).
- App shell: **`Layout`** renders **`h1`** text from **`APP_TITLE`** (`'Lightroom Tagger'`) — strong signal React mounted versus blank `#root`.

**Optional corroboration:** `GET /api/status` inside the fixture before opening the browser (fail fast vs CDP flake).

**Out of scope Phase 17:** Critical flows (**E2E-01…E2E-06**), CI matrix, parallelism — CONTEXT already marks these Phase 18+ / deferred.

---

## Cross-reference quick map

| Topic | Repo touchpoints |
|------|-------------------|
| Path hacks | ```1:7:apps/visualizer/backend/tests/conftest.py``` |
| In-process Flask API checks | ```13:21:apps/visualizer/backend/tests/test_app.py``` |
| Temp DB + `init_db` | ```11:48:apps/visualizer/backend/tests/test_orphan_recovery.py``` |
| Library fixture + monkeypatch/env | `apps/visualizer/backend/tests/test_images_detail_api.py` (`detail_client` + env), plus `monkeypatch.setenv("LIBRARY_DB", …)` in handler tests |
| Port guard + subprocess risks | `_refuse_if_port_in_use`, `socketio.run` in **`app.py`** |
| Frontend mount | **`main.tsx`**, **`Layout.tsx`** + **`APP_TITLE`** |

---

## RESEARCH COMPLETE
