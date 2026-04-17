---
id: SEED-012
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: Next UI polish milestone, perceived-performance work, or design-system / component-library pass
scope: Medium
related: SEED-008, SEED-011
---

# SEED-012: Skeleton loading everywhere + reusable image-grid primitive

## Why This Matters

Today, most pages show a plain text "Loading..." (via `PageLoading.tsx` →
`MSG_LOADING`) while cards and images are fetching. This is:

1. **Perceptually slow.** A blank page with "Loading..." feels broken or unresponsive.
   A skeleton in the shape of the real content feels instant — the user sees layout,
   orients themselves, and perceives the wait as shorter even though nothing
   technically changed.
2. **Jumpy / reflow-heavy.** When the real cards arrive, the layout shifts from
   "centered text" to "grid of cards". Skeletons of the same shape as the content
   eliminate the shift.
3. **Inconsistent.** Every page rolls its own loading state — some use
   `PageLoading`, some inline `<p>Loading...</p>`, some have nothing and just show an
   empty state momentarily. Card/image grids in particular have no standard loading
   behavior.

A `SkeletonGrid` primitive already exists in the codebase
(`components/ui/page-states/SkeletonGrid.tsx`) but it's barely used — most surfaces
that load images still fall back to the plain text spinner. The gap is both
**adoption** (use skeletons where cards/images load) and **a stronger primitive**
(the current `SkeletonGrid` hardcodes a 2/4/6-column grid and a card shape — not
flexible enough for Best Photos, Top Scored, Matches, Catalog, etc., which have
different aspect ratios, densities, and metadata layouts).

## When to Surface

**Trigger:** Next UI polish milestone, perceived-performance work, or design-system
/ component-library pass

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:

- UI polish / UX consistency
- Perceived performance or "app feels slow" complaints
- Design-system / component-library work
- Work on SEED-008 (Images page UI unification) — the reusable grid primitive this
  seed proposes is adjacent to SEED-008's card/match consistency work
- Work on SEED-011 (CVA adoption) — the grid + skeleton primitives should be
  authored with CVA variants from the start

## Scope Estimate

**Medium** — a phase or two. Two linked deliverables, both in scope:

### Piece A — Ship a proper `<Skeleton>` primitive + convert "Loading…" sites

- Introduce a canonical `<Skeleton>` primitive (and/or upgrade the existing
  `CardSkeleton` + `SkeletonGrid` in `page-states/`) with variants:
  - `rect` (default — rectangle with animate-pulse)
  - `image` (aspect-ratio-aware, for image placeholders)
  - `text` (single-line)
  - Size/width variants for text lines (`w-1/3`, `w-2/3`, `w-full`)
- Convert every `PageLoading` / inline "Loading..." site that sits above a
  card/image layout to use a skeleton shaped like the real content.
- Pages/components that need conversion (non-exhaustive, confirmed via grep):
  - `components/identity/BestPhotosGrid.tsx`
  - `components/identity/PostNextSuggestionsPanel.tsx`
  - `components/identity/StyleFingerprintPanel.tsx`
  - `components/insights/TopPhotosStrip.tsx`
  - `components/insights/InsightsKpiRow.tsx`
  - `components/insights/PerspectiveRadarSummary.tsx`
  - `components/insights/ScoreDistributionChart.tsx`
  - `components/analytics/PostingFrequencyChart.tsx`
  - `components/analytics/PostingHeatmap.tsx`
  - `components/analytics/CaptionHashtagPanel.tsx`
  - `components/analytics/UnpostedCatalogPanel.tsx`
  - `components/images/MatchesTab.tsx`
  - `components/images/InstagramDumpSettingsPanel.tsx`
  - `components/descriptions/DescriptionGrid.tsx`
  - `pages/DashboardPage.tsx`, `pages/AnalyticsPage.tsx`, `pages/ProcessingPage.tsx`
- Non-card surfaces (charts, KPI rows, panels) each get their own skeleton shape
  matching the final layout, not a generic grid.

### Piece B — Build a reusable `<ImageGrid>` component

Today each surface that renders a grid of image cards (BestPhotosGrid, TopPhotosStrip,
CatalogImageCard consumers, Matches, Descriptions) implements its own grid layout
independently. Consolidate into a single `<ImageGrid>` primitive that:

- Accepts a list of items + a render-prop (or a typed card component) for each cell
- Handles **loading** (renders N skeleton cells of the same shape as real cards),
  **empty** (renders an `EmptyState`), and **error** states internally
- Accepts grid-shape props (columns at each breakpoint, gap, aspect ratio, optional
  overlay badges, optional title-under-image density)
