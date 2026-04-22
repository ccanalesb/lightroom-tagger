# Phase 6 — Plan 03: match-group-tile-cards

## Objective

Rework `MatchGroupTile` so the Matches tab uses Catalog-style `ImageTile` affordance with a **footer metadata row** (no duplicate candidate/validated copy on the thumbnail overlay).

## Completed work

### Task 01 — `msgMatchGroupCandidates`

- Added `msgMatchGroupCandidates(count)` in `apps/visualizer/frontend/src/constants/strings.ts` next to match copy (`MATCH_VALIDATED`).
- **Commit:** `feat(phase-6-03): add msgMatchGroupCandidates string helper`

### Task 02 — `MatchGroupTile` refactor

- Removed `overlayBadges` from `ImageTile` (no corner badge for candidates or validated).
- **Validated (`group.has_validated`):** footer row with truncated catalog filename (`initial.catalog_image?.filename ?? initial.catalog_key`) and `<Badge variant="success">{MATCH_VALIDATED}</Badge>` in a `justify-between` flex row.
- **Unvalidated:** single line `msgMatchGroupCandidates(group.candidate_count)` only — no catalog filename, no badge.
- Kept `variant="grid"`, `pickInitialMatch`, and early `null` when no candidates.
- **Commit:** `feat(phase-6-03): move match group metadata to ImageTile footer`

### Task 03 — Tests

- Added `apps/visualizer/frontend/src/components/images/__tests__/MatchGroupTile.test.tsx` with:
  - Validated: expects `foo.jpg` and `MATCH_VALIDATED`, scoped via `data-testid="image-tile"`.
  - Unvalidated: expects `3 candidates`, asserts catalog filename `secret-catalog.jpg` is absent while Instagram title uses a non-matching thumb label.
- **Commit:** `feat(phase-6-03): add MatchGroupTile unit tests`

## Verification

```bash
cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run
```

- `tsc --noEmit`: exit 0
- `vitest run`: 40 files, 226 tests passed

## Self-Check: **PASSED**

- Footer carries validated filename + badge or unvalidated candidate count only.
- No `overlayBadges` on `MatchGroupTile`.
- `msgMatchGroupCandidates` centralized in `strings.ts`.
- Tests cover validated vs unvalidated copy.
- `STATE.md` / `ROADMAP.md` not modified.
