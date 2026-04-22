# Phase 6 · Plan 04 — perspective-footer-identity

## Objective

Surface the top-scoring identity perspective (`per_perspective`) on image tiles via the `ImageTile` `footer` slot in **BestPhotosGrid** (Identity) and **TopPhotosStrip** (Dashboard), reusing `PerspectiveBadge`.

## Delivered

1. **`pickDominantPerspective`** (`apps/visualizer/frontend/src/components/identity/pickDominantPerspective.ts`) — selects the entry with maximum finite `score`; empty/`undefined`/`null` input yields `null`; ties keep the first entry.
2. **BestPhotosGrid** — for each `IdentityBestPhotoItem` row, `footer` renders `PerspectiveBadge` when a dominant entry exists; existing Posted `overlayBadges` and `hidePostedMetadataBadge` unchanged.
3. **TopPhotosStrip** — same `footer` + `PerspectiveBadge` pattern for strip tiles.
4. **Tests** — `pickDominantPerspective.test.ts` (max score, empty, undefined, tie); `BestPhotosGrid.test.tsx` asserts footer text `Street 9` from fixture `per_perspective` + `display_name`.

## Commits (atomic per task)

| Commit     | Message |
|-----------|---------|
| `e50b2d2` | feat(phase-6-04): add pickDominantPerspective helper |
| `89e75e5` | feat(phase-6-04): show dominant perspective in BestPhotosGrid footer |
| `a75b1e5` | feat(phase-6-04): show dominant perspective in TopPhotosStrip footer |
| `bdddfc4` | feat(phase-6-04): test pickDominantPerspective and BestPhotosGrid perspective footer |

## Verification

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/frontend && npx tsc --noEmit && npx vitest run
```

**Result:** `tsc` exit 0; **231** tests passed (full suite at completion time).

## Self-Check: **PASSED**

- Dominant perspective from `row.per_perspective` drives `footer` + `PerspectiveBadge` in both grids.
- `displayName` passed from `IdentityPerPerspectiveScore.display_name` when present.
- No new npm dependencies; `STATE.md` / `ROADMAP.md` not modified.
