# Plan 03-01 — Matches API dump-media thumbnails and vision_match single-image result score

**Objective:** Enrich `GET /api/images/matches` with Instagram-side data from `instagram_dump_media` when `insta_key` is not in legacy `instagram_images`, and return `best_score` on completed `vision_match` jobs when matches exist (feeds `useSingleMatch` / `ImageDetailsModal`).

## Commits (task order)

| Task | Commit | Message |
|------|--------|---------|
| 1 | `2ca1b04` | feat(03-01): join instagram_dump_media into list_matches enrichment |
| 2 | `1e6ad01` | test(03-01): assert matches list enriches instagram_image from dump table |
| 3 | `7c40777` | feat(03-01): add best_score to vision_match job result when matches exist |

## Implementation notes

- **`list_matches`:** After loading `matches`, builds `model_lookup` from `matches`, collects `insta_keys`, loads `instagram_dump_media` in chunks of 500, enriches via `_enrich_instagram_media(..., desc_lookup)` (same shape as the Instagram tab), and indexes `dump_instagram_by_key`. Per-match and per-group `instagram_image` use `instagram_lookup.get(insta_key) or dump_instagram_by_key.get(insta_key)`; individual match rows only set `instagram_image` when that resolved value is truthy.
- **`handle_vision_match`:** After a successful `match_dump_media`, builds `result_payload` as before; if `matches` is non-empty, sets `best_score` to `max(float(m.get('total_score') or 0) for m in matches)` before `runner.complete_job`.

## Deviations

- **`roadmap update-plan-progress`:** No `roadmap` CLI in this environment; `.planning/ROADMAP.md` Phase 3 plan table was updated manually to mark **03-01** **Done**.

## Verification

- `pytest apps/visualizer/backend/tests/test_match_groups.py` — exit 0.
- `pytest apps/visualizer/backend/tests/test_handlers_single_match.py` — exit 0.
- `grep -q "instagram_dump_media" apps/visualizer/backend/api/images.py` — exit 0 (within `list_matches`).
- `rg "best_score" apps/visualizer/backend/jobs/handlers.py` — matches before `runner.complete_job` inside `handle_vision_match`.
