---
phase: 16
status: findings
files_reviewed: 3
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
---

# Code Review: Phase 16

## Summary

The Phase 16 additions exercise checkpoint resume, fingerprint mismatch reset, “all work already in checkpoint” completion, and `batch_score` orphan recovery. Mock wiring matches how `analyze` resolves library DB, loads jobs via `get_job`, and calls into `_run_describe_pass` / `_run_score_pass`. Fingerprint setup aligns with production code: `fingerprint_batch_describe` preserves pair order from selection; `fingerprint_batch_score` canonicalizes triple order via sort, so the stale-checkpoint score test correctly builds `fp` from a triple list whose iteration order differs from DB row order.

Overall the tests are meaningful and should catch regressions in skip/resume and recovery paths. One describe test stops short of the same end-to-end assertions as its score counterpart; remaining notes are minor brittleness and style.

## Findings

### Warning

1. **`test_batch_describe_fingerprint_mismatch_resets_and_reprocesses` — weak terminal assertions**  
   The test proves the mismatch log line and a single `describe_matched_image` call on the expected key, but unlike `test_batch_score_fingerprint_mismatch_resets_and_reprocesses` it does not assert `runner.complete_job` (or result totals such as `described` / `total`). A future regression that cleared the mismatch state and invoked describe but failed to finalize the job might go unnoticed. Consider mirroring the score test: `complete_job` once with `described == 1`, `total == 1` (and optionally `clear_checkpoint`).

### Info

1. **SQL-string branching in `mock_db.execute` helpers (`test_handlers_batch_score.py`)**  
   The `_exec` functions classify queries using substrings such as `'FROM images'` and `'image_scores'`. This matches existing patterns in the same file but will need updates if SQL text changes. Acceptable for unit tests; worth knowing if refactors start failing mysteriously.

2. **Duplication in `test_orphan_recovery.py`**  
   `test_recover_running_batch_score_with_checkpoint_requeues_pending` follows the same tempfile → `init_db` → `create_job` → `UPDATE` → `_recover_orphaned_jobs` → assertions shape as the `batch_describe` / `batch_analyze` cases. A `@pytest.mark.parametrize` over job type + checkpoint JSON would shrink noise; optional cleanup only.

3. **Naming: “stale” vs fingerprint mismatch**  
   `test_batch_describe_stale_checkpoint_no_work_completes` and `test_batch_score_stale_checkpoint_all_processed_completes` mean “checkpoint matches fingerprint and backlog is empty,” not “fingerprint stale.” The sibling tests use “fingerprint_mismatch” clearly. Consider renaming to e.g. `*_checkpoint_fully_resumed_completes` if future readers find “stale” ambiguous.

## Test isolation and quality notes

- **Isolation:** Handler tests use `@patch` scopes per test; orphan tests use `TemporaryDirectory` and a fresh SQLite file each time. No shared global state observed.
- **Correctness highlights:**  
  - Describe resume test fixes `max_workers: 1` so execution stays on the sequential path and `describe_matched_image` call count stays deterministic.  
  - Score stale test lists DB keys as `img_z` then `img_a` while the fingerprint uses sorted triple order; checkpoint `processed_triplets` cover both units — consistent with `fingerprint_batch_score` implementation.  
  - Orphan recovery for `batch_score` correctly expects `checkpoint_version == 1` to trigger re-queue, matching `_recover_orphaned_jobs` in `app.py`.
