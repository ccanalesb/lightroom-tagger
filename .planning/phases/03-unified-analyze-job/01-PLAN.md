---
plan: 01
title: Extract describe/score pass helpers and thin handler wrappers
wave: 1
depends_on: []
files_modified:
  - apps/visualizer/backend/jobs/handlers.py
autonomous: true
requirements:
  - JOB-06
---

<objective>
Refactor `handle_batch_describe` and `handle_batch_score` in `apps/visualizer/backend/jobs/handlers.py` so their post-selection processing bodies move into shared helpers `_run_describe_pass` and `_run_score_pass`, each accepting an explicit `selection` (pairs for describe; pairs for score — score helper expands to triples internally as today) and a `progress_range=(lo, hi)` that remaps every internal `0..100` progress tick onto `[lo, hi]` on the job row. Wrappers keep DB open/close, metadata parsing, and image-list construction unchanged; they call the helper with `progress_range=(0, 100)` and `log_prefix=""` so behaviour and checkpoints for `batch_describe` / `batch_score` stay identical (SC-3).
</objective>

<context>
Implements **D-01** and **D-02** only: extraction + wrapper rewire. **D-03**–**D-08**, nested `batch_analyze` checkpoints, and `handle_batch_analyze` land in plan **02**. Orphan recovery stays checkpoint-version-based in `app.py` (no allowlist); no `app.py` edits in this plan.

Progress remapping rule (from orchestrator): inside each helper, replace every `runner.update_progress(job_id, pct, msg)` where `pct` is the handler’s historical `0..100` style value with:

```python
lo, hi = progress_range
mapped = int(lo + (hi - lo) * pct / 100)
runner.update_progress(job_id, mapped, f"{log_prefix}{msg}" if log_prefix else msg)
```

With `progress_range=(0, 100)` this is a no-op for existing wrappers. Use the same mapping for the initial “Found N …” progress lines (today `int(5 + … * 90)` style) — treat the first argument to `update_progress` as the already-computed `pct` in `0..100` before mapping.

Checkpoint payloads written by `runner.persist_checkpoint` inside the helpers must remain exactly:

- Describe: `{'job_type': 'batch_describe', 'fingerprint': fp_bd, 'processed_pairs': sorted(processed_pairs), 'total_at_start': total_at_start}`
- Score: `{'job_type': 'batch_score', 'fingerprint': fp_bs, 'processed_triplets': sorted(processed_triplets), 'total_at_start': total_at_start}`

Resume reads must still require `chk.get('job_type') == 'batch_describe'` / `'batch_score'` exactly as today.
</context>

<tasks>
<task id="1.1">
<action>
In `apps/visualizer/backend/jobs/handlers.py`, immediately **above** `def handle_batch_describe(runner, job_id: str, metadata: dict):` (currently line ~943), add a small private helper:

```python
def _map_job_progress(progress_range: tuple[float, float], pct: int) -> int:
    lo, hi = progress_range
    return int(lo + (hi - lo) * pct / 100)
```

Add `_run_describe_pass` with this exact signature (type hints optional if the file omits them elsewhere, but names and parameter order are binding):

```python
def _run_describe_pass(
    runner,
    job_id: str,
    metadata: dict,
    lib_db,
    selection: list[tuple[str, str]],
    *,
    db_path: str,
    progress_range: tuple[float, float],
    log_prefix: str = "",
) -> None:
```

Move into `_run_describe_pass` **everything** from the current `handle_batch_describe` body starting at `total_at_start = len(images_to_describe)` through the successful-path `runner.clear_checkpoint(job_id)` + `runner.complete_job(job_id, result_summary)` **inclusive**, but change the opening line to `total_at_start = len(selection)` and set `images_to_describe = list(selection)` (copy) before fingerprint/checkpoint logic.

Inside the moved block:
- Replace `force = metadata.get('force', False)` with the same expression (still read from `metadata` — wrappers keep passing flat `force` for `batch_describe`).
- Re-read `max_workers`, `desc_provider_id`, `desc_provider_model`, `perspective_slugs`, `image_type`, `date_filter` from `metadata` exactly as the current handler does (either keep the assignments that currently live above `total_at_start` inside the helper by re-deriving from `metadata`, or pass them as extra parameters — **preferred:** re-derive from `metadata` inside `_run_describe_pass` to minimize wrapper parameter churn).
- Every `runner.update_progress(job_id, <expr>, <msg>)` becomes `runner.update_progress(job_id, _map_job_progress(progress_range, <expr>), f"{log_prefix}{msg}" if log_prefix else msg)`.
- Keep `runner.persist_checkpoint` bodies unchanged (`'job_type': 'batch_describe'`, same keys).
- Keep checkpoint resume guard: `chk_bd.get('job_type') == 'batch_describe'` unchanged.

Rewrite `handle_batch_describe` so that after `images_to_describe` is fully populated (the catalog/instagram branches ending ~line 1022), the only remaining work in the `try` before `except` is:

```python
_run_describe_pass(
    runner,
    job_id,
    metadata,
    lib_db,
    images_to_describe,
    db_path=db_path,
    progress_range=(0, 100),
    log_prefix="",
)
```

