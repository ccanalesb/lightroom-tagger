---
phase: 6
slug: images-page-visual-consistency
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-22
---

# Phase 6 — UI Design Contract

> Visual and interaction contract for **Images page visual consistency** (UI-01, UI-02, UI-03). Pre-populated from `06-CONTEXT.md` (D-01..D-12), `06-RESEARCH.md`, and the existing visualizer Tailwind + `ImageTile` design language. **Design system:** Tailwind + CSS variables (`tailwind.config.js` + `index.css`); not shadcn; composition via `cn()` where used.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | **none** (no shadcn; confirmed non-shadcn) |
| Preset | not applicable |
| Component library | **none** (custom `Badge` + domain primitives) |
| Icon library | **none** for this phase (text/Unicode chips only, e.g. `★` in existing badges) |
| Font | **Inter** stack (`font-sans` in `tailwind.config.js`) |

**Public badge surface (D-03):** After consolidation, all badge exports resolve through **one** barrel: `src/components/ui/badges/index.ts` (path confirmed below).

---

## Spacing Scale

Declared values (multiples of 4; aligns with `ImageTile` + chip rows):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Gap between stacked overlay badges (`gap-1`) |
| sm | 8px | `ImageTile` body `space-y-1` stack rhythm |
| md | 16px | Section-level spacing; tile horizontal padding often **12px** (`p-3`) on grid/compact |
| (flex) | 8px | **Chip row** inter-badge gap: `gap-2` on `ImageMetadataBadges` |
| lg | 24px | Section padding around image grids (parent layouts) |
| xl | 32px | Layout gaps between major page regions |
| 2xl | 48px | — |
| 3xl | 64px | — |

**Phase-specific usage:**

- **Chip row (`ImageMetadataBadges`, `PerspectiveBadge` row):** `flex items-center gap-2 flex-wrap` (8px inter-chip gap) — D-05, D-07, RESEARCH.
- **Match tile metadata (D-08..D-10):** New metadata line sits **below** the date line and **below** `ImageMetadataBadges`, with **8px** vertical separation from the chip row (`space-y-1` in body or equivalent).
- **Overlay badges:** Thumbnail `absolute right-2 top-2` (8px from edges); vertical stack `gap-1` (4px).

Exceptions: **none** beyond existing `ImageTile` variant padding (`p-2` strip vs `p-3` grid/compact/list).

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body (tile title) | **14px** (`text-sm`) | 500 (`font-medium`) | normal |
| Label (subtitle, date, metadata line) | **12px** (`text-xs` / `text-[10px]` strip) | 400 | normal |
| Badge / chip | **12px** (`text-xs` on `<Badge>`) | 600 (`font-semibold`) | single-line chips |
| Display | *n/a this phase* | — | — |

**Image type micro-label (D-02):** `ImageTypeBadge` **retains** `text-[10px]` for CAT/IG — intentional compact size.

