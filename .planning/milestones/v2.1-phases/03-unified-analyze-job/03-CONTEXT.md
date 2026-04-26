# Phase 3: Unified Analyze job - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the two-flow "describe then score" UX with a single default `batch_analyze` job that runs description → scoring in sequence over one shared image selection, while preserving the separate `batch_describe` / `batch_score` flows as an advanced option behind the existing "Advanced options" disclosure.

**In scope:**
- New `batch_analyze` job type in `apps/visualizer/backend/jobs/handlers.py` that runs describe → score in sequence on one shared selection
- Refactor: extract the processing bodies of `handle_batch_describe` / `handle_batch_score` into shared helpers and rewire the existing handlers as thin wrappers so their behavior (and tests) are unchanged
- Single shared image-selection query at the top of `handle_batch_analyze`, passed to both passes
- Per-stage sub-checkpoints (`checkpoint.describe`, `checkpoint.score`) reusing existing fingerprint helpers (`fingerprint_batch_describe`, `fingerprint_batch_score`) unchanged
- Register `batch_analyze` in the orphan-recovery allowlist so it resumes cleanly after a restart
- Frontend: rename `DescriptionsTab.tsx` → `AnalyzeTab.tsx` end-to-end (file, component name, nav label, URL tab slug, tests, imports)
- Primary CTA becomes "Analyze" calling `JobsAPI.create('batch_analyze', ...)`
- Separate "Generate Descriptions only" / "Run scoring only" buttons moved inside the existing "Advanced options" disclosure as a "Run stages separately" subsection
- Replace the single `force` checkbox with two checkboxes: "Force regenerate descriptions" and "Force regenerate scores"; both flow through `metadata` to the handler
- Tests for `batch_analyze` handler: zero-work completion, describe→score sequencing, per-stage fingerprint resume, partial describe failure does not block score, shared selection reaches both passes

**Out of scope (handed to later phases or explicitly excluded):**
- Changes to `handle_batch_describe` / `handle_batch_score` *behavior* — they become wrappers over the shared helpers with identical observable semantics; existing tests must pass unchanged
- Changes to the vision-call implementations, perspective rubrics, provider plumbing, or checkpoint fingerprint formats
- Weighted-by-work-units progress bar (fixed 50/50 split is explicitly chosen — see D-06)
- Unifying describe + vision-match in one call (SEED-014, deferred to v3.0)
- Touching `BatchActionPanel.tsx` (the descriptions-page batch action panel on the Descriptions page, not the Processing tab) — scope is confined to the Processing > Analyze tab
- Filter-framework migration of the Analyze tab's form — that's Phase 4
- Any changes to `JobQueueTab.tsx` / `JobDetailModal.tsx` beyond what falls out naturally from a new `job.type === 'batch_analyze'` being rendered
- URL-synced state for the new checkboxes or advanced toggle — not required by JOB-06

**Requirement locked by `.planning/REQUIREMENTS.md`:**
- **JOB-06** — Single unified "Analyze" job that runs description + scoring together, with an advanced toggle to run them separately

**Success criteria (from ROADMAP.md):**
1. `batch_analyze` job type runs describe → score in sequence with shared selection criteria
2. Default UI path launches Analyze; advanced toggle exposes separate describe/score
3. Existing `batch_describe` and `batch_score` tests continue to pass

</domain>

<decisions>
## Implementation Decisions

### Orchestration model (Area 1)

