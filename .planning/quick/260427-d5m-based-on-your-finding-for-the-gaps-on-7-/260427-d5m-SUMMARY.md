---
task_id: 260427-d5m
status: complete
completed: "2026-04-27"
commits:
  - 89038ad  # feat(jobs): improve log observability signal and payload hygiene
---

# SUMMARY: 260427-d5m Embed job log observability quick fix

## What was built

- Updated `.cursor/skills/investigate-job/scripts/inspect_job.py` to read from `job_logs` (instead of legacy `jobs.logs`), report total persisted log count, and show checkpoint progress from modern keys like `processed_pairs`.
- Added per-job log summary stats in `apps/visualizer/backend/database.py` and surfaced them through `list_jobs` / `get_active_jobs`:
  - `logs_total`
  - `warning_count`
  - `error_count`
  - `last_log_at`
- Added payload compaction in `apps/visualizer/backend/api/jobs.py` so large checkpoint arrays are replaced by count fields in API payloads:
  - `processed_pairs` -> `processed_pairs_count`
  - `processed_media_keys` -> `processed_media_keys_count`
  - `processed_image_keys` -> `processed_image_keys_count`
  - `processed_triplets` -> `processed_triplets_count`
- Added progress-log deduping in `apps/visualizer/backend/jobs/runner.py` so repeated identical `(progress, current_step)` updates do not flood `job_logs`.

## Verification

- Automated:
  - `/Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m pytest apps/visualizer/backend/tests/test_database.py apps/visualizer/backend/tests/test_jobs_api.py apps/visualizer/backend/tests/test_job_runner.py`
  - Result: `52 passed`
- Runtime spot checks against the live backend:
  - `inspect_job.py 7786f8fd-7c09-4aed-991e-d396eb2d4437` now reports non-zero persisted logs (`log entries 44361`).
  - `/api/jobs/` now returns summary counters and compact checkpoint metadata (`processed_pairs_count`, no raw `processed_pairs` list).
  - `/api/jobs/<id>?logs_limit=5` returns a short log tail plus full `logs_total`, with compact checkpoint fields.
