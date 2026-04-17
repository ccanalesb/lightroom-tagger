---
plan: 02
title: handle_batch_analyze orchestration, nested checkpoints, registry, checkpoint docstring
wave: 2
depends_on: [01]
files_modified:
  - apps/visualizer/backend/jobs/handlers.py
  - apps/visualizer/backend/jobs/checkpoint.py
autonomous: true
requirements:
  - JOB-06
---

<objective>
Implement `handle_batch_analyze` so one job runs describe then score over a single shared `(key, itype)` selection (**D-03**, **D-04**, **SC-1**), with **D-07** progress split `(0, 50)` then `(50, 100)`, **D-08** `current_step` values `"Describing"` / `"Scoring"` via `update_job_field(runner.db, job_id, 'current_step', ...)`, **D-06** combined result keys, **D-15**–**D-17** nested checkpoints, and **`JOB_HANDLERS`** registration. Extend `_run_describe_pass` / `_run_score_pass` from plan **01** with `finalize: bool = True` (default preserves `batch_describe` / `batch_score` behaviour) plus `nested_analyze_checkpoint: bool = False` for persistence routing. Update `checkpoint.py` module docstring for **D-18** (docs only; `app.py` orphan recovery stays checkpoint-version-based with no job-type allowlist).
</objective>

<context>
**Amendment to plan 01 helpers (same file, this plan owns the diff):** Add kw-only `finalize: bool = True` to `_run_describe_pass` and `_run_score_pass`. When `finalize=True` (default), keep identical end behaviour: `runner.clear_checkpoint(job_id)` then `runner.complete_job(job_id, <same dict shape as today>)` on success paths. When `finalize=False`, skip the terminal `clear_checkpoint` + `complete_job` pair **only** on the success path where the job would otherwise complete normally, and **return** a `dict` summary instead (`handle_batch_describe` / `handle_batch_score` always pass `finalize=True` so SC-3 holds). The helper must still call `fail_job` / `finalize_cancelled` / early `complete_job` for zero-work exactly as today — only the “happy heavy work finished” path is deferrable.

**Return convention:** `_run_describe_pass(..., finalize=False) -> dict | None` returns `None` if the job was already failed/cancelled/finalized inside the helper (caller should `return` immediately). On success with `finalize=False`, return at least: `{"described": int, "skipped": int, "failed": int, "total": int}` (mirror existing `result_summary` keys). `_run_score_pass(..., finalize=False)` returns `None` or `{"scored": int, "skipped": int, "failed": int, "total": int}` mirroring `score_result`.

**Metadata normalization (D-11):**

```python
metadata_for_describe = {**metadata, "force": bool(metadata.get("force_describe", False))}
metadata_for_score = {**metadata, "force": bool(metadata.get("force_score", False))}
```

Use these for `fingerprint_batch_describe` / `_run_describe_pass` and `fingerprint_batch_score` / `_run_score_pass` respectively inside `handle_batch_analyze`.

**Combined `complete_job` payload (D-06)** — exact keys required in the dict passed to `runner.complete_job` for `batch_analyze`:

`describe_total`, `describe_succeeded`, `describe_failed`, `score_total`, `score_succeeded`, `score_failed` (map `described→describe_succeeded`, `failed→describe_failed`, score similarly; totals use each pass’s `total` field).

**Nested checkpoint (D-15–D-17):** `merge_checkpoint_into_metadata` replaces the whole `metadata["checkpoint"]`. Implement `_analyze_load_checkpoint(runner, job_id) -> dict` reading `get_job` and returning the nested `checkpoint` dict or `{}`. Implement `_analyze_merge_persist(runner, job_id, *, stage: str, describe: dict, score: dict)` building `checkpoint_body = {"job_type": "batch_analyze", "stage": stage, "describe": describe, "score": score}` and calling `runner.persist_checkpoint(job_id, checkpoint_body)`. Each stage helper supplies updated `describe` or `score` sub-object while copying the sibling from `_analyze_load_checkpoint` when unchanged.