- **D-01:** Introduce `_run_describe_pass(runner, job_id, metadata, lib_db, selection, *, progress_range, log_prefix='')` and `_run_score_pass(runner, job_id, metadata, lib_db, selection, *, progress_range, log_prefix='')` helpers inside `apps/visualizer/backend/jobs/handlers.py`. Each helper encapsulates the full describe/score processing loop that lives in `handle_batch_describe` / `handle_batch_score` today: pre-filter, fingerprint + resume, per-image work, failure counting, consecutive-failure circuit breaker, checkpoint writes, result-dict construction.
- **D-02:** `handle_batch_describe` and `handle_batch_score` become thin wrappers that: open `lib_db`, build their own selection (as today), call the corresponding helper with `progress_range=(0, 100)` and no `log_prefix`, then `complete_job()` / `fail_job()` exactly as today. The intent is **zero observable behavior change** — `test_handlers_batch_describe.py` and `test_handlers_batch_score.py` must keep passing with no modification.
- **D-03:** `handle_batch_analyze` opens `lib_db`, builds a **shared selection** (the `(key, itype)` list) using the same logic that describe uses today, then:
  1. Calls `_run_describe_pass(runner, job_id, metadata, lib_db, selection, progress_range=(0, 50), log_prefix='[describe] ')` — returns a describe-result dict.
  2. Calls `_run_score_pass(runner, job_id, metadata, lib_db, selection, progress_range=(50, 100), log_prefix='[score] ')` — returns a score-result dict. The score pass expands `selection` to triples internally using `perspective_slugs` (same expansion logic as today).
  3. Combines results into a single result dict and calls `runner.complete_job(job_id, combined_result)`.
- **D-04:** The score pass **does not re-query the database** for its selection — it receives the same `(key, itype)` list the describe pass saw and expands to triples with `slugs`. This guarantees both stages operate on the same image set even if the database changes mid-job. Describe and score each keep their own DB-level pre-filters (already-described / already-scored skips) inside their helper, since those are separate concerns from the selection.

### Failure handling between stages (Area 2)

- **D-05:** Per-image describe failures do **not** remove the image from the score pass. The score pass already reads existing descriptions from the DB where available; a missing description becomes a per-image score warning (logged, counted under `score_failed`) rather than an upfront filter. This matches today's independent-handler semantics and keeps behavior honest to the user.
- **D-06:** `handle_batch_analyze` completes **successful** as long as the job runs to the end. The combined result dict carries `describe_total`, `describe_succeeded`, `describe_failed`, `score_total`, `score_succeeded`, `score_failed` so the Job Detail Modal can render stage-wise outcomes. Job is only marked **failed** if an exception propagates out of either helper OR if the existing consecutive-failure circuit breaker inside the describe pass trips (same ceiling as today); in the latter case the describe pass calls `runner.fail_job()` and `handle_batch_analyze` returns early without calling the score pass.

### Progress reporting (Area 3)

