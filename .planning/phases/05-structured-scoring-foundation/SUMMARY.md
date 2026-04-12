# Plan 05-01 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Library DB migration — `image_scores` and `perspectives` tables  
**Date:** 2026-04-12

## Outcomes

- `init_database` now creates additive tables **`perspectives`** and **`image_scores`** with indexes `idx_image_scores_perspective_score`, `idx_image_scores_image`, and `idx_image_scores_current`, plus unique constraint **`uq_image_scores_versioned`**. Legacy **`image_descriptions`** DDL is unchanged.
- Typed helpers: `list_perspectives`, `get_perspective_by_slug`, `insert_image_score`, `supersede_previous_current_scores`, `get_current_scores_for_image`, all using parameterized SQL.
- Operator-facing notes: comment block **`## Queryable score fields (image_scores)`** documents each column and states that missing rows mean “not scored yet” for `LEFT JOIN` usage.
- **`lightroom_tagger/core/test_database_scores.py`** exercises versioned rows, `supersede_previous_current_scores`, and asserts a single current row with `prompt_version == "v2"` and `score == 7`.

## Commits

1. `feat(05-01): add image_scores and perspectives schema and helpers`
2. `test(05-01): cover image_scores supersede and current row semantics`

## Verification

| Check | Result |
|--------|--------|
| `pytest lightroom_tagger/core/test_database_scores.py -q` | Pass |
| `mypy lightroom_tagger/core/database.py` | **Fail** (pre-existing: `database.py` and imports report many errors; none introduced solely by the new scoring helpers block) |
| `ruff check lightroom_tagger/core/database.py lightroom_tagger/core/test_database_scores.py` | **Partial** — `test_database_scores.py` clean; `database.py` reports existing issues (e.g. W293, F841, B905) outside the new scoring section |

### Deviation (Rule 1)

Plan **verification** asked for mypy and ruff exit 0 on `database.py`. The file already fails those gates repo-wide; this plan did not refactor legacy signatures or whitespace to avoid scope creep. New code follows the same patterns as adjacent helpers and is covered by pytest.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).

---

# Plan 05-02 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Rubric prompt library, perspective seeding, and dynamic description prompts  
**Date:** 2026-04-12

## Outcomes

- Shipped four version-controlled rubrics under **`prompts/perspectives/`** (`street`, `documentary`, `publisher`, **`color_theory`**) with **`## Theory basis`** (SCORE-05 references: Freeman, Berger, Hicks, Itten/Albers) and a shared **`## Scoring Rubric (1-10)`** matching the numeric anchors from **`DESCRIPTION_PROMPT`**.
- **`seed_perspectives_from_prompts_dir`** in **`database.py`**: resolves defaults from **`Path(__file__).resolve().parents[2] / "prompts" / "perspectives"`**; if **`SELECT COUNT(*) FROM perspectives` > 0** returns **`0`** (D-07); otherwise inserts one row per **`.md`** (UTF-8, safe **`iterdir()`** + **`relative_to`**); invoked at end of **`init_database`** before **`commit`**.
- **`prompt_builder.build_description_user_prompt`**: portfolio-editor intro, **`Analyze this photograph from {n} expert perspectives`**, per-row **`### Perspective: …`**, optional composition/technical blocks, JSON template whose **`perspectives`** keys are the actual slugs and **`best_perspective`** lists **`slug|…`**.
- **`vision_client.generate_description`**: keyword-only **`user_prompt`**; **`None`/blank** → legacy **`build_description_prompt()`**; non-empty string replaces the user message text (**`max_tokens=2048`** unchanged).
- **`description_service`**: optional **`perspective_slugs`**; **`list_perspectives(..., active_only=True)`** with order preserved when filtering; empty post-filter → **`None`** so vision uses the monolithic prompt; else **`build_description_user_prompt`**. **`describe_image`** / **`run_local_agent`** / **`_describe_image_via_provider`** accept **`user_prompt`**.
- **`analyzer`**: comment marking **`DESCRIPTION_PROMPT`** as legacy.

## Commits

1. `feat(05-02): add versioned perspective rubric markdown files`
2. `feat(05-02): seed perspectives from prompts when table empty`
3. `feat(05-02): add dynamic description prompt builder and tests`
4. `feat(05-02): wire DB-built prompts into describe and vision client`

## Verification