**Resume (D-16):** After building `shared_selection`, if loaded checkpoint has `stage == "score"` and `describe.fingerprint == fingerprint_batch_describe(metadata_for_describe, shared_selection)` with consistent `processed_pairs` semantics, skip describe and jump to score with `update_job_field(..., "Scoring")`. Otherwise run describe first with `"Describing"`.

**Fingerprint mismatch (D-17):** Use exact log strings:

- `checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh`
- `checkpoint mismatch: batch_analyze score fingerprint changed, starting score fresh`

**D-18:** Extend `apps/visualizer/backend/jobs/checkpoint.py` module docstring with a `**batch_analyze**` bullet documenting nested `describe` / `score`, `stage`, and fingerprint fields per D-15. Do **not** edit `apps/visualizer/backend/app.py` for allowlisting.
</context>

<tasks>
<task id="2.1">
<action>
In `apps/visualizer/backend/jobs/handlers.py`:

1. Add `_analyze_load_checkpoint`, `_analyze_merge_persist` (or equivalently named private functions) implementing `<context>` merge rules.

2. Extend `_run_describe_pass` and `_run_score_pass` signatures with kw-only `finalize: bool = True` and `nested_analyze_checkpoint: bool = False`. Default values preserve plan-01 behaviour.

3. When `nested_analyze_checkpoint=True`, replace flat `runner.persist_checkpoint` bodies with calls to `_analyze_merge_persist` that set `stage` to `'describe'` or `'score'` matching the active helper, and embed `fingerprint`, sorted processed ids list, `total_at_start` under the correct nested key.

4. When `nested_analyze_checkpoint=True`, replace checkpoint **resume** reads to load `processed_*` from nested `describe` / `score` objects when top-level `job_type == 'batch_analyze'` and fingerprints match; apply D-17 mismatch logs when fingerprints differ.

5. Update `handle_batch_describe` / `handle_batch_score` call sites to pass `finalize=True` explicitly (or rely on default) and `nested_analyze_checkpoint=False`.

