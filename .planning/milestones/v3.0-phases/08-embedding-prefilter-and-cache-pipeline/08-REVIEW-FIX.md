---
phase: 08-embedding-prefilter-and-cache-pipeline
status: fixed
fixes_applied: 3
---

# Phase 08 — Code review auto-fix (gsd-code-review-fixer)

Medium and high warnings from `08-REVIEW.md` were addressed inline before phase close. Info-level findings were **not** changed this round.

## WR-08-01 — Catalog similarity job has no frontend result surface

| Field | Value |
|-------|--------|
| **Status** | FIXED |
| **Commit** | `626e255` |

**Fix**

- Restored a compact “Latest similarity groups” preview on the primary Catalog Vision Cache card (`CatalogCacheTab.tsx`), immediately below the Build catalog cache CTA block (after success/error messaging).
- Data: `useQuery(['catalog.similarity.groups', { limit: 12, offset: 0 }], () => ImagesAPI.listCatalogSimilarityGroups(...))` (`CatalogCacheTab.tsx` ~lines 67–71, 223–226).
- Preview UI and empty state live in `CatalogSimilarityGroupsPreview` (~lines 329–397), following the pre–Phase 8 `MatchingTab` JSX pattern (`git show 79ba1e4:.../MatchingTab.tsx`).
- Copy: `CATALOG_CACHE_SIMILARITY_*` keys in `apps/visualizer/frontend/src/constants/strings.ts`.
- “View all” links to the existing Job Queue route `PROCESSING_JOB_QUEUE_ROUTE` (`/processing?tab=jobs`) via `react-router-dom` `Link` (no new route).
- After a successful `batch_catalog_similarity` enqueue from Advanced, `invalidateAll(['catalog.similarity.groups'])` refreshes the preview (`CatalogCacheTab.tsx` ~lines 114–117).

**Tests**

- Extended `apps/visualizer/frontend/src/components/processing/__tests__/CatalogCacheTab.test.tsx`: mocks `ImagesAPI.listCatalogSimilarityGroups`, asserts `{ limit: 12, offset: 0 }`, and checks rendered title / match summary / total groups label / “View all” `href`. Wrapped renders in `MemoryRouter` for `Link`.

---

## WR-08-02 — Instagram CLIP backlog helper full-table load

| Field | Value |
|-------|--------|
| **Status** | FIXED |
| **Commit** | `9b04f48` |

**Fix**

- Introduced `_instagram_dump_clip_embed_filters()` to centralize Instagram dump CLIP window predicates (`database.py` ~lines 3176–3202).
- `list_instagram_dump_keys_needing_clip_embedding()` now uses `LEFT JOIN image_clip_embeddings ce ON ce.image_key = m.media_key` with `ce.image_key IS NULL` and the same `ORDER BY m.date_folder DESC, m.media_key DESC` as the listing query (`database.py` ~lines 3222–3249). No per-call materialization of all embedding keys in Python.

**Tests**

- Added `TestDatabase.test_list_instagram_dump_keys_needing_clip_embedding_anti_join` in `lightroom_tagger/core/test_database.py` (~lines 561–594): three dump rows, embed middle key only → backlog lists the other two in deterministic order; embed all → empty backlog.
- Regression: `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` (suite re-run; all passed).

---

## WR-08-03 — Invalid `clip_top_k` metadata silently coerced

| Field | Value |
|-------|--------|
| **Status** | FIXED |
| **Commit** | `b6540ca` |

**Fix**

- On `(TypeError, ValueError)` when parsing `metadata['clip_top_k']`, `handle_vision_match` now calls `add_job_log(..., 'warning', '[vision-match] clip_top_k coercion: raw={raw_clip!r} -> default=50')` (`handlers.py` ~lines 493–503).

**Tests**

- Added `test_handle_vision_match_warns_on_invalid_clip_top_k` in `apps/visualizer/backend/tests/test_handlers_single_match.py` (patches `jobs.handlers.add_job_log`, metadata `clip_top_k='not-a-number'`, asserts warning payload and `clip_top_k=50` passed to `match_dump_media`).

---

## Verification

Commands run after all fixes:

- Backend: `uv run python -m pytest apps/visualizer/backend/tests/test_handlers_batch_embed_image.py apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py apps/visualizer/backend/tests/test_handlers_single_match.py lightroom_tagger/core/test_clip_similarity.py -q --tb=short` → **40 passed**
- Frontend: `npx tsc --noEmit` and `npm test -- --run` → **287 passed** (Vitest)

---

*Written by gsd-code-review-fixer (sequential commits, hooks preserved).*
