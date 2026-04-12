# Phase 5: Structured Scoring Foundation — Research

**Date:** 2026-04-12  
**Purpose:** Answer “What do I need to know to PLAN this phase well?” — current codebase state, gaps, approaches, and risks aligned with SCORE-02, SCORE-05, SCORE-06, SCORE-07, JOB-01, JOB-02 and `05-CONTEXT.md` decisions.

---

## 1. Score storage schema (`lightroom_tagger/core/database.py`)

### Current state

- **`image_descriptions`** is created in `init_database` with `CREATE TABLE IF NOT EXISTS` and includes: `image_key` (PK), `image_type`, `summary`, `composition`, `perspectives`, `technical`, `subjects` (JSON/text columns), `best_perspective`, `model_used`, `described_at`. Index `idx_desc_image_type` exists.
- **Migrations** after the big `executescript`: `_migrate_add_column` for selective columns on other tables; `_migrate_images_schema` loops expected `images` columns; `_migrate_unified_image_keys` uses `PRAGMA user_version` for a one-time key migration.
- **`_serialize_json` / JSON columns**: `store_image_description` passes `composition`, `perspectives`, `technical`, `subjects` through `_serialize_json` on insert/update. `get_image_description` explicitly `json.loads` those four columns (not `_deserialize_row`).
- **`_deserialize_row`**: Used for generic image/dump rows; deserializes `keywords`, `exif`, `exif_data`, `logs`, `metadata`, `result` — **not** the description-specific JSON fields (those use dedicated logic in `get_image_description`).
- **`store_image_description`**: `INSERT ... ON CONFLICT(image_key) DO UPDATE` — idempotent upsert by `image_key`.

### What needs to change

- Add **`image_scores`** (and likely **`perspectives`**) via the same pattern: `CREATE TABLE IF NOT EXISTS` in `init_database` plus any `_migrate_add_column` / index creation needed for existing DBs.
- Per **D-01** (`05-CONTEXT`): normalized rows (image × perspective × version) with queryable `score`, `rationale`, `model_used`, `prompt_version`, `scored_at`; **do not alter** `image_descriptions` shape for legacy compatibility.
- Document **nullable / legacy semantics** in plan (and operator-facing notes): existing catalogs have no score rows; joins should be `LEFT JOIN` from `images` or descriptions as appropriate.

### Risks / gotchas

- **Primary key design**: composite `(image_key, perspective, prompt_version)` vs surrogate `id` + unique constraint — affects upsert SQL and “current vs historical” (D-03). Planner must pick one and mirror it in API/query helpers.
- **Integration tests** that use minimal schemas (see STATE.md D-04-01): tests may need empty `image_scores` / `perspectives` tables if new code assumes they exist in raw SQL.

### Recommendations

- Follow **`store_image_description`** upsert style for score inserts; add focused getters (`list_scores_for_image`, `latest_scores_by_perspective`, etc.) in `database.py` rather than scattering SQL in handlers.
- Add indexes matching filter/sort stories for Phase 6, e.g. `(perspective, score)`, `(image_key)`.

---

## 2. Perspective registry & rubrics (`analyzer.py`, frontend)

### Current state

- **`DESCRIPTION_PROMPT`** in `lightroom_tagger/core/analyzer.py` (lines ~40–107) embeds three fixed perspectives (street, documentary, publisher), a shared **1–10 rubric**, composition/technical blocks, and a **required JSON schema** with literal keys `street` / `documentary` / `publisher`.
- **`build_description_prompt()`** returns that string unchanged.
- **`vision_client.generate_description`** calls `build_description_prompt()` with the image — single monolithic prompt path for all describes.
- **`parse_description_response`**: regex strip markdown fences, then `json.loads`; fallback greedy `\{.*\}`; on failure returns **`_DESCRIPTION_FALLBACK`** (empty strings / empty dicts) — not an exception.
- **Frontend**: no **CodeMirror** or **Monaco** dependencies found under `apps/visualizer/frontend` (grep clean). Perspective editor is **greenfield**.

### What needs to change

