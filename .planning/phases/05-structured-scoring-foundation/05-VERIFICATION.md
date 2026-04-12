---
status: passed
phase: "05-structured-scoring-foundation"
requirements_verified:
  - SCORE-02
  - SCORE-05
  - SCORE-06
  - SCORE-07
  - JOB-01
  - JOB-02
---

# Phase 05 verification — structured scoring foundation

Verification date: 2026-04-12. Evidence is from repository state at verification time (grep/read + automated commands below).

## Plan frontmatter → requirement coverage

| Plan   | Requirements in frontmatter | Accounted in REQUIREMENTS.md |
|--------|------------------------------|------------------------------|
| 05-01  | SCORE-02                     | SCORE-02 → Phase 5           |
| 05-02  | SCORE-05, SCORE-06           | SCORE-05, SCORE-06 → Phase 5 |
| 05-03  | SCORE-07                     | SCORE-07 → Phase 5           |
| 05-04  | SCORE-02, SCORE-06           | (same IDs)                   |
| 05-05  | JOB-01                       | JOB-01 → Phase 5             |
| 05-06  | JOB-02                       | JOB-02 → Phase 5             |

No requirement ID appears in phase plans without a matching row in `.planning/REQUIREMENTS.md` traceability. **Note:** The markdown checkboxes and the traceability table in `REQUIREMENTS.md` still show `[ ]` / `Pending` for these six IDs; updating those to reflect shipped foundation work is a documentation/process step, not a code gap.

## Requirement-by-requirement verification

| ID        | Requirement (summary) | Verified in codebase | Evidence |
|-----------|------------------------|----------------------|----------|
| **SCORE-02** | Queryable persisted scores (not only JSON) | Yes | `lightroom_tagger/core/database.py`: `CREATE TABLE IF NOT EXISTS image_scores` with real columns (`score`, `perspective_slug`, `prompt_version`, `is_current`, etc.), indexes, `uq_image_scores_versioned`; module appendix `# ## Queryable score fields (image_scores)` documents LEFT JOIN / missing row = not scored; `apps/visualizer/backend/api/perspectives.py` lines 1–2 document HTTP-oriented field keys for Phase 6 consumers. |
| **SCORE-05** | Critique prompts grounded in photography theory | Yes | `prompts/perspectives/*.md`: each file has `## Theory basis`; `street.md` cites **Michael Freeman** / *The Photographer's Eye*; `documentary.md` cites **John Berger** / *Understanding a Photograph*; `publisher.md` cites **Wilson Hicks** / *Words and Pictures*; `color_theory.md` cites **Albers** / **Itten** with **color harmony** / contrast language. |
| **SCORE-06** | New critique perspectives beyond original three | Yes | Fourth shipped rubric `prompts/perspectives/color_theory.md`; `seed_perspectives_from_prompts_dir` in `database.py`; REST CRUD + Processing **Perspectives** tab (`PerspectivesTab.tsx`, `ProcessingPage.tsx`); `DescriptionsTab.tsx` **Critique perspectives** + `metadata.perspective_slugs`; `handlers.py` passes `perspective_slugs` into `describe_*`. |
| **SCORE-07** | Validate / repair malformed structured LLM output before persist | Yes (library + tests; DB writes in Phase 6) | `lightroom_tagger/core/structured_output.py`: `ScoreResponse`, `repair_json_text`, `parse_score_response`, `parse_score_response_with_retry` (`fixer` + `llm_fixer`), `StructuredOutputError` with `input too large` and `Score response validation failed`; `vision_client.make_score_json_llm_fixer`; golden tests in `test_structured_output.py` including stubbed LLM fixer and `make_score_json_llm_fixer` smoke test. |
| **JOB-01** | Long-running jobs checkpoint progress | Yes | `apps/visualizer/backend/jobs/checkpoint.py` (`CHECKPOINT_VERSION`, fingerprints, `merge_checkpoint_into_metadata`); `runner.persist_checkpoint` / `clear_checkpoint`; `handlers.py` checkpoint bodies for `batch_describe`, `vision_match`, `enrich_catalog`, `prepare_catalog`; `match_instagram_dump.py` `resume_processed_keys` / `on_media_complete`; `test_job_checkpoint.py`. |
| **JOB-02** | Orphaned jobs recovered on startup | Yes | `app._recover_orphaned_jobs`: v1 checkpoint → `pending` + exact info log + print substring `re-queued pending with checkpoint`; else `failed` + legacy error string; `socketio.emit('jobs_recovered', …)`; `test_orphan_recovery.py`; frontend `useJobSocket` `jobs_recovered` + Processing banner (exact copy) + **Dismiss**. |

## Phase success criteria (cross-check)

| Criterion | Result |
|-----------|--------|
| 1. Migrations additive; `image_descriptions` intact | **Pass** — `CREATE TABLE IF NOT EXISTS image_descriptions` remains; `image_scores` / `perspectives` added separately. |
| 2. New perspective `color_theory` selectable | **Pass** — shipped rubric + UI/API + job metadata wiring. |
| 3. Critique prompts use theory framing | **Pass** — `## Theory basis` sections with named references (see SCORE-05). |
| 4. Malformed output: repair → LLM JSON repair → failure (D-12) | **Pass** — implemented in `structured_output.py` + `make_score_json_llm_fixer`; full describe blob remains legacy path per plan non-goal. |
| 5. Golden fixtures for validation/repair/llm_fixer | **Pass** — `RAW_*` fixtures and tests in `test_structured_output.py`. |
| 6. Restart mid-job resumes from checkpoint | **Pass** — checkpoint persistence + resume filtering in handlers; **human** full-stack kill test still valuable (below). |
| 7. Orphans detected; checkpointed → re-queue, else failed | **Pass** — `app.py` + tests. |

