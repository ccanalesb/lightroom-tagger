---
phase: 14-database-images-api-split
plan: 14-06
subsystem: api
tags: [flask, blueprint, routing, vite, typescript]

requires:
  - phase: "14-database-images-api-split"
    provides: "Wave 14-05 submodule split producing family blueprints and handlers"
provides:
  - "Five `register_blueprint` mounts under `/api/images/{catalog,stacks,instagram,matches,search}`"
  - "Nested search HTTP paths `/api/images/search/{nl-search,semantic-search,chat-search}`"
  - "Explicit app-level rules for `/api/images/catalog-similarity-groups` and `/api/images/dump-media`"
  - "Frontend `ImagesAPI.chatSearch` targeting `/images/search/chat-search` (relative to `/api` base)"
affects:
  - "visualizer-backend"
  - "visualizer-frontend live validation curl examples"

tech-stack:
  added: []
  patterns:
    - "D-09: one Flask Blueprint per image family plus `url_prefix`; no umbrella `images.bp`"

key-files:
  created: []
  modified:
    - "apps/visualizer/backend/app.py"
    - "apps/visualizer/backend/api/images/__init__.py"
    - "apps/visualizer/backend/api/images/catalog.py"
    - "apps/visualizer/backend/api/images/instagram.py"
    - "apps/visualizer/backend/api/images/matches.py"
    - "apps/visualizer/backend/api/images/stacks.py"
    - "apps/visualizer/backend/tests/test_images_*_api.py (search paths)"
    - "apps/visualizer/backend/tests/test_websocket.py"
    - "apps/visualizer/frontend/src/services/api.ts"

key-decisions:
  - "Invalid polymorphic URLs use `/api/images/<string:bad_type>/<path:image_key>` with `_invalid_polymorphic_image_detail` after family mounts (werkzeug ``regex`` converter unavailable in this environment)."

patterns-established:
  - "Search endpoints live under `search_bp` with prefix `/api/images/search`; JSON `thumbnail_url` fields remain `/api/images/catalog/<key>/thumbnail`."

requirements-completed: [REFACTOR-03]

duration: 18min
completed: 2026-05-06
---

# Phase 14 Plan 06: D-09 URL prefix migration Summary

**Visualizer image REST API mounted as five prefixed blueprints; search POSTs nested under `/api/images/search/...`; catalog similarity-groups and Instagram dump-media stay on explicit full paths.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-06T17:46:00Z (approx.)
- **Completed:** 2026-05-06T18:04:00Z (approx.)
- **Tasks:** 4
- **Files modified:** 11

## Accomplishments

- Removed umbrella `images` blueprint registration and wired `catalog_bp`, `stacks_bp`, `instagram_bp`, `matches_bp`, and `search_bp` with fixed D-09 prefixes in `create_app`.
- Trimmed decorator paths in catalog/instagram/stacks/matches so effective URLs stayed aligned except intentional search nesting.
- Backend tests and `ImagesAPI.chatSearch` updated for `/api/images/search/chat-search`; full `pytest` and frontend `tsc` + Vitest suites green.

## Task Commits

1. **Task 1 — Blueprint registrations + app-level similarity/dump-media rules + invalid-detail catch-all** — `b28851c` (feat)
2. **Task 2 — Submodule `@route` paths for prefixed blueprints + catalog/list slash alias** — `3984e14` (feat)
3. **Task 3 — Tests (search URLs + websocket fixture `instagram_bp`)** — `668ff69` (test)
4. **Task 4 — Frontend chat-search path** — `7ff8eff` (feat)

**Plan metadata:** `docs(14-06): add D-09 URL migration plan summary` (repository commit touching `14-06-SUMMARY.md`)

## Files Created/Modified

- `apps/visualizer/backend/app.py` — five blueprints; `add_url_rule` for catalog-similarity-groups + dump-media; legacy invalid-detail rule.
- `apps/visualizer/backend/api/images/*.py` — family route strings; similarity-groups and dump-media views exported for app mounting.
- `apps/visualizer/backend/tests/test_images_{nl,semantic,chat}_search_api.py` — POST paths under `/api/images/search/...`.
- `apps/visualizer/backend/tests/test_websocket.py` — `instagram_bp` instead of removed umbrella `bp`.
- `apps/visualizer/frontend/src/services/api.ts` — `ImagesAPI.chatSearch` → `/images/search/chat-search`.

## Decisions Made

- Invalid two-segment detail URLs reuse a trailing catch-all `<string:bad_type>` rule registered after blueprints so catalog/instagram mounts win specificity; avoids unregistered werkzeug ``regex`` converter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Blocking] werkzeug lacked `regex` URL converter**

- **Found during:** Task 1 (`create_app` `LookupError`)
- **Issue:** `app.add_url_rule(..., '<regex(...):bad_type>', ...)` failed at startup.
- **Fix:** Switched to `/api/images/<string:bad_type>/<path:image_key>` bound to `_invalid_polymorphic_image_detail`, documented ordering vs family blueprints.
- **Files modified:** `apps/visualizer/backend/app.py`
- **Verification:** `python -c "from app import create_app; create_app()"`; `pytest tests/test_images_detail_api.py`
- **Committed in:** `b28851c`

**2. [Rule 1 — Blocking] Broken `catalog.py` after route edits**

- **Found during:** Task 2 (`IndentationError` / missing detail route)
- **Issue:** `list_catalog_similarity_groups` orphaned `except` and missing `@catalog_bp.route` on catalog detail handler.
- **Fix:** Completed `except` body; added `@catalog_bp.route("/<path:image_key>", ...)` for `get_catalog_image_detail`; dual `@catalog_bp.route(""|"/")` on list for stable decorator count versus pre-split baseline.
- **Files modified:** `apps/visualizer/backend/api/images/catalog.py`
- **Verification:** `@catalog_bp.route` count `6`; `pytest` image suite
- **Committed in:** `3984e14`

---

**Total deviations:** 2 auto-fixed (2 blocking correctness)
**Impact on plan:** No intentional URL contract changes beyond D-09 search nesting; startup and catalog detail restored.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None.

## Next Phase Readiness

- Image API split URLs are stable for frontend/backend contract tests.
- Optional follow-up: refresh planning docs / curl snippets that still mention flat `/api/images/chat-search`.

## Self-Check: PASSED

- `cd apps/visualizer/backend && python -c "from app import create_app; create_app()"` → exit 0
- `cd apps/visualizer/backend && pytest -q` → 341 passed
- `cd apps/visualizer/frontend && npx tsc --noEmit` → exit 0
- `cd apps/visualizer/frontend && npm test -- --run` → 50 files / 284 tests passed

---
*Phase: 14-database-images-api-split*