6. Run SC-3 gate: `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` must exit **0** with **no edits** to those test files.
</action>
<read_first>
- apps/visualizer/backend/jobs/handlers.py
- apps/visualizer/backend/jobs/checkpoint.py
- apps/visualizer/backend/jobs/runner.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "finalize: bool = True" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines (both helper signatures) OR `rg -n "\*, finalize: bool = True" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines
- `rg -n "nested_analyze_checkpoint: bool = False" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines
- `rg -n "def _analyze_load_checkpoint" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "def _analyze_merge_persist" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "checkpoint mismatch: batch_analyze describe fingerprint changed, starting describe fresh" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "checkpoint mismatch: batch_analyze score fingerprint changed, starting score fresh" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0 without modifying either test file
</acceptance_criteria>
</task>

<task id="2.2">
<action>
In `apps/visualizer/backend/jobs/handlers.py`, implement `def handle_batch_analyze(runner, job_id: str, metadata: dict):` that:

1. Opens `lib_db` using the same `db_path` resolution pattern as `handle_batch_describe`.

2. Builds `shared_selection: list[tuple[str, str]]` using **identical** query logic to `handle_batch_describe` (catalog + instagram branches with `force`, `months`, `min_rating`, `get_undescribed_*`).

3. Builds `metadata_for_describe` / `metadata_for_score` per `<context>`.

4. Runs resume logic per `<context>` then:
   - `update_job_field(runner.db, job_id, 'current_step', 'Describing')` before starting describe (skip this write if describe is skipped by resume and you jump straight to score — then first write should be `'Scoring'` only).
   - Calls `_run_describe_pass(..., metadata=metadata_for_describe, selection=shared_selection, progress_range=(0, 50), log_prefix='[describe] ', nested_analyze_checkpoint=True, finalize=False)` when describe should run; if it returns `None`, return from `handle_batch_analyze`.
   - Before score: `update_job_field(runner.db, job_id, 'current_step', 'Scoring')`.
   - Calls `_run_score_pass(..., metadata=metadata_for_score, selection=shared_selection, progress_range=(50, 100), log_prefix='[score] ', nested_analyze_checkpoint=True, finalize=False)`; if `None`, return.

5. On success of both passes (both dicts non-None), `runner.clear_checkpoint(job_id)` once, then `runner.complete_job(job_id, combined)` with the six mandatory D-06 keys.

6. Append to `JOB_HANDLERS` dict exactly: `'batch_analyze': handle_batch_analyze,` (alphabetical placement optional; `rg` below pins presence).

7. Zero-selection behaviour: if both passes would do no work consistent with existing handlers, still complete successfully with numeric zeros for all six keys.
</action>
<read_first>
- apps/visualizer/backend/jobs/handlers.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "def handle_batch_analyze\(runner, job_id: str, metadata: dict\):" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "'batch_analyze': handle_batch_analyze" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "update_job_field\(runner\.db, job_id, 'current_step', 'Describing'\)" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line
- `rg -n "update_job_field\(runner\.db, job_id, 'current_step', 'Scoring'\)" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line
- `rg -n "_run_describe_pass\(" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines
- `rg -n "progress_range=\(0, 50\)" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line
- `rg -n "progress_range=\(50, 100\)" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line
- `rg -n "describe_total" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line
- `rg -n "score_succeeded" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0 (SC-3 guard)
</acceptance_criteria>
</task>

<task id="2.3">
<action>
In `apps/visualizer/backend/jobs/checkpoint.py`, extend the module docstring (lines 1–20 today) with a new bullet **`batch_analyze`** describing: top-level `job_type` `batch_analyze`, `stage` (`describe`|`score`), nested `describe` object (`fingerprint`, `processed_pairs`, `total_at_start`), nested `score` object (`fingerprint`, `processed_triplets`, `total_at_start`), and that `checkpoint_version: 1` applies at the merged checkpoint root (same as other jobs). No runtime logic changes in this file.
</action>
<read_first>
- apps/visualizer/backend/jobs/checkpoint.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "\*\*batch_analyze\*\*" apps/visualizer/backend/jobs/checkpoint.py` matches 1 line
- `rg -n "processed_triplets" apps/visualizer/backend/jobs/checkpoint.py` matches at least 2 lines (existing `batch_score` + new `batch_analyze` mention)
- `rg -n "batch_analyze" apps/visualizer/backend/jobs/checkpoint.py` matches at least 2 lines
- `cd apps/visualizer/backend && PYTHONPATH=. python -c "import jobs.checkpoint as c; assert 'batch_analyze' in c.__doc__; print('ok')"` prints `ok`
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0
- `rg -n "'batch_analyze'" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines (handler def context + dict key)
- `cd apps/visualizer/backend && PYTHONPATH=. python -c "from jobs.handlers import JOB_HANDLERS, handle_batch_analyze; assert JOB_HANDLERS.get('batch_analyze') is handle_batch_analyze; print('ok')"` prints `ok`
</verification>

<must_haves>
- **SC-1 / D-03 / D-04:** `handle_batch_analyze` builds selection once and passes the same `shared_selection` into both `_run_describe_pass` and `_run_score_pass` (score still expands to triples internally).
- **D-06:** Successful `batch_analyze` `complete_job` payload includes `describe_total`, `describe_succeeded`, `describe_failed`, `score_total`, `score_succeeded`, `score_failed`.
- **D-07:** Describe uses `progress_range=(0, 50)`; score uses `(50, 100)` with `[describe] ` / `[score] ` log prefixes.
- **D-08:** `current_step` updates to `"Describing"` / `"Scoring"` at the correct stage boundaries (no typos).
- **D-11:** Force flags come from `force_describe` / `force_score` via shallow-merge metadata passed into helpers.
- **D-15–D-17:** Nested checkpoint read/write + mismatch logs + resume skip rules implemented.
- **D-18:** `checkpoint.py` documents `batch_analyze`; no fictional `app.py` allowlist added.
- **SC-3:** Describe/score test files unchanged and passing after this plan.
</must_haves>
