---
phase: 12
slug: operational-baseline-embed-reliability
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-05
---

# Phase 12 — UI Design Contract

> Visual and interaction contract for **incremental** frontend work in Phase 12. Backend-heavy items (OPS-02, OPS-04, OPS-05) have **no UI contract** here. This file locks OPS-01 and OPS-03 only.

---

## Phase-scoped UI deliverables

### OPS-01 — “Visual similarity unavailable” / `no_clip_embedding` discoverability

**Intent (from `12-CONTEXT.md` D-01, D-02):** A navigation path to Processing → Catalog cache is enough (no new inline “Run embed” button). Any surface that already shows this failure must show **the same guidance + link affordances** as `SearchPage.tsx` (canonical).

**Canonical pattern — copy**

- Reuse **`SEARCH_PIN_HELP_EMBED`** and **`SEARCH_PIN_LINK_CACHE`** from `apps/visualizer/frontend/src/constants/strings.ts` for the instruction paragraph and the primary link label. Do not introduce divergent wording for the same situation unless product explicitly changes the strings file for all call sites.

**Canonical pattern — navigation**

- Primary link: **React Router `<Link>`** to **`PROCESSING_CATALOG_CACHE_ROUTE`** (same import/target as `SearchPage.tsx`).
- **Parity with SearchPage:** also render the secondary link to **`PROCESSING_JOB_QUEUE_ROUTE`** with label **`PROCESSING_OPEN_JOB_QUEUE`** when that pattern is already used on Search for `no_clip_embedding`, so users who land from other pages get the same escape hatches.
- Link styling: **`className="font-medium text-accent underline"`** (match SearchPage blocks ~423–444 and ~462–483).

**Canonical pattern — placement and semantics**

- The help block sits **under or beside** the existing error/warning copy for that surface (whatever layout that surface already uses); do not add a new page section or modal.
- If the parent surface uses a live region for warnings, keep **`role="status"`** and **`aria-live="polite"`** consistent with how that surface treats other non-fatal operational messages (SearchPage uses this on the pin warning container).

**Out of scope**

- **`SearchPage.tsx`** — already correct; no redesign.
- New components or routes.

**Implementation note for callers:** Sweep surfaces that surface `no_clip_embedding` or user-visible **“visual similarity unavailable”** (API/message parity with backend `get_catalog_image_similar` 404 copy) **other than** Search; align each to the pattern above.

---

### OPS-03 — “Why skipped” in `JobDetailModal`

**Intent (from `12-CONTEXT.md` D-07 — D-09, REQUIREMENTS OPS-03):** After embed jobs, users see a **post-job diagnosis** as counts by skip reason.

**Surface**

- **`JobDetailModal.tsx` only**, inside the existing **embed diagnostics** block (warning-styled card, title **`JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE`**). No new modal sections or pages.

**Data**

- Read skip counts from the job’s **`result`** object (same transport as today’s embed diagnostics). Backend phase work defines the exact field name (e.g. extension of `skip_reason_counts`); the UI must bind to whatever stable object the executor documents in the phase plan, as long as the three categories below are representable.

**Labels (exact user-visible strings — match REQUIREMENTS / `12-CONTEXT.md` specifics)**

| Category   | Label shown in UI |
|------------|-------------------|
| Missing file on disk / unreachable file | **Missing file** |
| Empty path | **Empty path** |
| No catalog DB row for key | **No DB row** |

Centralize these in **`constants/strings.ts`** (new exports) and reference them from `JobDetailModal` so copy stays single-sourced.

**Visibility rule**

- **Omit any category whose count is ≤ 0** (do not render a row, do not show “0”). If **all** categories are zero or the payload has no skip breakdown, **hide the entire** “why skipped” summary block **or** show nothing beyond existing embed diagnostics — never an empty grid.

**Layout / interaction**

- Reuse the **existing** diagnostics grid: **one row per visible category**, `text-text-secondary` label left, **count right** in **`font-mono text-xs`** (same as current `embedReasonCounts` rendering ~466–477).
- No expand/collapse, no charts, no new typography scale — only additional or relabeled rows inside the current card.

**Relationship to existing per-reason diagnostics**

- If the phase narrows the contract to **these three buckets** only, **remove or stop rendering** legacy rows that duplicate or contradict them (e.g. old label strings that don’t match the table above). Encode failures or other diagnostics, if still required by backend, are **out of scope for this OPS-03 table** unless a follow-on decision explicitly adds them back.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | **none** (no `components.json` / shadcn registry in visualizer frontend) |
| Preset | not applicable |
| Component library | Custom `apps/visualizer/frontend/src/components/ui/*` (Button, Card, Badge, etc.) |
| Icon library | Unchanged this phase |
| Font | **Inter** stack per `tailwind.config.js` |

*Phase 12 does not introduce tokens, themes, or layout primitives.*

---

## Spacing Scale

**Inherited** from project Tailwind usage and existing components. **No phase-specific spacing exceptions.**

Declared values (project standard, multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps, inline padding |
| sm | 8px | Compact element spacing |
| md | 16px | Default element spacing |
| lg | 24px | Section padding |
| xl | 32px | Layout gaps |
| 2xl | 48px | Major section breaks |
| 3xl | 64px | Page-level spacing |

Exceptions: **none (this phase)**

---

## Typography

**Inherited.** New copy uses existing utility classes from the canonical patterns (`text-xs`, `text-sm`, `font-medium`, `text-text`, `text-text-secondary`, `font-mono` for counts).

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 16px (`text-base` default) | 400 | 1.5 (browser / inherited) |
| Label | 14px (`text-sm`) | 500–600 | inherited |
| Heading | 14px (`text-sm` in modal cards) | 500 (`font-medium`) | inherited |
| Display | n/a this phase | — | — |

---

## Color

**Inherited** from CSS variables wired in `tailwind.config.js` (`text-accent`, `text-amber-600` / `dark:text-amber-400` for warnings where already used, `border-warning/40` on embed diagnostics card, etc.). **No new hex values for Phase 12.**

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `var(--color-background)` (`bg-bg`) | Page background |
| Secondary (30%) | `var(--color-surface)` | Cards, panels |
| Accent (10%) | `var(--color-accent)` | Underlined navigation links (OPS-01), accent callouts |
| Destructive | `var(--color-error)` | Unchanged; not used by OPS-01/OPS-03 additions |

Accent reserved for this phase: **primary navigation links** in the embed-help pattern and existing accent callouts (no change to global policy).

---

## Copywriting Contract

Phase-specific strings only; all other CTAs/empty/error copy **unchanged**.

| Element | Copy / rule |
|---------|-------------|
| OPS-01 guidance paragraph | **`SEARCH_PIN_HELP_EMBED`** — *Run "Embed catalog images only" (or Build catalog cache) under Processing → Catalog cache, then try again.* |
| OPS-01 primary link | Label **`SEARCH_PIN_LINK_CACHE`** → *Open Catalog cache* |
| OPS-01 secondary link | Label **`PROCESSING_OPEN_JOB_QUEUE`** → route `PROCESSING_JOB_QUEUE_ROUTE` (parity with SearchPage) |
| OPS-03 row: missing file | **Missing file** |
| OPS-03 row: empty path | **Empty path** |
| OPS-03 row: no DB row | **No DB row** |
| Primary CTA (phase) | **N/A** — no new CTA |
| Empty state (phase) | **N/A** |
| Error state (phase) | Existing per-surface messages stay; **append** OPS-01 help+links where the similarity-unavailable / `no_clip_embedding` condition already surfaces |
| Destructive confirmation (phase) | **N/A** |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable |
| Third-party | none | not applicable |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
