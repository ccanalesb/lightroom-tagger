---
phase: 17
status: findings
depth: standard
files_reviewed: 10
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
---

## Summary

E2E harness wiring is generally sound: selectors and URLs are built with `json.dumps` (Safer embedding for CDP snippets), static file serving uses `safe_join` and `send_from_directory`, and the jobs DB path relies on an absolute `DATABASE_PATH` (which `os.path.join` preserves correctly). Main risks are **subprocess pipe buffering**, an **unclosed SQLite connection** in the session fixture, and **fixed-port / environment assumptions**. No critical defects found.

### WR-01 (warning): Subprocess `PIPE` without readers can deadlock the Flask child
File: apps/visualizer/backend/tests/e2e/conftest.py  
Line: 51–67  
Issue: `subprocess.Popen` uses `stdout=subprocess.PIPE` and `stderr=subprocess.PIPE` but nothing reads those streams while the server runs. If the combined output exceeds the OS pipe buffer, the child can block on `write()` and the parent may spin until timeout or hang teardown.  
Fix: Prefer `subprocess.DEVNULL`, inherit the parent’s streams (`stdout=None`, `stderr=None`), or attach threads/async readers that drain the pipes for the fixture lifetime.

### WR-02 (warning): `init_db` connection leaked in pytest process
File: apps/visualizer/backend/tests/e2e/conftest.py  
Line: 37–38  
Issue: `init_db(str(jobs_db))` returns a `sqlite3.Connection` that is never closed. The subprocess then opens the same path. This often works with WAL but can surface as subtle locking or resource issues (especially on non-Linux or under load).  
Fix: Use `conn = init_db(...); try: ... finally: conn.close()` before starting Flask, or a context manager if the API supports it.

### WR-03 (warning): Hard-coded host/port for stack and health check
File: apps/visualizer/backend/tests/e2e/conftest.py  
Line: 30–35, 42–82  
Issue: Port `5099`, `FLASK_PORT`, `VITE_BACKEND_PORT`, and the health-check URL are fixed. A stray process already bound to that port can make the check hit the wrong service or leave the fixture flaky.  
Fix: Allocate a free port (e.g. `socket.bind(('', 0))`), pass it through env and `viz_e2e_base_url`, or fail fast with a clearer check that the response body matches expected JSON for `/api/status`.

### IN-01 (info): Empty package `__init__`
File: apps/visualizer/backend/tests/e2e/harness/__init__.py  
Line: 1  
Issue: The file is empty; callers import `harness.browser_session` directly, which is fine but inconsistent if you want a stable public surface (`from harness import BrowserSession`).  
Fix: Optionally re-export `BrowserSession` and document the intended import path.

### IN-02 (info): `BrowserSession.close` is intentionally a no-op
File: apps/visualizer/backend/tests/e2e/harness/browser_session.py  
Line: 117–119  
Issue: Teardown relies entirely on browser-harness daemon lifecycle; tests may accumulate remote state across sessions if the CLI keeps a long-lived browser.  
Fix: When browser-harness supports it, call an explicit shutdown primitive in `close()`; until then, document the constraint in the harness README next to Phase 17 notes.

### IN-03 (info): Orphan `.bak` handling in `export_fixture.py`
File: apps/visualizer/backend/tests/e2e/fixtures/export_fixture.py  
Line: 34–36  
Issue: The block removes `*.pre-key-migration.bak` if present but nothing in this function creates that file. Reads as leftover migration logic and may confuse maintainers.  
Fix: Remove the block or add a one-line comment tying it to a real migration step.

### IN-04 (info): README still references a future plan number
File: apps/visualizer/backend/tests/e2e/fixtures/README.md  
Line: 15–16  
Issue: “Wire the exact filenames in Plan 02” is stale relative to Phase 17 and may mislead.  
Fix: Rephrase to point at the current phase or the actual script path only.