- **D-07:** Fixed 50/50 progress split — describe pass maps its own internal 0–100% into the job's 0–50%; score pass maps its own 0–100% into the job's 50–100%. Implemented by the `progress_range=(lo, hi)` parameter on each helper, which wraps `runner.update_progress(job_id, pct, msg)` so any `pct` in 0–100 gets linearly remapped to `[lo, hi]`. 50/50 is accepted as simple and honest-enough even when scoring dominates runtime in practice (score ≈ N×M work units vs describe's N) — proportional weighting was considered and explicitly rejected to avoid mid-job reweighting surprises when perspectives change.
- **D-08:** `handle_batch_analyze` sets `current_step` on the job row to `"Describing"` at the start of the describe pass and `"Scoring"` at the start of the score pass, via `update_job_field(runner.db, job_id, 'current_step', ...)`. Both values flow through the existing `JobsAPI.get()` payload and render in `JobQueueTab` / `JobDetailModal` without any frontend change. Strings live in `constants/strings.ts` on the frontend; backend writes the raw values directly.

### UI surface on the Analyze tab (Area 4)

- **D-09:** Primary button label becomes **"Analyze"** (was "Generate Descriptions"). It calls `JobsAPI.create('batch_analyze', buildBatchJobMetadata())`. The existing `batchMinRating`, `imageType`, `dateFilter`, `selectedPerspectiveSlugs`, `descProviderId`, `descProviderModel`, `options.maxWorkers` all pass through unchanged — the metadata shape is a strict superset of what both old handlers accept.
- **D-10:** The always-visible area of the card shows **only the Analyze button**. The existing "Advanced options" disclosure (currently containing provider select + workers) gains a new subsection "Run stages separately" below provider/workers, containing two buttons: **"Generate Descriptions only"** (calls `batch_describe`) and **"Run scoring only"** (calls `batch_score`). This is the smallest visual churn and keeps power-user access discoverable.
- **D-11:** Replace the single `force` checkbox with **two independent checkboxes** (not inside the Advanced disclosure — they stay in the main form because they affect the Analyze flow):
  - **"Force regenerate descriptions"** → `metadata.force_describe: boolean`
  - **"Force regenerate scores"** → `metadata.force_score: boolean`
  The backend helpers honor these as `force` within their respective passes. For backwards compatibility with the existing handlers that still accept the flat `force` key, the wrappers translate: `handle_batch_describe` reads `metadata.force` (unchanged), `handle_batch_score` reads `metadata.force` (unchanged), `handle_batch_analyze` reads both new keys and passes each to its respective helper. When the frontend calls the "Generate Descriptions only" / "Run scoring only" buttons (advanced path), it sends `force: force_describe` or `force: force_score` respectively so the old handlers see the flat key they already understand.
- **D-12:** Card intro copy: **Title** "Analyze Images", **subtitle** "Run AI description + scoring in a single job. Advanced options let you run stages separately." All strings added to `constants/strings.ts` — no hardcoded literals in the component body. The existing "Descriptions produce the full structured JSON critique..." helper paragraph is removed (it described the old two-button split).

### Tab name & route (Area 5)

- **D-13:** **Full rename** of the Descriptions tab surface:
  - `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` → `AnalyzeTab.tsx`
  - Component export `DescriptionsTab` → `AnalyzeTab` (named export)
  - Nav label in `ProcessingPage.tsx` "Descriptions" → "Analyze"
  - URL tab slug `?tab=descriptions` → `?tab=analyze` (and anywhere the slug literal appears, e.g. `DESC_BATCH_VIEW_IN_JOBS` links if any pointed at the old slug)
  - All tests / imports referencing `DescriptionsTab` get updated (confirmed via `rg DescriptionsTab` in planning)
  - File rename uses `git mv` to preserve history
- **D-14:** The unrelated file `apps/visualizer/frontend/src/components/descriptions/BatchActionPanel.tsx` — which lives on the Descriptions *page* (not the Processing > Analyze tab) — is **out of scope** for this phase. Only the Processing tab renames.

### Checkpoint & resume semantics (Area 6)

- **D-15:** `batch_analyze` checkpoint shape (stored in the job row's `metadata.checkpoint` field, same location as existing handlers):
  ```json
  {
    "checkpoint_version": 1,
    "job_type": "batch_analyze",
    "stage": "describe" | "score",
    "describe": {
      "fingerprint": "sha256...",
      "processed_pairs": ["key|itype", ...],
      "total_at_start": 120
    },
    "score": {
      "fingerprint": "sha256...",
      "processed_triplets": ["key|itype|slug", ...],
      "total_at_start": 480
    }
  }
  ```
  The `stage` field is the resume entry point. The nested `describe` / `score` objects mirror exactly the existing single-handler checkpoint payloads so the existing `fingerprint_batch_describe` / `fingerprint_batch_score` helpers are reused unchanged.
- **D-16:** On job start inside `handle_batch_analyze`, read the existing checkpoint (if any). If `stage == "score"` and the `describe.fingerprint` still matches the current computed describe fingerprint, skip the describe pass entirely and jump to the score pass (with its own fingerprint check against the stored `score.fingerprint`). If `stage == "describe"`, re-enter the describe pass; after it finishes, advance `stage` to `"score"` before starting the score pass.
- **D-17:** **Per-stage fingerprint mismatch reset** — if the describe fingerprint changed, reset `describe.processed_pairs` and log `"checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh"` (mirroring the existing describe handler's mismatch log). Score stage is independent: its own fingerprint check happens when the score pass starts, and a score-fingerprint mismatch only resets score. Stage independence matches the existing per-handler behavior pattern.
- **D-18:** **Orphan recovery registration** — add `'batch_analyze'` to the allowlist / dispatcher wherever `batch_describe` / `batch_score` are enumerated for orphan recovery. Specifically: `apps/visualizer/backend/jobs/checkpoint.py` docstring + any `job_type in (...)` guard in `apps/visualizer/backend/tests/test_orphan_recovery.py` style paths and the recovery code they exercise. Planner will enumerate exact touchpoints.

### Claude's Discretion

- Exact naming of helper functions (`_run_describe_pass` / `_run_score_pass` vs other names) — implementation detail
- Whether to keep wrappers identical or add a `log_prefix` to their internal calls for nicer logs even in single-handler mode (safe either way)
- Specific test file layout for `batch_analyze` (new `test_handlers_batch_analyze.py` file vs extending existing files) — new file recommended for clarity but not locked
- Exact string keys in `constants/strings.ts` for new labels ("Analyze", "Run stages separately", "Force regenerate descriptions", "Force regenerate scores", title, subtitle) — planner picks names consistent with existing `DESC_*` / `ANALYZE_*` conventions
- Whether the "Run stages separately" subsection needs a divider/heading inside the Advanced disclosure or just inline buttons — style choice

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 3: Unified Analyze job" — goal, requirements, success criteria
- `.planning/REQUIREMENTS.md` §"Job queue & processing UX" — JOB-06 full text
- `.planning/seeds/SEED-001-unified-batch-job.md` — original seed with breadcrumbs and implementation path

### Prior phase context (carry-forward)
- `.planning/phases/02-job-queue-and-processing-ux/02-CONTEXT.md` — explicitly notes "Unified Analyze job… is Phase 3"; establishes the `JobsAPI.get()` + `logs_limit` conventions this phase inherits
- `.planning/phases/01-matching-review-polish/01-CONTEXT.md` — establishes the `constants/strings.ts` convention for all user-facing copy

### Backend touchpoints
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_describe` (lines 943–1249), `handle_batch_score` (lines 1251–1591), `JOB_HANDLERS` registry (lines 1594–1604). The new `handle_batch_analyze` lands here; existing handlers refactor to call shared helpers.
- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_batch_describe`, `fingerprint_batch_score` (reused unchanged); checkpoint-shape docstring must be updated to document the new `batch_analyze` shape
- `apps/visualizer/backend/jobs/runner.py` — `update_progress`, `complete_job`, `fail_job`, `clear_checkpoint` (used by new helpers the same way)
- `apps/visualizer/backend/database.py` — `add_job_log`, `get_job`, `update_job_field` (used for `current_step` writes)
- `apps/visualizer/backend/tests/test_handlers_batch_describe.py` — **must pass unchanged** after the refactor (success criterion SC-3)
- `apps/visualizer/backend/tests/test_handlers_batch_score.py` — **must pass unchanged** after the refactor (success criterion SC-3)
- `apps/visualizer/backend/tests/test_orphan_recovery.py` — orphan-recovery allowlist likely lives here or in code it exercises; `batch_analyze` must land in the same path
- `apps/visualizer/backend/tests/test_job_checkpoint.py` — pattern to follow when adding `batch_analyze` checkpoint tests

### Frontend touchpoints
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` — renames to `AnalyzeTab.tsx`; current structure (`buildBatchJobMetadata`, `startDescriptions`, `startBatchScoring`) is the starting point
- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx` — tab nav definition, URL slug handling
- `apps/visualizer/frontend/src/services/api.ts` — `JobsAPI.create()`; no new surface, just a new job-type string
- `apps/visualizer/frontend/src/constants/strings.ts` — add new keys for Analyze button, title, subtitle, two force checkboxes, "Run stages separately" label
- `apps/visualizer/frontend/src/components/ui/Button.tsx`, `Card.tsx` — reused, no changes

### Explicitly NOT a canonical ref
- `apps/visualizer/frontend/src/components/descriptions/BatchActionPanel.tsx` — unrelated Descriptions *page* surface, explicitly out of scope (see D-14)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`fingerprint_batch_describe` / `fingerprint_batch_score`** (`jobs/checkpoint.py`) — unchanged; nested under new `checkpoint.describe` / `checkpoint.score` keys
- **`runner.update_progress`, `complete_job`, `fail_job`, `clear_checkpoint`** — already used by both handlers; helpers call them through a thin `progress_range` remapper
- **`add_job_log`, `get_job`, `update_job_field`** — the existing logging + `current_step` write surface; new handler uses the same primitives
- **`buildBatchJobMetadata` in `DescriptionsTab.tsx`** — already builds a metadata object that's a strict superset of what both old handlers need; renamed tab reuses it with minimal change (add `force_describe` / `force_score` keys)
- **`Button`, `Card`, `CardHeader`, `CardTitle`, `CardContent` from `components/ui/`** — Analyze button and separate-stage buttons use the same primitives as today's "Generate Descriptions" / "Run batch scoring" buttons
- **`ProviderModelSelect`, `WorkerSlider`** — already inside the Advanced disclosure, untouched
- **`success_paginated()` response helper, `<Pagination>`** — not needed for this phase (Phase 2's territory)

### Established Patterns

- **Handler registration via `JOB_HANDLERS` dict** (`jobs/handlers.py` bottom) — new `'batch_analyze': handle_batch_analyze` entry is the only registry change
- **Checkpoint shape with `checkpoint_version: 1` + `job_type` + payload** — new shape follows the same envelope, just with nested stage objects
- **Per-handler consecutive-failure circuit breaker inside describe** — preserved exactly; the describe helper still calls `runner.fail_job()` when the ceiling trips, short-circuiting the analyze job before score starts
- **All user-facing strings in `constants/strings.ts`** — established Phase 1 pattern, reinforced Phase 2; continues here
- **Tab rendering via a `tab` URL query param on `ProcessingPage`** — the rename affects both the nav label and the slug value, not the rendering mechanism
- **Job polling via sockets + `job_updated` events** — unchanged; `JobQueueTab` / `JobDetailModal` re-render on any `job.type`, including the new `batch_analyze`

### Integration Points

- `JOB_HANDLERS` dict in `jobs/handlers.py` — single registry entry
- Orphan-recovery allowlist / dispatcher paths (exact location planner will pin down — `jobs/checkpoint.py` docstring + recovery code)
- `ProcessingPage.tsx` tab nav array — one label, one slug
- `DescriptionsTab.tsx` file rename → `AnalyzeTab.tsx` via `git mv`
- Frontend `JobsAPI.create` call sites — only the one in the renamed tab changes (new string literal `'batch_analyze'`, plus the two existing literals stay for the advanced-path buttons)

</code_context>

<specifics>
## Specific Ideas

- **Shared selection query happens exactly once** in `handle_batch_analyze`, at the top, before either pass starts. Both passes receive the same list — this is a hard requirement to keep the two stages consistent and to make the "shared selection criteria" clause of SC-1 true literally, not just nominally.
- **Zero behavior change for existing handlers.** The refactor's correctness is measured by `test_handlers_batch_describe.py` and `test_handlers_batch_score.py` continuing to pass without modification. Any test change signals a behavior drift that violates SC-3.
- **50/50 progress is deliberate**, even though score typically does ~4× the describe work. The alternative (weighted by N vs N×M) was considered and rejected to keep the progress-bar contract simple and predictable across varying perspective counts.
- **`current_step` text is how users understand which stage is running**, not the progress percentage. "Describing" → "Scoring" is the visible state transition.
- **Two independent force checkboxes** give the user precise control: "I updated my perspective rubric, rescore everything but don't re-describe" becomes a natural checkbox combination. The old single `force` checkbox couldn't express this.

</specifics>

<deferred>
## Deferred Ideas

- **Unified vision-match + describe in a single call** — SEED-014, already tracked for v3.0 alongside stacking work. Out of scope here; `batch_analyze` only unifies describe + score.
- **Filter-framework migration of the Analyze tab's form** (image type, date range, perspective checkboxes, min rating) — Phase 4 territory (FILTER-01/02).
- **URL-syncing the advanced disclosure open/closed state or the new force checkboxes** — rolls in naturally with SEED-010 (persist tab/filter state), not required by JOB-06.
- **Weighted-by-work-units progress split** — considered and explicitly rejected in D-07. Could be revisited if users report that the 50/50 bar feels misleading during large score passes.
- **Per-image describe failure → skip scoring for that image** — considered and rejected in D-05 in favor of independent-stage semantics matching today's handlers.
- **Unifying `BatchActionPanel.tsx` on the Descriptions page with the new Analyze tab flow** — different surface; separate design question for a later phase if the Descriptions page stays in the product.
- **Single combined checkpoint fingerprint** covering both stages — considered and rejected in D-15/D-17 in favor of per-stage fingerprints that reuse existing helpers unchanged.

</deferred>

---

*Phase: 03-unified-analyze-job*
*Context gathered: 2026-04-17*
