---
phase: 06-similarity-stack-ui
reviewed: 2026-04-25T12:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - lightroom_tagger/core/database.py
  - lightroom_tagger/core/identity_service.py
  - lightroom_tagger/core/clip_similarity.py
  - lightroom_tagger/core/test_database_stack_collapse.py
  - lightroom_tagger/core/test_clip_similarity.py
  - apps/visualizer/backend/api/images.py
  - apps/visualizer/backend/tests/test_images_clip_similar_api.py
  - apps/visualizer/frontend/src/services/api.ts
  - apps/visualizer/frontend/src/constants/strings.ts
  - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
  - apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx
  - apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx
  - apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx
  - apps/visualizer/frontend/src/components/identity/BestPhotosGrid.test.tsx
  - apps/visualizer/frontend/src/components/image-view/__tests__/ImageDetailModal.test.tsx
  - .planning/phases/06-similarity-stack-ui/06-01-PLAN.md
  - .planning/phases/06-similarity-stack-ui/06-02-PLAN.md
  - .planning/phases/06-similarity-stack-ui/06-03-PLAN.md
  - .planning/phases/06-similarity-stack-ui/06-04-PLAN.md
findings:
  critical: 0
  warning: 0
  info: 5
  total: 5
status: clean
---

# Phase 06-similarity-stack-ui: Code review

**Status:** `clean` (no security defects, no blocking correctness bugs identified in scope.)

**Automation:** `pytest` on `test_database_stack_collapse.py`, `test_clip_similarity.py`, `test_images_clip_similar_api.py` — 13 passed (2026-04-25).

## Summary

Stack collapse in SQL and `filter_order_keys_in_catalog` share the same `(m_st.image_key IS NULL OR i.key = st.representative_key)` fragment; CLIP similar flow applies `catalog_key_is_primary_grid_row` before catalog filters, then `filter_order_keys_in_catalog` in KNN order. The similar-images route calls `run_clip_similar_for_seed(..., limit=500, offset=0)` once and paginates in Flask — `total` matches the length of that filtered list, and result order is preserved through `query_catalog_images_by_keys`. Stack members use `_query_catalog_rows_for_stack_member_keys` without the collapse predicate, so the burst strip is correct. The frontend maps 404 to the no-embedding copy via the JSON `error` string through `request()`. No SQL injection, hardcoded secret, or `eval`/unsafe HTML paths were found in reviewed code.

## Info

### IN-01: Similar `total` is KNN-bounded, not a global “all similar in catalog” count

**File:** `apps/visualizer/backend/api/images.py:885-901` (see comment at 886-887)  
**Issue:** `total` is `len(full_pairs)` where `full_pairs` comes from a single vec KNN with `KNN_K_MAX` (500) and post-filters. More than 500 catalog images could in principle rank as neighbors if the KNN window were unbounded.  
**Note:** In-process pagination (`page_pairs = full_pairs[offset : offset + limit]`) is consistent with that list. API consumers and Phase 7 should treat `total` as “matches within the SIM-02 retrieval cap,” not a full exhaustive count.

### IN-02: `catalog_key_is_primary_grid_row` is evaluated once per KNN row

**File:** `lightroom_tagger/core/clip_similarity.py:99-104`  
**Issue:** Up to 500 extra SQLite round-trips per similar request. Acceptable for local use; if latency regresses, consider batching “non-rep member” checks set-wise.

### IN-03: `get_stack_members` docstring vs behavior

**File:** `apps/visualizer/backend/api/images.py:933-934`  
**Issue:** The one-line docstring says “representative + collapsed rules,” but the implementation intentionally **does not** apply primary-grid collapse (see `933` and `234-244`).  
**Fix:** Rephrase to “all members in `image_key` order, catalog-shaped (including non-representatives).”

### IN-04: `appendCatalogListSearchParams` / `CatalogListQueryParams` not a full mirror of the similar-route catalog filters

**File:** `apps/visualizer/frontend/src/services/api.ts:249-296`  
**Issue:** The backend `clip_filter_kwargs` for similar can include `dominant_colors`, `mood_tags`, and `has_repetition` (`_parse_clip_similar_catalog_params`); the shared TS helper does not append them. Current Phase 6 UI only passes `limit`/`offset` for similar, so there is no regression; Phase 7 should extend types + serialization if those filters are passed to `getCatalogSimilar`.

### IN-05: Gaps in automated tests (non-blocking)

- **Similar route:** No explicit test for `offset` / second-page slicing (list order vs `query_catalog_images_by_keys` is structurally correct but not asserted end-to-end).
- **React:** Relying on plan’s Vitest run; not re-executed in this review.

---

_Reviewer: Cursor (Phase 06 scope review)_

## Findings summary (concise)

| Area | Result |
|------|--------|
| SQLite stack collapse + member strip | Correct split: collapse on primary lists / similar neighbors; no collapse for stack strip helper. |
| CLIP / vec / filter order | KNN on `image_clip_embeddings` only; order preserved through filter; seed excluded. |
| Similar API contract | 404 + exact error string; `total`+pagination coherent within KNN cap; optional meta fields may exceed minimal TS `CatalogSimilarResponse` type. |
| `rank_best_photos` | Non-reps dropped before sort/posted; stack fields applied as specified. |
| UI / fetch | 404 body surfaced via `Error` message; nested modal for similar tiles; stack fetch cached on first expand. |

**Blocking issues:** none.
