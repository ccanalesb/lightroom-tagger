# Phase 4: Stack Detection — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce the `image_stacks` + `image_stack_members` schema and a `batch_stack_detect` job that groups burst sequences by `date_taken` into stacks. Delivers STACK-01 only.

Requirements in scope:
- **STACK-01**: Job detects burst shots (photos within a configurable time window by `date_taken`) and groups them into stacks, with checkpointed progress and null/bad `date_taken` handled safely
- **Schema**: `image_stacks` + `image_stack_members` with `UNIQUE(image_key)`; migrations idempotent

Out of scope:
- **STACK-02** (pHash near-duplicate clustering) — dropped entirely; offers no value for current workflow
- STACK-03, STACK-04, STACK-05 — belong to Phases 6 and 7
- No frontend stack UI in this phase — job is triggerable via existing job API; observable in `JobQueueTab`

</domain>

<decisions>
## Implementation Decisions

### Job Shape
- **D-01:** Single job type: `batch_stack_detect`. Burst-by-time pass only — no pHash pass. Registered in `JOB_HANDLERS` and `JOB_TYPES_REQUIRING_CATALOG` following existing batch job patterns (`batch_describe`, `batch_text_embed`).

### Representative Selection
- **D-02:** When a stack is created, the representative is chosen via a **three-tier cascade**:
  1. Highest Lightroom star rating (`images.rating`, non-zero)
  2. Highest AI aggregate score — `AVG(score)` from `image_scores` joined to active `perspectives` for that `image_key`; treat NULL/no-score as 0
  3. Last by `date_taken` — final deterministic fallback
- **D-03:** Representative is stored as `representative_key` on `image_stacks`. Must never be null after stack creation.

### Re-run Semantics
- **D-04:** **Incremental by default** — only processes images not yet assigned to any stack (`image_key NOT IN image_stack_members`). Consistent with the project-wide incremental + checkpoint pattern.
- **D-05:** Job metadata `force` param controls rebuild behaviour:
  - `false` (default / omitted): incremental — skip already-stacked images
  - `true`: rebuild all stacks from scratch (drop + recreate)
  - `"preserve_edited"`: rebuild non-user-modified stacks only, skip stacks flagged as user-edited — this flag is forward-looking for Phase 7 (STACK-05); in Phase 4 it behaves identically to `true` since no user edits can exist yet

### Configuration
- **D-06:** `stack_burst_delta_ms: int = 2000` added to the `Config` dataclass in `lightroom_tagger/core/config.py` with a 2000ms default. Persisted in `config.yaml`.
- **D-07:** Job metadata `delta_ms` overrides the config value for that run when supplied AND non-zero. Handler resolves: `raw = metadata.get("delta_ms"); resolved = raw if (raw is not None and raw != 0) else load_config().stack_burst_delta_ms`. Passing `delta_ms: 0` is treated as "use config" (same as omitting the key). A resolved value must be `>= 1` or the job fails.
- **D-08:** A new `StackDetectionSettingsPanel` component is added to `SettingsTab` (in `apps/visualizer/frontend/src/components/processing/SettingsTab.tsx`) — same pattern as `CatalogSettingsPanel` and `InstagramDumpSettingsPanel`. Exposes the persistent `stack_burst_delta_ms` default.

### Null / Bad date_taken Handling
- **D-09:** Images with null or unparseable `date_taken` are **excluded** from burst grouping entirely — they are not assigned to any stack and do not corrupt existing groups. The job logs a count of skipped images at completion.

### Job Lifecycle
- **D-10:** Job reports checkpointed progress consistent with `batch_text_embed` / `batch_describe` — per-image or per-batch progress updates, cancellation via `cancel_scope`, orphan recovery on restart.
- **D-11:** Job result payload includes: `{ stacks_created, stacks_updated, images_stacked, images_skipped_no_date, images_skipped_already_stacked }`.

