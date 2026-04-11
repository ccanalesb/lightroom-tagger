---
audit_date: 2026-04-11
phase: 04-ai-analysis
baseline: "apps/visualizer/frontend/DESIGN.md + .planning/phases/04-ai-analysis/04-CONTEXT.md"
method: code-only
screenshots: none
---

# Phase 4 (AI Analysis) — 6-Pillar UI Review

Retroactive visual/UX audit of Phase 4 frontend work. No browser session or screenshots; findings are from static review of implemented components and shared atoms.

## Scores

| Pillar | Score | Summary |
|--------|-------|---------|
| 1. Copywriting | 3/4 | Domain-specific labels and helper copy are strong; `alert()` for batch job feedback and terse generate CTAs are weaker. |
| 2. Visuals | 3/4 | Card badge row and modal layout are clear; icon-only modal close lacks accessible name; provider expand uses unlabeled ▲/▼. |
| 3. Color | 2/4 | Semantic tokens used in most Phase 4 surfaces; `GenerateButton`, `DescriptionPanel`/`CompactView`, and score utilities use gray/indigo/green stacks outside the design system. |
| 4. Typography | 3/4 | Mostly `text-sm` / `text-xs` / `text-card-title`; `CompactView` uses `text-[10px]` and Tailwind `gray-*` instead of type scale tokens. |
| 5. Spacing | 3/4 | Predominantly scale classes (`gap-4`, `p-6`, `space-y-6`); some arbitrary widths (`min-w-[8rem]`, `max-h-[90vh]`) are acceptable but less strict than the 8px scale table. |
| 6. Experience design | 2/4 | Loading/error/empty patterns exist for catalog and providers; catalog modal shows conflicting empty + loading copy; batch start uses blocking `alert()`; grid refetch is opacity-only. |

**Overall: 16/24**

## Top 3 priority fixes

1. **`CatalogImageModal.tsx` (approx. 161–176)** — While `loadingDesc` is true, still render `DescriptionPanel` with `description={null}`, which shows `DESC_PANEL_NO_DESCRIPTION` under “Loading description…”. Gate the panel (or pass a loading flag) so users do not see contradictory states.
2. **`GenerateButton.tsx` (20–29)** — Replace `bg-indigo-600`, `border-gray-300`, etc., with the shared `Button` variants or semantic classes (`bg-accent`, `text-text`, `border-border`) so primary describe actions match DESIGN.md’s single blue accent.
3. **`CatalogImageModal.tsx` (101–107)** — Add `aria-label="Close"` (or visible text) on the icon-only dismiss control for keyboard/screen-reader parity.

## Pillar detail (with code evidence)

### 1. Copywriting

**Strengths**

- Catalog analyzed filter mirrors posted filter with explicit options: “Analyzed only”, “Not analyzed” (`CatalogTab.tsx` 241–254).
- Batch minimum rating documents Instagram-only scope in helper text (`DescriptionsTab.tsx` 137–139).
- Connection status uses “Reachable” / “Unreachable” plus `title` for error detail (`ProviderCard.tsx` 48–54).

**Gaps**

- Batch job success/failure uses `alert()` (`DescriptionsTab.tsx` 63–65), which is generic browser chrome and easy to dismiss without reading.
- `GenerateButton` labels are “Generate” / “Regenerate” from constants (`GenerateButton.tsx` 14–18) — acceptable but could be more specific (“Generate description”) where space allows.
- Modal surfaces `String(err)` for API failures (`CatalogImageModal.tsx` 48, 78), which may expose raw exception text to users.

