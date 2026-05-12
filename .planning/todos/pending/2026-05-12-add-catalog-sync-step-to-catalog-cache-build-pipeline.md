---
created: 2026-05-12T17:11:41.945Z
title: Add catalog sync step to catalog_cache_build pipeline
area: pipeline
files:
  - lightroom_tagger/lightroom/reader.py:194-236
  - lightroom_tagger/core/cli.py:65-130
  - apps/visualizer/backend/jobs/handlers/stacks.py:608-757
  - apps/visualizer/backend/jobs/handlers/__init__.py
  - apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx
---

## Problem

`catalog_cache_build` (embed → stack → similarity) operates only on what's already
in `library.db`. There is no step that re-reads the `.lrcat` file and syncs new or
updated images first. As a result, images added to Lightroom after the last manual
`lightroom-tagger scan` run are invisible to the entire pipeline.

Discovered during investigation of `L1007724.DNG` not appearing after being added
to the catalog: `library.db` had 38,887 images while `.lrcat` had 39,316 — 429 new
images were silently missing. The only workaround today is running the CLI manually:

```bash
LIGHTRoom_CATALOG_LOCKING_MODE=NORMAL .venv/bin/python3 -m lightroom_tagger.core.cli scan \
  --catalog /Users/ccanales/lightroom/FinalCatalog/FinalCatalog-v13-3.lrcat \
  --db /Users/ccanales/projects/lightroom-tagger/library.db
```

This requires Lightroom to be open (WAL mode) so `locking_mode=EXCLUSIVE` must be
overridden with `NORMAL`.

## Solution

Add a `catalog_sync` stage as the first step of `catalog_cache_build` (before embed).
It should:

1. Read catalog path from config (`config.yaml` → `catalog_path`)
2. Call `get_image_records()` from `lightroom_tagger/lightroom/reader.py` with
   `LIGHTRoom_CATALOG_LOCKING_MODE=NORMAL` equivalent (open `mode=ro`, no exclusive lock)
3. Call `store_images_batch()` to upsert only new/changed records into `library.db`
4. Log how many images were added/updated vs already present
5. Expose it as a standalone `catalog_sync` job type in `JOB_HANDLERS` so it can
   also be triggered independently from the UI pipeline rows in `CatalogCacheTab.tsx`

Edge cases to handle:
- Lightroom has the catalog open (WAL) → use `mode=ro` URI, skip `EXCLUSIVE` locking
- Catalog path not configured → skip sync step with a warning log, continue pipeline
- Catalog file missing/locked → fail gracefully with `error_severity=warning`, continue