## Must-have verification by plan

### 05-01 — Library DB migration

| Must-have | Verified |
|-----------|----------|
| `image_scores` exposes queryable columns | Yes — DDL + indexes + helpers (`insert_image_score`, `get_current_scores_for_image`, `supersede_previous_current_scores`). |
| `perspectives` exists before API/seeding consumers | Yes — table in `init_database`; seed runs at end of init. |
| Docs for NULL / missing row | Yes — comment block at `database.py` ~1581–1596. |

### 05-02 — Rubrics, seeding, dynamic prompts

| Must-have | Verified |
|-----------|----------|
| SCORE-05: named theory under `## Theory basis` | Yes — all four `.md` files. |
| SCORE-06: fourth default `color_theory` after seed | Yes — file present; seed inserts all `prompts/perspectives/*.md` when table empty. |
| Dynamic JSON template uses selected slugs as keys | Yes — `prompt_builder.build_description_user_prompt` builds slug-keyed `perspectives` object. |

### 05-03 — Structured output (SCORE-07)

| Must-have | Verified |
|-----------|----------|
| Single module owns score JSON validation/repair | Yes — `structured_output.py` + `__all__`. |
| D-12: deterministic repair + one LLM repair hook + typed failure | Yes — `parse_score_response_with_retry` + `make_score_json_llm_fixer`; tests use callable stub for LLM leg. |
| Phase 6 must wire real `llm_fixer` on score persist | **Out of phase** — normative for Phase 6; not implemented in Phase 5 handlers (by design). |
| Tests prove repair, LLM hook, failures | Yes — `test_structured_output.py`. |

**Implementation note (from SUMMARY):** Plan text described setting `repaired_flag` when a second parse succeeds after `repair_json_text` changes text; because `parse_score_response` already applies `repair_json_text` before validation, that extra branch is redundant. Behavior still matches D-12 (fence/trailing-comma repair succeeds via `parse_score_response`; harder cases use `fixer` / `llm_fixer` / `StructuredOutputError`).

### 05-04 — API + UI + describe wiring

| Must-have | Verified |
|-----------|----------|
| SCORE-06 UI: list, editor, add, reset | Yes — `PerspectivesTab.tsx` (CodeMirror, Active toggle, etc.). |
| SCORE-02 field key list in API module | Yes — `perspectives.py` header comment lines 1–2. |
| `perspective_slugs` end-to-end for describe jobs | Yes — `DescriptionsTab.tsx` + `handlers.py` (multiple `perspective_slugs` references). |

### 05-05 — Job checkpoints

| Must-have | Verified |
|-----------|----------|
| `checkpoint_version: 1` for handler types | Yes — `CHECKPOINT_VERSION` + handler payloads documented in `checkpoint.py` docstring. |
| Fingerprint mismatch → ignore + log `checkpoint mismatch` | Yes — e.g. `handlers.py` logs containing `checkpoint mismatch`. |
| Completed jobs clear checkpoint | Yes — `runner.clear_checkpoint` call sites in `handlers.py` (5 handler success paths). |

### 05-06 — Orphan recovery

| Must-have | Verified |
|-----------|----------|
| JOB-02: checkpointed orphans → pending without manual Retry | Yes — `_recover_orphaned_jobs` + tests. |
| No checkpoint → failed + legacy guidance string | Yes — exact error string in `app.py` line 127. |
| User-visible notification | Yes — banner string + **Dismiss** on `ProcessingPage.tsx`. |

## Automated check results

| Command | Result |
|---------|--------|
| `uv run pytest lightroom_tagger/core/test_database_scores.py lightroom_tagger/core/test_prompt_builder.py lightroom_tagger/core/test_structured_output.py apps/visualizer/backend/tests/test_perspectives_api.py apps/visualizer/backend/tests/test_job_checkpoint.py apps/visualizer/backend/tests/test_orphan_recovery.py -q` | **18 passed** |
| `cd apps/visualizer/frontend && npm run lint` | **Exit 0** |
| `uv run python -c "import pydantic; assert pydantic.VERSION.startswith('2')"` | **OK** |

**Not re-run as full gates (see SUMMARY deviations):** `mypy` / `ruff` on entire `database.py` or transitive imports from `vision_client.py` — known pre-existing issues; Phase 5 touched files are covered by pytest + targeted lint where reported in `SUMMARY.md`.

## Human verification items

1. **End-to-end restart recovery:** Start a long `batch_describe`, kill the backend after at least one checkpoint write, restart — confirm job becomes **pending**, queue shows progress, and the Processing page banner appears once (socket `jobs_recovered`).
2. **Perspectives tab persistence:** Open `/processing?tab=perspectives`, edit markdown, **Save**, hard refresh — content matches saved row.
3. **Optional process hygiene:** Mark SCORE-02, SCORE-05, SCORE-06, SCORE-07, JOB-01, JOB-02 as complete in `.planning/REQUIREMENTS.md` when the team accepts Phase 5 as done (checkboxes + traceability `Status` column).

## Conclusion

Phase **05-structured-scoring-foundation** meets its stated goals and must-haves in code and automated tests. Remaining items are manual smoke tests and updating requirement checkboxes in `REQUIREMENTS.md` if desired for bookkeeping.