- **D-05–D-10**: Ship `prompts/perspectives/*.md` as factory defaults; seed **`perspectives` SQLite table** when empty; runtime reads from DB; disk only on seed / “reset to default”; editor = code editor (CodeMirror vs Monaco TBD).
- **SCORE-06 / success criterion 2**: At least **one additional perspective** (e.g. color theory, emotional impact, series coherence) in defaults + UI where perspectives are chosen for analysis (exact surface may straddle Phase 5 vs 6 — Phase 5 should still expose registry + selection plumbing if critique prompts are chosen here).
- **Dynamic describe/score prompts**: Building the user message will need **composition** from base template + N active perspectives (slugs + markdown bodies), and a JSON schema that lists **dynamic keys** or a **stable array shape** — the current fixed three-key `perspectives` object will not scale without a schema change for new describe flows (planner: backward compatibility for existing stored `image_descriptions.perspectives` JSON).

### Risks / gotchas

- **Slug stability**: `street` / `documentary` / `publisher` are baked into prompts and stored JSON; new perspectives need stable IDs and migration story if renaming.
- **“DB wins” (D-07)**: shipped `.md` updates never overwrite DB rows — document upgrade path for operators (export/import or reset).

### Recommendations

- Extract shared **rubric paragraph** (1–10 scale) into a reusable fragment referenced by each perspective `.md` or a shared `prompts/rubric.md` included by convention — reduces drift.
- **CodeMirror vs Monaco**: CodeMirror 6 is lighter and common with Tailwind/Vite; Monaco is heavier but familiar. Either is fine; match bundle size and theming to existing SPA (Tailwind, dark/light if any).

---

## 3. Structured output validation & repair (SCORE-07)

### Current state

- **Parsing only**: `parse_description_response` — best-effort extraction, **silent fallback** to empty structure.
- **Persistence gate**: `description_service._description_structured_is_valid` only checks **non-empty `summary` string**. Invalid JSON that yields empty summary → **no DB write**; valid JSON with empty summary → same. There is **no** structured validation of scores, perspective keys, or numeric ranges before storing partial blobs in `image_descriptions`.
- **No Pydantic** in root `pyproject.toml` dependencies today — **D-11** requires adding it.
- **`vision_client`**: `compare_images` uses `parse_vision_response` (separate path from descriptions); batch compare uses strict JSON instructions — still string parsing downstream.

### What needs to change

- **D-11–D-13**: Pydantic models for **score responses** (and possibly full describe responses if unified); validate **before** any write to `image_scores` (Phase 6 execution) and, per phase intent, ensure Phase 6 never commits unvalidated payloads.
- **D-12 pipeline**: (1) deterministic repair (strip fences, trailing commas, common fixes), (2) Pydantic parse, (3) on failure → **second LLM call** with minimal JSON-only repair prompt, (4) on failure → **fail job / image** with explicit error — **no silent empty rows**.
- **Golden fixtures**: pytest cases with representative malformed JSON (truncated, trailing comma, prose wrapper, wrong types) expecting repair vs hard-fail paths.

**Phase 5 handoff:** Plan **05-03** owns Pydantic + D-12 for **single-perspective score JSON** only. Retrofitting strict validation onto the full multi-perspective `parse_description_response` / describe persistence path is **explicitly out of scope for Phase 5** (tracked with Phase 6+ catalog/scoring work unless a future phase adds a dedicated describe-hardening plan).

### Risks / gotchas

- **Repair + log note (D-12)**: define where “repaired” is recorded (job log, optional column on score row, structured log field) so operators can audit quality.
- **Mypy**: new modules should satisfy `disallow_untyped_defs` per CONVENTIONS.md.

### Recommendations

- Centralize **`parse_and_validate_score_response(raw: str) -> Result`** in a small module (e.g. `lightroom_tagger/core/structured_output.py`) used by future scoring and optionally retrofitted to describe later.
- Consider **`model_validate_json`** (Pydantic v2) with `json.loads` + repair pre-step where needed.

### Validation architecture (summary)

```
LLM raw text
  → extract JSON substring (reuse ideas from parse_description_response)
  → repair pass (deterministic)
  → pydantic model_validate / model_validate_json
  → on ValidationError: optional LLM "fix to schema" retry with tiny prompt
  → success: return model; failure: raise typed error for job handler (no persist)
```

---

## 4. Job checkpointing & orphan recovery (JOB-01, JOB-02)

### Current state

