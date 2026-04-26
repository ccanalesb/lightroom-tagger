# Phase 6: Images Page Visual Consistency - Context

**Gathered:** 2026-04-25 (auto refresh)
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify visual consistency for Images-related tiles by consolidating badge primitives (UI-01), standardizing inline metadata chip behavior across Images tabs (UI-02), and aligning match-group tile structure with shared card patterns (UI-03), plus the phase-approved PerspectiveBadge rollout on Best Photos and Top Photos surfaces.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**12 requirements are locked.** See `06-UI-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `06-UI-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- UI-01 badge consolidation into a single `ui/badges` surface with unified exports and usage guidance.
- UI-02 consistent inline metadata chip row behavior for Instagram, Catalog, and Matches tile surfaces.
- UI-03 match-group tile layout and metadata-row consistency using the shared tile shell.
- D-11 and D-12 PerspectiveBadge behavior on `BestPhotosGrid` and `TopPhotosStrip`.

**Out of scope (from SPEC.md):**
- URL-synced filters, CVA migration, shadcn adoption, and full Instagram adapter parity.
- PerspectiveBadge expansion to other surfaces beyond Best Photos and Top Photos.
- New capability work outside visual-consistency contracts.

</spec_lock>

<decisions>
## Implementation Decisions

### Badge surface consolidation
- **D-01:** Keep `apps/visualizer/frontend/src/components/ui/badges/` as the single canonical badge location.
- **D-02:** Route all badge imports through one barrel (`../ui/badges`) instead of split paths.
- **D-03:** Keep specialized badge wrappers (`PerspectiveBadge`, `StatusBadge`, `VisionBadge`, `ImageTypeBadge`) wrapping the base `Badge` primitive.
- **D-04:** Keep `ScorePill` as a specialized primitive in the same badge surface and export it from the same barrel.

### Inline metadata chips across Images tabs
- **D-05:** Keep metadata chips rendered by `ImageMetadataBadges` inside `ImageTile` directly below the date line.
- **D-06:** Preserve the chip set contract: Posted, rating, Pick, AI, plus `PrimaryScorePill` when applicable.
- **D-07:** Use `hidePostedMetadataBadge` when `overlayBadges` shows Posted to prevent duplicate status cues.
- **D-08:** Preserve shared chip-row layout (`flex items-center gap-2 flex-wrap`) for responsive consistency.

### Match group tile composition
- **D-09:** Keep `MatchGroupTile` on the shared `ImageTile` shell; no separate wrapper card style.
- **D-10:** Keep metadata in the `footer` row: unvalidated groups emphasize candidate count (with optional confidence score); validated groups show validated status plus selected catalog filename.
- **D-11:** Keep review entrypoint behavior through `pickInitialMatch(group)` and `onOpenReview(group, initial)` with no alternate navigation flow.

### PerspectiveBadge rollout
- **D-12:** Show dominant perspective only (display name + score, color-mapped by slug) via `PerspectiveBadge` in `ImageTile.footer` on `BestPhotosGrid` and `TopPhotosStrip`.

### Claude's Discretion
- Fine-tune neutral fallback styling for unknown perspective slugs while preserving contrast in light/dark modes.
- Keep score formatting stable (`8` vs `8.2`) as long as it remains consistent with current badge readability.
- Adjust small spacing around footer badge rows (`mt-0`/`mt-1`) if needed for scanability without changing hierarchy.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements and scope
- `.planning/phases/06-images-page-visual-consistency/06-UI-SPEC.md` — locked UI contracts D-01..D-12 for this phase.
- `.planning/REQUIREMENTS.md` — UI-01, UI-02, UI-03 requirement definitions.
- `.planning/ROADMAP.md` — v2.1 Phase 6 milestone contract and completion intent.

### Badge primitives
- `apps/visualizer/frontend/src/components/ui/badges/index.ts` — single public export surface.
- `apps/visualizer/frontend/src/components/ui/badges/Badge.tsx` — base badge primitive and variants.
- `apps/visualizer/frontend/src/components/ui/badges/PerspectiveBadge.tsx` — perspective slug mapping and score label formatting.
- `apps/visualizer/frontend/src/components/ui/badges/ScorePill.tsx` — specialized score chip behavior.

### Shared tile and metadata primitives
- `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx` — canonical tile shell, overlay slot, footer slot, metadata row position.
- `apps/visualizer/frontend/src/components/image-view/ImageMetadataBadges.tsx` — chip row contract and posted-chip deduping flag.

### Surface integrations
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — baseline grid tile integration pattern.
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` — Instagram tile usage and footer composition.
- `apps/visualizer/frontend/src/components/images/MatchGroupTile.tsx` — match tile footer semantics for validated/unvalidated states.
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` — grouped match rendering and review flow.
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` — PerspectiveBadge footer + posted overlay behavior.
- `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx` — strip variant PerspectiveBadge footer behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ImageTile` already centralizes card shell, thumbnail overlay, metadata row, and footer extension points.
- `ImageMetadataBadges` already owns common chip rendering and hide-posted deduping behavior.
- `PerspectiveBadge` already maps known perspective slugs to color classes with neutral fallback.
- `fromBestPhotoRow` / `fromMatchSide` adapters already normalize row shapes for tile rendering.

### Established Patterns
- Tile shell consistency is enforced via `ImageTile` variants instead of per-tab custom wrappers.
- Footer content is the preferred extension point for secondary metadata lines.
- Badge import hygiene now routes through `../ui/badges` barrel.
- User-visible copy and labels continue to live in `constants/strings.ts`.

### Integration Points
- `MatchGroupTile` remains the central place for validated/unvalidated candidate-row wording and score display.
- `BestPhotosGrid` and `TopPhotosStrip` remain the only phase-approved PerspectiveBadge surfaces.
- `CatalogTab` and `InstagramTab` continue inheriting metadata-row behavior from `ImageTile` + `ImageMetadataBadges`.

</code_context>

<specifics>
## Specific Ideas

- Auto run selected recommended defaults for all gray areas using the active `06-UI-SPEC.md` and current codebase shape.
- Dominant-perspective presentation remains top-1 only, keeping tile density readable.
- No additional custom visual language was introduced beyond existing badge/tile primitives.

</specifics>

<deferred>
## Deferred Ideas

- Showing all four perspectives per tile (top-1 remains the phase contract).
- PerspectiveBadge rollout to other pages/surfaces outside Best Photos and Top Photos.

### Reviewed Todos (not folded)
- `Benchmark DINOv2/CLIP embeddings against user-validated match pairs` (`.planning/todos/pending/benchmark-embedding-recall.md`) — deferred; belongs to embedding/matching phases, not UI consistency scope.

</deferred>

---

*Phase: 06-images-page-visual-consistency*
*Context gathered: 2026-04-25*
