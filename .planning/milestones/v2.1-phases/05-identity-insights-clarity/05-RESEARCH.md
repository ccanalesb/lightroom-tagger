# Phase 5: Identity & Insights Clarity — Research

**Date:** 2026-04-21
**Status:** RESEARCH COMPLETE

## Summary

The frontend already maps `IdentityBestPhotoItem.instagram_posted` onto `ImageView` (`fromBestPhotoRow`) and shows a **Posted** chip in `ImageMetadataBadges` under every `ImageTile`; adding `overlayBadges` will surface the same semantic on the thumbnail (watch for duplicate labels). `IdentityPage` currently orders **Best photos → Style fingerprint → Post next**; reordering to **fingerprint → best → post next** is a straightforward child reorder plus section intros (`<p className="text-sm text-text-secondary">` after each section `<h2>`), with intros touched in each panel’s multiple early-return branches where applicable. `TopPhotosStrip` is a thin presentational component; Dashboard wiring lives in `DashboardPage`. **Critical for planning:** `.planning` and user context assume `/api/identity/best-photos?posted=…` and `IdentityAPI.getBestPhotos({ posted })`, but **the checked-in backend route and `rank_best_photos` do not parse or apply a `posted` filter**, and **`IdentityAPI.getBestPhotos` does not send `posted`**. The planner must either scope a small backend addition + client param, or define an alternative that still meets DASH-02/03 (see Risks).

## IDENT-04: BestPhotosGrid Posted Badge

### ImageTile overlayBadges pattern

- **Prop:** `overlayBadges?: ReactNode` on `ImageTileProps` (`ImageTile.tsx`).
- **Rendering:** If truthy, wrapped in `<div className="absolute right-2 top-2 flex flex-col gap-1">` inside the relative thumbnail container (`relative bg-surface`), i.e. **top-right**, column stack with `gap-1`.
- **Note:** `ImageTile` always renders `ImageMetadataBadges` in the body, which **also** shows `<Badge variant="success">Posted</Badge>` when `image.instagram_posted` is true — so overlay + body can **duplicate** “Posted” unless the plan hides one of them or accepts redundancy.

### ImageMetadataBadges existing usage

- **Import:** `import { Badge } from '../ui/Badge'` (re-export from `components/ui/Badge/index.ts`).
- **Posted:** `{image.instagram_posted ? <Badge variant="success">Posted</Badge> : null}` inside a `flex flex-wrap gap-2` row with rating/pick/AI/primary score pill.

### BestPhotosGrid current structure

- Fetches via `IdentityAPI.getBestPhotos({ limit: PAGE_SIZE, offset, sort_by_date: … })` — **no `posted` filter** in the client today.
- Maps `rows` to `<ImageTile … image={fromBestPhotoRow(row)} />`; `IdentityBestPhotoItem.instagram_posted` is available on each `row` and is passed through `fromBestPhotoRow` to `ImageView.instagram_posted`.
- States: `SkeletonGrid` while loading; `text-sm text-error` + `role="alert"` on error; empty uses `meta?.coverage_note ?? IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK` with `role="status"`.

### Implementation path

1. Import `Badge` from `../ui/Badge` (same as `ImageMetadataBadges`).
2. On each `ImageTile`, pass `overlayBadges={row.instagram_posted ? <Badge variant="success">Posted</Badge> : undefined}` (per `05-CONTEXT.md` D-01 / UI-SPEC).
3. **Decision for plan:** whether to suppress the body-row Posted chip for this grid (e.g. new optional prop on `ImageMetadataBadges` or a tile variant) to avoid double “Posted” labels.

## IDENT-05: Identity Page Narrative Flow

### Current section order + heading patterns

- **`IdentityPage.tsx`:** Single page title/subtitle (`IDENTITY_PAGE_TITLE` / `IDENTITY_PAGE_SUBTITLE`), then **`BestPhotosGrid` → `StyleFingerprintPanel` → `PostNextSuggestionsPanel`** (`space-y-8`).
- **Per-panel headings:** Each child renders its own `<section className="space-y-3" aria-labelledby="…">` with `<h2 id="…" className="text-card-title text-text">` (`BestPhotosGrid`, `StyleFingerprintPanel`, `PostNextSuggestionsPanel`).
- **Page-level precedent:** `DashboardPage` uses `<h1>` + `<p className="text-text-secondary">` for the page subtitle (no `text-sm` on that paragraph — Identity page matches). Section intros in UI-SPEC use **`text-sm text-text-secondary`** under `<h2>`.

