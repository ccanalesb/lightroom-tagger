---
created: 2026-04-11T16:17:19.478Z
title: Improve vision pipeline safety nets and SR2 support
area: tooling
files:
  - lightroom_tagger/core/analyzer.py:13
  - lightroom_tagger/core/vision_cache.py:48-96
  - lightroom_tagger/core/matcher.py:250-283
  - lightroom_tagger/core/vision_client.py:152-289
---

## Problem

Three compounding issues discovered during job `17975aa0` (vision_match, year=2025, gpt-5-mini):

### 1. Missing RAW format: `.sr2` not in RAW_EXTENSIONS
`RAW_EXTENSIONS` in `analyzer.py:13` lists `.arw` (Sony newer) and `.srw` (Samsung) but not `.sr2` (Sony Raw 2). ~70+ SR2 files in the catalog bypass the RAW-to-JPG conversion pipeline entirely. `get_viewable_path` returns the original 20MB `.sr2` path, `compress_image` (PIL) can't open it and falls back to original, and `get_or_create_cached_image` stores the 20MB original as the "cached" path.

### 2. No size validation on cached images
`get_or_create_cached_image` (vision_cache.py:93-96) silently stores the original file path when both `get_viewable_path` and `compress_image` return the original. There is no check on the resulting file size. A 20MB "cached" image enters the batch pipeline unchallenged.

### 3. No pre-flight size filtering in batch pipeline
`score_candidates_with_vision` builds `batch_candidates` (matcher.py:204-237) without checking cached image sizes. Oversized candidates enter `_call_batch_chunk`, which:
- Sends 10 candidates → 413 PayloadTooLargeError
- Recursively halves: 5 → 413, 2 → 413, 1 → still 413
- Logs "single-item chunk still too large, skipping" per candidate

In job `17975aa0`: 4,110 "single-item too large" warnings + 4,236 "413 splitting" warnings across 19 images. Each oversized candidate triggers ~4 wasted API calls before being skipped.

### Additional improvements needed
- Log deduplication: "single-item too large" is logged 10x per batch (once per retry), should be 1x
- Failed candidates from size errors should be flagged in the DB so future runs skip them
- The `reasoning_effort: "none"` fix is now Claude-only, but other models may need similar per-model extra_body tuning — consider a model capabilities registry

## Solution

1. **Add `.sr2` to `RAW_EXTENSIONS`** — simple one-liner, enables rawpy conversion for Sony Raw 2 files
2. **Add max cached size threshold** in `get_or_create_cached_image` — if the "cached" file exceeds e.g. 500KB, log a warning and return None (or a sentinel) so callers know it's unusable for vision APIs
3. **Pre-filter batch candidates by cached size** — before building `batch_candidates`, check file size and skip candidates above threshold, logging once per image how many were filtered
4. **Rebuild cache for SR2 files** — after adding `.sr2` support, incrementally rebuild cache entries for affected files
5. **Consider a model capabilities/config registry** — per-model settings for `extra_body`, max payload size, batch size preferences
