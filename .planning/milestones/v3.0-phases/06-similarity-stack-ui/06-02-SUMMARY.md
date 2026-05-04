---
phase: 06-similarity-stack-ui
plan: 2
subsystem: database
tags: [clip, sqlite-vec, knn, SIM-02, D-05]

requires:
  - phase: 06-similarity-stack-ui
    provides: catalog_key_is_primary_grid_row, stack collapse in catalog queries
provides:
  - CLIP-only KNN on image_clip_embeddings with order-preserving catalog + primary-grid post-filter
  - filter_order_keys_in_catalog for batched key membership with same predicates as query_catalog_images
affects:
  - 06-03 similar-images API (NoClipEmbeddingError → 404)

tech-stack:
  added: []
  patterns:
    - "Shared _append_query_catalog_image_filters for query_catalog_images and filter_order_keys_in_catalog"
    - "run_clip_similar_for_seed: over-fetch KNN, drop seed, primary-grid then filter_order_keys_in_catalog"

key-files:
  created:
    - lightroom_tagger/core/clip_similarity.py
    - lightroom_tagger/core/test_clip_similarity.py
  modified:
    - lightroom_tagger/core/database.py

key-decisions:
  - "NoClipEmbeddingError(seed_key) when seed has no image_clip_embeddings row; meta includes CLIP_EMBED_MODEL_ID and CLIP_EMBED_DIM from clip_embedding_service"
  - "knn_k = min(500, max(50, (offset+limit)*20)) with knn_clip_catalog_keys k clamped to KNN_K_MAX"

patterns-established:
  - "SIM-02 library layer: only image_clip_embeddings SQL — no 768-d text table string in module (D-05)"

requirements-completed: [SIM-02]

duration: 25min
completed: 2026-04-25
---

# Phase 6 Plan 2: SIM-02 CLIP similarity library Summary

**CLIP-only sqlite-vec KNN on `image_clip_embeddings`, order-preserving filters via `filter_order_keys_in_catalog`, and `NoClipEmbeddingError` for seeds missing embeddings — ready for Flask wiring in 06-03.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 1
- **Files modified:** 3 code + 1 test module + this summary

## Accomplishments

- `knn_clip_catalog_keys` / `get_clip_embedding_blob_for_key` / `run_clip_similar_for_seed` in `clip_similarity.py` with `KNN_K_MAX = 500` and documented over-fetch; seed excluded; `catalog_key_is_primary_grid_row` applied before catalog kwargs so non-representative stack members never appear in similar lists.
- `filter_order_keys_in_catalog` and `_append_query_catalog_image_filters` in `database.py` share predicates with `query_catalog_images` (incl. stack collapse).
- Pytest: missing embedding, seed exclusion, D-05 table target, non-rep neighbor excluded.

## Task Commits

1. **Task 1: clip_similarity + filter_order_keys_in_catalog** — one feat commit (see git log for hash)

## Files Created/Modified

- `lightroom_tagger/core/clip_similarity.py` — SIM-02 public API and `NoClipEmbeddingError`.
- `lightroom_tagger/core/database.py` — filter helper extraction + `filter_order_keys_in_catalog`.
- `lightroom_tagger/core/test_clip_similarity.py` — unit tests.

## Decisions Made

- Metadata dict includes `clip_model_id` and `clip_embed_dim` from `clip_embedding_service` plus optional `knn_fetched` / `knn_k_used` for transparency.

## Deviations from Plan

None — plan executed as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- 06-03 can import `run_clip_similar_for_seed` and map `NoClipEmbeddingError` to 404 with UI-spec error string.

## TDD Gate Compliance

Not applicable (plan type `execute`, not `tdd`).

## Self-Check: PASSED

- `python -m pytest lightroom_tagger/core/test_clip_similarity.py -q` passes.
- `rg "image_text_embeddings" lightroom_tagger/core/clip_similarity.py` → no matches.

---
*Phase: 06-similarity-stack-ui*
*Completed: 2026-04-25*
