# Phase 6: Images Page Visual Consistency - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify the visual language on the Images page: consolidate badge primitives under a consistent API (UI-01), adopt an inline chip-row pattern for badges on all Images page tabs (UI-02), and give match group tiles a richer card layout (UI-03). Extends to BestPhotosGrid (Identity) and TopPhotosStrip (Dashboard) for PerspectiveBadge placement — both surfaces in scope.

</domain>

<decisions>
## Implementation Decisions

### Badge consolidation (UI-01)
- **D-01:** Structural unification — all badge primitives consolidated under one folder (`ui/badges/` or equivalent). `VisionBadge`, `StatusBadge`, `ImageTypeBadge`, and the new `PerspectiveBadge` all wrap `<Badge>` internally. The `ui/Badge/` and `ui/badges/` split is resolved into a single location.
- **D-02:** Visual tokens harmonized across all badges — spacing, border, and rounding aligned — but intentional size differences are preserved where they make sense (e.g. `ImageTypeBadge` stays compact at `text-[10px]` since it renders a short CAT/IG label).
- **D-03:** Single barrel export is the public API for all badge primitives — consumers import from one path, not from `ui/Badge/` vs `ui/badges/` separately.
- **D-04:** Usage documented via inline JSDoc on each component — when and where to use each badge type.

### Inline chip-row pattern (UI-02)
- **D-05:** "Inline-in-description" = a chip row beneath the image/title in tile view, consistent with the `ImageMetadataBadges` pattern already used on Catalog tiles and Best Photos grid.
- **D-06:** Applies to all three Images page tabs: Instagram, Catalog, and Matches.
- **D-07:** Same chip set as Best Photos — Posted ✓, rating ★, Pick, AI — using the existing `ImageMetadataBadges` component wherever tiles appear on the Images page.

### Match card shape (UI-03)
- **D-08:** `MatchGroupTile` becomes a single Instagram image + metadata row below. The metadata row shows: catalog filename of the best candidate (or "N candidates" when unvalidated), and validation state badge.
- **D-09:** Card uses the same border/shadow/hover shell as CatalogTab tiles — visual parity with catalog cards.
- **D-10:** Unvalidated groups show "N candidates" in the metadata row only — no per-candidate metadata drilling. Validated groups show the catalog filename.

### PerspectiveBadge (UI-01 + extended scope)
- **D-11:** `PerspectiveBadge` renders perspective name + score with a color mapped to the perspective (e.g. `[Street 8.2]` in Street's color). Built as a proper primitive wrapping `<Badge>`.
- **D-12:** `PerspectiveBadge` (top 1 by score — the dominant perspective) appears on tile cards in **both** BestPhotosGrid (Identity page) and TopPhotosStrip (Dashboard). This is in scope for Phase 6. Planner decides exact placement (below the existing chip row, or appended to it).

### Claude's Discretion
- Which single folder name to use for the unified badge location (`ui/badges/` vs `ui/badge/` vs `ui/Badge/`)
- Exact color mapping for `PerspectiveBadge` per perspective (Street, Documentary, Publisher, Color Theory) — pick distinct, accessible colors
- Whether `PerspectiveBadge` appends to the existing `ImageMetadataBadges` row or renders as a separate row below it on Best Photos / Top Photos tiles
- Whether `ScorePill` (currently in `ui/badges/`) moves into the consolidated location or stays as a separate primitive

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Badge primitives (current state)
- `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx` — base `<Badge>` primitive (rounded-full, border, variants: default/success/warning/error/accent)
- `apps/visualizer/frontend/src/components/ui/badges/VisionBadge.tsx` — match vision result badge
- `apps/visualizer/frontend/src/components/ui/badges/StatusBadge.tsx` — job status badge
- `apps/visualizer/frontend/src/components/ui/badges/ImageTypeBadge.tsx` — CAT/IG type label
- `apps/visualizer/frontend/src/components/ui/badges/ScorePill.tsx` — score display pill

### Image tile and metadata
- `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx` — unified tile component; `overlayBadges` prop pattern
- `apps/visualizer/frontend/src/components/image-view/ImageMetadataBadges.tsx` — chip row (Posted, rating, Pick, AI + PrimaryScorePill); target for D-07 extension
- `apps/visualizer/frontend/src/components/image-view/imageTileVariants.ts` — tile variant classes

### Images page targets (UI-02, UI-03)
- `apps/visualizer/frontend/src/components/images/MatchGroupTile.tsx` — current single-image tile; target for D-08/D-09/D-10 card rework
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` — MatchGroupTile consumer
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — reference for card shell style
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` — target for D-06/D-07 chip row
- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` — Images page root

### Extended scope targets (D-12)
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` — target for PerspectiveBadge (top 1)
- `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx` — target for PerspectiveBadge (top 1)

### Requirements
- `.planning/REQUIREMENTS.md` — UI-01, UI-02, UI-03 definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ImageMetadataBadges` — already renders the Posted/rating/Pick/AI chip row; extend or reuse for D-07 on Instagram and Matches tiles
- `ImageTile.overlayBadges` — ReactNode overlay slot; MatchGroupTile already uses it for "Validated" / "N candidates" badge
- `Badge` base component — has full variant system; all specialized badges should wrap this
- `BestPhotosGrid` — already receives `ImageView` rows with `instagram_posted` and score data; has access to per-perspective scores via existing API response

### Established Patterns
- Badge chip rows use `flex items-center gap-2 flex-wrap` (see `ImageMetadataBadges`)
- Card shell: `rounded-card border border-border bg-bg shadow-card transition-all hover:border-border-strong hover:shadow-deep` (see `ImageTile`)
- Overlay badges: top-right positioned via `overlayBadges` prop on `ImageTile`
- All user-visible strings go in `constants/strings.ts`

### Integration Points
- `MatchGroupTile.tsx` — add metadata row below thumbnail (D-08); adopts card shell (D-09)
- `InstagramTab` tiles — ensure `ImageMetadataBadges` chip row is present (D-07)
- `BestPhotosGrid` + `TopPhotosStrip` — add `PerspectiveBadge` for top-1 perspective score (D-12)
- Badge folder restructure — update all import paths across the codebase after consolidation

</code_context>

<specifics>
## Specific Ideas

- User confirmed PerspectiveBadge already has a visual precedent inside the AI description section of the image modal — the new primitive should formalize that existing display
- User explicitly chose chip-row-beneath-tile (Option A) over prose-inline badges
- Match card is Option B (single image + metadata row below), not a two-panel layout
- PerspectiveBadge on tile grids shows **top 1 by score only** — not all 4 perspectives

</specifics>

<deferred>
## Deferred Ideas

- Showing all 4 perspective scores per tile (top-1 only is in scope for Phase 6; full breakdown deferred)
- PerspectiveBadge on any other surfaces beyond BestPhotosGrid and TopPhotosStrip

</deferred>

---

*Phase: 06-images-page-visual-consistency*
*Context gathered: 2026-04-21*
