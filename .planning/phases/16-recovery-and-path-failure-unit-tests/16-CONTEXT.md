# Phase 16: Recovery & path-failure unit tests — Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Add focused unit tests for two under-covered areas:
1. **TEST-01** — Restart/orphan recovery for `batch_describe` and `batch_score` handlers (checkpoint-resume within a running job, not just the app-level requeue path). `batch_analyze` resume is partially covered; fill remaining gaps.
2. **TEST-02** — Path-failure handling for embed job. Phase 12 already ships extensive preflight and skip_reason_counts tests in `test_handlers_batch_embed_image.py`. Phase 16 interprets TEST-02 as confirming coverage is solid and possibly adding any narrow gaps (e.g., empty-path edge cases for `batch_describe`/`batch_score` if those handlers touch file paths).

No new production code — tests only. All 663+ baseline tests must remain green.

</domain>

<decisions>
## Implementation Decisions

### TEST-01 scope

- **D-01:** Add checkpoint-resume tests to `test_handlers_batch_describe.py` — missing file:
  - resume skips already-processed pairs when checkpoint present
  - fingerprint mismatch resets and starts fresh
  - zero-work case with stale checkpoint (all pairs already processed)
- **D-02:** Add checkpoint-resume tests to `test_handlers_batch_score.py` (currently has one `test_batch_score_checkpoint_skips_already_processed_triplets` but no mismatch/reset/stale-checkpoint coverage)
- **D-03:** Extend `test_orphan_recovery.py` to cover `batch_score` job type (currently only `batch_describe` and `batch_analyze` are tested in orphan recovery)
- **D-04:** `batch_analyze` already has resume tests — add only a fingerprint-mismatch-mid-stage reset test if not already covered

### TEST-02 scope

- **D-05:** Phase 12 `test_handlers_batch_embed_image.py` covers preflight abort, boundary conditions, skip_reason_counts, and chain-mode override. No additional embed path tests needed.
- **D-06:** Check if `batch_describe` or `batch_score` handlers touch image file paths directly. If they do (e.g., for vision cache), add empty-path / missing-file unit tests. If they don't (they pass keys to downstream services that handle paths), mark TEST-02 satisfied by the embed tests.

### Test placement

- **D-07:** New tests go into the existing handler test files (`test_handlers_batch_describe.py`, `test_handlers_batch_score.py`, `test_orphan_recovery.py`) — no new files unless a test clearly belongs to a new module
- **D-08:** Mock pattern follows existing: `MagicMock()` runner with `is_cancelled.return_value = False`, `@patch('jobs.handlers.X.Y')` decoration chain

### Baseline protection

- **D-09:** Each plan's verification must run the full pytest suite and confirm the baseline count does not drop (≥663 tests, all passing)
- **D-10:** No changes to production code — test-only phase

### Claude's Discretion

- Which specific checkpoint fixture shapes to use (follow existing patterns in test_handlers_batch_analyze.py)
- Wave breakdown (parallelization of test files)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing test files (patterns to follow)
- `apps/visualizer/backend/tests/test_handlers_batch_analyze.py` — checkpoint-resume patterns (lines ~208–415), fingerprint mismatch reset
- `apps/visualizer/backend/tests/test_handlers_batch_describe.py` — existing describe handler tests (baseline shape)
- `apps/visualizer/backend/tests/test_handlers_batch_score.py` — existing score handler tests (baseline shape)
- `apps/visualizer/backend/tests/test_orphan_recovery.py` — `_recover_orphaned_jobs` coverage (batch_describe, batch_analyze)
- `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` — path-failure test patterns (preflight, skip_reason_counts)

### Production code being tested
- `apps/visualizer/backend/jobs/handlers/analyze.py` — batch_analyze handler
- `apps/visualizer/backend/jobs/handlers/__init__.py` — handler registration
- `apps/visualizer/backend/jobs/checkpoint.py` — fingerprint helpers, CHECKPOINT_VERSION
- `apps/visualizer/backend/app.py` — `_recover_orphaned_jobs` function

### Requirements
- `.planning/REQUIREMENTS.md` — TEST-01, TEST-02 definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_make_runner()` helper pattern (in each test file) — returns MagicMock runner with `is_cancelled.return_value = False`
- `@patch` decoration chain — standard mock pattern for `jobs.handlers.X.{function}`
- Checkpoint fixture shape from `test_handlers_batch_analyze.py` — `{'checkpoint': {'checkpoint_version': 1, 'job_type': '...', 'fingerprint': 'x', 'processed_pairs': []}}`

### Established Patterns
- Orphan recovery tests use `tempfile.TemporaryDirectory` + real `init_db` + `_recover_orphaned_jobs` import from `app`
- Handler tests use `patch` for `init_database`, `load_config`, `os.getenv`, `require_library_db`
- Assertions check `runner.complete_job.call_args` for result payload keys

### Integration Points
- `batch_describe` checkpoint lives under `metadata['checkpoint']` with `processed_pairs` list
- `batch_score` checkpoint uses `processed_triplets` list
- Fingerprint mismatch → handler logs mismatch message and resets (re-processes from scratch)

</code_context>

<specifics>
## Specific Ideas

- For describe fingerprint mismatch test: mock `fingerprint_batch_describe` to return a different value than what's in the checkpoint, assert the processed_pairs are not skipped
- For score fingerprint mismatch test: same pattern with `fingerprint_batch_score`
- For orphan recovery batch_score: same pattern as `test_recover_running_batch_analyze_with_checkpoint_requeues_pending` but with `batch_score` job type and score checkpoint shape

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 16-recovery-and-path-failure-unit-tests*
*Context gathered: 2026-05-06 (skip-discuss — scope clear)*
