---
plan: "01-04"
title: "User-initiated backfill via batch_describe metadata and AnalyzeTab checkbox"
status: complete
completed: 2026-04-23
---

## What Was Built

`fingerprint_batch_describe` now includes a stable `backfill_visual_tags` boolean so checkpoints change when the user toggles backfill. Batch describe (and the describe stage of `batch_analyze` via shared `metadata` and `metadata_for_describe`) selects catalog images with an `image_descriptions` row and `dominant_colors IS NULL`, respecting the same date/rating filters as normal describe, while Instagram/both still uses the usual Instagram path. `_run_describe_pass` passes effective `force` for describe calls when backfill is on, and skips the “already described” pre-filter. The Analyze tab’s Advanced options include a **Backfill visual tags** checkbox that sends `backfill_visual_tags: true` in `batch_describe` and `batch_analyze` job metadata.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| T01 | `fingerprint_batch_describe` + checkpoint tests for `backfill_visual_tags` | 23eb0a4 |
| T02 | Catalog selection SQL, `_run_describe_pass` `describe_force` + batch_analyze shared selection, handler tests | 3697ff2 |
| T03 | `strings`, `AnalyzeTab` Advanced checkbox, Vitest for submit metadata | 5ba21a8 |

## Key Files Modified

- `apps/visualizer/backend/jobs/checkpoint.py` — `backfill_visual_tags` in `fingerprint_batch_describe` payload.
- `apps/visualizer/backend/jobs/handlers.py` — `_select_catalog_keys_missing_visual_tags`, batch describe / batch analyze selection branches, `describe_force` in `_run_describe_pass`, empty-scope `add_job_log` for backfill.
- `apps/visualizer/backend/tests/test_job_checkpoint.py` — Fingerprint coverage for backfill.
- `apps/visualizer/backend/tests/test_handlers_batch_describe.py` — Backfill selection, `force=True` to describe, empty-scope logging.
- `apps/visualizer/frontend/src/constants/strings.ts` — `ANALYZE_BACKFILL_VISUAL_TAGS_LABEL`.
- `apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` — State, Advanced checkbox, metadata on analyze + describe-only.
- `apps/visualizer/frontend/src/components/processing/__tests__/AnalyzeTab.submit.test.tsx` — Assert `backfill_visual_tags: true` when checked.

## Issues Encountered

- Backfill `add_job_log` test initially asserted the wrong tuple index for the message; fixed to `args[3]`.

## Self-Check

- [x] All tasks executed
- [x] Each task committed individually
- [x] Tests pass (or documented)
- [x] SUMMARY.md created
