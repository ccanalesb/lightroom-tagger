# Phase 6: Scoring pipeline & catalog score UX — Context

**Gathered:** 2026-04-12 (auto-discuss / planner defaults)  
**Status:** Ready for execution planning

<domain>
## Phase Boundary

End-to-end **scoring jobs** that call the vision stack, validate output with Phase 5’s `parse_score_response_with_retry` + `make_score_json_llm_fixer`, and persist one row per image × perspective × rubric version into `image_scores`. **Read APIs and UI** expose current scores, model/prompt-version metadata, and historical rows after rubric changes. **Catalog list** gains SQL-backed filter/sort by persisted scores (consuming normalized columns and indexes from Phase 5). This phase does **not** change the legacy multi-perspective describe JSON schema or `parse_description_response` behavior.
</domain>

<decisions>
## Implementation Decisions

### Scoring vs describing
- **D-20:** Scoring uses **one vision call per (image, perspective_slug)** so the model returns a single object matching :class:`lightroom_tagger.core.structured_output.ScoreResponse` (`perspective_slug`, `score`, `rationale`). Batch jobs loop perspectives outer or inner, but each LLM response is validated independently before any write.
- **D-21:** Scoring reuses the same **provider + FallbackDispatcher** path as descriptions: `generate_description(client, model, image_path, user_prompt=...)` for the vision call; **no** `parse_description_response` on this path.

### Prompt assembly & rubric versioning
- **D-22:** Add `build_scoring_user_prompt(perspective_row: dict) -> str` in `lightroom_tagger/core/prompt_builder.py` — includes that perspective’s `display_name`, `slug`, and `prompt_markdown`, plus a fixed **JSON-only** contract matching `ScoreResponse` keys and the 1–10 rubric (aligned with Phase 5 score schema, not the full describe template in `build_description_user_prompt`).
- **D-23:** **`prompt_version`** stored on each `image_scores` row is a **deterministic fingerprint** of the perspective content at scoring time, e.g. `f"{slug}:{sha256(prompt_markdown_utf8).hexdigest()[:16]}"` (document exact formula in code). Editing `perspectives.prompt_markdown` in the UI changes the fingerprint, so re-scoring inserts new rows; older rows stay queryable with `is_current=0` after supersede.

### Persistence funnel (single write path)
- **D-24:** All successful score writes go through: `supersede_previous_current_scores(conn, image_key, image_type, perspective_slug, new_prompt_version)` → `insert_image_score(conn, row_dict)` inside one library DB transaction per persisted perspective score. Set `repaired_from_malformed=1` when `parse_score_response_with_retry` returns `repaired_flag True`.
- **D-25:** **`model_used`** label matches describe jobs: `provider_id:model_id` when the dispatcher returns both (mirror `description_service` / `_describe_image_via_provider` conventions).

### Idempotency & force
- **D-26:** With **`force=False`**, if a row already exists for `(image_key, image_type, perspective_slug, prompt_version)` with `is_current=1`, **skip** that scoring unit (no duplicate vision call). With **`force=True`**, remove or replace rows for that exact quadruple before insert so operators can refresh scores for the same rubric revision without UNIQUE constraint failures.

### Job types & checkpointing
- **D-27:** New job types: **`single_score`** (metadata: `image_key`, `image_type`, `perspective_slugs` list, `force`, optional `provider_id` / `provider_model`) and **`batch_score`** (same selection knobs as `batch_describe`: `image_type`, `date_filter`, `min_rating`, `max_workers`, `force`, `perspective_slugs`, providers).
- **D-28:** **`batch_score`** uses `runner.persist_checkpoint` with `job_type: 'batch_score'`, a new **`fingerprint_batch_score`** in `checkpoint.py` (canonical JSON including sorted `perspective_slugs`, providers, date/min_rating/force/image_type, and ordered work list), and a processed set of **triplets** `f"{key}|{itype}|{slug}"` for completed work units. Orphan recovery (existing `_recover_orphaned_jobs`) applies automatically when `checkpoint_version == 1`.

