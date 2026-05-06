---
plan: 16-02
status: complete
---

# Summary: batch_score checkpoint gaps + orphan recovery for batch_score

## What was built

- **`test_handlers_batch_score.py`**: `test_batch_score_fingerprint_mismatch_resets_and_reprocesses` asserts that when the stored checkpoint fingerprint does not match the current job fingerprint (via patched stable vs stale values), the handler logs the batch_score mismatch message, re-invokes scoring for units that were marked processed under the stale checkpoint, and completes with the expected counts. `test_batch_score_stale_checkpoint_all_processed_completes` builds a real `fingerprint_batch_score(metadata, triples)` so `processed_triplets` matches canonical sorted labels; when every unit is already in the checkpoint, scoring is skipped and the job completes with `scored == 0` and `total` matching the work list.
- **`test_orphan_recovery.py`**: `test_recover_running_batch_score_with_checkpoint_requeues_pending` mirrors the batch_analyze recovery test for job type `batch_score` with a v1 flat checkpoint (`job_type`, fingerprint, empty `processed_triplets`, `total_at_start`); after `_recover_orphaned_jobs`, the job is `pending` and the recovery log line is present.

## Key files

- apps/visualizer/backend/tests/test_handlers_batch_score.py
- apps/visualizer/backend/tests/test_orphan_recovery.py

## Test results

```
..........                                                               [100%]
10 passed in 2.95s
```

## Self-Check: PASSED
