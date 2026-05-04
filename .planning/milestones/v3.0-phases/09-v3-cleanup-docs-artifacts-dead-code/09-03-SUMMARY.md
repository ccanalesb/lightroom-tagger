---
phase: 09-v3-cleanup-docs-artifacts-dead-code
plan: 3
subsystem: ui
tags: [frontend, dead-code, sim-02, api, strings, gap-closure]

requires:
  - phase: 06-similarity-stack-ui
    provides: CatalogVisualSimilaritySection + ImageDetailModal "More like this" UI (later removed by quick 260427-f75)
provides:
  - Frontend `ImagesAPI.getCatalogSimilar` removed
  - Frontend `CatalogSimilarResponse` response type removed
  - 14 orphan `CATALOG_SIMILAR_*` string constants removed
  - Backend `GET /api/images/catalog/<key>/similar` route untouched (D-03)
affects: [09-04, gsd-verifier, future contributors searching for "More like this"]

tech-stack:
  added: []
  patterns:
    - "Orphan API removal pattern: client method + response type + i18n string family deleted together; backend route preserved when other consumers might still call it (D-03)"

key-files:
  created: []
  modified:
    - apps/visualizer/frontend/src/services/api.ts
    - apps/visualizer/frontend/src/constants/strings.ts

key-decisions:
  - "D-01 / D-03 honored: only frontend exports removed; backend route + tests untouched"
  - "Section comment intentionally omits the literal `CATALOG_SIMILAR_*` token so the acceptance gate `rg \"CATALOG_SIMILAR_\" apps/visualizer/frontend/src` exits 1 — the plan example used `e.g.` so the wording is non-binding"
  - "CATALOG_STACK_SHOW / CATALOG_STACK_HIDE preserved per plan, even though they currently have no in-src consumers — out of scope for Phase 9 dead-code closure"

patterns-established:
  - "Walkthrough disposition for orphan-only deletes: see plan 09-04 SUMMARY § 'Walkthrough disposition' — the phase-exit-walkthrough hook reads VERIFICATION.md, not SUMMARY.md, so any walkthrough_exempt flag must live on the eventual 09-VERIFICATION.md"

requirements-completed:
  - SIM-02

duration: 4 min
completed: 2026-04-29
---

# Phase 09 Plan 03: Frontend dead-code deletion Summary

**Frontend orphan exports removed (`ImagesAPI.getCatalogSimilar`, `CatalogSimilarResponse`, 14 `CATALOG_SIMILAR_*` constants); `tsc --noEmit` clean; backend `/similar` route + tests untouched per D-03.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-29T16:06Z
- **Completed:** 2026-04-29T16:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- **`api.ts`**: removed `ImagesAPI.getCatalogSimilar` method (incl. JSDoc) and `CatalogSimilarResponse` exported type — 19 lines deleted
- **`strings.ts`**: removed 14 `CATALOG_SIMILAR_*` constants (`CATALOG_SIMILAR_MORE_LIKE_THIS` through `CATALOG_SIMILAR_FETCH_ERROR`); preserved `CATALOG_STACK_SHOW` / `CATALOG_STACK_HIDE`; replaced `// Phase 06 — visual similarity & stack (SIM-02, STACK-03)` section comment with a stack-only scope comment
- **Backend untouched** per D-03: `GET /api/images/catalog/<key>/similar` Flask route and `tests/test_images_clip_similar_api.py` left in place
- `tsc --noEmit` exits 0 after deletions
- DRY callsite sweep ran for `ImageDetailModal` (still consumed by SearchPage, PostNextSuggestionsPanel, BestPhotosGrid, TopPhotosStrip, UnpostedCatalogPanel — none of those import the removed similarity exports)

## Task Commits

1. **Task 1: Remove getCatalogSimilar and CatalogSimilarResponse from api.ts** — `9f131f8` (refactor)
2. **Task 2: Remove CATALOG_SIMILAR_\* family from strings.ts and fix section comment** — `0e38fc6` (refactor)

## Files Created/Modified

