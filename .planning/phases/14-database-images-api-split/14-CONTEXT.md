# Phase 14: Database & Images API split - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Split two oversized modules:
- `lightroom_tagger/core/database.py` (3,557 lines) → 10-module subpackage (REFACTOR-02)
- `apps/visualizer/backend/api/images.py` (1,954 lines) → 6-module subpackage (REFACTOR-03)

Zero behavior change per commit. All tests must remain green after each individual commit.
No new job types, no logic changes. URL prefix migration for `images.py` Blueprints is
explicitly in scope (see D-09).

</domain>

<decisions>
## Implementation Decisions

### database.py split (REFACTOR-02)

- **D-01:** 10-module split under `lightroom_tagger/core/database/`:
  - `db_init.py` — `init_database`, all `_migrate_*` functions, `_dict_factory`, `_ensure_sqlite_vec_loaded`, `_migrate_add_column`, schema helpers
  - `catalog.py` — `store_image`, `store_images_batch`, `get_image`, `query_catalog_images`, `query_catalog_images_by_keys`, `filter_order_keys_in_catalog`, `get_all_images`, `get_image_count`, `delete_image`, `clear_all`, `search_by_*`, `generate_key`, `catalog_key_is_primary_grid_row`
  - `instagram.py` — `update_instagram_status`, `search_by_instagram_posted`, `get_images_without_hash`
  - `matches.py` — `get_rejected_pairs`, `apply_instagram_match_to_stack_members`, `catalog_has_instagram_match_conflict`
  - `descriptions.py` — `store_image_description`, `get_image_description`, `get_undescribed_catalog_images`, `get_undescribed_instagram_images`, `get_all_images_with_descriptions`, `build_description_search_document`, `build_description_fts_query`
  - `scores.py` — `insert_image_score`, `supersede_previous_current_scores`, `get_current_scores_for_image`, `list_score_history_for_perspective`, `list_all_scores_for_image`, `list_perspectives`, `get_perspective_by_slug`, `insert_perspective`, `update_perspective`, `delete_perspective`
  - `stacks.py` — `stack_metadata_for_api`, `catalog_image_stack_row_fields`, `stack_split_member_out`, `stack_merge_into`, `stack_set_representative`, `select_stack_representative_key_for_keys`, `list_catalog_stack_member_keys`, `StackMutationError`
  - `embeddings.py` — `upsert_image_text_embedding`, `upsert_image_clip_embedding`, `list_catalog_keys_needing_text_embedding`, `list_catalog_keys_for_text_embed_force`, `list_catalog_keys_needing_clip_embedding`, `list_catalog_keys_for_clip_embed_force`, `list_instagram_dump_keys_needing_clip_embedding`, `list_instagram_dump_keys_for_clip_embed_force`, `count_catalog_images_missing_text_embedding`, all `_embeddable_*` / `_list_catalog_keys_*_sql_params` helpers
  - `similarity.py` — `insert_catalog_similarity_group`, `list_clip_embedded_catalog_keys_newest_first`, `clear_catalog_similarity_results`, `get_catalog_image_similar`, `list_catalog_similarity_groups`
  - `vision_cache.py` — `init_vision_cache_table`, `init_vision_comparisons_table`, `get_vision_cached_image`, `store_vision_cached_image`, `is_vision_cache_valid`, `get_cache_stats`, `get_vision_comparison`, `store_vision_comparison`

- **D-02:** `__init__.py` re-exports the full public surface of all submodules so existing callers (`from lightroom_tagger.core.database import store_image` etc.) keep working without changes.

- **D-03:** `db_init.py` is the init/migration module. `__init__.py` re-exports `init_database` from it. All other submodules receive `conn: sqlite3.Connection` as a parameter — no circular imports.

- **D-04:** Single-consumer private helpers stay in their primary module (Phase 13 D-05 rule). No `common.py` needed for `database/` — there are no genuinely cross-cutting private helpers.