- Encapsulates the "posted" / "selected" / "score" visual conventions so every grid
  surfaces them consistently
- Is authored with CVA variants (see SEED-011) — `density: compact|comfortable`,
  `aspect: square|portrait|landscape|original`, `overlay: badges|metadata|none`

Result: every image grid on the app uses the same primitive; the skeleton state is
automatically the right shape because the primitive owns both.

### Out of scope

- Non-image loading (forms, modals, detail panels) beyond the trivial `<Skeleton>`
  usages. Those should adopt the `<Skeleton>` primitive opportunistically but aren't
  the focus.
- Shimmer animations beyond a simple `animate-pulse`. Can be layered later.
- Full route-level transition skeletons. Per-component loading is enough.

## Breadcrumbs

### Existing primitives (partial — needs extension)
- `apps/visualizer/frontend/src/components/ui/page-states/SkeletonGrid.tsx` —
  current skeleton; hardcoded 2/4/6 col grid and card shape, barely used
- `apps/visualizer/frontend/src/components/ui/page-states/PageLoading.tsx` — the
  ubiquitous "Loading..." text that most surfaces fall back to; needs replacing on
  card/image surfaces
- `apps/visualizer/frontend/src/components/ui/page-states/PageError.tsx`
- `apps/visualizer/frontend/src/components/ui/page-states/EmptyState.tsx`
- `apps/visualizer/frontend/src/constants/strings.ts` — `MSG_LOADING` constant

### Image-grid consumers (candidates to migrate to `<ImageGrid>`)
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx`
- `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx`
- `apps/visualizer/frontend/src/components/descriptions/DescriptionGrid.tsx`
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` (renders a grid of
  `CatalogImageCard`)
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx`
- `apps/visualizer/frontend/src/components/instagram/InstagramImageCard.tsx` consumers

### Card primitives the grid will render
- `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx`
- `apps/visualizer/frontend/src/components/matching/MatchCard.tsx`
- `apps/visualizer/frontend/src/components/instagram/InstagramImageCard.tsx`

### Related seeds
- **SEED-008 (Images page UI consistency)** — SEED-008 argues for unified card/match
  visual language; this seed argues for the grid primitive that renders them.
  Natural pair — ideally scoped together in the same milestone.
- **SEED-011 (adopt CVA for Tailwind variants)** — the new `<Skeleton>` and
  `<ImageGrid>` primitives should be authored with CVA from day one. If SEED-011
  ships first, this seed is cleaner. If this ships first, the new primitives are
  prime refactor targets in SEED-011.
- **SEED-003 (rethink Identity page clarity)** — Identity page grids (Best Photos,
  Post Next) are major consumers and would benefit.
- **SEED-006 (photo stacking)** — whatever `<ImageGrid>` looks like, it should leave
  room for "stack representative + count badge" as a variant.

## Notes

User feedback (2026-04-17):

> "The initial loading on many pages doesn't have a skeleton at all, only a
> loading. We should use a skeleton in every place where card and images are being
> loaded. That might need a better redesign of a reusable component to render grid
> images."

Decision log:
- Both pieces (skeleton primitive adoption + reusable `<ImageGrid>`) are in scope.
- Standalone seed — not merged into SEED-008 or SEED-011, but cross-referenced to
  both. Rationale: skeleton coverage is cross-cutting (Catalog, Matches, Insights,
  Analytics, Identity) and the grid primitive is its own piece worth naming even
  though it overlaps with SEED-008's card work.

Phased rollout within the milestone:
- **Phase 1:** Upgrade the `<Skeleton>` primitive (variants: rect/image/text). Ship
  the shape conventions. Convert 3–5 highest-traffic surfaces as reference
  conversions (Dashboard, Analytics, Best Photos).
- **Phase 2:** Build the `<ImageGrid>` primitive with CVA variants. Migrate Best
  Photos and one Catalog grid as proof.
- **Phase 3:** Migrate remaining image grids (Matches, Descriptions, Top Photos,
  Catalog). Drop the old `SkeletonGrid` and hand-rolled grid layouts.
- **Phase 4:** Sweep remaining `PageLoading` / inline "Loading..." sites on
  non-image panels (charts, KPI rows) and give them shape-appropriate skeletons.

Scope risk: migrating every image grid in one milestone could creep Large if there
are layout edge cases (Matches uses two-image side-by-side, Top Photos is a
horizontal strip, etc.). Plan to time-box Phase 3 and accept that some grids may
keep their bespoke layout if migration cost exceeds payoff.
