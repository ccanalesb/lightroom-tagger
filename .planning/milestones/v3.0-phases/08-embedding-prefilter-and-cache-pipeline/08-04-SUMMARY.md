---
phase: 08-embedding-prefilter-and-cache-pipeline
plan: "4"
subsystem: api
tags: [jobs, handlers, catalog, clip, embeddings, sqlite]

requires:
  - phase: 08-embedding-prefilter-and-cache-pipeline
    provides: Instagram-aware batch_embed_image scope + fingerprints (plan 08-03)
provides:
  - Composite job type catalog_cache_build chaining embed → stack_detect → catalog_similarity in-process with cancel propagation and D-08 stage banners
  - fingerprint_catalog_cache_build for composite metadata identity (no ordered key lists)
  - _catalog_cache_chain embed/stack checkpoint suppression when nested under composite job id
affects:
  - CatalogCacheTab UI trigger (plan 08-06)
  - MatchingTab cleanup (plan 08-05)

tech-stack:
  added: []
  patterns:
    - "_CatalogCacheStageRunner proxies runner with mapped progress (thirds) and captures complete_job/finalize_cancelled per stage"
    - "_catalog_cache_chain metadata skips standalone checkpoint blobs when stages run under composite catalog_cache_build"

key-files:
  created:
    - apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py
  modified:
    - apps/visualizer/backend/jobs/handlers.py
    - apps/visualizer/backend/jobs/checkpoint.py
    - apps/visualizer/backend/library_db.py

key-decisions:
  - "Warn-and-proceed after embed when catalog ∪ Instagram backlog count > 0 (deduped overlap), without aborting stack/similarity."
  - "Composite job does not persist per-stage checkpoints on the composite job row; fingerprint_catalog_cache_build remains metadata-only identity."
  - "Standalone batch_* handlers unchanged at entrypoints; inner stages honor _catalog_cache_chain for quieter logs (embed preamble, similarity preamble/completion)."

patterns-established:
  - "Composite catalog-cache stages invoked via inner functions + stage runner capture instead of enqueueing dependent jobs."

requirements-completed:
  - CACHE-01

duration: 35min
completed: "2026-04-27"
---

# Phase 8 Plan 4: catalog_cache_build composite job Summary

**Adds `catalog_cache_build` job type so operators run catalog+Instagram CLIP embedding, burst stack detection, and catalog similarity grouping in one cancel scope, with `[catalog-cache-build]` stage banners and backlog warnings instead of aborting downstream stages.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-27 (executor session)
- **Completed:** 2026-04-27
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Registered `catalog_cache_build` in `JOB_HANDLERS` and `JOB_TYPES_REQUIRING_CATALOG`, plus `fingerprint_catalog_cache_build` (CLIP model/dim, force_* flags, date filters, fixed embed scope `catalog_and_instagram`).
- Implemented `_handle_catalog_cache_build_inner`: preamble → embed (`image_type` union + `force_embed`) → optional incomplete-embedding warning → stack (`force_stack`) → similarity, with `runner.is_cancelled` guards between stages and `_CatalogCacheStageRunner` mapping each stage’s 5–100% progress onto ~thirds of the composite bar.
- Extended `_handle_batch_embed_image_inner` / `_handle_batch_stack_detect_inner` with `_catalog_cache_chain` to skip standalone checkpoint load/persist/clear when nested under the composite job id; extracted `_handle_catalog_similarity_inner` for reuse.

## Task Commits

1. **Task 1–2: Register + composite handler implementation** — `3674220` (feat)
2. **Tests: ordering, cancel-between-stages, stage=log substring** — `34090a1` (test)
3. **Docs: SUMMARY + STATE + ROADMAP** — committed as `docs(08-04): complete catalog_cache_build plan summary`

## Files Created/Modified

- `apps/visualizer/backend/jobs/handlers.py` — `_CatalogCacheStageRunner`, `_catalog_cache_stage_mapped_progress`, `handle_catalog_cache_build`, chain orchestration; `_catalog_cache_chain` branches; `_handle_catalog_similarity_inner`.
- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_catalog_cache_build`.
- `apps/visualizer/backend/library_db.py` — `catalog_cache_build` in `JOB_TYPES_REQUIRING_CATALOG`.
- `apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py` — registration, stage order, cancel propagation, banner substring, progress helper sanity check.

## Decisions Made

- Followed 08-RESEARCH **warn + proceed** for leftover embedding backlog after the embed stage (deduped catalog vs Instagram keys).
- Kept similarity semantics unchanged (`clear_catalog_similarity_results` always); `force_similarity` is carried in fingerprint only for future/UI alignment.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — pytest gates (`test_handlers_catalog_cache_build.py`, `test_handlers_batch_embed_image.py`, `test_handlers_single_match.py`) passed locally after implementation.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Backend CACHE-01 composite pipeline is ready for **08-05 / 08-06** UI wiring (`JobsAPI.create('catalog_cache_build', …)`).

---

*Phase: 08-embedding-prefilter-and-cache-pipeline*

## Self-Check: PASSED

- Key files exist on disk.
- `git log --oneline --grep=08-04` lists feat + test commits.
- Verification commands from PLAN.md `<verification>` re-run clean:
  - `uv run python -m pytest apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py apps/visualizer/backend/tests/test_handlers_batch_embed_image.py -q --tb=short` → pass.
  - `uv run python -m pytest apps/visualizer/backend/tests/test_handlers_single_match.py -q --tb=short` → pass.
