---
phase: 08-embedding-prefilter-and-cache-pipeline
plan: "08-03"
subsystem: database
tags: [sqlite-vec, clip, instagram-dump, batch_embed_image, fingerprint]

requires:
  - phase: 08-embedding-prefilter-and-cache-pipeline
    provides: Phase 8 CONTEXT D-01 decision and Wave 1 CLIP shortlist consumer expectations
provides:
  - "`list_instagram_dump_keys_needing_clip_embedding` / `_for_clip_embed_force` mirroring catalog CLIP backlog listing over `instagram_dump_media`"
  - "`batch_embed_image` accepts `image_type: catalog_and_instagram` with deterministic catalog-first union + collision warning"
  - "`fingerprint_batch_embed_image` canonical `image_type` of `catalog` vs `catalog_and_instagram` so checkpoints cannot cross scopes"
  - "Instagram dump path classification inside `_handle_batch_embed_image_inner` via `instagram_dump_media.file_path`"
affects:
  - 08-04-catalog-cache-build-composite (composite chain should enqueue embed with union scope)

tech-stack:
  added: []
  patterns-established:
    - "Instagram dump CLIP backlog lists reuse `image_clip_embeddings` presence filtering like catalog helpers; date window aligns with `_list_instagram_dump_clip_embed_sql_params` + compact `date_folder` ordering"

key-files:
  created: []
  modified:
    - lightroom_tagger/core/database.py
    - apps/visualizer/backend/jobs/checkpoint.py
    - apps/visualizer/backend/jobs/handlers.py
    - apps/visualizer/backend/tests/test_handlers_batch_embed_image.py

key-decisions:
  - "Fingerprint embed scope collapses unknown `image_type` values to `catalog` via `_normalized_batch_embed_image_type`, preserving legacy checkpoints unless union sentinel is explicitly requested"
  - "Catalog ∩ Instagram dump key collisions log once at warning and embed each physical row once using catalog-first ordering in the union list"

requirements-completed:
  - CACHE-01

duration: 40min
completed: "2026-04-27"
---

# Phase 8 Plan 03: Instagram embed extension D-01 Summary

**Instagram dump media keys gain first-class CLIP vec0 rows via `batch_embed_image` (`catalog_and_instagram`), with DB backlog helpers and fingerprint scope so catalog-only checkpoints cannot resume union runs.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-04-27T20:25:00Z (approx.)
- **Completed:** 2026-04-27T21:05:51Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Listed Instagram dump rows missing CLIP embeddings using the same vec0 presence rule as catalog listings, with date-window SQL aligned to existing dump `date_folder` conventions.
- Normalized `fingerprint_batch_embed_image` payload `image_type` to `catalog` | `catalog_and_instagram` so resume identity follows D-01 scope.
- Extended `_handle_batch_embed_image_inner` to build a deduped catalog-first work list, classify paths from `images` or `instagram_dump_media`, and emit a warning when catalog and dump share keys.

## Task Commits

1. **Task 1: Database helpers for Instagram CLIP backlog** — `191356d` (feat)
2. **Task 2: Extend fingerprint_batch_embed_image for scope** — `7415387` (feat)
3. **Task 3: Branch _handle_batch_embed_image_inner for catalog_and_instagram** — `467383d` (feat)

## Files Created/Modified

- `lightroom_tagger/core/database.py` — `_list_instagram_dump_clip_embed_sql_params`, `list_instagram_dump_keys_needing_clip_embedding`, `list_instagram_dump_keys_for_clip_embed_force`
- `apps/visualizer/backend/jobs/checkpoint.py` — `_normalized_batch_embed_image_type`, fingerprint payload uses canonical scope
- `apps/visualizer/backend/jobs/handlers.py` — union work list, dual-table `classify_path`, strict `image_type` gate
- `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` — IG backlog unit test, fingerprint scope test, union embed integration test

## Decisions Made

- Unknown `image_type` strings fail the job with an explicit message rather than silently coercing to union scope (union requires `catalog_and_instagram`).
- `min_rating` continues to apply only to catalog keys in SQL; Instagram dump rows do not participate in rating filtering (schema has no rating).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CACHE-01 UI/composite chain (Wave 08-04) can enqueue `batch_embed_image` with `metadata.image_type: catalog_and_instagram` so Instagram seeds participate in the embed stage before stack/similarity.

## Verification

Plan `<verification>`: Extended embed tests cover Instagram scope and fingerprint differentiation; handler branches on `catalog_and_instagram`.

Commands (PASS):

```text
cd /Users/ccanales/projects/lightroom-tagger && uv run python -m pytest apps/visualizer/backend/tests/test_handlers_batch_embed_image.py -q --tb=short
```

Result: **15 passed**

```text
cd /Users/ccanales/projects/lightroom-tagger && uv run python -m pytest apps/visualizer/backend/tests/test_handlers_single_match.py -q --tb=short
```

Result: **11 passed**

### Self-check task gates

- `grep -n 'def list_instagram_dump_keys_needing_clip_embedding' lightroom_tagger/core/database.py` → match present.
- Handler references `catalog_and_instagram` and `list_instagram_dump_keys_needing_clip_embedding` in `handlers.py`.
- `grep -n "batch_embed_image only supports" apps/visualizer/backend/jobs/handlers.py` → no matches (removed).
- Fingerprint test asserts differing hashes when only embed scope changes between catalog and union.

---

## Self-Check: PASSED

---
*Phase: 08-embedding-prefilter-and-cache-pipeline · Plan 08-03 · Completed: 2026-04-27*
