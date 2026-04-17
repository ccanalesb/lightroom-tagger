---
id: SEED-016
status: dormant
planted: 2026-04-17
planted_during: v2.0 shipped — planning next milestone
trigger_when: Next UX / review-flow milestone (catalog image treatment in general)
scope: Medium
---

# SEED-016: Rotate catalog images (match card + anywhere catalog images render)

## Why This Matters

When validating a match in the match detail modal, catalog and Instagram images
can differ in orientation — similar compositions become hard to compare, and the
reviewer ends up physically tilting their head to check whether a candidate is
really a match. That's friction on the most important action in the app:
**confirming a match correctly**.

Adding a rotation control directly improves **reviewer accuracy**: quick 90°
rotations (and ideally a free-rotate for subtle tilts) let the user align the
catalog image with the Instagram reference and make confident confirm / reject
calls without leaving the review flow.

Beyond the match modal, catalog images today are shown **as-is everywhere** —
no orientation handling, no per-image rotation, no remembered preference. This
seed should be scoped to the *catalog image as a surface*, not just the match
card, so the fix compounds across all views that render catalog images.

## When to Surface

**Trigger:** Next UX / review-flow milestone, or any milestone that touches how
catalog images are displayed.

Surface this seed during `/gsd-new-milestone` when the milestone scope matches
any of:

- Match review / validation UX
- Catalog image display or "images page" polish
- Identity / insights grids that render catalog thumbnails
- Generic image viewer / modal work
- Any work touching `CatalogImageModal`, `MatchImagesSection`, or the
  catalog image components below

## Scope Estimate

**Medium** — a phase or two.

Minimum viable slice (must-have):

- Rotation control (left 90° / right 90°, keyboard shortcut) on catalog images
  inside the match detail modal.
- CSS `transform: rotate(...)` on the image element; preserves source file.
- Respect image EXIF orientation if it isn't already being honored (verify
  first — may be handled by the browser, may not).

Full medium scope (why this isn't "small"):

- Apply the same rotation control to **every surface** that displays catalog
  images: `CatalogImageModal`, `CatalogImageCard`, `CatalogTab`, match card,
  identity grids, insights strips.
- Decide on persistence model:
  1. **Session-only** — rotation resets on reload (simplest, no backend).
  2. **Per-user preference** — persisted locally (localStorage) keyed by
     `catalog_key`.
  3. **Catalog-level** — stored in DB so it follows the image everywhere and
     optionally writes back to the Lightroom catalog. Biggest payoff, biggest
     scope.
- Likely land on (2) for this milestone and leave (3) as a follow-up.
- Extract a small reusable `RotatableImage` (or similar) component so every
  catalog-image surface gets the behavior for free — this is the architectural
  payoff that justifies medium over small.

Risks / open questions:

- EXIF orientation handling — is it already correct in the served image bytes?
  Confirm before adding rotation, or rotations will compound on incorrect
  baselines.
- Performance of rotated large images in grids (should be fine with CSS
  transform; verify on the Images page where many render at once).
- Interaction with any future crop / zoom / pan features — design the API so
  it composes.

## Breadcrumbs

Match review flow (primary motivation):

- `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchImagesSection.tsx`
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx`
- `apps/visualizer/frontend/src/components/matching/MatchCard.tsx`

All other catalog-image surfaces (must be covered too):

- `apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx`
- `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx`
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx`
- `apps/visualizer/frontend/src/components/identity/PostNextSuggestionsPanel.tsx`
- `apps/visualizer/frontend/src/components/identity/StyleFingerprintPanel.tsx`
- `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx`
- `apps/visualizer/frontend/src/components/insights/InsightsKpiRow.tsx`
- `apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.tsx`
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx`

Related seeds:

- SEED-004 — keep modal open after reject (same review flow).
- SEED-008 — images page UI consistency (natural home for a shared
  `RotatableImage` component).
- SEED-012 — skeleton loading and reusable image grid (if a reusable grid
  lands first, bake rotation into it).
- SEED-015 — matches sort unvalidated-first (pairs naturally in a matches
  review UX phase).

## Notes

Captured while planning the next milestone. User's framing was specifically
"catalog images are not treated at all" — this seed exists as much for the
**general catalog image UX debt** as for the immediate rotation need. When this
seed surfaces, resist the temptation to ship rotation-only on the match modal;
the compounding value is in making all catalog image surfaces share one
treatment.
