---
phase: 5
plan: "02"
slug: best-photos-overlay-posted-badge
subsystem: ui
tags: [react, vitest, identity, ImageTile, Badge, IDENT-04]

requires:
  - phase: 5
    provides: Optional `posted` on best-photos API and `IdentityAPI.getBestPhotos({ posted })` (Plan 01)
provides:
  - Top-right Posted overlay on Identity Best Photos tiles via `ImageTile.overlayBadges`
  - `hidePostedMetadataBadge` / `hidePostedBadge` to avoid duplicate Posted in metadata row when overlay is used
  - Global Badge label weight aligned to UI-SPEC (`font-semibold`)
affects: [Plan 03 Identity page intros (same BestPhotosGrid file — sequencing preserved)]

tech-stack:
  added: []
  patterns:
    - "Posted status: overlay for grid prominence, suppress duplicate chip via explicit prop passthrough"

key-files:
  created:
    - apps/visualizer/frontend/src/components/identity/BestPhotosGrid.test.tsx
  modified:
    - apps/visualizer/frontend/src/components/image-view/ImageMetadataBadges.tsx
    - apps/visualizer/frontend/src/components/image-view/ImageTile.tsx
    - apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx
    - apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx

key-decisions:
  - "Badge base text class uses `font-semibold` (not `font-medium`) to match UI-SPEC label weight for all badge variants, including Posted."

requirements-completed: [IDENT-04]

duration: ~20 min
completed: 2026-04-21T00:00:00Z
---

# Phase 5 Plan 02: Best Photos posted overlay + dedupe metadata chip — Summary

**Identity Best Photos tiles show a single top-right “Posted” success badge when `instagram_posted` is true, with the metadata-row Posted chip suppressed so IDENT-04 stays readable.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-21 (session)
- **Completed:** 2026-04-21
- **Tasks:** 3
- **Files touched:** 5 (1 new test file)

## Accomplishments

- Optional `hidePostedBadge` on `ImageMetadataBadges` and `hidePostedMetadataBadge` on `ImageTile` to avoid double “Posted” when the overlay carries the signal.
- `BestPhotosGrid` passes `overlayBadges={<Badge variant="success">Posted</Badge>}` for posted rows, `hidePostedMetadataBadge` on every tile, and `undefined` overlay for unposted rows.
- `Badge` label class updated from `font-medium` to `font-semibold` per Phase 5 UI-SPEC.
- RTL test asserts exactly one “Posted” in the best-photos region for a single posted item.

## Task Commits

Each task was committed atomically:

1. **Task 01: ImageMetadataBadges optional hide for Posted chip** — `039c3ac` (`feat(05-02): add hidePostedBadge props for ImageTile metadata row`)
2. **Task 02: BestPhotosGrid overlayBadges + Badge semibold** — `3d99d0c` (`feat(05-02): Posted overlay on BestPhotosGrid + Badge label semibold`)
3. **Task 03: RTL coverage for BestPhotosGrid** — `e0a4efc` (`test(05-02): BestPhotosGrid Posted overlay RTL (single badge)`)

## Files Created/Modified

- `ImageMetadataBadges.tsx` — `hidePostedBadge` prop; conditional `showPostedChip`.
- `ImageTile.tsx` — `hidePostedMetadataBadge` forwarded to `ImageMetadataBadges`.
- `BestPhotosGrid.tsx` — `Badge` import, `overlayBadges` + `hidePostedMetadataBadge={true}` on each tile.
- `Badge.tsx` — `font-semibold` for label text.
- `BestPhotosGrid.test.tsx` — mocked `getBestPhotos` with one posted row; `within(region)` + `getAllByText('Posted')` length `1`.

## Verification

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/frontend && npx tsc --noEmit && npx vitest run
```

- `tsc --noEmit`: exit 0
- `vitest run`: 39 files, 221 tests passed

## Self-Check: PASSED

Plan `<acceptance_criteria>` per task and repo `<verification>` command re-run successfully.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Steps

Ready for **Plan 03** (Identity page order + section intros, Wave 3 — depends on 01, 02).
