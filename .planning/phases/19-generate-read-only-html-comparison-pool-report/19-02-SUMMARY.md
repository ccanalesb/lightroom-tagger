---
phase: "19"
plan: 19-02
subsystem: matcher-snapshot-capture
tags:
  - matcher
  - visualizer-jobs
key-files:
  created: []
  modified:
    - lightroom_tagger/scripts/match_instagram_dump.py
    - apps/visualizer/backend/jobs/handlers/matching.py
metrics:
  tests:
    - /Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m pytest lightroom_tagger/scripts/test_match_instagram_dump.py -q
    - /Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m pytest apps/visualizer/backend/tests/test_handlers_single_match.py -q -k match_dump
---

# Plan 19-02 Summary

## Completed

- Added keyword-only `source_job_id` to `match_dump_media`.
- Persisted empty snapshots for no-candidate and empty-CLIP attempted rows.
- Persisted scored snapshots immediately after `score_candidates_with_vision`, before the cancel check and before match write transactions.
- Passed visualizer `job_id` into the matcher so report `--job-id` filters can use snapshot provenance.

## Commits

| Commit | Description |
|--------|-------------|
| pending | Matcher snapshot capture and job provenance |

## Verification

- `1 passed` for `lightroom_tagger/scripts/test_match_instagram_dump.py`.
- `3 passed, 9 deselected` for `apps/visualizer/backend/tests/test_handlers_single_match.py -k match_dump`.

## Deviations

- None.

## Self-Check: PASSED

Snapshot inserts now cover no-candidate, empty-CLIP, and post-score paths. The post-score insert runs before cancellation handling and the visualizer job UUID is stored as `source_job_id`.
