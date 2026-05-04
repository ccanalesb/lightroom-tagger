---
phase: 06-similarity-stack-ui
plan: 3
subsystem: api
tags: [flask, clip, stacks, SIM-02, STACK-03, pytest]

requires:
  - plan: 06-02-PLAN
    provides: run_clip_similar_for_seed, NoClipEmbeddingError, filter_order_keys_in_catalog
provides:
  - GET /api/images/catalog/{key}/similar (CLIP KNN + catalog DTOs + meta.clip_model_id)
  - GET /api/images/stacks/{stack_id}/members (full burst strip, ordered by image_key ASC)
  - Normalized stack_id / stack_member_count / is_stack_representative on catalog-shaped DTOs
affects:
  - 06-04 frontend similar/stack UI
  - Phase 7 reuse (D-02, D-04)

tech-stack:
  added: []
  patterns:
    - "One run_clip_similar_for_seed(limit=500,offset=0) then in-process pagination; total=len(full_pairs)"
    - "_query_catalog_rows_for_stack_member_keys mirrors by-keys SQL without primary-grid WHERE so non-rep members appear in stack strip"
    - "Import _deserialize_row for duplicated by-keys SQL in Flask layer"

key-files:
  created:
    - apps/visualizer/backend/tests/test_images_clip_similar_api.py
  modified:
    - apps/visualizer/backend/api/images.py

key-decisions:
  - "Stack members endpoint uses SQL without grid-collapse predicate; default query_catalog_images_by_keys would drop non-representative burst keys and break the stack strip (documented in code)."
  - "best_photos / identity: no API change; rank_best_photos (06-01) already attaches stack_id, stack_member_count, is_stack_representative."

patterns-established:
  - "404 missing CLIP row: exact error string Visual similarity is unavailable (06-UI-SPEC)"

requirements-completed: [SIM-02, STACK-03]

duration: 45min
completed: 2026-04-25
---

# Phase 6 Plan 3: Similarity & stack server API summary

**Flask routes for CLIP-only similar images and stack member strips, with catalog DTOs carrying stack metadata and pytest coverage for 404/200 contracts.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-04-25T00:00:00Z (approx.)
- **Completed:** 2026-04-25
- **Tasks:** 2
- **Files modified:** 2 (API + test module) + this summary

## Accomplishments

- `GET /api/images/catalog/<path:image_key>/similar` maps `NoClipEmbeddingError` to 404 with `{"error": "Visual similarity is unavailable"}`; success returns `images`, `total`, `meta` (including `clip_model_id` / `clip_embed_dim`), per-image `similarity`, `why_matched` (`Visual match (NN%)`), and `thumbnail_url`.
- `GET /api/images/stacks/<int:stack_id>/members` returns `items` in `image_key` ASC order; unknown stack → `error_not_found('stack')` (message contains `stack`).
- `_rows_to_catalog_api_images` normalizes `stack_id`, `stack_member_count`, and `is_stack_representative` for JSON clients.

## Task Commits

1. **Task 1–2: Routes, DTOs, tests** — `9696371` (`feat(06-03): CLIP similar and stack members API with tests`)
2. **Metadata:** `docs(06-03): complete similarity-stack API plan summary` (hash: see `git log -1 --oneline` for the summary file commit)

## Files Created/Modified

- `apps/visualizer/backend/api/images.py` — `get_catalog_image_similar`, `get_stack_members`, `_parse_clip_similar_catalog_params`, `_query_catalog_rows_for_stack_member_keys`, stack DTO block in `_rows_to_catalog_api_images`.
- `apps/visualizer/backend/tests/test_images_clip_similar_api.py` — 404/200 similar, members ordering, unknown stack, catalog `stack_member_count` on representative row.

## Decisions Made

- Stack strip must include non–primary-grid members, so the route uses helper SQL matching `query_catalog_images_by_keys` columns/joins but **without** the `(m_st … OR i.key = representative)` filter from the default catalog by-keys path.

## Deviations from Plan

### Auto-fixed / intentional adjustments

**1. Stack members query helper vs. plan “use `query_catalog_images_by_keys`”**
- **Found during:** Task 1 (stack members route)
- **Issue:** `query_catalog_images_by_keys` applies primary-grid collapse and **omits** non-representative stack members, which is incorrect for a burst “strip” listing all keys.
- **Fix:** Added `_query_catalog_rows_for_stack_member_keys` in `images.py` (same SELECT/joins, `WHERE i.key IN (...)` only) and documented in the helper docstring.
- **Files modified:** `apps/visualizer/backend/api/images.py`
- **Verification:** `test_stack_members_includes_both_keys_ordered` expects both rep and non-rep keys.

**2. `identity.py`**
- **None:** `rank_best_photos` already adds the three stack keys (06-01). No file change.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Browser/Electron client (06-04) can call documented routes; `meta.clip_model_id` is stable (`clip-ViT-B-32` in tests).

## TDD Gate Compliance

Not applicable (plan `type: execute`).

## Threat Flags

No additional surface beyond the plan’s trust boundaries: `get_image` guards unknown keys; `stack_id` is validated via `int` route + DB lookup.

## Self-Check: PASSED

- `apps/visualizer/backend/tests/test_images_clip_similar_api.py` exists; `pytest tests/test_images_clip_similar_api.py` passes (5 tests).
- `rg "/similar" apps/visualizer/backend/api/images.py` and `rg "stacks" … "members"` match routes.
- `9696371` is the feat commit; docs commit is the tip that adds this `06-03-SUMMARY.md`; `test_images_clip_similar_api.py` present.

---
*Phase: 06-similarity-stack-ui*
*Completed: 2026-04-25*
