---
phase: 14
status: issues_found
files_reviewed: 34
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
---

# Code Review: Phase 14 — database-images-api-split

## Summary

The database package split retains a single barrel (`lightroom_tagger.core.database`) with relative imports only inside `database/` (no `from lightroom_tagger.core.database import` in submodules — good for cycles). Blueprint registration in `app.py` keeps URL families distinct (`/api/images/catalog`, `/stacks`, `/instagram`, `/matches`, `/search`), with legacy routes and the invalid polymorphic detail rule ordered so they do not shadow real families. SQL in the reviewed API and core paths is bound-parameterized; thumbnail handlers enforce configured roots before `send_file`. Remaining issues are mostly consistency/UX: one dead `success_paginated` call on the Instagram list route, and CLIP “similar” accepting sort query parameters that the underlying pipeline intentionally does not apply (KNN order preserved), which diverges from frontend comments and can confuse API clients.

## Findings

### CR-001: Discarded `success_paginated` call on Instagram list (warning)

**File:** `apps/visualizer/backend/api/images/instagram.py:197-210`

**Issue:** `list_instagram_images` invokes `success_paginated(paginated, total, offset, limit)` and then ignores its return value, returning a separately built `jsonify({...})` payload. That duplicates the pagination envelope logic, risks drift from the canonical helper used by `jobs.py`, and matches the “dead / misleading code” pattern noted for the old monolithic images module.

**Recommendation:** Either `return success_paginated(...)` with the envelope field name the client expects (`data` vs `images` — align with `utils.responses.success_paginated` contract and update the frontend), or remove the unused call and document the intentional `{ total, images, pagination }` shape so the helper is not implied.

### CR-002: `sort_by_score` / `sort_by_date` accepted on CLIP similar but not applied (warning)

**File:** `apps/visualizer/backend/api/images/catalog.py:101-207` (see `clip_filter_kwargs` vs parsed `sort_raw` / `sort_date_raw`)

**Issue:** `_parse_clip_similar_catalog_params` validates `sort_by_score` and `sort_by_date` (including the rule that score sort requires `score_perspective`) but never passes those knobs into `run_clip_similar_for_seed` / `filter_order_keys_in_catalog`. The latter explicitly preserves KNN order and omits sort parameters by design (`filter_order_keys_in_catalog` docstring in `lightroom_tagger/core/database/catalog.py`). Clients that send the same query shape as catalog list + CLIP similar (the frontend type `CatalogListQueryParams` explicitly says “backend mirrors filters”) may believe sort affects CLIP results when it does not.

**Recommendation:** Document the behavior in the route docstring and API contract, or reject `sort_by_*` on this endpoint with `400` (“not supported for visual similarity; order is by CLIP distance”), or apply a documented post-sort only if product requirements demand it.

### CR-003: Exception text forwarded to clients on some catalog/instagram paths (info)

**Files:** `apps/visualizer/backend/api/images/catalog.py` (e.g. `error_server_error(str(e))`), `apps/visualizer/backend/api/images/instagram.py` (same pattern)

**Issue:** Broad `except` handlers return the stringified exception to the client on 500 responses, which can leak paths, library details, or other environment specifics in edge failures.

**Recommendation:** Log the full exception server-side and return a generic message (or error id) in the JSON body for production.

### CR-004: Thumbnail path logs to stdout on cache failure (info)

**File:** `apps/visualizer/backend/api/images/catalog.py:384-385`

**Issue:** `print(f"Cache generation failed for {image_key}: {cache_err}")` bypasses structured logging and may expose internal details in shared log streams.

**Recommendation:** Use the app/job logging facility and log at `warning`/`error` with optional stack trace, without printing to stdout in request hot paths.

### CR-005: `matches` API depends on Instagram private helpers (info)

**File:** `apps/visualizer/backend/api/images/matches.py:20-21`

**Issue:** `matches.py` imports `_deserialize_description` and `_enrich_instagram_media` from `instagram.py` (underscore-prefixed helpers). This couples sub-blueprints and makes refactors to Instagram enrichment risk breaking matches without a clear stable import surface.

**Recommendation:** Move shared enrichment/deserialization to `common.py` (or a small `images/enrichment.py`) and import from there, or expose a single public helper from `instagram.py` without a leading underscore.

### CR-006: Heavy imports on `api.images` package init (info)

**File:** `apps/visualizer/backend/api/images/__init__.py:3-10`

**Issue:** The package `__init__` imports `nl_catalog_search` and `ProviderRegistry` solely to re-export them. That increases import cost and side effects for any `from api.images import catalog_bp` consumer.

**Recommendation:** If callers need those symbols, prefer `from lightroom_tagger.core …` at use sites, or use lazy exports (`__getattr__`) if import time matters.

## Clean Files

Relative to the phase focus (imports, barrels, blueprints, URL paths, SQL injection, obvious missing re-exports), these files needed no issue entries:

`apps/visualizer/backend/api/analytics.py`, `apps/visualizer/backend/api/identity.py`, `apps/visualizer/backend/api/images/common.py`, `apps/visualizer/backend/api/images/search.py`, `apps/visualizer/backend/api/images/stacks.py`, `apps/visualizer/backend/app.py`, `apps/visualizer/backend/tests/test_images_chat_search_api.py`, `apps/visualizer/backend/tests/test_images_nl_search_api.py`, `apps/visualizer/backend/tests/test_images_semantic_search_api.py`, `apps/visualizer/frontend/src/services/api.ts` (paths and parameter wiring match the mounted blueprints for the reviewed endpoints), `lightroom_tagger/core/database/__init__.py`, `lightroom_tagger/core/database/db_init.py`, `lightroom_tagger/core/database/descriptions.py`, `lightroom_tagger/core/database/embeddings.py`, `lightroom_tagger/core/database/instagram.py`, `lightroom_tagger/core/database/matches.py`, `lightroom_tagger/core/database/scores.py`, `lightroom_tagger/core/database/similarity.py`, `lightroom_tagger/core/database/stacks.py`, `lightroom_tagger/core/database/vision_cache.py`, `lightroom_tagger/core/test_database_catalog.py`, `lightroom_tagger/core/test_database_db_init.py`, `lightroom_tagger/core/test_database_descriptions.py`, `lightroom_tagger/core/test_database_embeddings.py`, `lightroom_tagger/core/test_database_instagram.py`, `lightroom_tagger/core/test_database_matches.py`, `lightroom_tagger/core/test_database_similarity.py`, `lightroom_tagger/core/test_database_stacks.py`, `lightroom_tagger/core/test_database_vision_cache.py`

`lightroom_tagger/core/database/catalog.py` is referenced under CR-002 only for the documented behavior of `filter_order_keys_in_catalog` (sort not part of the CLIP membership filter). `lightroom_tagger/core/database/__init__.py` is a large but consistent barrel re-export; no missing-symbol or circular-import issues were found in the reviewed slice.
