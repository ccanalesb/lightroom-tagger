---
plan: 13-03
phase: 13
status: complete
---

# 13-03 Summary: Extract instagram.py

## What was built
Moved `handle_analyze_instagram` and `handle_instagram_import` from `_legacy.py` to `instagram.py`. `_legacy.py` re-imports those handlers so `exec()` still binds them on `jobs.handlers`. `JOB_HANDLERS` is defined only in `__init__.py` after `exec()`, mapping `'analyze_instagram'` / `'instagram_import'` to `instagram` module callables. Removed unused `import_dump` import from `_legacy.py`.

## Key files modified
- `apps/visualizer/backend/jobs/handlers/instagram.py` (populated)
- `apps/visualizer/backend/jobs/handlers/_legacy.py` (removed 2 handlers + `JOB_HANDLERS`; added `from .instagram import`)
- `apps/visualizer/backend/jobs/handlers/__init__.py` (`from .instagram import`; single `JOB_HANDLERS` registry)

## Verification
- Full pytest: passed (341)
- `from jobs.handlers.instagram import handle_analyze_instagram, handle_instagram_import`: passed
- `JOB_HANDLERS['analyze_instagram'].__module__ == 'jobs.handlers.instagram'`: passed

## Self-Check: PASSED