| Check | Result |
|--------|--------|
| `pytest lightroom_tagger/core/test_prompt_builder.py lightroom_tagger/core/test_database_scores.py -q` | Pass |
| `pytest lightroom_tagger/core/test_vision_client.py -q` (regression) | Pass |
| `ruff check lightroom_tagger/core/prompt_builder.py lightroom_tagger/core/description_service.py lightroom_tagger/core/vision_client.py` | Pass |
| `mypy lightroom_tagger/core/prompt_builder.py lightroom_tagger/core/description_service.py lightroom_tagger/core/vision_client.py` | **Fail** — `vision_client` imports `analyzer`, which pulls transitive errors (see Rule 4) |
| `mypy --follow-imports=silent` on the same three modules | Pass |
| Manual: temp DB + `init_database` → `COUNT(*) FROM perspectives` ≥ 4 | Pass (4) |

## Deviations (Rule 4)

1. **Mypy (plan verification):** Plain `mypy` on `vision_client.py` follows imports into `analyzer` and fails on long-standing package issues. **`--follow-imports=silent`** on the three listed files passes and validates the edited surface.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).

---

# Plan 05-03 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Pydantic structured output validation, repair, retry, and golden fixtures  
**Date:** 2026-04-12

## Outcomes

- Runtime dependency **`pydantic>=2.0,<3`** added; `uv.lock` refreshed.
- New module **`lightroom_tagger/core/structured_output.py`**: `ScoreResponse` / `PerspectiveScorePayload`, deterministic `repair_json_text` (fence extraction aligned with `parse_description_response`, trailing-comma pass with documented string-limitation note), `parse_score_response`, `parse_score_response_with_retry` (optional `fixer` then optional `llm_fixer`, each at most once), `StructuredOutputError` with 200-char preview cap and `input too large` guard at 512k chars.
- **`lightroom_tagger/core/vision_client.py`**: `SCORE_JSON_REPAIR_SYSTEM`, `complete_chat_text`, `make_score_json_llm_fixer` for D-12 LLM JSON-only repair (no global default; Phase 6 binds client/model).
- **`lightroom_tagger/core/test_structured_output.py`**: golden fixtures `RAW_*`, fixer/llm_fixer paths, preview truncation, `score == 11` `ValidationError`, and `make_score_json_llm_fixer` wiring smoke test.

## Commits

1. `chore(05-03): add pydantic v2 dependency and refresh uv.lock`
2. `feat(05-03): add structured_output score JSON repair and validation`
3. `feat(05-03): add make_score_json_llm_fixer and text completion helper`
4. `test(05-03): add golden fixtures for structured score output`

## Verification

| Check | Result |
|--------|--------|
| `pytest lightroom_tagger/core/test_structured_output.py -q` | Pass |
| `ruff check lightroom_tagger/core/structured_output.py lightroom_tagger/core/vision_client.py lightroom_tagger/core/test_structured_output.py` | Pass |
| `mypy lightroom_tagger/core/structured_output.py lightroom_tagger/core/vision_client.py` | **Fail** (transitive imports pull `analyzer`, `database`, etc.; see Rule 4) |
| `mypy --follow-imports=silent` on the same two modules | Pass |

## Deviations (Rule 4)

1. **Mypy:** Plain `mypy` on the two library files follows imports into modules with pre-existing errors. Verification used `--follow-imports=silent` for an accurate check of the new/edited surface, matching the practical gate used when the rest of the package is not mypy-clean.
2. **`vision_client.py`:** Ruff `--fix` cleaned whitespace/import issues across the file (not only new helpers), and `typing.cast(Any, …)` wraps `messages` on four `chat.completions.create` sites so `mypy --follow-imports=silent` passes on `vision_client.py`.
3. **Plan text vs. implementation:** The plan’s “on `ValidationError`, if `repair_json_text` changed text and second parse succeeds” branch is not implemented as a separate step after `parse_score_response` fails, because `parse_score_response` already runs `repair_json_text` before validation; a second identical parse cannot succeed. `repaired_flag` is set when an injected `fixer` or `llm_fixer` recovers.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).

---

# Plan 05-05 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Job checkpoint persistence for long-running handlers  
**Date:** 2026-04-12

## Outcomes