- **Visualizer jobs DB** (`apps/visualizer/backend/database.py`): `jobs` table — `id`, `type`, `status`, `progress`, `current_step`, `logs`, `result`, `error`, `error_severity`, timestamps, **`metadata` JSON**.
- **`update_job_field`**: Whitelist `metadata`, `result`, `error`, `logs` only — checkpoint data should live in **`metadata`** (or extend whitelist if a dedicated column is added).
- **`JobRunner`**: `start_job`, `update_progress` (writes status + log each step), `complete_job`, `fail_job`, cooperative cancel via `threading.Event` + DB `cancelled`.
- **`_job_processor`**: Picks `pending` jobs, `start_job`, runs handler.
- **`_recover_orphaned_jobs`** in `app.py` (lines ~95–106): For every job with `status == 'running'`, sets **`failed`** and logs a restart message — **no resume**, **no checkpoint read**.
- **`handle_batch_describe`**: Builds full `images_to_describe` list up front; sequential or `ThreadPoolExecutor`; updates progress from **completed count** only — **no persisted cursor** of remaining work. Successful describes are already in **library DB** (`image_descriptions`); on restart, **without checkpoint**, a non-`force` run skips already-described images via `get_undescribed_*`, but **job row is failed** so user must retry manually — progress **is** in the library DB but **job UX** is wrong per JOB-02.
- **`handle_vision_match`**: Delegates to **`match_dump_media`** with callbacks; single job span — checkpointing likely requires **metadata checkpoint** and/or **core matcher** resume hooks (high complexity).

### What needs to change

- **D-14–D-17**: Persist **checkpoint state** in `job.metadata` (or new column) at chosen granularity (D-15): e.g. list of completed keys, queue offset, last `media_key`, etc.
- On startup: for orphaned **`running`** jobs — if checkpoint present → set **`pending`** (or dedicated `resumed` → pending), clear/advance `running` stale state, **append log**, optionally **`socketio.emit`** so UI shows recovery (D-16). If **no** checkpoint → keep current **failed** behavior (D-17).
- **Handlers** must **skip** work already recorded in checkpoint and **merge** results into final `complete_job` payload.
- **Parallel `batch_describe`**: Checkpoint updates should run from the **coordinator** thread (after each `future.result()`) to avoid concurrent `update_job_field` races from workers.

### Risks / gotchas

- **Idempotency**: `force=True` batches may re-describe — checkpoint must record what **this job instance** completed, not only “what exists in DB”.
- **`vision_match`**: May need incremental checkpoint inside `lightroom_tagger/scripts/match_instagram_dump.py` / `match_dump_media` — largest engineering risk; planner may sequence JOB-01 for `batch_describe` first and stub vision_match checkpoint as “metadata only + re-entry flags” if core changes are too large for one phase.
- **05-CONTEXT D-14** says “ALL long-running job types” but examples name **scoring**, **`handle_batch_describe`**, **`handle_vision_match`** — clarify whether **`handle_enrich_catalog`**, **`handle_prepare_catalog`** are in scope for the same release (both loop over many images).

### Recommendations

- Define a small **`JobCheckpoint`** TypedDict or Pydantic model versioned with `checkpoint_version` in metadata.
- For **batch_describe**, minimal viable checkpoint: `processed_keys: string[]` or `completed_count` + ordered job input hash to detect metadata mismatch.

---

## 5. Provider stack (`provider_registry.py`, `fallback.py`, `provider_errors.py`)

### Current state

- **`ProviderRegistry`**: Loads `providers.json`, `get_client`, `list_models`, `get_retry_config`, `fallback_order`, `defaults` (includes description defaults per ARCHITECTURE).
- **`FallbackDispatcher.call_with_fallback`**: `operation` is a **log label** (`"compare"` / `"describe"`); `fn_factory(client, model)` returns zero-arg callable; **`retry_with_backoff`** then provider cascade on `RETRYABLE_ERRORS` and `NOT_RETRYABLE_ERRORS`.
- **`describe_image` → `_describe_image_via_provider`**: Uses dispatcher + `vision_client.generate_description` — scoring can mirror this with **`generate_description`**-style call but **different prompt builder** (from perspective registry), same client/fallback.

### What needs to change

- Scoring jobs (Phase 6 execution; Phase 5 foundation may add **stub handler** or shared **“vision completion with custom prompt”** helper) should use the **same registry + fallback** as describe.
- Optionally extend **`defaults`** in `providers.json` for a **`scoring`** default provider/model — or reuse **`defaults.description`** until product decides otherwise.

