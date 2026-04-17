---
id: SEED-008
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: Next UI polish milestone or design-system unification pass
scope: Medium
---

# SEED-008: Unify UI language on the Images page (badges, match cards, descriptions)

## Why This Matters

The Images page currently suffers from visual and interaction inconsistencies that hurt
both the aesthetics and the UX:

- **Badges look bad rendered as cards.** They're visually heavy, take up too much space,
  and feel out of place next to other elements. In Catalog, similar information is woven
  into the text description, which is cleaner and more scannable.
- **Discrepancy between badge displays.** The same concept (e.g., vision / image type /
  status) is rendered differently across components, so users can't rely on visual pattern
  recognition to quickly parse what they're looking at.
- **Matches are not cards**, while other elements on the page are — breaking the implicit
  "this is a container of info" affordance and making the page feel stitched together
  rather than designed.
- **UX impact, not just aesthetic:** inconsistent shapes/weights force the user to re-read
  each element instead of scanning by pattern, and the card-vs-inline mismatch hides the
  hierarchy of what's important.

Fixing this pays off across the whole visualizer because the same badge primitives are
reused in Catalog, Matches, Instagram, and the matching modals.

## When to Surface

**Trigger:** Next UI polish milestone, or any milestone that touches design-system
unification / component-library cleanup.

This seed should be presented during `/gsd-new-milestone` when the milestone scope
matches any of these conditions:

- Milestone theme is UI/UX polish, visual redesign, or consistency
- Work is planned on the Images page, Catalog page, or Matches surface
- A design-system / shared-component refactor is being scoped
- Complaints about "page feels inconsistent" show up in user feedback

## Scope Estimate

**Medium** — a phase or two. Roughly:

1. Audit current badge usages across Images / Catalog / Matches and decide per-context
   whether each signal belongs inline (in description text) or as a chip/badge.
2. Consolidate `Badge`, `VisionBadge`, `StatusBadge`, `ImageTypeBadge`,
   `PerspectiveBadge` into a consistent primitive + usage guidelines.
3. Decide whether matches should be cards (and which card style — the Catalog card
   pattern vs a lighter list-row pattern). Apply uniformly.
4. Update the Images page to follow the unified pattern. Regression-check Catalog +
   Matches + Instagram views that share the primitives.

Not a full design-system milestone — scoped to the shared visual language of these three
surfaces.

## Breadcrumbs

Related code in the current codebase:

- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` — the page in question
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` — matches presentation on Images page
- `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx` — base badge primitive
- `apps/visualizer/frontend/src/components/ui/badges/VisionBadge.tsx`
- `apps/visualizer/frontend/src/components/ui/badges/StatusBadge.tsx`
- `apps/visualizer/frontend/src/components/ui/badges/ImageTypeBadge.tsx`
- `apps/visualizer/frontend/src/components/matching/PerspectiveBadge.tsx`
- `apps/visualizer/frontend/src/components/matching/MatchCard.tsx` — reference "card" pattern
- `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx` — inline-description pattern to emulate
- `apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx`
- `apps/visualizer/frontend/src/components/catalog/ImageScoresPanel.tsx`

Related seeds:

- SEED-003 (rethink identity page clarity) — adjacent UX/clarity concerns, may want to
  coordinate if a broader UI polish milestone is scoped.

## Notes

Captured during v2.0 wrap-up. User observation:

> "At images, there is an inconsistency in the use of the badges. They don't look good
> as cards — they could be inline in the text descriptions like in Catalog. There's a
> discrepancy in how both are displayed. Matches are not cards. A lot of UI
> inconsistency between elements on that page."

User confirmed this is both an aesthetic and a UX problem, scoped as Medium.
