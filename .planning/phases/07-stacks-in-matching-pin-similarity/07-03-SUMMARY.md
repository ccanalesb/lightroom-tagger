---
phase: 07-stacks-in-matching-pin-similarity
plan: 3
subsystem: ui
tags: [react, stacks, toast, catalog, vitest]

requires:
  - phase: 07-02
    provides: transactional stack split/merge/representative HTTP API
provides:
  - Shared `ConfirmModalFrame` + `useUndoToast` / `UndoToastBar` for destructive flows
  - Catalog stack strip: split, make representative, merge (source stack id)
  - Catalog image detail modal: same stack actions with confirm + representative undo
  - `ImagesAPI.splitStackMember`, `mergeStacks`, `setStackRepresentative` with cache invalidation
affects:
  - Images UI / catalog browse
  - Match reject modal (shared confirm shell)

tech-stack:
  added: []
  patterns:
    - "Confirm + optional timed undo via `offerUndo(message, onUndo)`"
    - "Reject confirm uses same modal frame as stack edits"

key-files:
  created:
    - apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx
  modified:
    - apps/visualizer/frontend/src/components/matching/match-detail-modal/RejectConfirmModal.tsx
    - apps/visualizer/frontend/src/constants/strings.ts
    - apps/visualizer/frontend/src/services/api.ts
    - apps/visualizer/frontend/src/components/image-view/adapters.ts
    - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
    - apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx
    - apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx

key-decisions:
  - "Representative change exposes timed Undo that calls `setStackRepresentative` with the previous rep; split/merge omit undo (no safe inverse in current API)."
  - "Merge uses numeric source stack id inline next to the expanded strip (power-user affordance)."
  - "Match reject keeps confirmation-only behavior (no server un-reject); shared abstraction is the modal shell + undo hook for stack flows."

patterns-established:
  - "`ConfirmModalFrame` for stacked destructive dialogs above the main UI"

requirements-completed: [STACK-05]

duration: 25 min
completed: 2026-04-26
---

# Phase 7 Plan 3: Stack edit UI + shared confirm/undo — Summary

**Shipped stack split/merge/representative controls in the catalog stack strip and catalog detail modal, with a reusable confirm shell (used by reject-match) and a timed undo path for representative changes.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-26T18:07Z (approx.)
- **Completed:** 2026-04-26T18:10Z (approx.)
- **Tasks:** 3
- **Files touched:** 8 (+ this summary)

## Accomplishments

- Added `ConfirmUndoAction.tsx` (`ConfirmModalFrame`, `useUndoToast`, `UndoToastBar`) and refactored `RejectConfirmModal` to use the shared frame (no behavior change in reject tests).
- Wired `ImagesAPI` stack mutations with `invalidateAll` for catalog, detail, dashboard, and identity caches; extended `ImageView` / `fromCatalogListRow` with stack metadata for modal context.
- Catalog expanded stack UI and catalog `ImageDetailModal` now run mutations behind the same confirm pattern; representative updates show an undo toast that reverts via API.

## Task Commits

1. **Task 1: Create shared confirm+undo component** — `39ca66d` — `feat(07-03): shared confirm shell + undo toast hook for destructive actions`
2. **Task 2: Wire stack edit actions in Images UI** — `e8f90d3` — `feat(07-03): stack split/merge/representative UI with confirm + undo toast`
3. **Task 3: Frontend tests for stack edit UX** — `1145a61` — `test(07-03): CatalogTab stack confirm, mutation, and undo paths`

## Verification

Commands (all **passed**):

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/frontend && npm test -- run \
  src/components/matching/match-detail-modal/__tests__/MatchDetailModal.reject.test.tsx \
  src/components/images/__tests__/CatalogTab.test.tsx
```

- `MatchDetailModal.reject.test.tsx`: 3 tests passed (plan referenced `MatchDetailModal.test.tsx`; actual file is `MatchDetailModal.reject.test.tsx`).
- `CatalogTab.test.tsx`: 6 tests passed (includes confirm gate, `splitStackMember` dispatch, `setStackRepresentative` + undo).

`npx tsc --noEmit` in `apps/visualizer/frontend`: **clean**.

## Self-Check: PASSED

## Deviations from Plan

None for behavior — plan listed `MatchDetailModal.tsx` under task 1; reject flow migration is fully contained in `RejectConfirmModal.tsx` + shared UI module, so the matching `MatchDetailModal.tsx` file did not require edits.

Supporting files beyond plan frontmatter `files_modified`: `constants/strings.ts` (stack copy), `components/image-view/adapters.ts` (pass `stack_*` into `ImageView` from catalog rows).

## Next

Ready for **07-04-PLAN** (or next plan in phase 7 roadmap).
