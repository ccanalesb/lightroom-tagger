---
plan: 02
title: Validate writes catalog capture date to Instagram created_at
wave: 1
depends_on: []
files_modified:
  - lightroom_tagger/core/database.py
  - apps/visualizer/backend/tests/test_match_validation.py
autonomous: true
requirements:
  - POLISH-02
---

<objective>
When a match is validated, if the matched Instagram row has no `created_at` but the catalog image has `date_taken`, persist that date onto the Instagram side so future reads (including match sorting) see a stable timestamp — **D-12**, inside the same DB transaction as validation.
</objective>

<context>
Implements **D-12** exactly: on validate (the code path invoked from `toggle_match_validation` → `validate_match` in `lightroom_tagger/core/database.py`), when Instagram `created_at` is missing and the catalog image has `capture_date` / `date_taken`, write the catalog value into the Instagram record. The handler entry point remains `apps/visualizer/backend/api/images.py` `toggle_match_validation` (~673) calling `validate_match`; logic lives in `validate_match` so a single `db.commit()` can cover match update + Instagram update.
</context>

<tasks>
<task id="2.1">
<action>In `lightroom_tagger/core/database.py`: (1) If `instagram_images` has no `created_at` column in current `CREATE TABLE` (lines ~246–257), add `_migrate_add_column(conn, 'instagram_images', 'created_at', 'TEXT')` next to other migrations (~354–358). (2) Extend `validate_match` (starts line 1300) **before** `db.commit()`: after the `UPDATE matches SET validated_at = ?` execute, `SELECT date_taken FROM images WHERE key = ?` for `catalog_key`; load Instagram row from `instagram_images` where `key = insta_key` **or** `instagram_dump_media` where `media_key = insta_key` depending on which table holds that key (mirror how `list_matches` resolves `instagram_lookup` vs dump). If catalog `date_taken` is truthy and Instagram `created_at` is NULL/empty string, run `UPDATE` on the correct table setting `created_at = date_taken` (ISO string as stored elsewhere). (3) Keep a single final `db.commit()` for the validate operation.</action>
<read_first>
- lightroom_tagger/core/database.py (`validate_match`, `_migrate_add_column`, `init_database` migration block)
- apps/visualizer/backend/api/images.py (`toggle_match_validation`, lines 673–692)
- .planning/phases/01-matching-review-polish/01-CONTEXT.md (D-11/D-12 wording)
</read_first>
<acceptance_criteria>
- `rg -n "validate_match" lightroom_tagger/core/database.py` and file content includes `created_at` assignment or `UPDATE` tied to validate path; OR `rg "_migrate_add_column\\(conn, 'instagram_images', 'created_at'" lightroom_tagger/core/database.py` returns a line
- `python -m pytest apps/visualizer/backend/tests/test_match_validation.py -k created_at_write` exits 0 (use actual new test name in `-k`)
</acceptance_criteria>
</task>

<task id="2.2">
<action>In `apps/visualizer/backend/tests/test_match_validation.py`, add `test_validate_writes_catalog_date_to_instagram_when_created_at_missing`: extend `_seed_match` pattern or new helper that inserts `instagram_dump_media` (or `instagram_images` after migration) with `created_at` NULL, catalog `images.date_taken` set, match unvalidated; `client.patch('/api/images/matches/cat_001/ig_001/validate')`; reopen DB with `init_database`, `SELECT created_at FROM instagram_dump_media WHERE media_key = ?` or `instagram_images` as appropriate — assert column equals catalog `date_taken` date string.</action>
<read_first>
- apps/visualizer/backend/tests/test_match_validation.py
- lightroom_tagger/core/database.py (`init_database`, `validate_match`)
</read_first>
<acceptance_criteria>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_match_validation.py -v` exits 0
- New test function name appears in file (grep `def test_validate_writes` returns a line)
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_match_validation.py -v` exits 0
- `python -m pytest lightroom_tagger/core/test_database.py` only if validate_match changes ripple — run if such tests exist and reference `validate_match`; otherwise skip
</verification>

<must_haves>
- Validating a match can persist a missing Instagram `created_at` from the catalog image `date_taken` in the library DB.
- No extra HTTP route; behavior is covered by an automated test.
- Phase 1 roadmap success criterion 3 remains achievable because sort keys gain real timestamps after validate.
</must_haves>