### Risks / gotchas

- **`generate_description`** hardcodes `build_description_prompt()` — scoring needs either a parameter **`prompt: str`** or a sibling function **`generate_scoring_response(client, model, image_path, prompt, ...)`** to avoid duplicating HTTP logic.

### Recommendations

- Refactor `vision_client.generate_description` to accept **`system/user prompt`** or **`messages` builder** while keeping **`_map_openai_error`** centralized.

---

## 6. Architecture & conventions (cross-cutting)

- **Layers**: Library owns library SQLite + domain; visualizer owns jobs SQLite + Flask/Socket.IO — new **`image_scores` / `perspectives`** tables belong to **library DB**; job checkpoint state belongs to **visualizer jobs DB** `metadata`.
- **APIs**: New REST routes under `apps/visualizer/backend/api/` using existing response helpers (`utils/responses.py`).
- **Realtime**: Recovery toast/event should use existing **`job_updated`** / Socket.IO patterns (`JobRunner.emit_progress` already emits full job row).
- **Quality gates**: Black, Ruff, mypy per CONVENTIONS.md; add tests under `lightroom_tagger/core/` or `apps/visualizer/backend/tests/` consistent with existing layout.

---

## 7. Photography theory grounding (SCORE-05)

### Intent

Critique prompts should cite **real critique / composition theory**, not generic “be a harsh critic” instructions — aligns with **SCORE-05** and `05-CONTEXT` specifics.

### Reference frameworks (for rubric authors)

- **Michael Freeman — *The Photographer’s Eye***: systematic composition — frame dynamics, graphic elements (points, lines, rhythm), light/color, **intent** (documentary vs expressive, clear vs ambiguous), and process (anticipation, juxtaposition). Useful for **composition / design** perspectives and for a **“visual design / intent”** style rubric.
- **John Berger — *Understanding a Photograph***: photographs as **documents of meaning**, context, and social/historical reading — strong anchor for **documentary / editorial** lenses (complements but is more interpretive than Freeman’s formalism).
- **Classic critique dimensions** (usable as perspective seeds): **color theory** (Itten / Albers traditions — harmony, contrast, temperature); **emotional impact** (affect, mood, viewer empathy); **series coherence** (sequence, variation, repetition — Sander / sequence editors’ language).

### Recommendations for planning

- Each `prompts/perspectives/*.md` should include a short **“Theory basis”** bullet list (book/framework + 1–2 sentences) so SCORE-05 is auditable in-repo.
- Keep **operational rubric** (1–10 anchors) adjacent to theory so models can map abstract ideas to numeric scores consistently.

---

## 8. Requirement traceability (this phase)

| ID | Research takeaway |
|----|-------------------|
| **SCORE-02** | New normalized `image_scores` + SQL-friendly columns; indexes for filter/sort. |
| **SCORE-05** | Theory-named sections in perspective markdown + documented sources. |
| **SCORE-06** | `perspectives` table + UI list/edit + ≥1 new default perspective; dynamic prompt/schema strategy. |
| **SCORE-07** | Pydantic + repair/retry + tests; no silent bad persists. |
| **JOB-01** | Checkpoint in `job.metadata` + handler resume logic for long jobs. |
| **JOB-02** | Replace fail-only `_recover_orphaned_jobs` with checkpoint-aware **pending re-queue** + user-visible notification. |

---

## 9. Open questions for PLAN.md

1. **Composite PK vs surrogate** for `image_scores` and definition of “current” row (D-03).
2. **Whether `handle_enrich_catalog` / `handle_prepare_catalog`** get checkpoints in Phase 5 or a follow-up (D-14 wording vs time budget).
3. **Depth of `vision_match` checkpoint** — full resume inside `match_dump_media` vs job-level “restart from scratch with smarter skip flags”.
4. **Describe pipeline retrofit**: Should Phase 5 tighten validation for **existing** `describe_image` outputs, or only define validation for **new scoring** path (SCORE-07 scope vs regression risk).
5. **CodeMirror vs Monaco** — bundle size vs editing UX.

---

## RESEARCH COMPLETE

All scoped codebase areas were inspected at source level; photography theory direction is documented for rubric authors. No blocking unknowns — remaining items are product/engineering tradeoffs for PLAN.md.
