# Phase 5: Structured Scoring Foundation - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Additive library DB schema for queryable per-perspective scores; photography-theory-grounded rubrics with configurable perspectives; strict structured-output validation and repair before any scoring job persists data; job checkpointing and auto-recovery so long-running jobs survive backend restarts. This phase lays the foundation — the actual scoring pipeline (triggering jobs, producing scores) is Phase 6.

</domain>

<decisions>
## Implementation Decisions

### Score Storage Schema
- **D-01:** New normalized `image_scores` table — one row per image × perspective × version. Columns include `image_key`, `perspective`, `score` (integer 1–10), `rationale` (text), `model_used`, `prompt_version`, `scored_at`. Existing `image_descriptions` table stays untouched.
- **D-02:** Per-perspective scores are queryable via standard SQL (`WHERE perspective = 'street' AND score >= 7`), enabling catalog filter/sort in Phase 6.
- **D-03:** Version history is built-in — re-running scoring with an updated rubric inserts new rows; old rows are preserved. The strategy for distinguishing "current" vs "historical" is at Claude's discretion.
- **D-04:** Relationship between `image_scores` and `image_descriptions` is at Claude's discretion (independent table vs scoring-run parent grouping).

### Perspective Registry & Rubric Design
- **D-05:** Perspectives ship as markdown files in a `prompts/perspectives/` directory — one `.md` file per perspective. These are factory defaults, version-controlled and diffable.
- **D-06:** On first run (or when the `perspectives` DB table is empty), seed the table from the `.md` files on disk. After seeding, the DB is the runtime truth — disk files are ignored.
- **D-07:** DB always wins. Once a perspective is in the DB, shipped `.md` updates do not overwrite it. User keeps full control. A "reset to defaults" action re-reads from disk.
- **D-08:** All perspectives are equal — the original three (street, documentary, publisher) have no special protected status. Users can edit, deactivate, or delete any perspective, and create new ones that work identically.
- **D-09:** Perspective editing in the UI uses a code editor component (CodeMirror or Monaco) for raw markdown editing. No WYSIWYG or markdown preview — the content is LLM instructions, not documentation.
- **D-10:** UI flow: perspectives list (name, description, active toggle) → click to edit in code editor → save writes to DB immediately → "Add perspective" provides a blank template → "Reset to default" re-reads the `.md` file for that perspective.

### Structured Output Validation & Repair
- **D-11:** Add Pydantic as a dependency. Define score response models as Pydantic classes for validation, type coercion, and error reporting.
- **D-12:** Repair-then-retry strategy: on malformed LLM output, first attempt best-effort repair (extract JSON from markdown fences, fix trailing commas, coerce types). If repair succeeds, persist with a log note. If repair fails, retry the LLM call with a stricter/simpler prompt. If the retry also fails, fail the job for that image with a clear error.
- **D-13:** Golden fixture tests demonstrate validation/repair behavior for representative malformed JSON (per SCORE-07 success criterion).

### Job Checkpointing & Resume
- **D-14:** Checkpointing applies to ALL long-running job types — new scoring handlers AND existing `handle_batch_describe` and `handle_vision_match`. Consistent behavior across the board.
- **D-15:** Checkpoint granularity (per-image vs per-batch) is at Claude's discretion.
- **D-16:** On startup, orphaned jobs with checkpoint data are auto-resumed (re-enqueued automatically). A UI notification (toast/websocket event) informs the user that jobs were recovered. Replaces the current behavior of marking orphaned jobs as failed.
- **D-17:** Jobs without checkpoint data that are found orphaned on startup are marked failed with a clear message (current behavior preserved for non-checkpointed edge cases).

