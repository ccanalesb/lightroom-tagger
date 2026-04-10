# Technical Concerns

## Technical Debt

- **Dual SQLite worlds.** The visualizer keeps a separate jobs DB (`apps/visualizer/backend/database.py`, path from `DATABASE_PATH` / `visualizer.db`) while catalog/Instagram data lives in `LIBRARY_DB` (`library.db` by default). Job handlers open the library DB directly (`jobs/handlers.py` via `init_database`). Operators must keep env vars aligned; mismatches cause “database not found” or empty UIs with no single source of truth for “which DB am I using?”

- **CORS vs Socket.IO policy mismatch.** REST uses `CORS(app, origins=config.FRONTEND_URL.split(','))` in `apps/visualizer/backend/app.py`, but `SocketIO(..., cors_allowed_origins="*")` allows any browser origin for WebSockets. Tightening REST without tightening Socket.IO leaves a partial hardening story.

- **Debug defaults in production config.** `apps/visualizer/backend/config.py` sets `FLASK_DEBUG` default to `true`. Combined with `allow_unsafe_werkzeug=True` in `app.py`’s `socketio.run`, this is appropriate for local dev only and easy to ship accidentally.

- **Dead / misleading code in list routes.** `apps/visualizer/backend/api/images.py` calls `success_paginated(...)` for `/instagram` but discards its return value and builds a parallel `jsonify({...})` shape. That invites drift between “standard” pagination and what clients actually get.

- **Instagram browser stack is operationally heavy.** `lightroom_tagger/instagram/browser.py` depends on external `agent-browser`, hard-coded waits, `/tmp/instagram_posts.json`, and duplicate crawl paths (`fetch_posts` vs `crawl_instagram_browser`). Fragile against Instagram DOM/API changes and hard to test without the full toolchain.

- **Logging inconsistency.** Much of the backend and job pipeline uses `print()` (`app.py`, `jobs/handlers.py`, `api/images.py`) while `api/system.py` uses `logging`. No structured correlation IDs across HTTP jobs and vision calls.

- **Environment variable typo risk.** `lightroom_tagger/lightroom/reader.py` documents `LIGHTRoom_CATALOG_LOCKING_MODE` (camel “Room”) instead of “LIGHTROOM”. Anyone setting the conventional name will not get the intended behavior.

- **Untracked scratch at repo root.** `test_direct_match.py` (per git status) is ad-hoc driver code; if kept, it should live under `scripts/` or tests with documented purpose to avoid confusion.

## Known Issues

- **Schema vs. access pattern for descriptions.** `image_descriptions` uses `PRIMARY KEY (image_key)` only (`lightroom_tagger/core/database.py`), while API enrichment uses composite keys `(image_key, image_type)` (`apps/visualizer/backend/api/images.py`). If the same `image_key` were ever reused across `catalog` and `instagram`, one row would overwrite the other. Today keys are usually namespaced by convention, not enforcement.

- **`query_by_exif` ignores `date_window_days`.** `lightroom_tagger/core/matcher.py` documents a date window but never applies it in SQL—callers may assume temporal filtering that does not exist.

- **Socket “cancel” is a no-op for workers.** `apps/visualizer/backend/websocket/events.py` emits `job_cancel_requested` on `cancel_job` but nothing in `jobs/handlers.py` or `JobRunner` subscribes to cancel in-flight matching; only the REST `DELETE` on `/api/jobs/<id>` updates DB status. Long vision jobs can keep running until the handler finishes.

- **Orphan recovery is coarse.** `_recover_orphaned_jobs` marks every `running` job as `failed` on restart (`app.py`). There is no “resume” path for idempotent job types.

- **Plan-file TODOs (non-code).** `docs/plans/2026-04-09-frontend-notion-redesign.md` notes placeholder counts (`TODO: Add catalog count API`). Treat as product backlog, not runtime bugs.

- **Leftover debug flavor.** `matcher.py` logs “DEBUG: Candidate keys” for the first batch candidate; harmless but noisy in production logs if `debug` logs are enabled.

## Security Concerns

- **No authentication on the visualizer API.** All routes under `/api/*` and Socket.IO are effectively open on the bind address. Suitable only for trusted LAN or localhost; exposing `FLASK_HOST=0.0.0.0` without a reverse proxy and auth is high risk.

