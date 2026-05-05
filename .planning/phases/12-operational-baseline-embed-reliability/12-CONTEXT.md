# Phase 12: Operational baseline & embed reliability - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix five operational gaps in the embed pipeline and backend restart lifecycle:
- OPS-01: Embed job discoverability from "Visual similarity unavailable" error states
- OPS-02: Embed job preflight — sample paths before full run, fail fast on high unreachable rate
- OPS-03: Embed job result payload includes "why skipped" breakdown; UI renders it in job detail modal
- OPS-04: Backend restart with orphaned `batch_analyze` jobs no longer floods logs with redundant compression output
- OPS-05: `test_providers_api::TestDefaults` pre-existing test failure fixed (note: already passing as of 2026-05-05 — verify at start of phase)

New capabilities (search features, new job types, new UI pages) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### OPS-01 — Embed job discoverability
- **D-01:** Navigation link to the Processing tab (Catalog cache) is sufficient — no inline trigger button needed.
- **D-02:** Apply consistently: wherever a `no_clip_embedding` / "Visual similarity unavailable" error surfaces in the UI, it should show guidance text + a navigation link to the Processing tab. The Search page already does this correctly; other surfaces should follow the same pattern.

### OPS-02 — Path-failure preflight
- **D-03:** Preflight uses a **fixed small sample** of paths before the full embed run. Claude picks the exact count (target range: 20–50 paths).
- **D-04:** Abort threshold is **>50% unreachable** in the sample — if more than half the sampled paths are inaccessible, the job fails fast.
- **D-05:** On abort: **hard stop with a single actionable message** — no confirm prompt. Message should include the count (e.g. "12/20 sampled paths unreachable"), a likely cause (network share / missing mount), and a retry instruction.
- **D-06:** "Unreachable" covers: missing file on disk, empty path string, and network share not mounted. These are the three cases to detect in the sampler.

### OPS-03 — "Why skipped" summary
- **D-07:** The embed job result payload must include a skip breakdown with counts for: **missing file**, **empty path**, **no DB row**.
- **D-08:** The breakdown is rendered in the **job detail modal only**, in the existing embed diagnostics section (`JobDetailModal.tsx`, already has embed-specific rendering at line 300).
- **D-09:** **Zero-skip categories are hidden** — only show categories with count > 0.

### OPS-04 — Compression log noise on restart
- **D-10:** On `batch_analyze` resume after restart, already-compressed images are **skipped silently** (no per-image log).
- **D-11:** One **summary log at the end** of the resume pass: "N images already compressed, skipped." (Only emitted if N > 0.)

### OPS-05 — Pre-existing test failure
- **D-12:** `test_providers_api::TestDefaults` was passing (19/19) as of context-gather date. Verify at phase start with `pytest apps/visualizer/backend/tests/test_providers_api.py -x`. If it has regressed, fix before proceeding; if still green, no action needed.

### Claude's Discretion
- Exact preflight sample count within the 20–50 range (D-03)
- Exact wording of the preflight abort message (must include count/sample ratio and likely cause)
- Whether the preflight sampler shuffles or takes a head/tail slice of paths

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend — orphan recovery & restart
- `apps/visualizer/backend/app.py` — `_recover_orphaned_jobs()` (line ~170): re-queues jobs with v1 checkpoint, fails the rest; this is where OPS-04 compression noise originates on resume

### Backend — embed job handler
- `apps/visualizer/backend/jobs/handlers.py` — `batch_embed_image` handler; contains preflight seed override at line ~72 (`_EMBED_PREFLIGHT_SEED`); embed diagnostics payload shape defined here

### Backend — test suite
- `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` — existing embed handler tests
- `apps/visualizer/backend/tests/test_orphan_recovery.py` — existing orphan recovery tests
- `apps/visualizer/backend/tests/test_providers_api.py` — `TestDefaults` class (OPS-05)

### Frontend — embed error state & discoverability
- `apps/visualizer/frontend/src/pages/SearchPage.tsx` — existing `no_clip_embedding` warning with navigation links (lines ~423–446, ~462–481); reference pattern for D-02
- `apps/visualizer/frontend/src/constants/strings.ts` — `SEARCH_PIN_WARN_NO_CLIP`, `SEARCH_PIN_HELP_EMBED`, `SEARCH_PIN_LINK_CACHE` (lines ~562–566)
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — embed diagnostics section (line ~300); target for OPS-03 skip breakdown rendering

### Frontend — processing tab
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx` — embed job trigger UI; `PROCESSING_CATALOG_CACHE_ROUTE` navigation target

### Backend — similarity API (returns 404 when embeddings missing)
- `apps/visualizer/backend/api/images.py` — `get_catalog_image_similar()` (line ~913): returns `{"error": "Visual similarity is unavailable"}` 404 when no embeddings

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_EMBED_PREFLIGHT_SEED` override in `handlers.py` (~line 72): test-only seed for the preflight sampler — the preflight mechanism partially exists; needs the threshold + abort logic added
- `JobDetailModal.tsx` embed diagnostics block (line ~300): already branches on `batch_embed_image` job type; OPS-03 skip breakdown slots in here
- `test_orphan_recovery.py`: existing test coverage for orphan recovery — extend for OPS-04 compression noise scenario
- `SEARCH_PIN_HELP_EMBED` / `SEARCH_PIN_LINK_CACHE` constants: reference pattern for OPS-01 consistent error guidance

### Established Patterns
- Job result payloads use a flat dict with named count keys (e.g. `described`, `skipped`, `failed`) — OPS-03 breakdown follows this convention
- Error messages in job logs use `add_job_log(db, job_id, 'error'/'info', '...')` — preflight abort and compression summary use this
- Frontend embed diagnostics already group by category — OPS-03 skip breakdown follows existing grouping pattern

### Integration Points
- Preflight abort must call `update_job_status(db, job_id, 'failed')` + `add_job_log(db, job_id, 'error', ...)` before returning
- OPS-03 skip breakdown is part of the job's result payload (stored in job metadata), not a separate API call
- OPS-04 fix lives in the `batch_analyze` resume path inside `handlers.py`, not in `_recover_orphaned_jobs()`

</code_context>

<specifics>
## Specific Ideas

- Preflight abort message format: "X/N sampled paths unreachable — this usually means your network share is not mounted. Check your mount and retry." (exact wording at Claude's discretion, must include ratio)
- OPS-03 skip category labels for the UI: "Missing file", "Empty path", "No DB row" — match the REQUIREMENTS.md wording exactly

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-operational-baseline-embed-reliability*
*Context gathered: 2026-05-05*