### Section intro implementation

- Add **one** `<p className="text-sm text-text-secondary">` **immediately after** each section `<h2>`, sourcing copy from `constants/strings.ts` (names in `05-UI-SPEC.md`, e.g. `IDENTITY_INTRO_STYLE_FINGERPRINT`, `IDENTITY_INTRO_BEST_PHOTOS`, `IDENTITY_INTRO_POST_NEXT`).
- **`StyleFingerprintPanel`** has **four** return paths (loading, error, empty, main) each with its own `<h2>` — each path should include the same intro after the heading for consistent narrative.
- **`BestPhotosGrid` / `PostNextSuggestionsPanel`:** single main structure; add intro after `<h2>` before `<Card>`.

### Implementation path

1. `IdentityPage.tsx`: reorder children to `StyleFingerprintPanel` → `BestPhotosGrid` → `PostNextSuggestionsPanel`.
2. Append new string exports in `constants/strings.ts` and wire intros in the three components (not only `IdentityPage`, because headings live inside panels).
3. **IDENT-05 requirement** mentions “differentiated card treatments”; **`05-CONTEXT.md` D-04** explicitly defers extra card styling — align plan with CONTEXT/UI-SPEC (grid vs list already differentiates).

## DASH-02 + DASH-03: TopPhotosStrip Tab Control

### Current TopPhotosStrip structure

- **Props:** `{ items, loading, error, emptyMessage }` — fully controlled; **no fetching**.
- **Loading:** `MSG_LOADING` in `text-sm text-text-secondary`, `role="status"`, `aria-live="polite"`.
- **Error:** `text-sm text-error`, `role="alert"`.
- **Empty:** `text-sm text-text-secondary`, `role="status"`.
- **Success:** Horizontal strip `-mx-1 flex gap-3 overflow-x-auto pb-2 pt-1` of `ImageTile` `variant="strip"` + `ImageDetailModal` on selection.

### DashboardPage integration

- One `useEffect` runs `Promise.allSettled` including `IdentityAPI.getBestPhotos({ limit: 8 })` (no `posted`).
- State: `bestItems`, `bestMeta`, `bestTotal`, `errBest`, `loadingBest`; `bestEmptyMessage` from `bestMeta?.coverage_note ?? IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK` when `bestTotal === 0`.
- Renders `TopPhotosStrip` inside Highlights `<Card>`.

### getBestPhotos API

- **Types:** `IdentityBestPhotoItem` includes `instagram_posted: boolean`.
- **Current client (`IdentityAPI.getBestPhotos`):** params are `limit`, `offset`, `min_perspectives`, `sort_by_date` only — **`posted` is not in the TypeScript signature and is not appended to the query string.**
- **Backend (`apps/visualizer/backend/api/identity.py` `best_photos`):** parses pagination, `min_perspectives`, `sort_by_date` only; **`posted` is not read**; `rank_best_photos` has **no posted filter**.

### Tabs component

- **Location:** `apps/visualizer/frontend/src/components/ui/Tabs/Tabs.tsx`.
- **API:** **Controlled only** — `tabs: { id, label, content }[]`, `activeTab: string`, `onTabChange: (tabId: string) => void`.
- **Styling:** `border-b border-border`; buttons `px-4 py-2.5 text-sm font-semibold`; active `border-b-[3px] border-accent text-accent`; inactive `opacity-60` + hover. **`05-UI-SPEC.md`** suggests aligning to `py-2` (4px scale) for this phase.
- **Layout note:** Tab **content** wrapper uses `mt-6` — may be loose for a dense strip; planner may use tab **buttons** only and render `TopPhotosStrip` below without the default content wrapper, or adjust spacing.

### Implementation path

