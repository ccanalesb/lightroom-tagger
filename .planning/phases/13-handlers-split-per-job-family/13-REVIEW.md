---
phase: 13
status: clean
depth: standard
files_reviewed: 8
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
---

# Phase 13 Code Review

## Summary

The monolith job-handler package has been split into family modules (`common`, `analyze`, `embed`, `instagram`, `matching`, `stacks`) with `__init__.py` re-exporting handlers into a **15-entry** `JOB_HANDLERS` map. Import graph is acyclic (`stacks` → `embed` only; `embed` does not import `stacks`). **`pytest`** was run over the eleven handler-focused test modules in scope (**115 tests**, all passing), and a direct import sanity check confirms all handler keys resolve.

No logic regressions, broken patch targets, or circular-import hazards were identified. Remaining notes are documentation and minor cleanliness only.

## Findings

### Finding 1

**Severity:** INFO  
**File:** `apps/visualizer/backend/tests/test_handlers_date_window.py`  
**Issue:** Module docstring still refers to Sphinx-style ``jobs.handlers._resolve_date_window``, but `_resolve_date_window` now lives under `jobs.handlers.common`. Not a failing test — only misleads future readers search-navigating the codebase.  
**Recommendation:** Point the reference at `jobs.handlers.common._resolve_date_window` (or use a Sphinx-friendly path if docs are generated).

### Finding 2

**Severity:** INFO  
**File:** `apps/visualizer/backend/jobs/handlers/analyze.py`, `apps/visualizer/backend/jobs/handlers/matching.py`  
**Issue:** Several inner paths assign `config = load_config()` where `config` is never read afterward (for example `_handle_batch_describe_inner`, `_handle_batch_score_inner`, `handle_single_score`, and duplicated `load_config()` calls mid-`handle_vision_match`). This is harmless at runtime but adds noise under strict linters / dead-code checks and may pre-date the split.  
**Recommendation:** Remove assignments that have no downstream use if you want a quieter tree; defer if you intentionally keep symmetry with other handlers.

### Finding 3

**Severity:** INFO  
**File:** `apps/visualizer/backend/jobs/handlers/stacks.py` → `apps/visualizer/backend/jobs/handlers/embed.py`  
**Issue:** `_handle_catalog_cache_build_inner` calls private `_handle_batch_embed_image_inner` from another module — a deliberate coupling for the composite job, but it ties stack/catalog-cache behavior to embed internals.  
**Recommendation:** Accept as-is unless you prefer a tiny public façade (for example `@internal` facade on `embed` or moving shared “inner” orchestration behind a neutral helper) for navigation and future refactors.

## Verification Notes (not counted as findings)

- **Patches:** Tests patch symbols where they are resolved (`jobs.handlers.analyze.*`, `jobs.handlers.embed.*`, `jobs.handlers.matching.*`, `jobs.handlers.stacks.*`, `jobs.handlers.common.require_library_db`) — aligned with Phase 13 layout after the split (`test_handlers_date_window.py` correctly patches `common.require_library_db` used by `_resolve_library_db_or_fail`).
- **`JOB_HANDLERS`:** All **15** expected job types registered; ordering in the dict differs from alphanumeric sort only — dispatcher uses keys, so immaterial.
- **`__all__`:** Narrowed to `('JOB_HANDLERS',)` — `from jobs.handlers import handle_batch_describe` still works via normal submodule imports from `__init__.py`; only `from jobs.handlers import *` is constrained.