### Claude's Discretion
- Exact SQL for burst grouping (window function vs. self-join vs. sort-and-scan in Python)
- Whether `image_stacks` stores `stack_size` as a denormalized count or always derives it from `image_stack_members`
- Exact migration approach (new `_migrate_image_stacks` helper inside `init_database` following existing pattern)
- Checkpoint fingerprint key composition for `batch_stack_detect`
- Whether `StackDetectionSettingsPanel` uses an existing API endpoint for config reads/writes or a new one (follow existing settings panel pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — STACK-01 definition; implementation guidance (use `date_taken`, `image_stacks` + `image_stack_members` with `UNIQUE(image_key)`); STACK-02 explicitly dropped from this phase

### Roadmap
- `.planning/ROADMAP.md` §Phase 4 — success criteria (4 items); note STACK-02 is descoped per D-01

### Prior phase context
- `.planning/phases/03-semantic-search-and-results/03-CONTEXT.md` — D-05 (`batch_text_embed` as canonical batch job pattern), D-01 (`JOB_TYPES_REQUIRING_CATALOG` registration)

### Codebase — backend
- `lightroom_tagger/core/config.py` — `Config` dataclass; add `stack_burst_delta_ms` here
- `lightroom_tagger/core/database.py` — `init_database` (migration point), `library_write` (all DB writes go here), `images` table schema (`date_taken`, `rating`, `phash` columns)
- `lightroom_tagger/core/phash.py` — `hamming_distance`, `compare_hashes` — available if ever needed; not used in Phase 4
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_text_embed` (canonical new batch job pattern to follow), `JOB_HANDLERS` registry at bottom of file
- `apps/visualizer/backend/jobs/checkpoint.py` — fingerprint helpers and `merge_checkpoint_into_metadata`; add `fingerprint_batch_stack_detect` here
- `apps/visualizer/backend/library_db.py` — `JOB_TYPES_REQUIRING_CATALOG` (register `batch_stack_detect`)

### Codebase — frontend
- `apps/visualizer/frontend/src/components/processing/SettingsTab.tsx` — where `StackDetectionSettingsPanel` is added
- `apps/visualizer/frontend/src/components/images/CatalogSettingsPanel.tsx` — reference implementation for a settings panel

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `lightroom_tagger/core/phash.py` — `hamming_distance(hash1, hash2)` and `compare_hashes(hash1, hash2, threshold)` — ready to use if pHash ever re-enters scope
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_text_embed` is the cleanest recent example of a new batch job; follow its structure for `handle_batch_stack_detect`
- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_catalog_keys` and `fingerprint_batch_text_embed` as reference for new fingerprint helper
- `library_write` context manager — all `image_stacks` and `image_stack_members` writes must go through this
- `add_job_log`, `update_job_field`, `runner.complete_job` / `runner.fail_job` — standard job lifecycle calls

### Established Patterns
- **Batch job structure:** cancel-scope wrapper → resolve library DB → load config → load/validate checkpoint → process in batches → checkpoint after each batch → complete/fail
- **DB migrations:** `_migrate_add_column` helper + idempotent `CREATE TABLE IF NOT EXISTS` inside `init_database`; new migration step follows `_migrate_image_text_embeddings_vec0` as a recent example
- **Config resolution in handlers:** `load_config()` called inside handler; job metadata values override config fields
- **Representative selection JOIN:** LEFT JOIN `image_descriptions` on `image_key`; aggregate score is the sum or average of perspective scores — planner should check actual score column names in `image_descriptions`

### Integration Points
- `init_database` — add `_migrate_image_stacks` step here
- `JOB_HANDLERS` dict at bottom of `handlers.py` — add `'batch_stack_detect': handle_batch_stack_detect`
- `JOB_TYPES_REQUIRING_CATALOG` in `library_db.py` — add `'batch_stack_detect'`
- `SettingsTab.tsx` — import and render `StackDetectionSettingsPanel` alongside existing panels
- Config API (existing settings panel pattern) — `StackDetectionSettingsPanel` reads/writes `stack_burst_delta_ms`

</code_context>

<specifics>
## Specific Ideas

- Default `delta_ms`: **2000ms** (2 seconds) — reasonable for burst shooting; user can lower for fast bursts or raise for bracketing sequences
- Three-tier representative cascade must use a single SQL query where possible (ORDER BY rating DESC, ai_score DESC, date_taken DESC LIMIT 1) rather than three round-trips
- `force: "preserve_edited"` flag is intentionally baked in now so Phase 7 (STACK-05) doesn't need to change the job API contract — planner should add a `user_modified` boolean column to `image_stacks` schema even though nothing sets it to `true` in Phase 4
- Job result log line example: `"Stacked 47 images into 12 stacks (3 images skipped: no date_taken, 0 skipped: already stacked)"`

</specifics>

<deferred>
## Deferred / Dropped

- **STACK-02 (pHash near-duplicate clustering)** — dropped entirely. Does not offer sufficient value for the current workflow. Not deferred to a later phase — removed from scope.
- **Stack UI** (STACK-03) — catalog/Best Photos representative display belongs to Phase 6
- **Stack-aware matching** (STACK-04) — belongs to Phase 7
- **Split/merge/change representative UI** (STACK-05) — belongs to Phase 7; `user_modified` flag is scaffolded in schema but not set by any UI until then

</deferred>

---

*Phase: 04-stack-detection*
*Context gathered: 2026-04-24*
