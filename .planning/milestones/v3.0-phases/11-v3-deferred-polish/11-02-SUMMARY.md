---
phase: 11-v3-deferred-polish
plan: "11-02"
subsystem: ui
tags: [react, accessibility, toast, copy-centralization]

requires:
  - phase: 11-01
    provides: CATALOG_CACHE_* string constants in strings.ts for Catalog Cache tab copy
provides:
  - Disclosure pattern on Matching Advanced Options (aria-expanded, aria-controls, panel id, type=button)
  - Message-only undo toasts that honor DEFAULT_UNDO_TIMEOUT_MS without an Undo control
  - CatalogCacheTab UI strings sourced from strings.ts plus NAS troubleshooting paragraph
affects:
  - phase 11 frontend polish (remaining plans e.g. 11-03)

tech-stack:
  added: []
  patterns:
    - "Optional onUndo on UndoToastBar; visibility gated by toast state, not props-only"

key-files:
  created: []
  modified:
    - apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx
    - apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx
    - apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx

key-decisions:
  - "offerUndo uses explicit if (onUndo != null) branches so acceptance rg excludes legacy if (!onUndo) early-return pattern"

patterns-established:
  - "Undo toast live region (role=status, aria-live=polite) applies to message-only and undo variants"

requirements-completed: []

duration: ~15 min
completed: 2026-05-04
---

# Phase 11 Plan 11-02: AdvancedOptions a11y, undo toast, CatalogCacheTab copy — Summary

**Matching Advanced Options now exposes a proper disclosure control; message-only undo notifications stay visible for the full timeout; Catalog Cache tab copy and NAS guidance live in `strings.ts` constants.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-04T16:30:00Z (approx.)
- **Completed:** 2026-05-04T16:45:00Z (approx.)
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `type="button"`, `aria-expanded`, `aria-controls`, and `id="advanced-options-panel"` wiring on Advanced Options disclosure.
- Fixed `offerUndo(message)` without rollback callback to show a timed status toast; `UndoToastBar` renders Undo only when `toast.onUndo` is set; `UndoToastBarProps.onUndo` is optional.
- Replaced twelve inline Catalog Cache strings with `CATALOG_CACHE_*` imports and appended NAS troubleshooting copy below cache location.

## Task Commits

Each task was committed atomically:

1. **Task T1: AdvancedOptions a11y** — `f677703` (feat)
2. **Task T2: Undo toast message-only** — `0560864` (fix)
3. **Task T3: CatalogCacheTab strings + NAS** — `a685a37` (refactor)

## Files Created/Modified

- `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` — disclosure button and panel ids for assistive tech.
- `apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx` — `offerUndo` timeout path without `onUndo`; conditional Undo button; optional bar prop.
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx` — imports and JSX wired to `strings.ts`; NAS paragraph after cache location block.

## Decisions Made

- Used `if (onUndo != null)` / `else` in `offerUndo` so the plan’s “no `if (!onUndo)`” acceptance check is satisfied while preserving an explicit `setToast({ kind: 'visible', message })` branch.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Verification

From `apps/visualizer/frontend`:

```text
npx tsc --noEmit  → exit 0
npx vitest run    → exit 0 (282 tests)
```

## Next Phase Readiness

Ready for plan **11-03** in this phase directory.

## Self-Check: PASSED

- Plan `<verification>` commands re-run after all tasks: PASS.

---
*Phase: 11-v3-deferred-polish*
*Completed: 2026-05-04*
