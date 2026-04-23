---
plan: "01-02"
title: "Describe prompt and _store_structured mapping for visual tags + API JSON deserialization"
status: complete
completed: "2026-04-23"
---

## What Was Built

The describe user prompt and legacy `DESCRIPTION_PROMPT` now document **root-level** `dominant_colors`, `mood_tags`, and `has_repetition`, with matching `_DESCRIPTION_FALLBACK` defaults. `_store_structured` maps the LLM JSON into `store_image_description` using **top-level first**, then `technical.dominant_colors` or `technical.mood` fallbacks, and `has_repetition` coerced or passed through to DB coercion. `get_image_description` and the visualizer `_deserialize_description` path deserialize the two new JSON list columns for API clients.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| T01 | Extended `build_description_user_prompt` JSON template and rubric for root visual fields | f4ef974 |
| T02 | Aligned `DESCRIPTION_PROMPT` and `_DESCRIPTION_FALLBACK` in `analyzer.py` | 629be5b |
| T03 | `_store_structured` mapping + `get_image_description` JSON for `dominant_colors` / `mood_tags` | 95b880b |
| T04 | `_DESC_JSON_COLS`, null-safe `store_image_description` dicts in `match_instagram_dump.py`, unit tests | 7773619 |

## Key Files Modified

- `lightroom_tagger/core/prompt_builder.py` — Root `dominant_colors` / `mood_tags` / `has_repetition` in template; technical block note on precedence.
- `lightroom_tagger/core/analyzer.py` — Documented JSON shape and parse-failure defaults for the three root keys.
- `lightroom_tagger/core/description_service.py` — `_store_structured` computes DC/MT/HR with technical fallbacks.
- `lightroom_tagger/core/database.py` — `get_image_description` deserializes `dominant_colors` and `mood_tags`.
- `apps/visualizer/backend/api/images.py` — `_DESC_JSON_COLS` includes new JSON columns.
- `lightroom_tagger/scripts/match_instagram_dump.py` — Explicit `None` for new optional fields on inline describe storage.
- `lightroom_tagger/core/test_description_service.py` — Tests for mood fallback, color fallback, full round-trip; removed obsolete `update_instagram_status` mock (symbol no longer on module).

## Issues Encountered

- **TestMatchDumpMediaDescriptions** patched `update_instagram_status`, which is not defined on `match_instagram_dump` — tests failed before any 01-02 code change. Removed those patch lines so `pytest` matches the current script imports.

## Self-Check

- [x] All tasks executed
- [x] Each task committed individually
- [x] Tests pass (or documented)
- [x] SUMMARY.md created
