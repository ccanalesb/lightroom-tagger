---
plan: 01
status: complete
completed: 2026-04-17
requirements: [JOB-04, JOB-05]
commits:
  - a1e6996 feat(jobs-api): paginate list and add logs_limit param (02-01)
  - e17af92 test(jobs-api): cover pagination envelope and logs_limit (02-01)
key-files:
  modified:
    - apps/visualizer/backend/database.py
    - apps/visualizer/backend/api/jobs.py
    - apps/visualizer/backend/tests/test_jobs_api.py
---

## Summary

Backend jobs API now returns the canonical `success_paginated()` envelope on `GET /api/jobs/` and supports optional `?logs_limit=N` truncation on `GET /api/jobs/<id>` with a `logs_total` field always populated on the payload. This plan also adds the `count_jobs(db, status)` helper next to `list_jobs` and extends `list_jobs` with an `offset` parameter.

## What changed

**`database.py`**
- `list_jobs(db, status=None, limit=50, offset=0)` — adds `offset` parameter; both SQL branches now use `LIMIT ? OFFSET ?`.
- `count_jobs(db, status=None) -> int` — new helper, mirrors the filter shape of `list_jobs`, returns a single integer using the existing `_dict_factory` row format.

**`api/jobs.py`**
- Import `count_jobs` from `database` and `success_paginated` from `utils.responses`.
- `list_all_jobs` now parses `status` / `limit` / `offset` query params (defaults `50` / `0`), clamps `limit` to `[1, 500]` and `offset` to `>=0`, and returns `success_paginated(jobs, total=total, offset=offset, limit=limit)` — same envelope used by `api/images.py`, `api/analytics.py`, and `api/identity.py`.
- `get_job_details` now reads an optional `?logs_limit` query param:
  - omitted → unlimited logs, `logs_total` populated (backwards-compat).
  - `0` → unlimited logs, `logs_total` populated (expand path).
  - `N > 0` → clamp to `[1, 10_000]`, return the most recent `N` entries via `logs[-effective_limit:]`.

**`tests/test_jobs_api.py`**
- `test_list_jobs` updated to assert the envelope shape (`data`, `total`, `pagination.current_page=1`, `pagination.limit=50`, `pagination.offset=0`, `pagination.has_more=False`).
- Six new tests: `test_list_jobs_respects_limit_and_offset`, `test_list_jobs_total_count_matches_status_filter`, `test_list_jobs_default_limit_50`, `test_get_job_truncates_logs_when_logs_limit_set`, `test_get_job_logs_limit_zero_returns_all`, `test_get_job_logs_total_present_when_no_param`.

## Verification evidence

- `PYTHONPATH=. .venv/bin/python -m pytest apps/visualizer/backend/tests/test_jobs_api.py -v` → 11 passed, 0 failed.
- `PYTHONPATH=. .venv/bin/python -m pytest apps/visualizer/backend/tests/` → 128 passed. One pre-existing failure in `test_providers_api.py::TestDefaults::test_should_return_defaults` (same failure noted in Phase 1 VERIFICATION.md, unrelated to Phase 2).
- Module import smoke: `from database import list_jobs, count_jobs` and `from api.jobs import bp` both resolve.

## Deviations

- **Python interpreter:** tests were run against `.venv/bin/python` (Python 3.12.13) rather than system `python3`. The plan's acceptance criteria used `PYTHONPATH=. python ...` — with the system `python3` being 3.9 on this host and the codebase using PEP 604 type syntax (`dict | None`), the project's canonical interpreter is the project's own venv. No behavioural deviation from the plan; only the interpreter alias differs.

## Self-Check: PASSED

All acceptance criteria verified. All tests pass (aside from the pre-existing unrelated `test_providers_api` failure).