- `apps/visualizer/frontend/src/services/api.ts` — removed `getCatalogSimilar` method and `CatalogSimilarResponse` type
- `apps/visualizer/frontend/src/constants/strings.ts` — removed 14 `CATALOG_SIMILAR_*` constants, refactored section comment

## Decisions Made

- **Comment wording:** Plan task 2 step 2 gave an `e.g.` example comment that contained the literal `CATALOG_SIMILAR_*` token, but the `<acceptance_criteria>` for the same task requires `rg "CATALOG_SIMILAR_" apps/visualizer/frontend/src` to exit 1 (zero hits). The acceptance gate is binding and the example wording is suggestive (`e.g.`), so the committed comment paraphrases without the literal token: `// Phase 06 — stack expand/collapse (STACK-03). On-demand similarity copy was removed in Phase 9 (SIM-02 pivoted to job-driven materialized groups).` This satisfies both spirit (documents the removal for future readers) and letter (rg gate exits 1).
- **CATALOG_STACK_SHOW / CATALOG_STACK_HIDE preserved** even though `rg "CATALOG_STACK_SHOW|CATALOG_STACK_HIDE"` finds no consumers in src outside of `strings.ts` itself. Plan 09-03 task 2 explicitly preserves them; full dead-code sweep across stack constants is out of scope for Phase 9.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Section comment example contained literal `CATALOG_SIMILAR_*` token that would have failed the acceptance grep**
- **Found during:** Task 2 (after first commit, the rollup grep `rg "CATALOG_SIMILAR_"` returned the new comment line)
- **Issue:** The plan's `e.g.` example comment ("`Job-driven similarity copy lived in removed CATALOG_SIMILAR_*`") embedded the literal token, which conflicts with the binding acceptance criterion `rg "CATALOG_SIMILAR_" apps/visualizer/frontend/src` exits 1.
- **Fix:** Paraphrased the comment to avoid the literal `CATALOG_SIMILAR_*` token while preserving its informational intent: explains the removal happened in Phase 9 and that SIM-02 pivoted to job-driven materialized groups.
- **Files modified:** `apps/visualizer/frontend/src/constants/strings.ts`
- **Verification:** Both `rg "CATALOG_SIMILAR_" apps/visualizer/frontend/src` and the combined rollup `rg "CATALOG_SIMILAR_|getCatalogSimilar|CatalogSimilarResponse" apps/visualizer/frontend/src` exit 1; `tsc --noEmit` exits 0.
- **Committed in:** `0e38fc6` (Task 2 commit, after the in-place comment fix)

---

**Total deviations:** 1 auto-fixed (1 plan-text inconsistency between `e.g.` example and binding acceptance criterion)
**Impact on plan:** Zero — the deviation reconciled an intra-plan inconsistency. The plan's intent (zero `CATALOG_SIMILAR_*` hits in `apps/visualizer/frontend/src`) is fully met.

## Issues Encountered

None.

## Walkthrough disposition

These deletions are **orphan-only** changes to `api.ts` and `strings.ts` — no rendered UI surface was added or changed. The `phase-exit-walkthrough` hook keys off `*-VERIFICATION.md`, not `*-SUMMARY.md`, so any walkthrough exemption flag is a no-op on this SUMMARY. The full disposition (instructing gsd-verifier to set `walkthrough_exempt: true` on `09-VERIFICATION.md` when stamping `status: passed`) lives in the **`09-04-SUMMARY.md` § Walkthrough disposition** subsection per the plan's `<verification>` field.

## Next Phase Readiness

- Plan 09-04 (Wave 2 verification rollup) will rerun the same `rg` and `tsc` gates from a clean tree — already satisfied
- ESLint check is part of plan 09-04 (`npm run lint`) — not run in this plan to honor the `files_modified` scope
- Backend tests for `GET /api/images/catalog/<key>/similar` remain in `tests/test_images_clip_similar_api.py` per D-03 — Plan 09-04 backend pytest sweep will exercise them

---
*Phase: 09-v3-cleanup-docs-artifacts-dead-code*
*Completed: 2026-04-29*
