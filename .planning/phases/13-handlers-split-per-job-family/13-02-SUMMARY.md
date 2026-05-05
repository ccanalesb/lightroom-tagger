---
plan: 13-02
phase: 13
status: complete
---

# 13-02 Summary: Extract common.py

## What was built
Moved 5 constants and 5 cross-family helpers from `_legacy.py` to `common.py`:
constants: `_CHECKPOINT_MAX_ENTRIES`, `_LEGACY_DATE_FILTER_MONTHS`, `_CATALOG_NOT_VIDEO_SQL`, `_INSTAGRAM_NOT_VIDEO_SQL`; helpers: `_resolve_library_db_or_fail`, `_failure_severity_from_exception`, `_resolve_date_window`, `_select_catalog_keys`, `_select_instagram_keys`.

Re-exported back into `_legacy.py` via `from .common import (...)`. Updated targeted tests to import helpers from `jobs.handlers.common`.

Moved `_failure_severity_from_exception`’s exception imports into `common`; dropped unused `AuthenticationError` / `InvalidRequestError` imports from `_legacy.py`.

## Key files modified
- `apps/visualizer/backend/jobs/handlers/common.py` (populated from scaffold)
- `apps/visualizer/backend/jobs/handlers/_legacy.py` (removed 9 definitions, added from .common import)
- `apps/visualizer/backend/tests/test_handlers_date_window.py` (imports + `require_library_db` patch target)
- `apps/visualizer/backend/tests/test_select_instagram_keys.py`
- `apps/visualizer/backend/tests/test_handlers_batch_analyze.py`, `test_handlers_batch_describe.py`, `test_handlers_batch_score.py` — `@patch('jobs.handlers.common.require_library_db', …)` so mocks hit `_resolve_library_db_or_fail` (which resolves `require_library_db` in `common`’s namespace). Handlers that still call `require_library_db()` directly in `_legacy.py` (e.g. `handle_vision_match`) keep patching `jobs.handlers.require_library_db`.

## Verification
- Full pytest (`apps/visualizer/backend`): passed (341 tests)
- `from jobs.handlers.common import _resolve_date_window, _select_instagram_keys`: passed
- `from jobs.handlers import JOB_HANDLERS` / length 15: passed

## Self-Check: PASSED
