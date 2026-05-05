# Phase 13 — Research: Handlers split (per-job-family)

**Date:** 2026-05-05  
**Goal:** Answer “What do I need to know to PLAN this phase well?” for **REFACTOR-01** / Phase 13.

Sources: `handlers.py` (full read + ripgrep), `13-CONTEXT.md`, `STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `app.py`, `jobs/__init__.py`, `checkpoint.py`, `runner.py`, all `jobs.handlers` imports under `apps/visualizer/backend/tests/`.

---

## Summary

To plan well you need:

1. **Exact physical line ranges** per family in the current monolith (below) — they match `13-CONTEXT.md` handler start lines; “end” is the line *before* the next top-level `def` / `class` or `JOB_HANDLERS`.
2. **Which symbols tests patch or import** — many patches target **`jobs.handlers.<name>`** because names were bound on the **single** module. After the split, **`unittest.mock.patch` targets must follow the submodule** where each name is imported (`jobs.handlers.analyze.add_job_log`, etc.), unless you standardize on patching **upstream** (`database.add_job_log`, `library_db.require_library_db`, …).
3. **Scaffold:** replace the **file** `jobs/handlers.py` with a **package** `jobs/handlers/` in one rename step; keep a shrinking **legacy module** (e.g. `_legacy.py`) inside the package until the last family is moved, so `from jobs.handlers import JOB_HANDLERS` stays valid throughout (`app.py` line 213).
4. **`common.py` vs family modules:** D-06 from CONTEXT is right for shared *selection/date/severity* helpers and `_CATALOG_NOT_VIDEO_SQL`; add **`_CHECKPOINT_MAX_ENTRIES`** and **`_INSTAGRAM_NOT_VIDEO_SQL` / `_LEGACY_DATE_FILTER_MONTHS`** to common — they are multi-consumer or exclusively support common helpers. **`_select_catalog_keys_missing_visual_tags`** is **analyze-only** (D-05) — not in D-06; place it in **`analyze.py`**.
5. **Composite job (`catalog_cache_build`):** lives in **`stacks.py`** per CONTEXT; it calls inners from embed + stacks. Unavoidable **internal imports** (`stacks` → `embed`) are **one-way** if `embed` never imports `stacks`.
6. **Package API:** **`__init__.py` exposes only `JOB_HANDLERS`** (D-02). No handler re-exports; **`__all__ = ("JOB_HANDLERS",)`** is optional documentation only. Tests import **handlers from submodules** (D-03).

---

## Handler Family Boundaries

Verified from `apps/visualizer/backend/jobs/handlers.py` (**3,849 lines**; `JOB_HANDLERS` dict **3833–3849**).

Start lines match `13-CONTEXT.md`. Ranges use inclusive start and end at the line before the next sibling top-level definition (or end of meaningful block).

| Family | File (CONTEXT) | Content (line range) | Notes |
|--------|------------------|------------------------|-------|
| **Bootstrap / composite-only (top of file)** | `stacks.py` (move here per D-01) | **79–133** `_catalog_cache_stage_mapped_progress`, class `_CatalogCacheStageRunner` | CONTEXT places class + mapper on stacks; used only by `handle_catalog_cache_build`. |
| **Shared constants + common helpers** | `common.py` | **63–76** module constants; **135–160** `_CATALOG_NOT_VIDEO_SQL`, `_INSTAGRAM_NOT_VIDEO_SQL`; **163–398** helpers through `_select_instagram_keys` | Constants **63–71** are mixed-frequency today; see “Constants” section — split by consumer when moving. |
| **Instagram** | `instagram.py` | **401–466** `handle_analyze_instagram`, `handle_instagram_import` | Stops before `_expand_matches_for_lightroom_writes`. |
| **Matching** | `matching.py` | **468–1126** `_expand_matches_for_lightroom_writes`, `handle_vision_match`, `handle_enrich_catalog`, `handle_prepare_catalog` | Ends before `_score_single_image` at 1127. |
| **Analyze** (describe / score / analyze) | `analyze.py` | **1127–2465** from `_score_single_image` through end of `_handle_batch_analyze_inner` (last code line **2465**; next handler **`handle_batch_text_embed`** at **2468**) | **1242** `handle_single_describe`, **1292** `handle_single_score`, **1751** `handle_batch_describe`, **2227** `handle_batch_score`, **2301** `handle_batch_analyze`. Per CONTEXT **does not** include **`batch_text_embed`** (that is **`embed.py`**). |
| **Embed** | `embed.py` | **2468–3159** `handle_batch_text_embed`, `_handle_batch_text_embed_inner`, `handle_batch_embed_image`, `_handle_batch_embed_image_inner` | **2468** / **2679** match CONTEXT. |
| **Stacks + similarity + cache build** | `stacks.py` | **3161–3831** `_normalize_stack_detect_force` through end of `_handle_catalog_cache_build_inner` | **3255** `handle_batch_catalog_similarity`, **3378** `handle_batch_stack_detect`, **3675** `catalog_cache_build`. Includes stack-only helpers (**3161–3253**) and catalog-cache orchestration. |
| **Registry** | `__init__.py` | **3833–3849** `JOB_HANDLERS` | Assembled from submodule callables only after split. |

**Verification vs CONTEXT:** Listed handler entry lines (401, 407, 483, 761, 906, 1242, 1292, 1751, 2227, 2301, 2468, 2679, 3255, 3378, 3675) match the file exactly.

---

## Cross-Family Helpers (for common.py)

### Confirmed in D-06 (move to `common.py`)

| Symbol | Lines | Callers / rationale |
|--------|-------|---------------------|
| `_resolve_library_db_or_fail` | 163–174 | Many handlers (grep: instagram, matching, analyze, embed, stacks). |
| `_failure_severity_from_exception` | 176–184 | Instagram, matching, analyze paths, embed, stacks. |
| `_select_catalog_keys` | 248–305 | Batch describe/score/analyze, text embed, batch embed (catalog list paths). |
| `_select_instagram_keys` | 346–398 | Batch describe/score/analyze, batch embed (`catalog_and_instagram`). |
| `_resolve_date_window` + `_LEGACY_DATE_FILTER_MONTHS` | 186–246 | Batch describe/score/analyze, embed, **and** `handle_catalog_cache_build` (line 3686). |
| `_CATALOG_NOT_VIDEO_SQL` | 137–148 | `_select_catalog_keys` and `_select_catalog_keys_missing_visual_tags`. |

**D-05 clarification (not D-06):** `_select_catalog_keys_missing_visual_tags` (308–344) is used **only** by the analyze/describe batch selection path — keep in **`analyze.py`**, not `common.py`.

### Add to common (shared constant; not in D-06 text but required by code)

| Symbol | Consumers |
|--------|-----------|
| `_CHECKPOINT_MAX_ENTRIES` (63) | `handle_vision_match`, `handle_enrich_catalog`, `handle_prepare_catalog`, `_run_describe_pass`, `_run_score_pass`, `handle_batch_text_embed`, `handle_batch_stack_detect` (and related). **True cross-family.** |

### Add to common with `_select_instagram_keys`

| Symbol | Rationale |
|--------|------------|
| `_INSTAGRAM_NOT_VIDEO_SQL` (149–160) | Only referenced inside `_select_instagram_keys`. Keeps SQL next to helper. |

### D-05 — Single-consumer / family-local (NOT `common.py`)

| Symbol | Lines | Primary module |
|--------|-------|----------------|
| `_expand_matches_for_lightroom_writes` | 468–481 | `matching.py` |
| `_score_single_image`, `_diagnose_describe_skip`, `_describe_single_image` | 1127+ | `analyze.py` |
| `_map_job_progress`, `_analyze_load_checkpoint`, `_analyze_merge_persist`, `_run_describe_pass`, `_handle_batch_describe_inner`, `_run_score_pass`, `_handle_batch_score_inner`, `_handle_batch_analyze_inner` | 1370–2466 | `analyze.py` |
| `_CatalogCacheStageRunner`, `_catalog_cache_stage_mapped_progress` | 79–133 | `stacks.py` (per CONTEXT) |
| `_normalize_stack_detect_force`, `_parse_date_taken_utc`, `_build_burst_segments`, `_select_stack_representative_key`, `_catalog_similarity_why_matched_line` | 3161–3253 | `stacks.py` |
| `_handle_catalog_similarity_inner`, `_handle_batch_stack_detect_inner`, `_handle_catalog_cache_build_inner` | — | `stacks.py` |

**Imports:** `_failure_severity_from_exception` needs `AuthenticationError`, `InvalidRequestError` from `lightroom_tagger.core.provider_errors` — **`common.py` imports those**; family modules import from `common`.

---

## Test Import Analysis

### Files touching `jobs.handlers` (grep over repo)

| File | Role |
|------|------|
| `app.py` | `from jobs.handlers import JOB_HANDLERS` — **unchanged** if package `__init__.py` exports it (D-04). |
| `tests/test_handlers_batch_analyze.py` | `from jobs.handlers import handle_batch_analyze`; many `@patch('jobs.handlers.*')` including **`fingerprint_batch_describe`** on **handlers** (import re-exports from `checkpoint`). |
| `tests/test_handlers_batch_describe.py` | `handle_batch_describe` + patches on `jobs.handlers.{add_job_log,init_database,...}` |
| `tests/test_handlers_batch_score.py` | Same pattern + `jobs.handlers._score_single_image` |
| `tests/test_handlers_batch_embed_image.py` | **`import jobs.handlers as job_handlers`** — monkeypatches **`job_handlers.encode_images`**, **`resolve_filepath`**, **`_EMBED_PREFLIGHT_*`**, **`_EMBED_SKIP_DETAIL_LOG_LIMIT`** (expects these names **on the package module**). |
| `tests/test_handlers_batch_text_embed.py` | `handle_batch_text_embed` + patches |
| `tests/test_handlers_batch_stack_detect.py` | **`from jobs.handlers import _build_burst_segments`**, `handle_batch_stack_detect`, patches |
| `tests/test_handlers_batch_catalog_similarity.py` | `handle_batch_catalog_similarity` only |
| `tests/test_handlers_catalog_cache_build.py` | `JOB_HANDLERS`, `handle_catalog_cache_build`, patches on **`list_*_clip_embedding`**, **`_handle_*_inner`**, **`_catalog_cache_stage_mapped_progress`**; **`import jobs.handlers as job_handlers` is unused** (dead import). |
| `tests/test_handlers_single_match.py` | `handle_vision_match` + patches on `match_dump_media`, etc. |
| `tests/test_handlers_date_window.py` | **`from jobs.handlers import _resolve_date_window`**, `handle_batch_describe`, `handle_batch_score`, `_patched_handler_env` patches **`jobs.handlers.init_database`** |
| `tests/test_select_instagram_keys.py` | **`from jobs.handlers import _select_instagram_keys`** |
| `tests/test_stack_matching_integration.py` | `handle_vision_match` |
| `lightroom_tagger/scripts/test_import_instagram_dump.py` | Docstring only — **`apps.visualizer.backend.jobs.handlers._select_instagram_keys`** path in comment; update when module moves. |

**Patch / import migration rule:** After split, either:

- **Preferred (D-03):** `from jobs.handlers.analyze import handle_batch_describe` and **`@patch('jobs.handlers.analyze.add_job_log')`** (same for each submodule), **or**
- **Alternative:** patch **`database.add_job_log`**, **`lightroom_tagger.core.database.init_database`**, etc., to avoid churn when moving lines between files.

**Special case — `test_handlers_batch_embed_image`:** Today it patches **`jobs.handlers.encode_images`** — `encode_images` is imported from **`lightroom_tagger.core.clip_embedding_service`** into `handlers.py`. After embed split, patch **`jobs.handlers.embed.encode_images`** (or patch **`lightroom_tagger.core.clip_embedding_service.encode_images`** once).

**Special case — `test_handlers_batch_analyze`:** Patches **`jobs.handlers.fingerprint_batch_describe`** — after split, patch **`jobs.handlers.analyze.fingerprint_batch_describe`** if the submodule imports it, or **`jobs.checkpoint.fingerprint_batch_describe`** for stability.

**Count:** Raw `jobs.handlers` occurrences are **~313** across backend tests + `app.py` (not “~60 import lines” only — CONTEXT’s D-03 estimate is low; **patch strings dominate**).

---

## Module-Level Side Effects

| Item | Current location | Placement |
|------|------------------|-----------|
| `from . import path_setup as _path_setup  # noqa: F401` | Line 51 | **Exactly once** in **`handlers/__init__.py`** (per CONTEXT — not duplicated per submodule). |
| Imports | Lines 1–61 | Split across **family modules** + **`common.py`** — each submodule imports only what it uses (mirrors `checkpoint.py` pattern). |
| Fingerprint imports from `.checkpoint` | 52–60 | **Per handler family** that needs them (analyze, embed, matching, stacks). |
| Globally reused constants **63–76** | Top of file | Split by owner: embed tunables → `embed.py`; checkpoint cap → `common.py`; vision/sim/stack throttles → `matching.py` / `stacks.py`. |
| `_PREFLIGHT_RNG_SEED` (73–76) | Module | **`embed.py`** (with batch embed; tests may set via `jobs.handlers.embed._PREFLIGHT_RNG_SEED`). |
| `JOB_HANDLERS` | 3833–3849 | **`__init__.py` only**. |