**Generic label search** (`Submit`, `Click Here`, `OK`, `Cancel`) in Phase 4–touched UI files: no matches in the listed files (`JobQueueTab` elsewhere uses “Cancel`, out of this audit’s file list).

### 2. Visuals

**Strengths**

- `CatalogImageCard` keeps badges and score pill in one wrap row with consistent chip sizing (`CatalogImageCard.tsx` 42–54).
- Modal uses a two-column grid with image and metadata separation (`CatalogImageModal.tsx` 110–118).

**Gaps**

- Modal close control is icon-only SVG with no `aria-label` (`CatalogImageModal.tsx` 101–107).
- Provider card expand indicator is `▲` / `▼` text without accessible state (`ProviderCard.tsx` 57); the header `button` could expose `aria-expanded`.
- **Reference:** `ModelList` reorder/remove controls include `aria-label` (`ModelList.tsx` 57–79) — good contrast to modal close.

### 3. Color

**Strengths**

- Catalog tab, cards, modal body, and processing forms lean on `bg-bg`, `border-border`, `text-text`, `text-accent`, `text-error`, etc. (e.g. `CatalogTab.tsx` 216, 232; `CatalogImageCard.tsx` 27).

**Gaps**

- `GenerateButton` hardcodes indigo/gray Tailwind palette (`GenerateButton.tsx` 21–22) — conflicts with DESIGN.md single accent (`#0075de` / token `accent`).
- `DescriptionPanel` empty state uses `text-gray-400` (`DescriptionPanel.tsx` 14).
- `CompactView` uses `text-gray-600`, `text-gray-400`, and score pill via `descriptionScoreColor` → `green-700`/`yellow-700`/`red-700` on `*-50` backgrounds (`CompactView.tsx` 17–24; `scoreColorClasses.ts` 3–5). Semantic success/warning/error tokens exist in DESIGN.md but are not used here.
- Modal overlay uses inline `rgba(0, 0, 0, 0.75)` (`CatalogImageModal.tsx` 93) instead of a token or shared overlay class.
- **Accent density:** `CatalogImageCard` uses `variant="accent"` for rating, Pick, and AI (`CatalogImageCard.tsx` 45–47), which dilutes the “accent = primary interactive” rule from DESIGN.md.

### 4. Typography

**Counts (Phase 4–touched components)**

- **Sizes observed:** `text-card-title` (modal title), `text-base` + `font-semibold` (Providers default models heading), `text-sm`, `text-xs`, and one `text-[10px]` in `CompactView` (not in a Phase 4–edited file but shown inside modal via `DescriptionPanel`).
- **Weights observed:** `font-medium`, `font-semibold`; body copy defaults to normal weight.

**Gaps**

- `text-[10px]` in `CompactView.tsx` 24 sits below DESIGN.md “Tiny” (12px) scale.
- Gray utility classes for body text bypass `text-text-secondary` / `text-text-tertiary`.

### 5. Spacing

**Strengths**

- Catalog tab filter row uses `gap-3`, labels `gap-1.5`, page sections `space-y-6` (`CatalogTab.tsx` 207–224).
- Modal content `p-6`, `gap-6` (`CatalogImageModal.tsx` 110).

**Gaps**

- `CatalogTab` inputs use `min-w-[8rem] w-36` / `w-28` (`CatalogTab.tsx` 283, 332) — functional but arbitrary vs strict 8px multiples.
- Modal `max-h-[90vh]` (`CatalogImageModal.tsx` 97, 110) — common pattern; document or standardize if the design system adds viewport tokens.

### 6. Experience design

**Strengths**

- Catalog: initial load vs refetch (`fetching` opacity, `initialLoad` full message) (`CatalogTab.tsx` 186, 340–374, 374).
- Catalog list: structured error panel with next steps (`CatalogTab.tsx` 344–350).
- Providers tab: loading and error cards (`ProvidersTab.tsx` 121–134).
- `GenerateButton` disables while `generating` (`GenerateButton.tsx` 28–29).

**Gaps**

- **Conflicting AI description states** in catalog modal (see Top fix #1): `loadingDesc` + `DescriptionPanel` with `null` (`CatalogImageModal.tsx` 163–167).
- Batch describe: `alert()` for success/error (`DescriptionsTab.tsx` 63–65) — no in-app status, no link to Job Queue.
- Refetching catalog does not show a spinner; only `opacity-50 pointer-events-none` (`CatalogTab.tsx` 374) — subtle on fast networks, invisible concern on slow ones.
- `ProvidersAPI.getDefaults()` failures in `DescriptionsTab` are only `console.error` (no user-visible empty state for description provider defaults in advanced section).

## Files audited

| File | Notes |
|------|--------|
| `apps/visualizer/frontend/src/services/api.ts` | Types and query params only; no visual surface. |
| `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` | Analyzed filter, states, grid. |
| `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx` | AI badge, score pill. |
| `apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx` | Description panel, generate, AI badge. |
| `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` | Batch scope, min rating, alerts. |
| `apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx` | Health polling, description defaults. |
| `apps/visualizer/frontend/src/components/providers/ProviderCard.tsx` | Connection badges. |
| `apps/visualizer/frontend/src/components/DescriptionPanel/DescriptionPanel.tsx` | Empty state styling (shared). |
| `apps/visualizer/frontend/src/components/DescriptionPanel/CompactView.tsx` | Compact typography/colors (shared). |
| `apps/visualizer/frontend/src/components/ui/description-atoms/GenerateButton.tsx` | CTA styling. |

**Related (referenced):** `apps/visualizer/frontend/src/utils/scoreColorClasses.ts`, `apps/visualizer/frontend/src/components/providers/ModelList.tsx`.

## Recommendation counts

- **Priority fixes:** 3 (listed above).
- **Minor recommendations:** 8 — raw error strings in modal; `alert()` batch UX; refetch loading affordance; accent overuse on catalog badges; overlay rgba token; provider `aria-expanded`; optional CTA copy specificity; defaults fetch error surfacing.

---

*Audit completed: 2026-04-11. No screenshots captured; no git commits from this audit.*