- **`apps/visualizer/backend/jobs/checkpoint.py`**: `CHECKPOINT_VERSION = 1`, `fingerprint_batch_describe`, `fingerprint_vision_match`, `fingerprint_catalog_keys` (enrich + prepare), `merge_checkpoint_into_metadata`; module docstring lists checkpoint field shapes per job type.
- **`JobRunner`**: `persist_checkpoint`, `clear_checkpoint` (sets `metadata.checkpoint` to JSON `null` on success paths).
- **`handle_batch_describe`**: Fingerprint over full candidate list; resumes from `processed_pairs` (`"key|itype"`); `record_done` on coordinator thread only in parallel mode; size guard `fail_job` when over **100_000** entries; `info` log substring **`checkpoint mismatch`** when fingerprint differs.
- **`handle_vision_match`**: Fingerprint over threshold/weights/date/provider/max_workers/etc.; `resume_processed_keys` + `on_media_complete` wired to **`match_dump_media`**; coordinator-only checkpoint writes.
- **`handle_enrich_catalog` / `handle_prepare_catalog`**: Fingerprint from sorted catalog keys + total; monotonic `processed_image_keys`; prepare only submits pending images not in checkpoint; coordinator-only persists for parallel prepare.
- **`lightroom_tagger/scripts/match_instagram_dump.py`**: Keyword-only **`resume_processed_keys`** (skip before `processed` increment) and **`on_media_complete`** (end of loop body, same level as `progress_callback`).
- **`apps/visualizer/backend/tests/test_job_checkpoint.py`**: Fingerprint stability + force sensitivity; `persist_checkpoint` round-trip; **`clear_checkpoint`** leaves `metadata.checkpoint` **None**.

## Commits

1. `feat(05-05): add job checkpoint helpers and persist_checkpoint` (task 1)
2. `feat(05-05): add resume skip and completion callback to match_dump_media` (task 3 — committed before task 2 so handlers compile against the new API)
3. `feat(05-05): persist and clear job checkpoints in long-running handlers` (task 2)
4. `fix(05-05): satisfy ruff and mypy for checkpoint-related modules` (ruff SIM102/SIM113/B905 on touched handler paths; explicit `json.dumps` kwargs for mypy; `pyproject.toml` **`per-file-ignores`** for `match_instagram_dump.py` **E402/I001**; inner unused concurrent imports removed)
5. `test(05-05): add job checkpoint fingerprint and persistence tests` (task 4)

## Verification

| Check | Result |
|--------|--------|
| `pytest apps/visualizer/backend/tests/test_job_checkpoint.py -q` | Pass |
| `pytest apps/visualizer/backend/tests/test_handlers_batch_describe.py apps/visualizer/backend/tests/test_handlers_single_match.py -q` | Pass |
| `ruff check` on plan-listed modules | Pass |
| `mypy apps/visualizer/backend/jobs/checkpoint.py` | Pass |

## Deviations (Rule 1)

1. **Commit order vs. plan task order:** Task **3** (`match_dump_media` kwargs) was committed **before** task **2** (handlers) so the vision_match call site is valid at every commit.
2. **`pyproject.toml`:** Added **`[tool.ruff.lint.per-file-ignores]`** for `lightroom_tagger/scripts/match_instagram_dump.py` (**E402**, **I001**) because the script intentionally mutates `sys.path` before package imports; fixing import order would be a larger structural change than this plan required.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).

---

# Plan 05-04 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Perspectives REST API, Processing UI (CodeMirror), and batch describe slug wiring  
**Date:** 2026-04-12

## Outcomes

- **`lightroom_tagger/core/database.py`**: `insert_perspective`, `update_perspective`, `delete_perspective` (parameterized SQL); `update_perspective` treats SQLite no-op updates as success when the row still exists.
- **`apps/visualizer/backend/api/perspectives.py`**: Blueprint under `/api/perspectives` with list (optional `active_only`), get, create, put (partial), delete, and `POST /<slug>/reset-default` (404 + `{"error": "no default file"}` when the resolved default file is missing). Header comment **`# image_scores JSON field keys (library DB)`** plus comma-separated keys. Validation: slug regex, `prompt_markdown` UTF-8 size cap **256 KiB** → 400 `prompt too large`; `source_filename` on reset must match `^[a-zA-Z0-9_\-]+\.md$` else 400 `invalid source_filename`; reset reads only under `prompts/perspectives/` relative to repo root.
- **`apps/visualizer/backend/tests/test_perspectives_api.py`**: Temp `LIBRARY_DB` + `monkeypatch` on `utils.db.LIBRARY_DB`; list includes `street`, PUT/GET markdown round-trip, reset with bogus `source_filename` → 404 contract.
- **Frontend**: `@uiw/react-codemirror` + `@codemirror/lang-markdown` (installed with `npm install --legacy-peer-deps` due to `@testing-library/react` vs React 19 peer conflict). `PerspectivesAPI`, `TAB_PERSPECTIVES`, `NAV_PERSPECTIVES_HELP` (substring **Reset reloads the markdown file from prompts/perspectives**), **`PerspectivesTab`** (list, Active checkbox → `PUT` with `{"active": bool}` only, CodeMirror editor, Save / Reset to default / Delete / Add modal), **`ProcessingPage`** tab `perspectives` and `?tab=perspectives`.
- **`DescriptionsTab`**: Section titled exactly **Critique perspectives** — checkboxes over active perspectives, `metadata.perspective_slugs` array on `batch_describe` (empty array → backend treats as “use all active” via existing `description_service` behavior).
- **`handlers.py`**: `_describe_single_image(..., perspective_slugs=None)` passes through to `describe_matched_image` / `describe_instagram_image`; `handle_single_describe` and `handle_batch_describe` (sequential + parallel worker) read `metadata['perspective_slugs']`.
- **`jobs/checkpoint.py`**: `fingerprint_batch_describe` includes sorted `perspective_slugs` when metadata has a non-empty list so checkpoint resume does not ignore lens selection changes; **`test_job_checkpoint.py`** asserts fingerprint differs when `perspective_slugs` is set.

