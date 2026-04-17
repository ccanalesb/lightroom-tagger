---
phase: 3
title: Unified Analyze job
milestone: v2.1
status: complete
verified_at: "2026-04-17T23:59:00.000Z"
---

# Phase 3 — Verification

Requirement coverage: **JOB-06**.

## Plans executed

| Plan | Title | Commit | Status |
|------|-------|--------|--------|
| 01 | Extract `_run_describe_pass` / `_run_score_pass` helpers | `d0aa5fd` | ✅ |
| 02 | `handle_batch_analyze` + nested checkpoints + `JOB_HANDLERS` | `1f96bd2` | ✅ |
| 03 | Backend tests for `batch_analyze` + orphan recovery | `b5e1299` | ✅ |
| 04 | Frontend `AnalyzeTab` rename, strings, primary CTA, advanced split | `60e9eae` | ✅ |

## Success criteria

1. **SC-1 — `batch_analyze` runs describe → score with shared selection.** ✅ Verified by
   `test_batch_analyze_runs_describe_then_score`, `test_batch_analyze_describe_failures_still_invoke_score`,
   and `handle_batch_analyze` building `shared_selection` once and passing it to both
   `_run_describe_pass` and `_run_score_pass` in `apps/visualizer/backend/jobs/handlers.py`.
2. **SC-2 — Default UI launches Analyze; advanced toggle exposes separate describe/score.** ✅
   `AnalyzeTab.tsx` renders only the primary **Analyze** button outside the Advanced disclosure
   and a "Run stages separately" section with describe-only / score-only buttons inside it.
3. **SC-3 — Existing `batch_describe` / `batch_score` tests continue to pass.** ✅
   `tests/test_handlers_batch_describe.py` and `tests/test_handlers_batch_score.py` were not
   edited and both suites are green after every refactor step.

## Must-haves (D-01..D-18)

- **D-05 / partial failures** — `test_batch_analyze_describe_failures_still_invoke_score`
  asserts score still runs for every image even when describe raises on one of them.
- **D-06 / combined payload** — `handle_batch_analyze` calls `runner.complete_job(job_id, {...})`
  with exactly `describe_total`, `describe_succeeded`, `describe_failed`, `score_total`,
  `score_succeeded`, `score_failed` (integers).
- **D-07 / 50/50 progress split** — describe pass receives `progress_range=(0, 50)`,
  score pass receives `progress_range=(50, 100)` via `_map_job_progress`.
- **D-08 / `current_step`** — `test_batch_analyze_sets_current_step_describing_then_scoring`
  asserts the handler calls `update_job_field(..., 'current_step', 'Describing')` before
  describe and `'Scoring'` before score. Added `'current_step'` to
  `database._ALLOWED_JOB_UPDATE_FIELDS` (minimum allowlist surface for D-08).
- **D-09 / primary CTA** — `startAnalyze` in `AnalyzeTab.tsx` calls
  `JobsAPI.create('batch_analyze', buildBatchJobMetadata())`.
- **D-10 / advanced split** — `ANALYZE_ADVANCED_RUN_SEPARATELY_TITLE` section lives inside
  the existing Advanced disclosure; describe-only and score-only buttons wire to
  `batch_describe` / `batch_score` with flat `force` for legacy handlers.
- **D-11 / two force booleans** — `forceDescribe` and `forceScore` state; analyze payload
  includes `force_describe` + `force_score`; legacy paths include flat `force` only.
- **D-12 / centralized strings** — `ANALYZE_CARD_TITLE`, `ANALYZE_CARD_SUBTITLE`,
  `ANALYZE_PRIMARY_BUTTON`, `ANALYZE_ADVANCED_*`, `ANALYZE_FORCE_*`, `ANALYZE_*_JOB_STARTED`,
  `ANALYZE_JOB_FAILED_PREFIX`, `TAB_ANALYZE` added to `constants/strings.ts`.
- **D-13 / full rename** — `git mv` preserves history; exported `AnalyzeTab`; tab id `'analyze'`;
  URL slug `?tab=analyze`; `/descriptions` legacy route redirects to `?tab=analyze`.
- **D-15..D-17 / resume + fingerprint mismatch** —
  `test_batch_analyze_resume_skips_describe_when_stage_score` proves the skip path;
  `test_batch_analyze_describe_fingerprint_mismatch_resets_pairs` proves the mismatch log
  `"checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh"`
  is emitted and describe restarts.
- **D-18 / orphan recovery** —
  `test_recover_running_batch_analyze_with_checkpoint_requeues_pending` passes without any
  `app.py` edit; recovery stays checkpoint-version-based.

## Automated checks

| Command | Result |
|---------|--------|
| `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_analyze.py tests/test_orphan_recovery.py tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` | ✅ 21 passed |
| `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest` | ⚠ 138 passed / 1 failed (`test_providers_api.py::TestDefaults::test_should_return_defaults` — pre-existing, unrelated to Phase 3; provider default drift between `ollama` and `github_copilot`) |
| `cd apps/visualizer/frontend && npx tsc --noEmit` | ✅ exit 0 (required fixing two pre-existing `window.setTimeout` → `setTimeout` typings in `MatchDetailModal.tsx` to clear pre-existing TS errors blocking the plan AC) |
| `cd apps/visualizer/frontend && npm test -- --run` | ✅ 121 passed / 21 files |

## Risks and follow-ups

- **Pre-existing provider-defaults test failure** is unrelated to Phase 3 and was present
  before execution started (verified via stash-and-rerun on `master@1f96bd2`).
- **`current_step` allowlist expansion** is the minimum change needed for D-08; no other
  plan in v2.1 currently writes to this field.
- **Documentation** — `checkpoint.py` module docstring now describes the nested
  `batch_analyze` checkpoint structure (Plan 02 scope).

## Sign-off

Phase 3 meets all three success criteria and all eighteen Plan-document decisions (D-01..D-18).
Ready to archive.