**No** `atexit`, **no** thread starts, **no** logging config at import — only **path_setup** side effect.

---

## Scaffold Strategy

**Constraint:** Cannot coexist: **`jobs/handlers.py`** (module file) **and** **`jobs/handlers/`** (package). Python resolves the package if both exist — **do not leave both.**

**Recommended sequence (aligns with D-07–D-09):**

1. **Rename** `apps/visualizer/backend/jobs/handlers.py` → `apps/visualizer/backend/jobs/handlers/_legacy.py` (or `_flat.py`). Create `handlers/__init__.py` that:
   - runs **`path_setup`** import once;
   - **`from ._legacy import JOB_HANDLERS`** (or re-builds dict from submodule attrs once plumbing exists).
2. **First green commit:** Package exists; **`from jobs.handlers import JOB_HANDLERS`** still works; **no** behavior change. Run full pytest.
3. **Introduce empty** `common.py`, `instagram.py`, … as needed; **move one family** out of `_legacy.py` into `instagram.py`, update `_legacy` to stop defining those functions (or delete definitions and import from `instagram` inside `_legacy` temporarily — avoid duplication). Update **`__init__.py`** `JOB_HANDLERS` mapping to reference new module functions. **Update tests for that family’s patch paths** in the same commit.
4. Repeat per family; **`_legacy.py` shrinks** until deleted on the final commit.