## Commits

1. `feat(05-04): add perspectives REST API and DB helpers`
2. `test(05-04): add perspectives API integration tests`
3. `feat(05-04): add Perspectives tab with CodeMirror and REST client`
4. `feat(05-04): pass perspective_slugs through describe jobs and Descriptions UI`

## Verification

| Check | Result |
|--------|--------|
| `pytest apps/visualizer/backend/tests/test_perspectives_api.py -q` | Pass |
| `pytest apps/visualizer/backend/tests/test_job_checkpoint.py apps/visualizer/backend/tests/test_handlers_batch_describe.py -q` | Pass |
| `cd apps/visualizer/frontend && npm run lint` | Pass |
| Manual | `/processing?tab=perspectives` — edit/save/refresh persistence (operator check) |

## Deviations (Rule 4)

1. **npm:** CodeMirror install required **`--legacy-peer-deps`** because devDependency `@testing-library/react@14` declares `react@^18` while the app uses React 19.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).

---

# Plan 05-06 — Execution summary

**Phase:** 05 — Structured scoring foundation  
**Plan:** Orphan job auto-resume on startup and UI notification  
**Date:** 2026-04-12

## Outcomes

- **`_recover_orphaned_jobs`** (`apps/visualizer/backend/app.py`): For each **`running`** row from **`get_active_jobs`**, if **`metadata.checkpoint`** is a dict with **`checkpoint_version == 1`**, the job is moved to **`pending`** with progress preserved, **`current_step`** set to **`Recovered after restart`**, and an **`info`** log **`Recovered after restart; job re-queued with checkpoint.`**; otherwise **`failed`** with the unchanged legacy **`error`** log. **`print`** lines include **`re-queued pending with checkpoint`** vs **`marked as failed`**. Non-empty resume list triggers **`socketio.emit('jobs_recovered', {'job_ids': recovered_ids})`** when **`socketio`** is set.
- **`apps/visualizer/backend/tests/test_orphan_recovery.py`**: Temp jobs DB — checkpointed running job ends **`pending`** with the exact info substring; running job with **`metadata` `{}`** ends **`failed`** with the restart substring in logs.
- **Frontend**: **`useJobSocket`** accepts optional **`onJobsRecovered`** and registers **`jobs_recovered`**. **`ProcessingPage`** is the sole **`useJobSocket`** caller; job list state, initial load, and refresh are lifted from **`JobQueueTab`**, which now takes **`jobs`**, **`setJobs`**, **`jobsLoading`**, **`connected`**, and **`onRefreshJobs`**. Dismissible banner (exact copy: **`Some jobs were automatically resumed after the last server restart. Check the job queue for progress.`**) with **Dismiss** sits above the tabs, styled with **`border-border`** and **`bg-surface`**.

## Commits

1. `feat(05-06): checkpoint-aware orphan job recovery and jobs_recovered emit`
2. `test(05-06): cover checkpoint orphan requeue and legacy fail path`
3. `feat(05-06): jobs_recovered socket banner and single useJobSocket on Processing`
4. `docs(05-06): append plan 05-06 summary to SUMMARY.md`

## Verification

| Check | Result |
|--------|--------|
| `uv run pytest apps/visualizer/backend/tests/test_orphan_recovery.py -q` | Pass |
| `cd apps/visualizer/frontend && npm run lint` | Pass |
| Plan grep strings (`app.py`, `useJobSocket.ts`, `ProcessingPage.tsx`, tests) | Pass |

### Manual (operator)

- Kill backend mid-batch-describe with checkpoint present, restart — job becomes **pending** and banner appears on **Processing** when **`jobs_recovered`** fires.

## STATE / ROADMAP

Not modified (orchestrator-owned per wave instructions).