### API shape
- **D-29:** New REST routes under **`/api/scores`** (dedicated blueprint) to avoid overloading `descriptions` and to keep catalog `images` blueprint focused on listing/thumbnails. Example: `GET /api/scores/<path:image_key>?image_type=catalog` returns `{ current: [...] }`; `GET /api/scores/<path:image_key>/history?image_type=catalog&perspective_slug=street` returns all rows for that slice ordered by `scored_at DESC`.
- **D-30:** JSON field names for score rows over the wire match `perspectives.py` header comment: `image_key`, `image_type`, `perspective_slug`, `score`, `rationale`, `model_used`, `prompt_version`, `scored_at`, `is_current`, `repaired_from_malformed`, plus `id` when present.

### Catalog filter/sort
- **D-31:** Extend `query_catalog_images` with optional **`score_perspective`** (slug), **`min_score`** (1–10), and **`sort_by_score`** (`asc` | `desc` | none). Implement via `LEFT JOIN image_scores` on `is_current=1` and matching `perspective_slug`. Images with no score for that perspective sort after scored rows when sorting desc (SQLite-safe ordering with `score IS NULL` sentinel).

### UI placement
- **D-32:** **Processing → Descriptions** tab (or adjacent section in the same tab): add **“Score images”** controls mirroring batch describe (sources, date window, perspectives checkboxes, workers, provider selects) calling `JobsAPI.create('batch_score', metadata)` — keeps operator workflow next to describe. Single-image **Score** action lives in **`CatalogImageModal`** beside description generate (reuse `JobsAPI.create('single_score', ...)` + `useJobSocket` refresh pattern).
- **D-33:** Score panel in **`CatalogImageModal`** shows current scores (badges or list), **model_used** and **prompt_version** per row, collapsible **history** per perspective (from history endpoint). Follow `DESIGN.md` tokens (surface, border, text-secondary).

### Claude’s discretion (resolved defaults)
- **Triplet checkpoint keys** preferred over nested dicts for simpler resume merging.
- **New module** `lightroom_tagger/core/scoring_service.py` owns `score_catalog_image_perspective` / `score_instagram_dump_perspective` (names at implementer’s choice) so `description_service.py` stays describe-focused.

</decisions>

<canonical_refs>
## Canonical References

**Phase 5 handoff (must stay compatible)**
- `lightroom_tagger/core/database.py` — `insert_image_score`, `supersede_previous_current_scores`, `get_current_scores_for_image`, `get_perspective_by_slug`, `list_perspectives`
- `lightroom_tagger/core/structured_output.py` — `ScoreResponse`, `parse_score_response_with_retry`, `StructuredOutputError`
- `lightroom_tagger/core/vision_client.py` — `generate_description`, `complete_chat_text`, `make_score_json_llm_fixer`
- `lightroom_tagger/core/prompt_builder.py` — `build_description_user_prompt` (reference only; scoring uses new builder)
- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_batch_describe`, `CHECKPOINT_VERSION`
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_describe`, `handle_single_describe`, `_describe_single_image`, `JOB_HANDLERS`
- `apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx` — describe job + `DescriptionsAPI` pattern
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` — batch job metadata pattern

</canonical_refs>

<code_context>
## Existing Code Insights

- Describe path uses `FallbackDispatcher.call_with_fallback(operation="describe", ...)`; scoring should use the same dispatcher with a `fn_factory` that returns a lambda calling `generate_description(..., user_prompt=scoring_prompt)`.
- `query_catalog_images` already `LEFT JOIN image_descriptions` for `analyzed`; score filters add a second optional join or subquery — keep one query for count + page to preserve pagination correctness.
- Catalog modal already listens for `single_describe` job completion via `useJobSocket`; replicate for `single_score`.

</code_context>

---

*Phase: 06-scoring-pipeline-catalog-ux*
