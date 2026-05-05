---
plan: 13-01
phase: 13
status: complete
---

# 13-01 Summary: Scaffold handlers/ package

## What was built
Replaced flat `jobs/handlers.py` with `jobs/handlers/` package. All handler code lives in `_legacy.py`. Package `__init__.py` imports `path_setup` once, then **exec-compiles** `_legacy.py` into the `jobs.handlers` namespace so `unittest.mock.patch('jobs.handlers.*')` hits the same globals handler bodies use (matching the old single-module layout). Empty family stub modules were added (`analyze`, `common`, `embed`, `instagram`, `matching`, `stacks`).

## Key files created
- `apps/visualizer/backend/jobs/handlers/__init__.py`
- `apps/visualizer/backend/jobs/handlers/_legacy.py`
- `apps/visualizer/backend/jobs/handlers/common.py` (stub)
- `apps/visualizer/backend/jobs/handlers/analyze.py` (stub)
- `apps/visualizer/backend/jobs/handlers/embed.py` (stub)
- `apps/visualizer/backend/jobs/handlers/instagram.py` (stub)
- `apps/visualizer/backend/jobs/handlers/matching.py` (stub)
- `apps/visualizer/backend/jobs/handlers/stacks.py` (stub)
- `.planning/phases/13-handlers-split-per-job-family/HANDLERS-SHIM-EXPORTS.txt`

## Verification
- Full pytest: passed (341 tests)
- Smoke import `from jobs.handlers import JOB_HANDLERS` with 15 keys: passed
- `handlers.py` deleted, only `handlers/` package exists: confirmed
- `_legacy.py`: no `path_setup`; `from ..checkpoint import` present: confirmed

## Self-Check: PASSED
