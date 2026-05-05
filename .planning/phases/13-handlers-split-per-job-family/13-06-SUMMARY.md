# Phase 13 wave 6 — `stacks.py` extraction (13-06)

## Objective

Moved the stacks / catalog similarity / `catalog_cache_build` composite family out of `handlers/_legacy.py` into `handlers/stacks.py`, with `_legacy.py` re-exporting symbols via `from .stacks import …` so existing `exec(_legacy.py)` wiring keeps `jobs.handlers` attributes stable.

## What shipped

- **`stacks.py`**: `_catalog_cache_stage_mapped_progress`, `_CatalogCacheStageRunner`, `_normalize_stack_detect_force`, `_parse_date_taken_utc`, `_build_burst_segments` (still in this module — not in `common.py`), `_select_stack_representative_key`, `_catalog_similarity_why_matched_line`, inner handlers and entrypoints (`handle_batch_catalog_similarity`, `handle_batch_stack_detect`, `handle_catalog_cache_build`), and constants `_CATALOG_SIMILARITY_SUMMARY_EVERY` / `_STACK_DETECT_SUMMARY_EVERY`.
- **Composite wiring**: `stacks` imports `_handle_batch_embed_image_inner` from `embed` only (one-way: `embed` does not reference `stacks`).
- **`__init__.py`**: After `exec(_legacy)`, explicit `from .stacks import` for the three public handlers (aligned with other family modules).
- **Tests**: Patches target modules where names are bound — e.g. `jobs.handlers.stacks.add_job_log` (not `jobs.handlers.add_job_log`), `jobs.handlers.stacks._handle_batch_embed_image_inner` (not `embed` alone, because `stacks` binds the import at load time), and list helpers on `jobs.handlers.stacks`.

## Verification

- `python -c` imports for `jobs.handlers.stacks`, `JOB_HANDLERS` length 15, and `import embed` + `import stacks` without cycle.
- `pytest` (full suite): **341 passed**.

## Notes

- `_build_burst_segments` remains defined in `stacks.py` only (not duplicated in `common.py`).