**Alternative (less ideal):** Single commit that moves everything — violates “green after each commit.”

**`test_handlers_batch_embed_image`:** Plan either **re-export for tests** (violates D-02 spirit) **or** switch monkeypatch target to **`jobs.handlers.embed`** — plan should standardize on **`embed` submodule** for `_EMBED_*` and `encode_images`.

---

## Circular Import Risks

| Edge | Risk | Mitigation |
|------|------|------------|
| `common.py` | Must not import `analyze`, `matching`, … | **Only** stdlib + third-party + `database`/`library_db`/shared core as needed. |
| `stacks.handle_catalog_cache_build` | Needs `_handle_batch_embed_image_inner`, `_handle_batch_stack_detect_inner`, `_handle_catalog_similarity_inner` | **`from .embed import _handle_batch_embed_image_inner`** inside **`stacks.py`** (or **`catalog_cache_build.py`** if you split further — **out of scope**). **Do not** have `embed` import `stacks`. |
| `matching.py` | Large imports for vision/enrich/prepare | Should not need `embed` or `stacks`. |

**Risk level:** **Low** if **`embed` stays a leaf** (no imports from `stacks`/`matching`/`analyze` beyond `common`).

---

## Constants: `common.py` vs Family Modules

| Constant | Suggested home |
|----------|----------------|
| `_CHECKPOINT_MAX_ENTRIES` | `common.py` |
| `_CATALOG_NOT_VIDEO_SQL` | `common.py` (D-06) |
| `_INSTAGRAM_NOT_VIDEO_SQL` | `common.py` (paired with `_select_instagram_keys`) |
| `_LEGACY_DATE_FILTER_MONTHS` | `common.py` (only used by `_resolve_date_window`) |
| `_BATCH_EMBED_IMAGE_SIZE`, `_EMBED_PREFLIGHT_*`, `_EMBED_SKIP_DETAIL_LOG_LIMIT`, `_EMBED_SUMMARY_LOG_EVERY`, `_PREFLIGHT_RNG_SEED` | **`embed.py`** |
| `_CATALOG_SIMILARITY_SUMMARY_EVERY`, `_STACK_DETECT_SUMMARY_EVERY` | **`stacks.py`** |
| `_VISION_MATCH_PREFILTER_SUMMARY_EVERY` | **`matching.py`** |

---

## Python Package Considerations (`__init__.py`)

- **`__all__`:** Optional `("JOB_HANDLERS",)` — **no** handler symbols in `__all__` per D-02.
- **No re-exports** of handlers for production; tests use **explicit submodule imports** (D-03).
- **`importlib.reload`** / dynamic code: unlikely; if any, **reload package** after split.

---

## Validation Architecture

| Layer | Command / check |
|-------|-----------------|
| **Full backend suite** | From `apps/visualizer/backend`: `pytest` — **663** tests baseline per REQUIREMENTS. |
| **After each commit** | Same full suite (or at minimum `pytest apps/visualizer/backend/tests` if repo layout permits). |
| **Contracts** | No change to log field shapes (`.cursor/rules/job-log-contract.mdc`); **job-ui-contract** flags **`handlers.py` —** when file becomes package, confirm hooks/scripts still enforce intent (may reference path; update if needed). |
| **Smoke** | `from jobs.handlers import JOB_HANDLERS` in `app.py` import path unchanged. |

**Zero behavior change:** Same `JOB_HANDLERS` keys → same callables (by identity **not** required — same **behavior** required). Prefer **one commit per family** + full pytest **before** pushing next extraction.

---

## RESEARCH COMPLETE