- **Option A — Extend `TopPhotosStrip`:** Add optional tab UI + internal state **or** keep it dumb and add a parent `TopPhotosTabbedStrip` that owns tab state + fetch per tab.
- **Option B — Replace:** New component (tabs + strip + modal) used from `DashboardPage`; keep `TopPhotosStrip` as the inner renderer for one tab’s content.
- **Recommendation:** Parent in `DashboardPage` (or a small `DashboardTopPhotosCard`) owns **active tab** and **per-tab fetch state** (items/meta/total/loading/error), calls **`getBestPhotos` with the right params** once `posted` exists server-side and in the client. Use **`Tabs`** if the `mt-6` gap is acceptable or fork the nav markup from `Tabs.tsx` without the content wrapper.
- **DASH-03 vs CONTEXT:** `REQUIREMENTS.md` ties DASH-03 to the **shared filter framework**. **`useFilters`** can back tri-state **without** `FilterBar` (same pattern as `InstagramTab` / discussion in `STATE.md`): e.g. one `select` descriptor `postedTab` → map to API params in the fetch effect. That satisfies “shared framework” more cleanly than raw `useState` if compliance is strict.

## Supporting Patterns

### Badge variant="success"

- **File:** `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx`.
- **Props:** `children`, `variant?: 'default' | 'success' | 'warning' | 'error' | 'accent'`, `className?`.
- **Success styling:** `bg-green-50 dark:bg-green-900/20 text-success border-…`; base uses `text-xs font-medium` (UI-SPEC prefers semibold for labels — pre-existing Badge typography).

### String constants pattern

- **File:** `apps/visualizer/frontend/src/constants/strings.ts` — named `export const UPPER_SNAKE = '…'`; Identity block around `IDENTITY_PAGE_*`, `IDENTITY_SECTION_*`, etc.
- **Add:** New `IDENTITY_INTRO_*` strings next to existing Identity exports; optional tab labels e.g. `INSIGHTS_TOP_PHOTOS_TAB_UNPOSTED` if not inlined.

### Loading/empty/error patterns

- **TopPhotosStrip:** Text rows (`MSG_LOADING` / error / empty); no skeleton for the strip.
- **BestPhotosGrid:** `SkeletonGrid` for loading grid; same error/empty text patterns as strip conceptually.
- **Follow:** Keep `role="alert"` for errors, `role="status"` for loading/empty; reuse `IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK` / `meta.coverage_note` per tab when totals are zero.

## Risks & Landmines

1. **`posted` filter gap:** User/context assumes backend + client support for `getBestPhotos({ posted })`. **Repository state:** neither `IdentityAPI.getBestPhotos` nor `identity.py` `best_photos` implements it; `rank_best_photos` has no posted filter. **Planning must resolve** backend + API client vs. alternative (unacceptable: client-only slice of an unfiltered list breaks “top 8 unposted” ranking semantics).
2. **Duplicate Posted UI:** Overlay badge + `ImageMetadataBadges` both show Posted for the same tile unless explicitly deduped.
3. **`Tabs` spacing:** Default `mt-6` between nav and strip may fight Highlights card density; verify visually or use tab nav only.
4. **DASH-02 roadmap vs unified tabs:** ROADMAP success criteria still describe “two labeled sections”; **user decision** in `05-CONTEXT.md` is **one tab strip (Unposted | Posted | All)** — plan should follow CONTEXT/UI-SPEC and treat ROADMAP text as superseded for UI shape.
5. **DASH-03 wording:** Requirement text says “filter framework”; **implementing with `useFilters` + schema without `FilterBar`** is the likely compliance path if “bespoke `useState`” is considered out of scope.
6. **Badge / UI-SPEC typography:** Existing `Badge` uses `font-medium`; UI-SPEC asks `font-semibold` for label row — align in-plan if you touch Badge (scope carefully).

## Planning Recommendations

1. **Wave 1 — Clarify or implement `posted` pipeline:** Confirm backend + `IdentityAPI.getBestPhotos` + types; without this, Dashboard tabs cannot be spec-correct.
2. **Wave 2 — IDENT-04:** `BestPhotosGrid` overlay badges + duplicate-label decision.
3. **Wave 3 — IDENT-05:** Reorder `IdentityPage`, add string constants, add intros across `StyleFingerprintPanel` branches + other panels.
4. **Wave 4 — DASH-02/03:** `DashboardPage` + tabbed top photos (`useFilters` or controlled tabs), per-tab loading/error/empty, reuse strip/modal pattern; update or wrap `TopPhotosStrip`.
5. **Verification:** Frontend tests touching `DashboardPage` / adapters; consider RTL tests for tab switching and badge presence on tiles.

## RESEARCH COMPLETE
