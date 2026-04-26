---
plan: 03
title: Backend tests for batch_analyze and orphan recovery
wave: 3
depends_on: [02]
files_modified:
  - apps/visualizer/backend/tests/test_handlers_batch_analyze.py
  - apps/visualizer/backend/tests/test_orphan_recovery.py
autonomous: true
requirements:
  - JOB-06
---

<objective>
Add focused pytest coverage for `handle_batch_analyze` (SC-1, D-05, D-06, D-08, D-15–D-17) and extend orphan-recovery tests so a **running** `batch_analyze` job with `metadata.checkpoint.checkpoint_version == 1` re-queues to `pending` exactly like `batch_describe` today (**D-18**, orchestrator-verified behaviour in `app.py`).
</objective>

<context>
New tests live in `apps/visualizer/backend/tests/test_handlers_batch_analyze.py`. Follow the patching/stacking style from `tests/test_handlers_batch_describe.py` (`MagicMock` runner with `runner.is_cancelled.return_value = False`, patch `init_database`, `load_config`, `os.getenv`, `os.path.exists`, and the heavy IO entrypoints).

**SC-3 guard:** Never modify `tests/test_handlers_batch_describe.py` or `tests/test_handlers_batch_score.py` in this plan.

Orphan test mirrors `test_recover_running_job_with_checkpoint_requeues_pending` but uses `create_job(db, "batch_analyze", {})` and nested checkpoint JSON:

```json
{
  "checkpoint": {
    "checkpoint_version": 1,
    "job_type": "batch_analyze",
    "stage": "describe",
    "describe": {"fingerprint": "x", "processed_pairs": [], "total_at_start": 0},
    "score": {"fingerprint": "y", "processed_triplets": [], "total_at_start": 0}
  }
}
```

Assert post-recovery `status == "pending"` and log message substring `Recovered after restart; job re-queued with checkpoint.` appears (same assertion style as existing test).
</context>

<tasks>
<task id="3.1">
<action>
Create `apps/visualizer/backend/tests/test_handlers_batch_analyze.py` with at least these tests (names are binding):

1. `test_batch_analyze_completes_with_zero_images` — same fixture pattern as `test_batch_describe_should_complete_with_zero_images`: empty `fetchall`, call `handle_batch_analyze(runner, 'job', {'image_type': 'catalog'})`, assert `runner.complete_job` once, payload has `describe_total == 0`, `describe_succeeded == 0`, `describe_failed == 0`, `score_total == 0`, `score_succeeded == 0`, `score_failed == 0`.

2. `test_batch_analyze_runs_describe_then_score` — stub **two** underlying calls: patch `lightroom_tagger.core.description_service.describe_matched_image` to return `True` for two catalog keys **and** patch `_score_single_image` (import path `jobs.handlers._score_single_image`) to return `('scored', True, None)` twice per `(key, slug)` work units — simplest catalog-only with **one** perspective slug in metadata `perspective_slugs: ['p1']` so score processes two triplets. Assert describe mock count `2`, `_score_single_image` call count `2`, `complete_job` once, `describe_succeeded == 2`, `score_succeeded == 2`.

3. `test_batch_analyze_describe_failures_still_invoke_score` — two images: describe returns success then failure (e.g. `side_effect = [True, Exception('x')]`), `_score_single_image` always `('scored', True, None)`. Assert `complete_job` called, `describe_failed >= 1`, `score_succeeded == 2` (both images still scored) — proves D-05.

4. `test_batch_analyze_sets_current_step_describing_then_scoring` — minimal happy path with 1 image; wrap `jobs.handlers.update_job_field` with `MagicMock(wraps=real_fn)` or assert calls on `runner.db` if handler calls `update_job_field(runner.db, ...)` directly — **preferred:** `patch('jobs.handlers.update_job_field', wraps=update_job_field)` and assert call args include `('current_step', 'Describing')` before describe work and `('current_step', 'Scoring')` before score work (use `call_args_list` ordering).

