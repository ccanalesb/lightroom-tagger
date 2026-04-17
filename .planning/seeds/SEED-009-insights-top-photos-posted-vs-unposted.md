---
id: SEED-009
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: Next UI polish milestone, or when SEED-007 (reusable filter) ships
scope: Medium
depends_on: SEED-007
---

# SEED-009: Differentiate posted vs. unposted photos in Insights → Top Scored Photos

## Why This Matters

The Insights page shows a "Top Scored Photos" strip, but every photo in it looks
identical regardless of whether it's already been posted to Instagram. The primary
value of this view is **surfacing hidden gems** — high-scored photos the user hasn't
posted yet and could still use — but today that signal is invisible. Users have to
click into each photo to find out whether they've already used it.

This is purely a UI gap: the backend data already includes `instagram_posted` per row
(see `TopPhotosStrip.tsx` line 29, mapping it into the modal stub), so nothing on the
API or scoring side needs to change. The problem is that:

1. There's no visual differentiation on the strip itself.
2. There's no way to filter down to just the actionable set (unposted top photos).

**Primary intent:** "Find hidden gems" — help me see at a glance which of my
highest-scored photos I haven't posted yet, so I can decide what to queue up next.
Feeds naturally into Post Next suggestions on the Identity page.

**Secondary benefit:** validating the scorer — if all my top-scored photos are ones
I've already posted, that's a positive signal that the scoring pipeline aligns with
my actual posting instincts.

## When to Surface

**Trigger:** Next UI polish milestone, or when SEED-007 (reusable filter) ships

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:

- UI/UX polish or consistency work
- Insights or Analytics page improvements
- Identity page / Post Next suggestion improvements (the "hidden gems" framing
  is closely adjacent)
- The reusable filter framework (SEED-007) is being built or just shipped — this
  seed is a natural first consumer

## Scope Estimate

**Medium** — a phase or two. Two linked pieces:

### Piece A — Split top photos into two sections (UI, small-medium)

Instead of one flat strip, render **two labeled groups** inside the "Top Scored
Photos" area on Insights:

1. **Top unposted** (primary, rendered first, larger / more prominent) — "hidden gems
   you haven't posted yet"
2. **Top already posted** (secondary, rendered below, possibly collapsed by default
   or with a lighter visual treatment) — "your highest-scored posted work"

Each section shows the top N of its group (probably N=6–10 each, tunable). Empty
states per section: "No unposted photos in the top scored set" / "No top-scored
photos have been posted yet".

Open question (defer to implementation): should the sections be ranked independently
(top unposted by score, top posted by score) or pulled from a single ranked list and
split? Probably independent ranking is more useful for the hidden-gems framing.

### Piece B — Add the shared posted filter to the strip (depends on SEED-007)

Add a tri-state **posted filter** (posted / unposted / all) to the Top Photos strip,
using the reusable filter component from SEED-007. Default state = **all** (so the
split-section layout above is still visible), but the user can collapse to just one
group via the filter.

This filter should be the exact same primitive used in Catalog's posted filter
(SEED-007 Phase 1 deliverable), so the UX is consistent across the app.

### Out of scope

- Changing how scores are computed.
- Stack-aware top photos (covered by SEED-006).
- Redesigning the rest of the Insights page (adjacent but separate — overlaps with
  SEED-003).

## Breadcrumbs

### The component that needs changes
- `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx` — current flat
  strip; already receives `instagram_posted` per row (line 29) but doesn't surface it
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx` — parent page that renders
  the strip (and has its own bespoke filters that should migrate to SEED-007)

### Data source (already exposes posted status)
- `apps/visualizer/frontend/src/services/api.ts` — `IdentityBestPhotoItem` type
  (includes `instagram_posted`)
- `lightroom_tagger/core/identity_service.py` — assembles the best-photos payload
- `apps/visualizer/backend/api/` — identity endpoint already returns posted flag

### Related UI that treats posted as a first-class signal (visual language reference)
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — already has
  posted filter logic (the pattern to consolidate into SEED-007 and reuse here)
- `apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.tsx` — the
  existing "what haven't I posted" view on Analytics; this seed is the Insights-page
  counterpart

### Related seeds
- **SEED-007 (reusable filter component)** — **dependency**. Piece B of this seed
  consumes the shared posted tri-state filter. Also this seed's planting surfaced
  that Analytics' bespoke filter needs to migrate to SEED-007.
- **SEED-003 (rethink Identity page clarity)** — adjacent; the hidden-gems framing
  feeds Post Next suggestions which live on the Identity page.
- **SEED-006 (photo stacking)** — if stacking ships first, "top unposted" should
  probably dedupe via stack representative (a burst of unposted near-duplicates
  should show once, not six times).

## Notes

User feedback (2026-04-17):

> "At insights we have top score photos, but there is no way to differentiate
> between posted and not posted."

Chosen UX direction:
- **Visual treatment:** split into two labeled sections ("Top unposted" / "Top
  already posted") — chosen over corner badges, dimming, or ring colors.
- **Filter:** add shared tri-state posted filter from SEED-007.
- **Primary framing:** "find hidden gems" (actionable / feeds Post Next), with
  scorer validation as a secondary benefit.

Same conversation also triggered an amendment to SEED-007 to cover the Analytics
page filter as another consumer of the reusable filter framework.
