# Phase 6 — Plan 01 execution summary

**Slug:** badge-barrel-and-primitives  
**Completed:** 2026-04-22

## What was built

### Key files created

- `apps/visualizer/frontend/src/components/ui/badges/Badge.tsx` — base badge (moved from removed `ui/Badge/`).
- `apps/visualizer/frontend/src/components/ui/badges/PerspectiveBadge.tsx` — perspective slug + score chip with hue bundles (street, documentary, publisher, color_theory).

### Key files modified

- `apps/visualizer/frontend/src/components/ui/badges/index.ts` — barrel exports: `Badge`, `ImageTypeBadge`, `PerspectiveBadge`, `ScorePill`, `StatusBadge`, `VisionBadge`.
- `VisionBadge.tsx`, `StatusBadge.tsx`, `ImageTypeBadge.tsx` — render through `<Badge>` with mapped variants / Tailwind overrides per plan.
- `ScorePill.tsx` — file-level JSDoc (D-04); implementation unchanged aside from doc consolidation.
- All former `../ui/Badge` / `../../ui/Badge/Badge` consumers repointed to `../ui/badges` (including `FilterChip`, `PrimaryScorePill` barrel import).
- `JobCard.tsx` — single `import { Badge, StatusBadge } from '../ui/badges'`.
- `apps/visualizer/frontend/src/components/ui/__tests__/Badges.test.tsx` — assertions updated for `Badge` token classes (`bg-*-50`, semantic `text-*`, `border-2` for `withBorder`).

### Removed

- `apps/visualizer/frontend/src/components/ui/Badge/` directory (no longer present).

## Deviations from the plan

- **`ImageTile.test.tsx`** import path was updated during Task 01 so `rg 'ui/Badge'` could reach zero matches before deleting the old folder; the plan listed this under Task 03 only.
- **`visionBadge.ts` / `statusBadgeClasses` in `jobStatus.ts`** remain in the codebase for `MatchScoreBadges` and existing util tests; only the React badge components were decoupled from those helpers.
- **UNCERTAIN / undefined vision results** now use the shared `warning` (orange) `Badge` variant instead of the previous yellow `visionBadgeClasses` palette — matches the plan’s variant mapping.

## Self-Check: **PASSED**

- `rg "from ['\"].*ui/Badge" apps/visualizer/frontend/src` — no results.
- `ui/badges/index.ts` exports: `Badge`, `VisionBadge`, `StatusBadge`, `ImageTypeBadge`, `ScorePill`, `PerspectiveBadge`.
- No `components/ui/Badge/` under the frontend.
- JSDoc present on `Badge`, `VisionBadge`, `StatusBadge`, `ImageTypeBadge`, `PerspectiveBadge`, `ScorePill`.
- `npx tsc --noEmit && npx vitest run` (from `apps/visualizer/frontend`) — exit 0, 221 tests passed.

## Commits

1. `feat(phase-6-01): move base Badge into ui/badges barrel`
2. `feat(phase-6-01): wrap badges in Badge primitive, add PerspectiveBadge, JSDoc`
3. `feat(phase-6-01): consolidate JobCard badge imports, align badge tests`
4. `docs(phase-6-01): add plan 01 execution summary`