### Claude's Discretion
- Score versioning strategy for current vs historical (D-03): `is_current` flag, supersede chain, timestamp-based, or other
- Scoring run grouping (D-04): independent `image_scores` table vs parent `image_scoring_runs` table
- Checkpoint granularity (D-15): per-image, per-batch, or hybrid approach
- Code editor choice: CodeMirror vs Monaco vs other lightweight option
- Exact `perspectives` table schema (columns for name, slug, description, prompt_text, active, user_modified, etc.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Score storage & perspectives
- `lightroom_tagger/core/database.py` — Current `image_descriptions` table schema (lines 221–234), `init_database` migration pattern, `store_image_description` for reference on insert/upsert conventions
- `lightroom_tagger/core/analyzer.py` — Current `DESCRIPTION_PROMPT` with existing 3 perspectives and scoring rubric (lines 39–120), `describe_image` function, JSON parsing approach

### Validation & structured output
- `lightroom_tagger/core/description_service.py` — Current `_description_structured_is_valid` (summary-only check), `describe_matched_image` and `_store_structured` patterns
- `lightroom_tagger/core/vision_client.py` — OpenAI-compatible client interface, `_map_openai_error` for error handling patterns

### Job system
- `apps/visualizer/backend/jobs/runner.py` — `JobRunner` class: `start_job`, `complete_job`, `fail_job`, `is_cancelled`, cooperative cancel via `threading.Event`
- `apps/visualizer/backend/jobs/handlers.py` — `JOB_HANDLERS` dispatch, `handle_batch_describe` and `handle_vision_match` for checkpoint retrofit targets
- `apps/visualizer/backend/app.py` (lines 95–106) — Current `_recover_orphaned_jobs` implementation to be replaced with auto-resume
- `apps/visualizer/backend/database.py` — Visualizer jobs DB schema, `update_job_status`, `update_job_field`, `add_job_log`

### Provider stack
- `lightroom_tagger/core/provider_registry.py` — `ProviderRegistry`, provider/model resolution
- `lightroom_tagger/core/fallback.py` — `FallbackDispatcher` retry + cascade pattern
- `lightroom_tagger/core/provider_errors.py` — Error hierarchy, `RETRYABLE_ERRORS`

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Layer overview, data flow, key abstractions
- `.planning/codebase/CONVENTIONS.md` — Naming, error handling, test patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `image_descriptions` table and `store_image_description`: reference for insert/upsert pattern with JSON serialization — new `image_scores` table should follow the same conventions
- `_deserialize_row` / `_serialize_json` helpers in `core/database.py`: reuse for any JSON columns in the new schema
- `ProviderRegistry` + `FallbackDispatcher`: scoring jobs should use the same provider/fallback stack as descriptions
- `describe_image` in `analyzer.py`: starting point for the scoring prompt flow — scoring will follow a similar pattern but with per-perspective prompts from the registry
- `JobRunner` class: checkpoint and resume logic extends this — `update_progress` already writes to the jobs DB per step

### Established Patterns
- **SQLite WAL + `init_database` migrations**: new tables/columns added via `CREATE TABLE IF NOT EXISTS` + migration helpers for existing DBs
- **Job handler convention**: functions in `handlers.py` receive `(runner, job_id, metadata)` and use `runner.update_progress` / `runner.complete_job` / `runner.fail_job`
- **Flask blueprint + response helpers**: new API endpoints follow `utils/responses.py` patterns
- **Cooperative cancellation**: all long-running loops check `runner.is_cancelled(job_id)` — checkpoint logic must integrate with this

### Integration Points
- `init_database` in `core/database.py`: add `image_scores` and `perspectives` table creation
- `JOB_HANDLERS` dict in `handlers.py`: register new scoring job type(s)
- `_recover_orphaned_jobs` in `app.py`: replace with checkpoint-aware auto-resume
- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx` or Settings area: perspective management UI
- `config.yaml` / `core/config.py`: potential config for default checkpoint interval or perspective directory path

</code_context>

<specifics>
## Specific Ideas

- Perspective prompts should be grounded in photography theory from publications and critique frameworks (SCORE-05) — the `.md` files should reference or incorporate theory, not just be generic instructions
- The existing `DESCRIPTION_PROMPT` in `analyzer.py` already has a detailed scoring rubric (1–10 scale with descriptors) — this should be extracted and made part of the perspective template structure
- "Reset to defaults" per perspective, not all-or-nothing

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-structured-scoring-foundation*
*Context gathered: 2026-04-12*