Remove the duplicated code block that now lives in `_run_describe_pass`. Preserve `old_model_env`, outer `try`/`except`/`finally`, `lib_db` open/close, and the `DESCRIPTION_VISION_MODEL` restore in `finally` exactly as today.
</action>
<read_first>
- apps/visualizer/backend/jobs/handlers.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "def _map_job_progress\(progress_range: tuple\[float, float\], pct: int\) -> int:" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "def _run_describe_pass\(" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "_run_describe_pass\(" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines (definition + call from `handle_batch_describe`)
- `rg -n "progress_range=\(0, 100\)" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line inside or next to `handle_batch_describe`
- `rg -n "'job_type': 'batch_describe'" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line (checkpoint payload)
- `rg -n "chk_bd\.get\('job_type'\) == 'batch_describe'" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py -v` exits 0 with **zero** test file edits
</acceptance_criteria>
</task>

<task id="1.2">
<action>
In the same file, add `_run_score_pass` immediately before `def handle_batch_score(runner, job_id: str, metadata: dict):` with signature:

```python
def _run_score_pass(
    runner,
    job_id: str,
    metadata: dict,
    lib_db,
    selection: list[tuple[str, str]],
    *,
    db_path: str,
    progress_range: tuple[float, float],
    log_prefix: str = "",
) -> None:
```

Move into `_run_score_pass` the full processing body from the current `handle_batch_score` starting at `images_for_scores: list[tuple[str, str]] = []` through `runner.clear_checkpoint(job_id)` + `runner.complete_job(job_id, score_result)` **inclusive**, but replace the opening collection with: start from `images_for_scores = list(selection)` and **delete** the duplicated SQL / `list_perspectives` / catalog+instagram population block that previously rebuilt `images_for_scores` (lines ~1293–1341 today). The helper must still:

- Resolve `perspective_slugs` from `metadata` or `list_perspectives(lib_db, active_only=True)` exactly as today.
- Build `work_triples`, `fp_bs`, checkpoint resume with `chk_bs.get('job_type') == 'batch_score'`, DB pre-filter for already-scored triplets when `not force`, parallel vs sequential branches, `record_done` with `'job_type': 'batch_score'` payload, `consecutive_failures` stop logic, and final `score_result` dict keys (`scored`, `skipped`, `failed`, `total`, `image_type`, `date_filter`, `force`).

Remap **all** `runner.update_progress(job_id, …)` calls in this block through `_map_job_progress(progress_range, …)` and prefix `msg` with `log_prefix` when non-empty.

Rewrite `handle_batch_score` so the `try` body keeps: config/db_path checks, `lib_db = init_database`, metadata parsing (`image_type`, `date_filter`, `force`, providers, `months`, `min_rating`, `max_workers`, `perspective_slugs` resolution), rebuild `images_for_scores` with the **same** catalog/instagram SQL and branches as today (lines ~1293–1341), then call:

```python
_run_score_pass(
    runner,
    job_id,
    metadata,
    lib_db,
    images_for_scores,
    db_path=db_path,
    progress_range=(0, 100),
    log_prefix="",
)
```

Remove the duplicated score loop/checkpoint/complete section from `handle_batch_score`.
</action>
<read_first>
- apps/visualizer/backend/jobs/handlers.py
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "def _run_score_pass\(" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "_run_score_pass\(" apps/visualizer/backend/jobs/handlers.py` matches at least 2 lines (definition + call from `handle_batch_score`)
- `rg -n "'job_type': 'batch_score'" apps/visualizer/backend/jobs/handlers.py` matches at least 1 line inside `_run_score_pass` (or reachable from it)
- `rg -n "chk_bs\.get\('job_type'\) == 'batch_score'" apps/visualizer/backend/jobs/handlers.py` matches 1 line
- `rg -n "_map_job_progress\(progress_range," apps/visualizer/backend/jobs/handlers.py` matches at least 4 lines total (describe + score paths each use it)
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_score.py -v` exits 0 with **zero** test file edits
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0 (combined SC-3 gate)
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py -v` exits 0
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_orphan_recovery.py -v` exits 0 (refactor must not break recovery tests)
- `rg -n "def handle_batch_describe" apps/visualizer/backend/jobs/handlers.py` matches 1 line; `rg -n "def handle_batch_score" apps/visualizer/backend/jobs/handlers.py` matches 1 line
</verification>

<must_haves>
- **D-01 / D-02:** `_run_describe_pass` and `_run_score_pass` exist; `handle_batch_describe` / `handle_batch_score` are thin orchestration wrappers (open DB, parse metadata, build selection, call helper, handle exceptions) with `progress_range=(0, 100)` and empty `log_prefix`.
- **SC-3:** `apps/visualizer/backend/tests/test_handlers_batch_describe.py` and `apps/visualizer/backend/tests/test_handlers_batch_score.py` pass with **no file modifications**.
- Flat checkpoint contract unchanged: `job_type` `'batch_describe'` / `'batch_score'`, same fingerprint helpers, same resume keys (`processed_pairs` / `processed_triplets`).
- All internal progress ticks for the two job types are driven through `_map_job_progress` so plan **02** can pass `(0, 50)` / `(50, 100)` without duplicating loop bodies.
</must_haves>