- **D-05:** `library_write` and `resolve_filepath` (currently in `lightroom_tagger/core/database.py`) belong to catalog mutation — move to `catalog.py`.

### test_database.py co-split (REFACTOR-02)

- **D-06:** Tests mirror the module structure 1:1. One test file per submodule:
  - `test_database_db_init.py`
  - `test_database_catalog.py`
  - `test_database_instagram.py`
  - `test_database_matches.py`
  - `test_database_descriptions.py`
  - `test_database_scores.py` (already exists — update imports)
  - `test_database_stacks.py` (absorbs `test_database_stack_collapse.py`)
  - `test_database_embeddings.py`
  - `test_database_similarity.py`
  - `test_database_vision_cache.py`
  - `test_database_nl_filter_arrays.py` stays as-is (tests filter logic, update imports)

- **D-07:** Existing test files that already have a clean scope (`test_database_scores.py`, `test_database_stack_collapse.py`, `test_database_nl_filter_arrays.py`) are renamed/updated to fit the new naming scheme rather than deleted and rewritten.

### images.py split (REFACTOR-03)

- **D-08:** 6-module split under `apps/visualizer/backend/api/images/`:
  - `catalog.py` — `/catalog`, `/catalog/<key>/thumbnail`, `/catalog/months`, `/catalog/<key>/similar`, `/catalog-similarity-groups`, `/<image_type>/<key>` fallback
  - `stacks.py` — `/stacks/<id>/members`, `/stacks/<id>/split-member`, `/stacks/<id>/merge`, `/stacks/<id>/representative`
  - `instagram.py` — `/instagram`, `/instagram/months`, `/instagram/<key>/thumbnail`, `/dump-media`
  - `matches.py` — `/matches`, `/matches/<catalog_key>/<insta_key>/validate`, `/matches/<catalog_key>/<insta_key>/reject`
  - `search.py` — `/nl-search`, `/semantic-search`, `/chat-search`
  - `common.py` — genuinely cross-cutting helpers only: `_clamp_pagination`, `_canonical_path`, `_parent_dir_if_exists`, `_is_path_under_allowed_roots`, `_instagram_thumbnail_roots`, `_catalog_thumbnail_roots`, `_filter_by_date`, `_extract_source_folder`

- **D-09 (scope expansion):** Each submodule owns its own Flask Blueprint with its own URL prefix. `app.py` registers each Blueprint individually. URL prefixes change:
  - `catalog_bp` → `/api/images/catalog`
  - `stacks_bp` → `/api/images/stacks`
  - `instagram_bp` → `/api/images/instagram`
  - `matches_bp` → `/api/images/matches`
  - `search_bp` → `/api/images/search`
  - All 42 frontend `fetch` call sites in `apps/visualizer/frontend/src/` must be audited and updated to new URL paths as part of this phase.

- **D-10:** Single-consumer helpers stay in their primary module (Phase 13 D-05 rule):
  - `_enrich_instagram_media`, `_deserialize_description` → `instagram.py`
  - `_rows_to_catalog_api_images`, `_query_catalog_rows_for_stack_member_keys`, `_clip_similarity_why_matched_line`, `_parse_clip_similar_catalog_params`, `_effective_catalog_nl_kwargs` → `catalog.py`
  - `_merge_chat_search_metadata`, `_chat_pin_context`, `_extract_images_from_tool_messages` → `search.py`

- **D-11:** `__init__.py` aggregates all 5 Blueprints and re-exports them so `app.py` can import cleanly:
  ```python
  from api.images import catalog_bp, stacks_bp, instagram_bp, matches_bp, search_bp
  ```

### Split order & atomicity (both splits)

- **D-12:** Same discipline as Phase 13 — scaffold commit first (empty submodules + `__init__.py` re-exporting everything from the original file), then one commit per domain family, tests green after each commit. Final commit removes the original flat file.