- **Arbitrary file read via thumbnail endpoints (by design, but sensitive).** `get_instagram_thumbnail` and `get_catalog_thumbnail` (`api/images.py`) call `send_file` on paths stored in SQLite. Anyone who can write to `library.db` (or exploit another bug that mutates paths) could point routes at arbitrary readable files. Paths are not re-validated against an allowlist after lookup.

- **Job creation accepts arbitrary JSON metadata.** `POST /api/jobs/` (`api/jobs.py`) stores `metadata` with minimal validation. Large payloads bloat the jobs table; nested structures are trusted by handlers (e.g. `weights`, `provider_id`). No size cap or schema validation at the boundary.

- **API keys in `providers.json`.** `lightroom_tagger/core/provider_registry.py` supports inline `api_key` in JSON as well as env vars (`_resolve_api_key`). Filesystem permissions and `.gitignore` for `providers.json` are critical; a committed key is a credential leak.

- **Secrets in app config.** `lightroom_tagger/core/config.py` / `config.py` map `CLOUDFLARE_API_TOKEN` and similar into dataclass fields—ensure `config.yaml` and env are not world-readable in shared environments.

- **Subprocess surface.** `lightroom_tagger/instagram/browser.py` invokes `agent-browser` and `curl` with list arguments (no `shell=True`), which avoids shell injection. Still, URLs and session names originate from crawled content; dependency compromise or malicious URLs are trust-boundary concerns for the machine running the crawler.

## Performance Issues

- **Full-table reads before pagination.** `list_instagram_images` loads `SELECT * FROM instagram_dump_media` then filters/sorts/paginates in Python (`api/images.py`). Same pattern for `list_catalog_images` (`SELECT * FROM images`). Growth toward tens of thousands of rows will increase memory and latency linearly.

- **Matches endpoint loads entire graph.** `list_matches` pulls all `matches`, all `instagram_images`, and all `images` into dicts (`api/images.py`). This is \(O(n)\) memory and CPU per request.

- **Vision matching cost.** Batch path in `score_candidates_with_vision` (`matcher.py`) reduces round-trips but each batch still encodes many images as base64 (`vision_client.py`). Provider latency scales with batch size (see `docs/BATCH_API_TESTING_RESULTS.md`: 60–90s for large batches).

- **Per-request DB connections.** `@with_db` opens and closes `library.db` per HTTP handler (`utils/db.py`). Under concurrency, SQLite serializes writers; many parallel thumbnail generations or writes from jobs plus HTTP can contend despite WAL.

- **Job thread + HTTP + matching share library DB.** `init_database` uses `check_same_thread=False` (`lightroom_tagger/core/database.py`), which allows cross-thread use but does not remove SQLite write locking. Heavy matching jobs while serving the UI can cause `busy_timeout` waits (5s).

## Fragile Areas

- **UNC / NAS path resolution.** `matcher.py` rewrites `//server/share/...` to `/Volumes/share/...`; `path_utils.resolve_catalog_path` and `resolve_filepath` in `database.py` also participate. Any change to mount layout (different SMB path, Linux) breaks matching and thumbnails silently (skipped candidates, 404 thumbnails).

- **Lightroom catalog locking.** `connect_catalog` in `reader.py` defaults to `PRAGMA locking_mode=EXCLUSIVE` for WAL-on-NAS reliability. Lightroom open concurrently, or another tool touching the catalog, yields “database is locked” or exclusive-mode conflicts—documented in comments but easy to hit in real workflows.

- **Instagram / scraping selectors.** Browser automation uses fixed CSS selectors and sleep timings (`browser.py`). Instagram UI changes break crawls without test failures in CI if those paths are not exercised.

- **Provider and JSON parsing.** Vision responses must be valid JSON (`vision_client.py`, analyzer prompts). Model drift or prose outputs cause parse failures; batch responses aggregate more failure modes.

- **Migration by `ALTER TABLE` with dynamic table names.** `_migrate_add_column` uses `PRAGMA table_info({table})` and `ALTER TABLE` (`database.py`). Table/column names are internal constants only—safe today, but any future dynamic input would be SQL injection risk.

- **Frontend error surface.** `apps/visualizer/frontend/src/services/api.ts` throws `Error` with status text only—no structured error body for users; debugging production issues relies on network tab inspection.

- **Rate limit handling in matcher.** Consecutive rate limits increment toward an abort threshold (`RATE_LIMIT_ABORT_THRESHOLD` in `matcher.py`). Tuning mismatch with provider quotas can abort large batches mid-run or hide partial results.

---

*Generated for GSD codebase mapping. Refresh when major subsystems (auth, DB layout, matching pipeline) change.*
