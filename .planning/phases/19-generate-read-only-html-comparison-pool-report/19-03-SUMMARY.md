---
phase: "19"
plan: 19-03
subsystem: comparison-pool-report
tags:
  - cli
  - html-report
  - offline-assets
key-files:
  created:
    - lightroom_tagger/scripts/generate_comparison_pool_report.py
  modified:
    - lightroom_tagger/core/database/instagram.py
    - lightroom_tagger/core/database/__init__.py
metrics:
  tests:
    - /Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m py_compile lightroom_tagger/scripts/generate_comparison_pool_report.py
    - /Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m lightroom_tagger.scripts.generate_comparison_pool_report --help
---

# Plan 19-03 Summary

## Completed

- Added `list_comparison_pool_report_targets` for default unmatched + attempted report rows with `month`, `job_id`, `media_key`, and `limit` filters.
- Added `python -m lightroom_tagger.scripts.generate_comparison_pool_report`.
- Wrote static `report.html` plus compressed JPEGs under `assets/`.
- Kept raw filesystem paths out of the primary `<main id="lt-primary-comparison-pool">`; debug details render separately with `lt-pool-debug`.

## Commits

| Commit | Description |
|--------|-------------|
| pending | Offline comparison-pool report CLI and target query |

## Verification

- Report module compiles.
- CLI help includes `--job-id` and `--media-key`.

## Deviations

- Reconstruction was implemented with the report generator work instead of left as a placeholder, because the follow-on test plan needs the behavior.

## Self-Check: PASSED

The CLI flags, output folder layout, JPEG asset compression, escaped HTML text, primary main container, and reconstruction hook are present.
