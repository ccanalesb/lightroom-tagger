---
plan: 01
title: Backend match-group sort and tombstone serialization
wave: 1
depends_on: []
files_modified:
  - apps/visualizer/backend/api/images.py
  - apps/visualizer/backend/tests/test_match_groups.py
autonomous: true
requirements:
  - POLISH-02
---

<objective>
Rewrite `list_matches` so grouped results are ordered server-side before pagination: actionable unvalidated groups first, then the reviewed bucket (validated matches and fully-rejected tombstones), with newest-first ordering within each bucket using the Instagram `created_at` → catalog `date_taken` → NULL fallback chain. Emit `all_rejected` and synthetic empty-candidate groups so the client can render tombstones after refresh.
</objective>

<context>
Implements **D-08** (server-side sort before `[offset:offset+limit]`), **D-09** (two-bucket ordering with newest-first DESC, NULLS LAST), and **D-11** (photo-date resolution chain). Synthetic empty-candidate groups and `all_rejected` are serialized here as the API contract for POLISH-02 list ordering; tombstone **UI** is implemented in plan `05-PLAN.md` only.
</context>

<tasks>
<task id="1.1">
<action>In `apps/visualizer/backend/api/images.py` inside `list_matches` (function starts line 560), after the loop that builds `match_groups` (append dict ends ~648) and **before** `_clamp_pagination` at lines 650–654: (1) For each group dict add boolean `all_rejected: False` when `len(candidates) > 0`. (2) Query exactly `SELECT DISTINCT insta_key FROM rejected_matches` (no aliases or column substitutions — column name `insta_key` per `rejected_matches` schema) and compute `insta_keys_with_matches = {insta_key from groups}`. For each `insta_key` that has ≥1 `rejected_matches` row and **no** remaining row in `matches` for that `insta_key`, append a synthetic group dict with `'candidates': []`, `'candidate_count': 0`, `'best_score': 0.0`, `'has_validated': False`, `'all_rejected': True`, `'instagram_key': insta_key`, `'instagram_image': instagram_lookup.get(insta_key) or dump_instagram_by_key.get(insta_key)` (same lookup pattern as existing enriched candidates ~624–630). (3) Define `sort_bucket(g) = 1` if `g.get('all_rejected') or g.get('has_validated')` else `0`. Define `photo_ts(g)` as: first `g['instagram_image'].get('created_at')` if `instagram_image` dict present and `created_at` truthy; else max of `c.get('catalog_image', {}).get('date_taken')` / `c.get('catalog_image', {}).get('date_taken')` from candidates (use actual sqlite row keys already mapped on enriched matches — today `catalog_image` comes from `catalog_lookup` rows keyed as `images` table dicts with `date_taken` field per `catalog_lookup` fill ~629–630); else `None` for NULLS LAST. (4) Sort `match_groups` with key `(sort_bucket ASC, photo_ts DESC with None last)` — in Python sort use `sort_bucket`, then negate timestamp or use `(sort_bucket, 0 if ts else 1, ts or '')` pattern so NULLS sort last within bucket. (5) Keep existing pagination slice on the **sorted** list at lines 650–654.</action>
<read_first>
- apps/visualizer/backend/api/images.py
- .planning/phases/01-matching-review-polish/01-CONTEXT.md
- lightroom_tagger/core/database.py (schema: `matches`, `rejected_matches`, `images.date_taken`, `instagram_dump_media.created_at`)
</read_first>
<acceptance_criteria>
- `rg -n "all_rejected" apps/visualizer/backend/api/images.py` prints at least one line inside `list_matches`
- `rg -n "sort_bucket|photo_ts" apps/visualizer/backend/api/images.py` prints helper definitions or inline sort key used for `match_groups` sort
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_match_groups.py -v` exits 0
</acceptance_criteria>
</task>

<task id="1.2">
<action>In `apps/visualizer/backend/tests/test_match_groups.py`, add `test_list_matches_sorts_unvalidated_before_validated_bucket` using the existing `_make_client` / `init_database` / `store_match` pattern: seed two `insta_key` groups — group A unvalidated with newer `instagram_images` or `instagram_dump_media.created_at`, group B validated (`validated_at` set on its match row) with older `created_at` — assert JSON `match_groups[0]['instagram_key']` is the unvalidated key. Add `test_list_matches_all_rejected_tombstone_in_validated_bucket_after_validated_group` (or shorter name under 100 chars): seed a validated group and a separate `insta_key` with only `rejected_matches` rows and no `matches` row, assert tombstone group appears **after** validated group in `match_groups` and has `'all_rejected' is True` and `'candidates' == []`.</action>
<read_first>
- apps/visualizer/backend/tests/test_match_groups.py
- apps/visualizer/backend/api/images.py (`list_matches`)
- lightroom_tagger/core/database.py (`store_match`, `reject_match` or raw SQL for `rejected_matches` inserts)
</read_first>
<acceptance_criteria>
- `pytest apps/visualizer/backend/tests/test_match_groups.py -k "sorts_unvalidated or tombstone"` exits 0 (adjust `-k` substring to match actual test function names)
- New test functions contain assert on `'all_rejected'` key for tombstone case
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_match_groups.py -v` exits 0
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_match_groups.py -k sort` exits 0 (or full file if no `-k` match)
- Manual: `curl -s 'http://localhost:5001/api/images/matches?limit=5&offset=0'` (when backend running) returns JSON whose first `match_groups` entry has `has_validated` false and `all_rejected` false when such data exists — optional; pytest sufficient for CI
</verification>

<must_haves>
- Matches list API returns groups in an order consistent with roadmap Phase 1 success criterion 3 (unvalidated before reviewed, newest-first within bucket per `created_at` / fallback).
- Pagination applies **after** the new ordering in `list_matches`.
- Fully-rejected Instagram keys with no remaining `matches` rows can still appear as `match_groups` entries with `candidates: []` and `all_rejected: true` for downstream UI.
</must_haves>
