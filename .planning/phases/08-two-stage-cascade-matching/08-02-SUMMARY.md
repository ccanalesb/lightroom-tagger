---
phase: 8
plan: "02"
status: complete
---

# Summary: Phase 8-02 — Two-stage cascade scoring

## What was built

- **`match_dump_media`:** Loads Instagram AI summaries from `image_descriptions` via `get_image_description`, sets `dump_image['ai_summary']`, optionally generates and stores descriptions with `generate_description` + `store_image_description` when `skip_undescribed=False` and paths exist. Catalog candidates carry `ai_summary` from `find_candidates_by_date`, with the same inline-describe path for undescribed catalog rows when allowed. `skip_undescribed` is forwarded to `score_candidates_with_vision`. Captions stay in `description`; AI summaries are not copied into `description`.

- **`score_candidates_with_vision`:** Precomputes per-candidate description similarity with `compare_descriptions_batch` when `desc_weight > 0` (respecting `skip_undescribed`). Vision compression, batch vision calls, sequential `compare_with_vision`, and `store_vision_comparison` run only when `vision_weight > 0`. When `vision_weight == 0`, scores use phash + description only with `vision_score = 0`. Final score uses nominal fixed weights (D-10): `(phash_weight * phash_score) + (desc_weight * desc_sim_01) + (vision_weight * vision_score)` — no `weight_sum` or `desc_available` renormalization.

- **Tests:** Seven new matcher tests cover vision skip, description skip, backward-compatible pure-vision scoring, nominal merge, empty-summary behavior, description-before-vision call order, and no redistribution when all summaries are empty.

## Key files

- `lightroom_tagger/core/matcher.py` — two-stage scoring, vision guard, nominal merge
- `lightroom_tagger/scripts/match_instagram_dump.py` — ai_summary loading, skip_undescribed
- `lightroom_tagger/core/test_matcher.py` — 7 new tests

## Self-Check: PASSED

## Test results

```
...............                                                          [100%]
15 passed in ~0.3s

$ python -m pytest lightroom_tagger/core/test_description_batch.py -q
....                                                                     [100%]
4 passed
```