5. `test_batch_analyze_resume_skips_describe_when_stage_score` — seed `get_job` / `runner` metadata via patching `jobs.handlers.get_job` so first read inside handler returns metadata with nested checkpoint `stage: "score"`, matching `describe.fingerprint` to whatever the handler computes for the mocked selection (use `patch.object` on `fingerprint_batch_describe` to return a constant `'fp'` both in stored checkpoint and live computation). Assert `describe_matched_image` (or `describe_matched_image` patch target) **not** called while `_score_single_image` **is** called — proves D-16 skip path.

6. `test_batch_analyze_describe_fingerprint_mismatch_resets_pairs` — arrange `get_job` to return nested checkpoint with mismatched `describe.fingerprint` vs patched `fingerprint_batch_describe` return value; assert log or `add_job_log` includes substring `checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh` (patch `add_job_log` and inspect messages list).

Each test file top should import `MagicMock`, `patch` like existing handler tests.
</action>
<read_first>
- apps/visualizer/backend/tests/test_handlers_batch_describe.py
- apps/visualizer/backend/tests/test_handlers_batch_score.py
- apps/visualizer/backend/jobs/handlers.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/backend/tests/test_handlers_batch_analyze.py && echo ok` prints `ok`
- `rg -n "def test_batch_analyze_completes_with_zero_images" apps/visualizer/backend/tests/test_handlers_batch_analyze.py` matches 1 line
- `rg -n "def test_batch_analyze_runs_describe_then_score" apps/visualizer/backend/tests/test_handlers_batch_analyze.py` matches 1 line
- `rg -n "def test_batch_analyze_describe_failures_still_invoke_score" apps/visualizer/backend/tests/test_handlers_batch_analyze.py` matches 1 line
- `rg -n "def test_batch_analyze_sets_current_step_describing_then_scoring" apps/visualizer/backend/tests/test_handlers_batch_analyze.py` matches 1 line
- `rg -n "handle_batch_analyze" apps/visualizer/backend/tests/test_handlers_batch_analyze.py` matches at least 6 lines
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_analyze.py -v` exits 0
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0 (SC-3 guard; executor must not save edits to those two files)
</acceptance_criteria>
</task>

<task id="3.2">
<action>
In `apps/visualizer/backend/tests/test_orphan_recovery.py`, append `test_recover_running_batch_analyze_with_checkpoint_requeues_pending()` duplicating the structure of `test_recover_running_job_with_checkpoint_requeues_pending` except:

- `create_job(db, "batch_analyze", {})`
- `meta["checkpoint"]` uses the nested JSON from `<context>` (`job_type`: `"batch_analyze"`, `stage`: `"describe"`, both sub-objects present).

Keep the same `UPDATE jobs SET status='running'...` pattern and assert identical recovery log substring and `status == "pending"` after `_recover_orphaned_jobs(db)`.
</action>
<read_first>
- apps/visualizer/backend/tests/test_orphan_recovery.py
- apps/visualizer/backend/app.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "def test_recover_running_batch_analyze_with_checkpoint_requeues_pending" apps/visualizer/backend/tests/test_orphan_recovery.py` matches 1 line
- `rg -n '"job_type": "batch_analyze"' apps/visualizer/backend/tests/test_orphan_recovery.py` matches at least 1 line
- `rg -n '"stage": "describe"' apps/visualizer/backend/tests/test_orphan_recovery.py` matches at least 1 line
- `rg -n "create_job\(db, \"batch_analyze\"" apps/visualizer/backend/tests/test_orphan_recovery.py` matches 1 line
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_orphan_recovery.py -v` exits 0
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0 (SC-3 regression)
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_analyze.py tests/test_orphan_recovery.py tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/ -v` exits 0 (full backend suite)
</verification>

<must_haves>
- **SC-1:** At least one test proves describe and score both execute against the same mocked selection cardinality.
- **D-05:** Describe partial failure test still expects score calls / `score_succeeded` consistent with full selection size.
- **D-06:** Zero-work and happy-path tests assert the six combined metric keys exist and are ints.
- **D-08:** `current_step` ordering assertions exist.
- **D-15–D-17:** Resume + mismatch tests exist with the exact mismatch log strings from CONTEXT.
- **D-18 / orphan:** New `batch_analyze` orphan recovery test passes without any `app.py` change.
- **SC-3:** Legacy handler tests untouched and green.
</must_haves>
