# Phase 10: Batch scoring fix and integration bug fixes - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix three integration bugs from the v2.0 audit: (1) `batch_score` non-force image selection queries undescribed images instead of unscored images, returning zero candidates after bulk describe; (2) `/api/identity/suggestions` parses `offset` but discards it, breaking pagination; (3) identity aggregation includes Instagram scores when all identity features are catalog-facing, risking theoretical key collisions.

</domain>

<decisions>
## Implementation Decisions

### Batch score non-force image selection (Bug 1)
- **D-01:** When `force=False`, `handle_batch_score` currently calls `get_undescribed_catalog_images` / `get_undescribed_instagram_images` — these return images without *descriptions*, not without *scores*. After bulk describe completes, this returns zero images and batch scoring queues nothing. The fix must select images that lack current scores instead.
- **D-02:** The same bug exists for the Instagram path (`get_undescribed_instagram_images` on line 1324-1327 of `handlers.py`).

### Claude's Discretion
- Approach for finding unscored images (new DB helper vs inline SQL vs per-perspective filtering at scoring time) — pick whatever is cleanest and most consistent with the existing `get_undescribed_*` pattern.

### Suggestions pagination (Bug 2)
- **D-03:** In `api/identity.py` line 77, `offset` is parsed via `_clamp_pagination` but stored as `_offset` (unused). `suggest_what_to_post_next` doesn't accept an `offset` parameter. Fix: pass `offset` into `suggest_what_to_post_next`, slice the sorted candidates list by `[offset:offset+limit]`, and return `total` (count of all candidates before slicing) in the response alongside `candidates` and `meta`.
- **D-04:** The frontend `PostNextSuggestionsPanel` should be able to use `total` for proper pagination or "load more" behavior.

### Identity key scoping (Bug 3)
- **D-05:** Filter `_SCORES_BASE_SQL` in `identity_service.py` to `AND s.image_type = 'catalog'` since all identity features (best photos, fingerprint, suggestions) are catalog-facing per Phase 8 D-40. This is a one-line fix that eliminates any theoretical key collision between catalog and Instagram image keys without requiring a compound-key refactor throughout the module.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Batch score handler
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_score` (lines ~1243-1400), specifically the non-force selection block (lines 1306-1327) that incorrectly calls `get_undescribed_*`
- `lightroom_tagger/core/database.py` — `get_undescribed_catalog_images`, `get_undescribed_instagram_images` (the wrong functions being called), plus `image_scores` table helpers

### Identity API and service
- `apps/visualizer/backend/api/identity.py` — `suggestions` endpoint (line 72-96), `_offset` discard on line 77
- `lightroom_tagger/core/identity_service.py` — `suggest_what_to_post_next` (missing offset param), `_SCORES_BASE_SQL` (missing image_type filter), `compute_image_aggregate_scores`

### Existing tests
- `apps/visualizer/backend/tests/test_handlers_batch_score.py` — existing batch score tests that mock `get_undescribed_catalog_images`
- `lightroom_tagger/core/test_identity_service.py` — existing identity service tests

### Phase context
- `.planning/phases/06-scoring-pipeline-catalog-ux/06-CONTEXT.md` — D-26 (force/idempotency), D-27/D-28 (batch_score job type and checkpointing)
- `.planning/phases/08-identity-suggestions/08-CONTEXT.md` — D-40 (catalog-facing aggregation), D-44 (suggestions candidates)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_undescribed_catalog_images` in `database.py` — pattern to mirror for an "unscored" variant (LEFT JOIN + NULL check)
- `_clamp_pagination` in `api/images.py` — already used by identity API, returns `(limit, offset)` tuple
- `fingerprint_batch_score` in `checkpoint.py` — checkpoint logic unaffected by this fix but must remain compatible

### Established Patterns
- Non-force selection in `handle_batch_describe` uses `get_undescribed_*` helpers; scoring should follow the same helper-function pattern
- Identity API returns `{ items, total, meta }` for `best-photos`; suggestions should follow the same shape after adding `total`

### Integration Points
- `handle_batch_score` non-force path (lines 1306-1327) — swap out the `get_undescribed_*` calls
- `api/identity.py` suggestions endpoint — rename `_offset` to `offset`, pass through to service
- `identity_service.py` `_SCORES_BASE_SQL` — add WHERE clause for `image_type`
- `suggest_what_to_post_next` signature — add `offset: int` parameter, slice candidates, return `total`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — these are targeted bug fixes with clear expected behavior defined in the phase success criteria.

</specifics>

<deferred>
## Deferred Ideas

- Full compound `(image_key, image_type)` keying throughout identity_service — only needed if Instagram identity features are added in a future phase. Current catalog-only filter is sufficient.

</deferred>

---

*Phase: 10-batch-scoring-fix-and-integration-bugs*
*Context gathered: 2026-04-14*