**PerspectiveBadge label format (D-11):** Same badge label typography as base `Badge` (`text-xs font-semibold`). **Content pattern:** perspective display name (from API) + **non-breaking** score, e.g. `Street 8.2` (space between name and score; one decimal for score; exact formatting in `strings.ts` or a small formatter in the component.

---

## Color

| Role | Value (light, `:root`) | Usage |
|------|------------------------|--------|
| Dominant (60%) | `#ffffff` (`--color-background` / `bg`) | App background, page canvas |
| Secondary (30%) | `#f6f5f4` (`--color-surface`) + card shell | Side panels, table backgrounds, **tile inner thumb** `bg-surface` |
| Cards / tiles | `#ffffff` + border (`--color-border`) | **`ImageTile` shell:** `bg-bg border-border`** — D-09 parity with Catalog |
| Accent (10%) | `#0075de` (`--color-accent`) | **Primary** links, focus ring (`ring-accent`), filter controls, `Badge variant="accent"` for rating/pick/AI chips |
| Destructive | `#e03e3e` (`--color-error`) | Destructive / error only |

**Dark mode:** All of the above have **paired** values under `.dark` in `index.css` — **no** hardcoded one-off grays for new components; use `bg` / `surface` / `text-*` / `border` tokens or the same `Badge` variant pattern as existing components.

**Accent reserved for:** Interactive affordances (focus rings, links, primary actions), and **non-status** informational chips that already use `variant="accent"` in catalog (rating, Pick, AI). **Do not** reintroduce a second ad-hoc blue for badges — use `accent` / `accent-light` or `Badge` variants.

**PerspectiveBadge — perspective → color (D-11; accessible contrast on light + dark):**

Map by **`perspective_slug`** (case-normalized; unknown slugs use **default** `Badge` styling).

| `perspective_slug` (canonical) | Tailwind class bundle (on `<Badge className=…>` or wrapper) | Rationale |
|--------------------------------|---------------------------------------------------------------|-----------|
| `street` | `!bg-violet-50 dark:!bg-violet-900/20 !text-violet-900 dark:!text-violet-100 !border-violet-200 dark:!border-violet-800` | Distinct hue from other three; readable on both themes |
| `documentary` | `!bg-amber-50 dark:!bg-amber-900/20 !text-amber-900 dark:!text-amber-100 !border-amber-200 dark:!border-amber-800` | Warm, reportage association |
| `publisher` | `!bg-rose-50 dark:!bg-rose-900/20 !text-rose-900 dark:!text-rose-100 !border-rose-200 dark:!border-rose-800` | Editorial / presentation association |
| `color_theory` (and alias `color-theory` if present) | `!bg-emerald-50 dark:!bg-emerald-900/20 !text-emerald-900 dark:!text-emerald-100 !border-emerald-200 dark:!border-emerald-800` | Distinct from Street violet; “color” cue |
| **default / other** | Base `variant="default"` (`bg-surface text-text-secondary border-border`) | Extensibility (RESEARCH: API may return additional slugs) |

**Note:** `!` may be used **only** where needed to override `variantClasses` if `PerspectiveBadge` is implemented as `<Badge variant="default" className={map[slug]} />`. Prefer a **single implementation** (wrapper + token map) so contrast stays consistent.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA (page-level) | **None new** — this phase is visual consistency. Existing **tab** and **open image** flows unchanged; primary actions remain on parent pages/modals. |
| Empty state heading | Reuse **existing** `MATCHES_TAB_EMPTY` / Instagram empty patterns per tab — no new marketing copy. |
| Empty state body | Same as today; next step = run matching / change filters (tab-specific). |
| Error state | **Pattern:** one line problem + one line recovery (e.g. retry, check connection) — match existing `DashboardPage` / tab fetch error lists from Phase 5. |
| Destructive confirmation | **N/A** this phase (no new destructive actions). |

**New strings (must live in `constants/strings.ts`):** Match metadata line (D-08/D-10) if not already present — e.g. **“N candidates”** pluralization, **validated** vs **unvalidated** labels only if the UI needs full words beyond `Badge` text. **PerspectiveBadge** does **not** need long prose — short labels come from API `display_name`.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | *none* | not applicable |
| Third-party | *none* | not applicable |

---

## Phase 6 — UI-01: Badge consolidation

| ID | Contract |
|----|-----------|
| D-01 | **Single folder:** `apps/visualizer/frontend/src/components/ui/badges/` is the **canonical** home for **base** `Badge.tsx` and **all** specialized badge files (`VisionBadge`, `StatusBadge`, `ImageTypeBadge`, `ScorePill`, new `PerspectiveBadge`). **Rationale (RESEARCH):** Plural `badges` already exists; move `ui/Badge/` **into** this tree and re-export; minimizes churn vs renaming to `ui/badge/`. |
| D-02 | **Visual tokens:** All specialized badges that wrap `<Badge>` use **shared** border + rounding policy (`rounded-full` for chip-style; `ImageTypeBadge` may keep **smaller** padding + `text-[10px]` per D-02). |
| D-03 | **Imports:** Application code imports **only** from `@/components/ui/badges` (or relative `../ui/badges`) — **one barrel** re-exports `Badge`, `ScorePill`, `PrimaryScorePill` consumers updated as needed, etc. |
| D-04 | **Documentation:** **JSDoc** on each exported badge component: **when** to use, **where** (tile vs job list vs description card). |
| **ScorePill (discretion)** | **Stays a separate primitive** co-located under `ui/badges/`. It **does not** have to share the same outer wrapper as `Badge` internally if threshold coloring stays clearer via existing `descriptionScoreColor` — but **file location** and **export** are unified via the barrel. **PrimaryScorePill** remains the bridge from `ImageView` → `ScorePill` for aggregate / catalog / description scores. |

---

## Phase 6 — UI-02: Inline chip row on Images tabs

| ID | Contract |
|----|-----------|
| D-05 | **“Inline-in-description”** = **`ImageMetadataBadges` row** directly under the title/subtitle/date block inside **`ImageTile` body** — same order as Catalog. |
| D-06 | **Tabs in scope:** **Instagram**, **Catalog**, **Matches** — each tile that represents a browsable image uses the **same** `ImageTile` + `ImageMetadataBadges` pipeline unless a plan explicitly documents an adapter/API exception. |
| D-07 | **Chip set:** Posted ✓, rating ★, Pick, **AI** — plus **`PrimaryScorePill`** when `primaryScoreSource` ≠ `'none'`. **Hide-empty rule:** only render chips for which **data exists** (current behavior). Instagram list rows may leave chips sparse until adapters/APIs populate `ai_analyzed` / `instagram_posted` — **no** duplicate **prose** badges in the body if overlay already shows Matched/Described (follow Best Photos **overlay vs row** de-duplication patterns from Phase 5). |

**Layout:** `className` on the chip container remains **`flex items-center gap-2 flex-wrap`**.

---

## Phase 6 — UI-03: Match group tile card

| ID | Contract |
|----|-----------|
| D-08 | **Layout:** **One** Instagram thumbnail + **metadata row below** the standard title/date/chip block: shows **catalog filename of the validated match** when validated; **unvalidated** uses **“N candidates”** copy (and **not** a competing filename in that row). |
| D-09 | **Shell:** **Identical** to Catalog tiles: `rounded-card border border-border bg-bg shadow-card transition-all hover:border-border-strong hover:shadow-deep` — already from shared **`ImageTile`**; **no** extra outer wrapper that changes shadow/border. |
| D-10 | **Unvalidated:** Metadata row = **candidate count** only (plus validation `Badge` where applicable per plan). **Validated:** **Single** catalog filename for the validated candidate (planner picks exact field from `Match` / `candidates[]`). |

**Implementation note:** Prefer **`ImageTile` `footer`** for the D-08/D-10 line so the chip row stays **only** `ImageMetadataBadges` (D-07) — **footer** is the dedicated slot below the chip row (RESEARCH, aligns with D-12 placement pattern).

**Overlay (existing):** Top-right `overlayBadges` may remain for quick scan **or** be reduced to avoid **duplicate** information with the new row — final composition is **planner/implementation** choice as long as D-08/D-10 text remains **on the row** and shell matches D-09.

---

## Phase 6 — D-11 / D-12: PerspectiveBadge (Identity + Dashboard)

| ID | Contract |
|----|-----------|
| D-11 | **Component:** `PerspectiveBadge` wraps **`<Badge>`** (or the consolidated export). Shows **dominant** perspective: **top 1** by `score` over `identity_per_perspective` (stable tie-break: `display_name` or `perspective_slug` sort). **Format:** short label + one decimal, e.g. `Street 8.2` (exact format centralized). **Colors:** per table in **Color** section above. |
| D-12 | **Surfaces:** **BestPhotosGrid** and **TopPhotosStrip** only (per CONTEXT deferred list). **Placement (discretion resolved):** **Separate row below** the `ImageMetadataBadges` row — implement via **`ImageTile` `footer`** containing `PerspectiveBadge` (with `mt-0` if footer is directly after chip row; body `space-y-1` provides vertical rhythm). **Rationale:** Keeps the primary chip row scannable; avoids wrapping + density issues from appending a second “hero” chip inline. **Optional:** `mt-1` on footer if visual separation needs a nudge; stay within 4px grid. |

**Data:** `ImageView.identity_per_perspective` / `fromBestPhotoRow` — no UI for full four-perspective list on tiles in Phase 6 (deferred).

---

## Non-goals (this phase)

- URL-synced filters, new shadcn components, CVA adoption, full Instagram API parity (RESEARCH risk areas) — **tracked** in plans, not part of the **visual** contract.
- PerspectiveBadge on surfaces other than BestPhotosGrid + TopPhotosStrip (**deferred** in CONTEXT).

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

## Traceability

| Source | Decisions used |
|--------|----------------|
| `06-CONTEXT.md` | D-01..D-12 (structure, patterns, scope) |
| `06-RESEARCH.md` | Stack, file layout recommendation, `ImageTile` / adapter notes |
| `REQUIREMENTS.md` | UI-01, UI-02, UI-03 |
| `tailwind.config.js` + `index.css` | Tokens, font, semantic colors |
| `Badge.tsx`, `ImageTile.tsx`, `ImageMetadataBadges.tsx` | Baseline class contracts |
