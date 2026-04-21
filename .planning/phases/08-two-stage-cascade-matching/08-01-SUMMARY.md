---
phase: 8
plan: "01"
status: complete
---

# Summary: Phase 8-01 — SQL JOIN + compare_descriptions_batch

## What was built

- **`find_candidates_by_date`** now loads catalog rows with a `LEFT JOIN` to `image_descriptions` for `image_type = 'catalog'`, exposing AI text as **`ai_summary`** (`COALESCE(d.summary, '')`) without overwriting Lightroom **`description`**.
- **`compare_descriptions_batch`** mirrors **`compare_images_batch`**: empty candidates → `{}`, JSON-only system prompt, text-only user content (no images), same `{"results": [{"id", "confidence"}]}` contract, Claude `extra_body` / `reasoning_effort`, `_map_openai_error` on API failures, parse failures → all-zero scores per candidate.

## Key files

- lightroom_tagger/core/matcher.py — LEFT JOIN ai_summary
- lightroom_tagger/core/vision_client.py — compare_descriptions_batch
- lightroom_tagger/core/test_description_batch.py — 4 unit tests

## Self-Check: PASSED

## Test results

```
$ python -m pytest lightroom_tagger/core/test_description_batch.py -q
....                                                                     [100%]
4 passed in 0.26s
```
