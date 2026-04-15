# Plan 06-01 — Summary

**Title:** Scoring job handlers, vision + structured parse, and `image_scores` persistence  
**Executed:** 2026-04-12

## Outcomes

- **`build_scoring_user_prompt`** — Single-perspective JSON contract (`perspective_slug`, `score`, `rationale`) in `lightroom_tagger/core/prompt_builder.py`.
- **`lightroom_tagger/core/scoring_service.py`** — `compute_prompt_version`, idempotency helpers, `score_image_for_perspective` using `FallbackDispatcher` with `operation="score"`, `generate_description` + `parse_score_response_with_retry` with non-`None` `llm_fixer` from `make_score_json_llm_fixer` / `complete_chat_text`, and writes only via `supersede_previous_current_scores` + `insert_image_score`. Legacy path (`provider_id` omitted) uses `run_local_agent` + Ollama text repair for the fixer.
- **Checkpoints** — `fingerprint_batch_score` in `apps/visualizer/backend/jobs/checkpoint.py` (canonical JSON + sorted triple list).
- **Jobs** — `handle_single_score`, `handle_batch_score` in `handlers.py` registered on `JOB_HANDLERS`; batch work list mirrors `handle_batch_describe` image selection × selected perspectives; checkpoint field `processed_triplets`; parallel workers use per-thread library DB connections.
- **Tests** — `test_scoring_service.py`, extended `test_job_checkpoint.py`, new `test_handlers_batch_score.py`.
- **UI** — Processing → Descriptions: **Run batch scoring** (`JobsAPI.create('batch_score', …)`) sharing metadata builder with batch describe.

## Commits (atomic, newest last)

1. `feat(06-01): add build_scoring_user_prompt for score JSON contract`
2. `feat(06-01): add scoring_service with vision parse and image_scores writes`
3. `feat(06-01): add fingerprint_batch_score for scoring checkpoint resume`
4. `feat(06-01): add single_score and batch_score job handlers`
5. `test(06-01): add scoring_service unit and persistence tests`
6. `test(06-01): cover fingerprint_batch_score stability`
7. `test(06-01): add batch_score handler smoke and checkpoint tests`
8. `feat(06-01): add batch scoring control to Descriptions tab`

## Verification

- `pytest lightroom_tagger/core/test_scoring_service.py apps/visualizer/backend/tests/test_job_checkpoint.py apps/visualizer/backend/tests/test_handlers_batch_score.py -q` — pass (9 tests).
- `npm run build` in `apps/visualizer/frontend` — pass.
- `ruff check` on listed Python files — pass.
- `mypy lightroom_tagger/core/scoring_service.py lightroom_tagger/core/prompt_builder.py --follow-imports=silent` — pass.

## Deviations (Rule 1–4)

- **Rule 2 (process):** Plan verification cites bare `mypy` on those two paths; full transitive check reports existing errors in other modules. Isolated verification used `--follow-imports=silent` so only the touched modules are gates, matching the intent of “mypy-clean” new code.

## Not done here (per plan / scope)

- `STATE.md` / `ROADMAP.md` — intentionally not modified.
- REST `/api/scores` and catalog modal **single_score** — deferred to later phase work (referenced in `06-CONTEXT.md`).
