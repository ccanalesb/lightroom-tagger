---
plan: 13-07
phase: 13
status: complete
---

# 13-07 Summary: Extract analyze.py, delete _legacy.py

## What was built
Moved analyze/describe/score family to `analyze.py`. Rewrote `__init__.py` with explicit imports from all 6 family modules (no exec(), no _legacy). Deleted `_legacy.py`. Phase 13 handlers split complete.

## Final structure
- `common.py` — cross-family helpers (5 functions, 4 constants)
- `instagram.py` — analyze_instagram, instagram_import
- `embed.py` — batch_embed_image, batch_text_embed + inner helpers + constants
- `matching.py` — vision_match, enrich_catalog, prepare_catalog + helpers
- `stacks.py` — batch_stack_detect, batch_catalog_similarity, catalog_cache_build + helpers
- `analyze.py` — batch_describe, single_describe, batch_score, single_score, batch_analyze + helpers
- `__init__.py` — explicit imports from all families, JOB_HANDLERS

## Key files deleted
- `apps/visualizer/backend/jobs/handlers/_legacy.py` ← DELETED

## Verification
- Full pytest: passed (341 tests)
- No `_legacy.py` exists
- `__init__.py` has no `exec()` call
- JOB_HANDLERS: 15 keys

## Self-Check: PASSED
