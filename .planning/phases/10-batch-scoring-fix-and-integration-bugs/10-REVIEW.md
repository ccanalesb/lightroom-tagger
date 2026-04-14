---
status: issues_found
phase: 10
depth: standard
files_reviewed: 8
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
---

# Code Review: Phase 10

## Summary

Batch scoring now aligns the non-force catalog image set with the filtered SQL used for force scoring, and identity suggestions correctly thread pagination offset while restricting score aggregation to catalog rows. The changes are coherent and tests cover the main regression risks; two medium issues remain (misleading suggestions empty state when offset is past the end, and missing job logs on the parallel batch_score path).

## Findings

### WARNING-01: Misleading `empty_state` when `offset` exceeds candidate count

**File:** lightroom_tagger/core/identity_service.py  
**Line:** 533–536  
**Severity:** warning  
**Description:** After slicing `page = candidates_full[offset : offset + lim]`, if the slice is empty because `offset` (or `offset + limit`) is past the list—while `total_candidates` is still greater than zero—the code sets `empty_state` to “No unposted catalog images meet perspective coverage…”. That text describes a real empty catalog of suggestions, not “no rows on this page.” API clients that pass a large `offset` (or a bug in the client) get the wrong diagnostic.  
**Suggestion:** Only set that message when `total_candidates == 0`. If `total_candidates > 0` and `out_candidates` is empty, set `empty_state` to something like “No more suggestions on this page” or leave `empty_state` null and rely on `total` + empty `candidates`.

### WARNING-02: Parallel `batch_score` workers omit `log_callback`

**File:** apps/visualizer/backend/jobs/handlers.py  
**Line:** 1443–1450  
**Severity:** warning  
**Description:** The sequential path defines `log_callback` and passes it to `_score_single_image`, but `process_score_worker` passes `None`. For `max_workers > 1` and `total > 3`, detailed scoring logs are not attached to the job, unlike the sequential path and unlike batch describe patterns that may still surface warnings per item via other means.  
**Suggestion:** Thread logging into workers in a thread-safe way (e.g. a small queue consumed on the main thread that calls `add_job_log`, or a callback that marshals to the coordinator thread), matching sequential behavior.

### INFO-01: Duplicated catalog SQL for `force` True vs False

**File:** apps/visualizer/backend/jobs/handlers.py  
**Line:** 1287–1315  
**Severity:** info  
**Description:** The catalog branch repeats the same `SELECT key FROM images` + optional `WHERE` construction for both `force` branches. This matches the intended fix (non-force uses the same image universe as force before the current-score pre-filter) but duplicates logic and risks future drift if one branch is edited alone.  
**Suggestion:** Build `sql` / `sql_params` once for catalog (after the `if force` / `else` distinction is no longer needed for selection), or extract a small helper `_catalog_keys_for_batch_score(lib_db, months, min_rating)`.

### INFO-02: Tests do not assert date / rating filters on non-force batch_score

**File:** apps/visualizer/backend/tests/test_handlers_batch_score.py  
**Line:** (file-level)  
**Severity:** info  
**Description:** `test_batch_score_non_force_never_calls_get_undescribed_catalog_images` proves the undescribed helper is not used and scoring runs, but nothing verifies that `date_filter` / `months` or `min_rating` are applied to the catalog `SELECT` in the non-force path. A regression could drop those predicates without failing tests.  
**Suggestion:** Add a test where `mock_db.execute` captures SQL/params (or side-effect inspects call args) for `SELECT key FROM images` with `date_taken` / `rating` conditions when `date_filter` and `min_rating` are set.

### INFO-03: DB pre-filter for “already scored” only runs when `slug_versions` is non-empty

**File:** apps/visualizer/backend/jobs/handlers.py  
**Line:** 1373–1401  
**Severity:** info  
**Description:** If every slug in `perspective_slugs` fails `get_perspective_by_slug`, `slug_versions` stays empty, the `if slug_versions:` block is skipped, and no pre-filter runs—though work triples may still be scheduled for those slugs. This is an edge case (misconfigured slugs) but can mean redundant scoring attempts until failures accumulate.  
**Suggestion:** If `perspective_slugs` was explicitly provided and any slug has no row, fail fast or log a clear warning; or run pre-filter only for known slugs and drop unknown slugs from `work_triples`.
