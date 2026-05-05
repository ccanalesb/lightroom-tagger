# Phase 13: Handlers split (per-job-family) - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Split `apps/visualizer/backend/jobs/handlers.py` (3,849 lines, 15 handlers) into a
per-job-family subpackage. Zero behavior change — all tests must remain green after
each individual commit. No new job types, no logic changes, no API changes.

</domain>

<decisions>
## Implementation Decisions

### Module structure
- **D-01:** Convert `jobs/handlers.py` into a subpackage `jobs/handlers/` with the following files:
  - `__init__.py` — assembles and exposes `JOB_HANDLERS`; no handler re-exports
  - `analyze.py` — `handle_single_describe`, `handle_single_score`, `handle_batch_describe`, `handle_batch_score`, `handle_batch_analyze`
  - `embed.py` — `handle_batch_embed_image`, `handle_batch_text_embed`
  - `matching.py` — `handle_vision_match`, `handle_enrich_catalog`, `handle_prepare_catalog`
  - `stacks.py` — `handle_batch_stack_detect`, `handle_batch_catalog_similarity`, `handle_catalog_cache_build`
  - `instagram.py` — `handle_analyze_instagram`, `handle_instagram_import`
  - `common.py` — cross-family private helpers (see D-06)

### Import strategy
- **D-02:** `__init__.py` exposes **only `JOB_HANDLERS`** — assembled explicitly from submodule imports. No handler re-exports.
- **D-03:** All test imports updated to point at the submodule directly (e.g. `from jobs.handlers.analyze import handle_batch_describe`). ~60 import lines across ~15 test files.
- **D-04:** `app.py` import `from jobs.handlers import JOB_HANDLERS` is **unchanged** — works because `JOB_HANDLERS` lives in `__init__.py`.

### Shared private helpers
- **D-05:** Single-consumer helpers stay in their primary-consumer module (e.g. `_expand_matches_for_lightroom_writes` in `matching.py`, `_build_burst_segments` in `stacks.py`, `_CatalogCacheStageRunner` + `_catalog_cache_stage_mapped_progress` in `stacks.py`).
- **D-06:** True cross-family helpers move to `common.py`:
  - `_resolve_library_db_or_fail`
  - `_failure_severity_from_exception`
  - `_select_catalog_keys`
  - `_select_catalog_keys_missing_visual_tags`
  - `_select_instagram_keys`
  - `_resolve_date_window`
  - `_CATALOG_NOT_VIDEO_SQL` constant

### Split order & atomicity
- **D-07:** **Scaffold commit first** — create `jobs/handlers/` subpackage with empty submodules + `__init__.py` that imports from all submodules and re-assembles `JOB_HANDLERS`. At this point all handlers still live in the old flat file (temporarily re-exported). Tests green.
- **D-08:** Then **one commit per family** (5 commits), moving handlers + their single-consumer helpers + updating affected test imports. After each commit: tests green.
- **D-09:** Final commit removes the old flat `jobs/handlers.py` entirely (should be empty by this point).

### Claude's Discretion
- Exact scaffold strategy for keeping tests green between commits (temporary re-exports from old flat file vs. moving content immediately)
- Whether `common.py` module-level constants (`_CHECKPOINT_MAX_ENTRIES` etc.) are also moved to `common.py` or stay in their primary-consumer module
- Order of the 5 family migration commits (suggested: instagram → embed → matching → stacks → analyze, simplest to most complex)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary file being split
- `apps/visualizer/backend/jobs/handlers.py` — full source; read entirely before planning. Handler boundaries at lines: 401 (analyze_instagram), 407 (instagram_import), 483 (vision_match), 761 (enrich_catalog), 906 (prepare_catalog), 1242 (single_describe), 1292 (single_score), 1751 (batch_describe), 2227 (batch_score), 2301 (batch_analyze), 2468 (batch_text_embed), 2679 (batch_embed_image), 3255 (batch_catalog_similarity), 3378 (batch_stack_detect), 3675 (catalog_cache_build)

### Handler registry consumer
- `apps/visualizer/backend/app.py` line ~213 — `from jobs.handlers import JOB_HANDLERS`; line ~283 — dispatch logic. Import path must remain stable.

### Test files importing from jobs.handlers (all need import updates in D-03)
- `apps/visualizer/backend/tests/test_handlers_batch_analyze.py`
- `apps/visualizer/backend/tests/test_handlers_batch_describe.py`
- `apps/visualizer/backend/tests/test_handlers_batch_score.py`
- `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py`
- `apps/visualizer/backend/tests/test_handlers_batch_text_embed.py`
- `apps/visualizer/backend/tests/test_handlers_batch_stack_detect.py`
- `apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py`
- `apps/visualizer/backend/tests/test_handlers_batch_catalog_similarity.py`
- `apps/visualizer/backend/tests/test_handlers_single_match.py`
- `apps/visualizer/backend/tests/test_handlers_date_window.py`
- `apps/visualizer/backend/tests/test_select_instagram_keys.py`
- `apps/visualizer/backend/tests/test_stack_matching_integration.py`

### Existing jobs package structure
- `apps/visualizer/backend/jobs/__init__.py`
- `apps/visualizer/backend/jobs/checkpoint.py` — fingerprint helpers imported by handlers
- `apps/visualizer/backend/jobs/runner.py` — `JobRunner` used by all handlers
- `apps/visualizer/backend/jobs/path_setup.py` — `_path_setup` side-effect import at top of handlers.py

### Cursor rules that apply
- `.cursor/rules/job-log-contract.mdc` — log shape requirements (no behavior changes, but verify compliance is preserved)
- `.cursor/rules/job-ui-contract.mdc` — UI contract (no new handlers; existing contracts unchanged)
- `.cursor/rules/backend-restart.mdc` — restart protocol after backend changes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jobs/checkpoint.py` — all fingerprint helpers already in a separate module; import pattern to follow for the split
- `jobs/runner.py` — `JobRunner` already separate; establishes the pattern this phase extends
- `_CATALOG_NOT_VIDEO_SQL` constant (line 137) — used by multiple handlers; candidate for `common.py`
- `_PREFLIGHT_RNG_SEED` (line 72) — test-only override; lives in `embed.py` with `handle_batch_embed_image`

### Established Patterns
- All handlers share the same signature: `handler(runner, job_id: str, metadata: dict) -> None`
- Private helpers prefixed with `_` and snake_case — convention carries over to submodules
- Module-level constants prefixed with `_` and SCREAMING_SNAKE_CASE per handler family
- `from . import path_setup as _path_setup  # noqa: F401` side-effect import at top of current `handlers.py` — must be preserved in `__init__.py` or each submodule (once, not multiple times)

### Integration Points
- `JOB_HANDLERS` dict in `__init__.py` is the single integration point with `app.py` — all other changes are internal
- `jobs/handlers/` subpackage `__init__.py` must import all submodules to trigger their module-level side effects (if any)
- `checkpoint.py` imports are per-handler — each submodule imports only the fingerprint helpers it uses

</code_context>

<specifics>
## Specific Ideas

- Suggested family migration order (simplest to most complex): instagram → embed → matching → stacks → analyze
- `_path_setup` side-effect import should live only in `__init__.py`, not duplicated across submodules
- The scaffold commit's `__init__.py` can temporarily import `handle_*` names from the still-flat `handlers_old.py` (or keep the flat file as a transitional shim) — planner picks the cleanest approach

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-handlers-split-per-job-family*
*Context gathered: 2026-05-05*