### Claude's Discretion
- Exact order of the per-family migration commits within each split
- Whether `_sort_catalog_key_rows_newest_first` and `_non_empty_str_list_for_json_array_filter` (catalog query helpers) go in `catalog.py` or a `catalog_query.py` sub-helper — planner decides based on line count
- Whether `seed_perspectives_from_prompts_dir` belongs in `scores.py` or `db_init.py` — planner reads the function body to decide

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary files being split
- `lightroom_tagger/core/database.py` — full source (3,557 lines); read entirely before planning. Domain boundaries at approximate lines: init/migrations 1–630, catalog 681–1595, instagram/matches 1596–1800, stacks 1767–2043, embeddings 2125–3275, similarity 3276–3350, vision_cache 3351–3557 (confirm with grep)
- `apps/visualizer/backend/api/images.py` — full source (1,954 lines); route boundaries per grep output in CONTEXT gathering

### Blueprint registration
- `apps/visualizer/backend/app.py` lines 131–140 — current Blueprint registrations; `images.bp` at `/api/images` is replaced by 5 new Blueprint registrations (D-09)

### Frontend API call sites (42 references — all need URL updates per D-09)
- Search `apps/visualizer/frontend/src/` for `/api/images` to enumerate all fetch call sites before starting REFACTOR-03

### Existing test files to rename/update (REFACTOR-02)
- `lightroom_tagger/core/test_database.py` (1,074 lines)
- `lightroom_tagger/core/test_database_scores.py`
- `lightroom_tagger/core/test_database_stack_collapse.py`
- `lightroom_tagger/core/test_database_nl_filter_arrays.py`

### Phase 13 patterns (follow same discipline)
- `.planning/phases/13-handlers-split-per-job-family/13-CONTEXT.md` — D-01 through D-09 establish the split pattern this phase follows
- `.planning/phases/13-handlers-split-per-job-family/13-PATTERNS.md` — file inventory, analog patterns, import registry patterns

### Cursor rules that apply
- `.cursor/rules/job-log-contract.mdc` — verify compliance preserved after split
- `.cursor/rules/job-ui-contract.mdc` — no new API surface; existing contracts unchanged (modulo URL migration)
- `.cursor/rules/backend-restart.mdc` — restart protocol after backend changes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jobs/handlers/` subpackage (Phase 13 output) — direct analog for both splits; read `__init__.py` and any family module for the exact scaffold pattern to replicate
- `jobs/checkpoint.py` — focused module pattern: module docstring, `from __future__ import annotations`, focused imports, no package `__init__` re-exports

### Established Patterns
- Phase 13 scaffold pattern: empty submodules + `__init__.py` re-exporting from original flat file as first commit, then migrate family by family
- `with_db` decorator in `images.py` — used on every route; must be importable from `common.py` or preserved per-submodule (planner confirms current location)
- `sqlite3.Connection` passed as parameter throughout `database.py` — no global state; submodules are pure function collections, no circular import risk

### Integration Points
- `lightroom_tagger/core/database.py` is imported by `lightroom_tagger/core/` services (`analyzer.py`, `matcher.py`, `description_service.py`, `scoring_service.py`, `embedding_service.py`, etc.) — `__init__.py` re-exports keep these untouched
- `apps/visualizer/backend/api/images.py` is registered in `app.py` as `images.bp` — replaced by 5 Blueprint registrations after D-09
- Frontend: 42 fetch call sites across `apps/visualizer/frontend/src/` reference `/api/images/*` paths — all need updating per D-09

</code_context>

<specifics>
## Specific Ideas

- The URL prefix migration (D-09) is an explicit scope expansion accepted by the user. The planner must include a frontend audit task as a distinct plan step — not a footnote.
- "Zero behavior change" constraint still applies to all logic; only URLs and module boundaries change.

</specifics>

<deferred>
## Deferred Ideas

- E2E testing with browser harness (TEST-03, E2E-01..E2E-06) — scoped to Phase 17 and 18, not this phase
- `cli.py` split — lower urgency, deferred to future milestone per REQUIREMENTS.md

</deferred>

---

*Phase: 14-database-images-api-split*
*Context gathered: 2026-05-06*
