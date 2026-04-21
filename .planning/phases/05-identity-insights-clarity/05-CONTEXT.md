# Phase 5: Identity & Insights Clarity - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Errata (read before Wave sequencing)

Research and Plan 01 found a gap: the API must gain **`posted` query support** (backend + client typings) in **Wave 1 (Plan 01)**. Downstream work assumes that filter exists. This phase is **not** purely frontend-only despite the original boundary note below — treat Plan 01 as required for `posted` filtering.

## Phase Boundary

Surface posted/unposted status on BestPhotosGrid cards (IDENT-04), reorder the Identity page for a fingerprint → best work → post next narrative flow with section intros (IDENT-05), and replace the Dashboard Top Photos area with a tabbed Unposted / Posted / All view that covers both DASH-02 and DASH-03 in a single unified control.

~~This phase is **frontend-only** — the backend `/api/identity/best-photos` endpoint already accepts a `posted` boolean param. No backend changes needed.~~ **SUPERSEDED by Errata above.** Plan 01 (Wave 1) adds `posted` support to the backend and TypeScript client before any Dashboard tab work.

</domain>

<decisions>
## Implementation Decisions

### IDENT-04: Posted badge on BestPhotosGrid cards
- **D-01:** Show a small "Posted" overlay badge top-right on posted tiles using the existing `overlayBadges?: ReactNode` prop on `ImageTile`. Reuse `<Badge variant="success">Posted</Badge>` consistent with `ImageMetadataBadges`. Unposted tiles get no badge (absence = not yet posted).

### IDENT-05: Identity page narrative flow
- **D-02:** Reorder Identity page sections to: `StyleFingerprintPanel` → `BestPhotosGrid` → `PostNextSuggestionsPanel`. Fingerprint first establishes the photographer's voice, Best Photos shows it in practice, Post Next acts on it.
- **D-03:** Add a brief 1-2 sentence section intro beneath each section heading. Planner writes the copy — should orient the user on what each section shows and why it matters. These are `<p className="text-sm text-text-secondary">` below the `<h2>`, consistent with existing page subtitle patterns.
- **D-04:** No additional card-level visual differentiation needed between Best Photos and Post Next. The existing layout difference (tile grid vs ranked list) plus reorder + intros fully satisfies IDENT-05.

### DASH-02 + DASH-03: Dashboard Top Photos (unified)
- **D-06:** Replace the current single-strip `TopPhotosStrip` and the planned two-section split with a **tab strip: Unposted | Posted | All**, defaulting to "Unposted." This single UI element covers both DASH-02 (unposted prominent, posted secondary) and DASH-03 (posted-status filter). Each tab fetches independently via `getBestPhotos({ limit: 8, posted: false/true/undefined })`. The "All" tab fetches without a posted filter. Planner decides whether to use the existing `<Tabs>` component or a lightweight inline tab pattern.

### Claude's Discretion
- Section intro copy for the three Identity sections (fingerprint, best photos, post next)
- Number of photos per tab in TopPhotosStrip (8 is reasonable default for all tabs)
- Whether "All" tab shows 8 or 12 photos
- Tab component choice for TopPhotosStrip (existing `<Tabs>` component or lightweight inline variant)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing components to build on
- `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx` — `overlayBadges` prop pattern
- `apps/visualizer/frontend/src/components/image-view/ImageMetadataBadges.tsx` — existing `<Badge variant="success">Posted</Badge>` pattern
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` — target for D-01
- `apps/visualizer/frontend/src/pages/IdentityPage.tsx` — target for D-02, D-03
- `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx` — target for D-06
- `apps/visualizer/frontend/src/pages/DashboardPage.tsx` — TopPhotosStrip consumer to update for D-06

### Filter framework (Phase 4)
- `apps/visualizer/frontend/src/hooks/useFilters.ts` — hook for D-06 if tab state goes through filter framework
- `apps/visualizer/frontend/src/components/filters/FilterBar.tsx` — reference (D-06 uses tabs, not FilterBar)

### API
- `apps/visualizer/frontend/src/services/api.ts` — `IdentityAPI.getBestPhotos` accepts `posted?: boolean`; `IdentityBestPhotoItem.instagram_posted: boolean`

### Requirements
- `.planning/REQUIREMENTS.md` — IDENT-04, IDENT-05, DASH-02, DASH-03 definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ImageTile.overlayBadges`: ReactNode overlay slot — drop `<Badge variant="success">` directly into BestPhotosGrid's tile rendering for D-01
- `Badge` component: `variant="success"` already used for posted status elsewhere — consistent reuse
- `useFilters` + `FilterBar`: in place from Phase 4 — available if tab state needs to integrate (but D-06 may not need the full FilterBar; a lightweight tab strip may be cleaner)
- `IdentityAPI.getBestPhotos({ posted: boolean })`: backend already supports posted filtering — tab switching is purely a frontend fetch param change

### Established Patterns
- Section heading pattern: `<h2 className="text-card-title text-text">` + `<p className="text-sm text-text-secondary">` for intros (matches existing DashboardPage subtitle style)
- Page sections use `<section className="space-y-3" aria-labelledby="...">` with `aria-labelledby` for accessibility
- Filter state via `useFilters` hook — if tabs need to be URL-stable or reset-able, that hook could hold the tab key; otherwise local `useState` is fine

### Integration Points
- `IdentityPage.tsx`: section order change (D-02) is a reorder of 3 JSX children + adding section intros
- `BestPhotosGrid.tsx`: pass `overlayBadges={row.instagram_posted ? <Badge variant="success">Posted</Badge> : undefined}` to each `<ImageTile>`
- `DashboardPage.tsx`: swap `<TopPhotosStrip>` for a new tabbed variant + 3 fetches (or lazy fetch on tab switch)
- `TopPhotosStrip.tsx`: extend or replace with a tab-aware version

</code_context>

<specifics>
## Specific Ideas

- User explicitly chose a **tab strip (Unposted | Posted | All)** over FilterBar chips, two-section split, or segmented controls — they want the tab paradigm specifically
- "Unposted" as the default tab — most actionable photos surface first
- User found the two-section split + separate filter redundant — collapsing DASH-02 and DASH-03 into one tab control was the user's preference, not Claude's

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-identity-insights-clarity*
*Context gathered: 2026-04-21*
