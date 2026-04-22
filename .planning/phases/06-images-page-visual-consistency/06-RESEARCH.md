## RESEARCH COMPLETE

### Phase Summary

**Phase 6 (Images page visual consistency)** unifies how badges, metadata chips, and match tiles look and behave: one badge “surface area” and import story (**UI-01**), a single **inline chip row** (Posted / rating / Pick / AI / primary score) on Instagram, Catalog, and Matches tiles where data allows (**UI-02**), and **match group tiles** that read like catalog cards and expose a **dedicated metadata line** (filename or candidate count + validation) (**UI-03**). The same release extends **Identity** and **Dashboard** tiles with a **top-1 perspective** badge (dominant `PerspectiveBadge`) so identity surfaces feel consistent with the new badge system (**D-11 / D-12** in `06-CONTEXT.md`).

This matters because the Images page is a high-traffic triage surface; today Instagram vs Catalog vs Matches use overlapping primitives (`ui/Badge` vs hand-rolled chips in `ui/badges`) and Instagram tiles still rely on **thumbnail overlays** for “Matched / Described” without the same **chip row** scannability as Catalog. Aligning to `ImageMetadataBadges` + a consolidated badge folder reduces visual drift and future import churn.

**Requirements:** `REQUIREMENTS.md` **UI-01**, **UI-02**, **UI-03**; implementation decisions **D-01–D-12** in `06-CONTEXT.md`. **UI-02/UI-03** should follow a stable **UI-01** API (`REQUIREMENTS.md` dependency note).

---

### Current State Analysis

#### `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx`

- **Role:** Base `<Badge>` primitive: `inline-flex`, `px-2.5 py-0.5`, `rounded-full`, `text-xs font-semibold`, `border`, variants `default | success | warning | error | accent` via `variantClasses` (semantic + green/orange/red/blue Tailwind, dark-mode aware for several variants).
- **API:** `{ children, variant?, className? }`.
- **Barrel:** `ui/Badge/index.ts` re-exports `Badge`.

#### `apps/visualizer/frontend/src/components/ui/badges/VisionBadge.tsx`

- **Role:** Renders match **vision result** (SAME / DIFFERENT / UNCERTAIN) using `visionBadgeClasses` from `utils/visionBadge` — **not** `<Badge>`; `px-2 py-1` `rounded` (not `rounded-full`).
- **API:** `{ result: string | undefined }`.
- **Usage:** **No production consumers**; only `components/ui/__tests__/Badges.test.tsx` (dead weight for the feature surface, but part of the “badge story” to consolidate).
- **Note:** `MatchScoreBadges.tsx` inlines a `<span>` with `visionBadgeClasses` instead of using `VisionBadge` — duplicate pattern.

#### `apps/visualizer/frontend/src/components/ui/badges/StatusBadge.tsx`

- **Role:** Human-readable **job status** via `STATUS_LABELS` + `statusBadgeClasses` (`utils/jobStatus`) — **not** `<Badge>`; `px-2 py-1` `rounded`.
- **API:** `{ status, withBorder? }`.
- **Consumer:** `JobCard.tsx` (Processing).

#### `apps/visualizer/frontend/src/components/ui/badges/ImageTypeBadge.tsx`

- **Role:** Compact **CAT / IG** label; **not** `<Badge>`; `text-[10px]`, `px-1.5 py-0.5`, `rounded`, hardcoded `bg-blue-100` / `bg-pink-100` (no dark tokens).
- **API:** `{ type: 'catalog' | 'instagram' }`.
- **Consumers:** `DescriptionCard`, `DescriptionDetailModal`.

#### `apps/visualizer/frontend/src/components/ui/badges/ScorePill.tsx`

- **Role:** Score display with **threshold colors** via `descriptionScoreColor` (`utils/scoreColorClasses`) — **not** `<Badge>`; `rounded-full` like base Badge but different padding/label layout.
- **API:** `{ score, label?, className? }` — `PrimaryScorePill` is the main consumer.
- **Tests:** `ui/badges/__tests__/ScorePill.test.tsx`.

#### `apps/visualizer/frontend/src/components/image-view/ImageMetadataBadges.tsx`

- **Role:** **Chip row** for tiles/modals: `flex items-center gap-2 flex-wrap`. Uses **`<Badge variant="success|accent">`** for Posted (when `image.instagram_posted`), rating ★, Pick, AI; optional `PrimaryScorePill` (unless `hidePrimaryScore` or `primaryScoreSource === 'none'`).
- **API:** `image: ImageView`, `primaryScoreSource`, `hidePrimaryScore?`, `hidePostedBadge?`, `className?`.
- **Pattern:** Canonical **Catalog / Best Photos** scannable row (per `06-CONTEXT`).

#### `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx`

- **Role:** Shared **card shell** + thumbnail + body. Root classes (shell): `rounded-card border border-border bg-bg shadow-card transition-all hover:border-border-strong hover:shadow-deep` (matches `06-CONTEXT` / ROADMAP “CatalogImageCard” affordance).
- **API:** `image`, `variant`, `primaryScoreSource`, `onClick`, `subtitle?`, `overlayBadges?`, `footer?`, `hidePostedMetadataBadge?`, `className?`.
- **Structure:** Thumbnail; optional **top-right** `overlayBadges` in `absolute right-2 top-2 flex flex-col gap-1`; body = title, optional subtitle, date line, then **`ImageMetadataBadges`**, then optional **`footer`**.

#### `apps/visualizer/frontend/src/components/image-view/imageTileVariants.ts`

- **Role:** `imageTileVariantClasses` for `grid | strip | list | compact` (spacing, thumb aspect, text sizes). Used by all `ImageTile` call sites.

#### `apps/visualizer/frontend/src/components/images/MatchGroupTile.tsx`

- **Role:** Renders one **Instagram** side of a match group via `fromMatchSide(..., 'instagram')` + `ImageTile` `variant="grid"`, `primaryScoreSource="none"` (no `PrimaryScorePill`). **Overlay:** “Validated” (`success`) or “N candidate(s)” (`accent`) via `<Badge>`.
- **Gaps vs D-08–D-10:** No **second metadata row** (catalog filename or “N candidates” **below** the standard tile content); `ImageTile` **`footer` is unused** here (only used in `ImageTile.test.tsx` today). No distinction yet between overlay copy and a **dedicated** metadata line as in decisions.

#### `apps/visualizer/frontend/src/components/images/InstagramTab.tsx`

- **Role:** `ImageTile` per `fromInstagramRow(image)`, `primaryScoreSource="none"`, `subtitle` from folder fields, **overlay** “Matched” / “Described” from `renderInstagramOverlayBadges` (`<Badge>`). **No** `hidePostedMetadataBadge` (overlay does not include Posted in the same way as Best Photos).
- **Chip row:** `ImageMetadataBadges` runs inside `ImageTile` but **data often missing** (see *Chip-row Pattern* and *API data gaps*).
- **Filters:** Phase 4 `FilterBar` + `useFilters`.

#### `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`

- **Role:** Reference **grid** of `ImageTile` + `fromCatalogListRow`, `primaryScoreSource="catalog"` (full chip row + perspective/description-driven `PrimaryScorePill` when data exists). **No** overlay badges. Card shell = **inherited** from `ImageTile` (no extra wrapper).

#### `apps/visualizer/frontend/src/pages/ImagesPage.tsx`

- **Role:** Tabs: Instagram, Catalog, Matches — no layout changes required for research; phase work lands in tab components and shared image-view primitives.

#### `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx`

- **Role:** `ImageTile` `variant="compact"`, `primaryScoreSource="identity"`, **overlay** `<Badge variant="success">Posted</Badge>` when `row.instagram_posted`, `hidePostedMetadataBadge={true}` to avoid **duplicate** “Posted” in the chip row.
- **Data:** `IdentityAPI.getBestPhotos` → `IdentityBestPhotoItem` including `per_perspective: IdentityPerPerspectiveScore[]` (see `services/api.ts`). `fromBestPhotoRow` maps into `ImageView.identity_per_perspective` (among other identity fields).

#### `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx`

- **Role:** Horizontal strip: `ImageTile` `variant="strip"`, `primaryScoreSource="identity"`, **no** overlay, **no** `hidePostedMetadataBadge` (Posted appears in **metadata row** when `instagram_posted` is true on the `ImageView`).
- **Data:** Same `fromBestPhotoRow` / `IdentityBestPhotoItem` shape as Best Photos; perspective array available on each row for **PerspectiveBadge** (top-1 by score).

#### `apps/visualizer/frontend/src/constants/strings.ts`

- **Role:** All user-visible copy should stay centralized; new strings for match metadata / perspective labels should land here (per project + `06-CONTEXT` code_context).

#### `apps/visualizer/frontend/src/services/api.ts` (types relevant to planning)

- **`ImageView`:** Superset; identity fields `identity_aggregate_score`, `identity_perspectives_covered`, `identity_eligible`, **`identity_per_perspective?: IdentityPerPerspectiveScore[]`**; catalog/description scoring fields; optional `instagram_posted` / `ai_analyzed` / `rating` / `pick`, etc.
- **`IdentityPerPerspectiveScore`:** `perspective_slug`, `display_name`, `score`, plus audit fields.
- **`IdentityBestPhotoItem`:** Includes `per_perspective` (maps to `ImageView` via `fromBestPhotoRow`).
- **`MatchGroup` / `Match`:** `has_validated`, `candidate_count`, `candidates[]` with optional embedded `catalog_image` / `instagram_image`; **`validated_at`** on `Match` for finding the validated row.
- **`InstagramImage` (list):** **No** `rating`, `pick`, or `instagram_posted` in the TS interface; list payload from backend `_enrich_instagram_media` includes `description`, `matched_catalog_key`, etc., but **not** the same `ai_analyzed` / `instagram_posted` flags as catalog list rows (see *Risk Areas*).

#### `apps/visualizer/frontend/src/components/image-view/adapters.ts`

- **`fromInstagramRow`:** Maps `description` → `description_summary` but does **not** set `ai_analyzed` (so **`ImageMetadataBadges` “AI” chip will not show** for Instagram list even when `description` is non-empty). Does **not** set `instagram_posted`.
- **`fromMatchSide`:** Instagram side; typically no identity scores (per adapter comments).
- **`fromBestPhotoRow`:** Full identity + `identity_per_perspective` — **sufficient** for top-1 perspective badge on tiles.

---

### Badge Consolidation (UI-01)

#### Folder structure today

| Location | Files |
|----------|--------|
| `components/ui/Badge/` | `Badge.tsx`, `index.ts` (exports `Badge` only) |
| `components/ui/badges/` | `ImageTypeBadge.tsx`, `StatusBadge.tsx`, `VisionBadge.tsx`, `ScorePill.tsx`, `index.ts`, `__tests__/ScorePill.test.tsx` |

#### Which components wrap `Badge` vs standalone

| Component | Wraps `<Badge>`? | Notes |
|-----------|------------------|--------|
| `Badge` | N/A (base) | Single source of variant tokens. |
| `ImageMetadataBadges` | Uses `Badge` directly | Domain-specific row. |
| `ScorePill` | **No** | Uses `descriptionScoreColor` + `rounded-full` span. |
| `VisionBadge` | **No** | Uses `visionBadgeClasses` + `rounded` (not `rounded-full`). |
| `StatusBadge` | **No** | Uses `statusBadgeClasses` + `rounded`. |
| `ImageTypeBadge` | **No** | Smallest type; non-semantic blue/pink. |

**Conclusion:** D-01/D-04 require migrating specialized badges to **use `<Badge>`** (or a thin styled wrapper) + shared spacing/border/rounding policy; **D-02** allows **keeping** `ImageTypeBadge` at `text-[10px]` (explicit in user decisions).

#### Recommended consolidated location and reasoning

- **Practical default:** keep **`ui/badges/`** (already plural, already holds `ScorePill` and specialized chips) and **move `Badge.tsx` (base) + `index.ts` barrel into that folder** so **one** `index.ts` exports `{ Badge, ImageTypeBadge, … }`. Alternatively **`ui/badges/primitives/Badge.tsx`** if you want subfolders; avoid two top-level `Badge` and `badges` folders long-term.
- **Reasoning:** `06-CONTEXT` D-03 asks for a **single public path**; `FilterBar` / `ImageMetadataBadges` already think of “badges” as a family. Renaming to `ui/badge/` (singular) is possible but would churn more import paths; **picking one folder and a barrel** matters more than the exact name.

#### Files that import `ui/Badge` or `ui/badges` (import updates after consolidation)

**`../ui/Badge` or `../../ui/Badge` or `ui/Badge/Badge` (17 call sites in TS/TSX):**

`BestPhotosGrid`, `ImageMetadataBadges`, `MatchGroupTile`, `InstagramTab`, `CatalogImageDetailSections`, `JobDetailModal`, `FilterChip/FilterChip` (**direct** `ui/Badge/Badge`), `JobQueueTab`, `InsightsKpiRow`, `ImageScoresPanel`, `PerspectivesTab`, `ProviderCard`, `JobCard` (also `../ui/badges` for `StatusBadge`), `CatalogCacheTab`, `ImageTile.test.tsx`.

**`../ui/badges` (barrel) or `../ui/badges/ScorePill`:**

- Barrel: `DescriptionDetailModal`, `DescriptionCard`, `JobCard` (`StatusBadge`), `Badges.test.tsx` (relative `../badges` under `ui/__tests__`).
- Direct `ScorePill`: `PrimaryScorePill.tsx`.

A **single barrel** at `ui/badges/index.ts` (or `ui/badge/index.ts`) should re-export **both** `Badge` and all specialized components so `PrimaryScorePill` and `JobCard` can share one path.

#### Color / Tailwind token usage (snapshot)

- **Base `Badge`:** `bg-surface`, `text-success` / `text-warning` / `text-error` / `text-accent`, `border-border`, green/orange/red/blue backgrounds per variant.
- **ImageTypeBadge:** `bg-blue-100 text-blue-700` / `bg-pink-100 text-pink-700` (not semantic `bg-bg`-style).
- **Vision (utils):** `bg-green-100` / `red` / `yellow` (match result).
- **Status (`jobStatus.ts`):** status-specific backgrounds/borders.
- **ScorePill / `descriptionScoreColor`:** green/yellow/red by numeric threshold.
- **Match modal scores:** ad-hoc `bg-blue-100`, `gray-100`, `amber-100` in `MatchScoreBadges` (out of scope for folder move but related visual debt).

---

### Chip-row Pattern (UI-02)

- **Does `InstagramTab` use `ImageMetadataBadges`?** **Yes, indirectly** — every `ImageTile` renders `ImageMetadataBadges` in the body. `InstagramTab` does **not** import `ImageMetadataBadges` by name; it is **not** bypassed. What’s missing is **populated `ImageView` fields** and design parity with Catalog (chips are often empty except via **overlays** “Matched / Described”).
- **`ImageMetadataBadges` vs tab data:** Needs `image.instagram_posted`, `rating`, `pick`, `ai_analyzed` for the standard chips, plus `PrimaryScorePill` when `primaryScoreSource` ≠ `'none'`. Instagram tab passes **`primaryScoreSource="none"`**, so **no** aggregate / catalog score pill by design.
- **Instagram list vs catalog list:** Catalog rows from the API include computed **`ai_analyzed`** and **`instagram_posted`**. Instagram **list** enrichment (`_enrich_instagram_media` in `apps/visualizer/backend/api/images.py`) returns **`description`** (string) but **not** the same `ai_analyzed` / `instagram_posted` fields the frontend `ImageView` chip row expects. **`fromInstagramRow`** does not derive `ai_analyzed` from `description`, so the **“AI” chip does not light up** even when the overlay shows “Described.” **Rating / Pick** are **Lightroom catalog-only** — absent from `InstagramImage`, so those chips will **not** show on Instagram (acceptable if “same chip set” means *same component, only chips with data* — planner should confirm copy vs hide-empty).
- **`MatchGroupTile` metadata row:** Today **no** extra row beyond `ImageTile`’s default (title, date, `ImageMetadataBadges` with **no** primary score, typically sparse). **D-08–D-10** add a **dedicated** line (likely `footer` or a small block below the chip row) for catalog filename / “N candidates” + validation; **not** the same as `ImageMetadataBadges` alone.

---

### Match Card Shape (UI-03)

- **`MatchGroupTile` today:** `pickInitialMatch` → `fromMatchSide` (instagram) → `ImageTile` **grid** + **overlay** validation/candidate `Badge` only. **Shell** already matches Catalog (same `ImageTile` root classes). Gap is **content**: **D-08** metadata under the image area and **D-10** unvalidated “N candidates” as the **row** (overlay may be reduced or kept — planner per D-09 vs overlay duplication).
- **Card shell to match Catalog:** `ImageTile` line (already identified):

```54:55:apps/visualizer/frontend/src/components/image-view/ImageTile.tsx
      className={`group overflow-hidden rounded-card border border-border bg-bg shadow-card transition-all hover:border-border-strong hover:shadow-deep ${classes.root} ${className}`.trim()}
      data-testid="image-tile"
```

- **Data for metadata row:** **Catalog filename:** from `Match.catalog_image?.filename` or key tail when embedded row exists (needs runtime check of match list payloads). **“N candidates”:** `group.candidate_count`. **Validation state:** `group.has_validated` + optionally which candidate is validated via `candidates[].validated_at`. **Subtlety:** D-08 text says “best candidate” filename; D-10 says “validated” groups show “the” catalog filename — **planner** should pick **validated match’s** catalog file when `has_validated`, and **unvalidated** use “N candidates” only (per D-10).

---

### PerspectiveBadge (D-11, D-12)

- **Data available on cards:** `IdentityBestPhotoItem.per_perspective: IdentityPerPerspectiveScore[]` — each has `perspective_slug`, `display_name`, `score` (and metadata). `fromBestPhotoRow` copies to `ImageView.identity_per_perspective`. **Top-1 by score** = `max` over this array (tie-break e.g. by `display_name` or slug for stability). **Color Theory** may appear as a **slug** in API even if `ImageDescription`’s TypeScript `perspectives` type only lists `street` / `documentary` / `publisher` in `api.ts` — use **`perspective_slug` + `display_name`** for labels, not only the old description keys.
- **Where to inject (BestPhotosGrid / TopPhotosStrip):** `ImageTile` already renders `ImageMetadataBadges` then `footer`. Options aligned with D-12: (1) **`footer={<PerspectiveBadge ... />}`** as a second row under the chip row, or (2) **extend** `ImageMetadataBadges` with an optional **children/slot** for PerspectiveBadge, or (3) add **`perspectiveSlot`** on `ImageTile`. **Footer** is **already in the public API** and unused in production — good fit with minimal `ImageTile` API churn.
- **Precedent:** `utils/scoreColorClasses.perspectiveBadgeColor` exists (score-threshold **green/yellow/red**) — different from D-11’s “**perspective** → hue” mapping; new component likely needs a **slug → color** map (D-12 discretion) with contrast checks in `DESIGN.md` semantic tokens.
- **Modal:** User note in CONTEXT: AI description area already shows per-perspective display — new primitive should **align** with that for consistency (grep `DescriptionPanel` / modal when implementing).

---

### Recommended Implementation Approach

#### Wave structure (suggested)

1. **Wave 1 — UI-01 / foundation:** Unify `Badge` + specialized badges + barrel (`index.ts`); add **`PerspectiveBadge`** wrapping `<Badge>`; **JSDoc** on each export (D-04); update imports repo-wide. Optionally **re-export** old paths temporarily (`ui/Badge` → forward to new barrel) to reduce a single huge PR (team choice).
2. **Wave 2 — UI-02:** **`fromInstagramRow`** (and/or API) so chip row can reflect **Described/AI** and **Posted** semantics without contradicting `IDENT-04` patterns; wire **Matches/Instagram** tiles to the **same** chip component rules as Catalog; resolve overlay vs chip **duplication** (Best Photos already uses `hidePostedMetadataBadge` — Instagram may need analogous rules for Matched/Described).
3. **Wave 3 — UI-03:** **`MatchGroupTile`**: `footer` (or equivalent) for filename / candidate count; align validation affordance with D-08–D-10; adjust tests.
4. **Wave 4 — D-12:** **BestPhotosGrid** + **TopPhotosStrip** `PerspectiveBadge` (top-1) via `footer` or shared helper consuming `image.identity_per_perspective`.

**Order of operations:** Consolidate **badge folder + PerspectiveBadge** before or in parallel with chip fixes, but **import stability** is Wave 1’s exit gate. **Match card** and **Identity/Dashboard** tiles can follow once `ImageView` + `ImageTile` contract is clear.

**Import path strategy:** `rg`/`grep` for `ui/Badge`, `ui/badges`, `Badge/Badge`; then either **one** mechanical pass (preferred with CI `tsc` + `vitest`) or codemod. **FilterChip**’s `../../ui/Badge/Badge` is easy to miss — include in checklist.

**Tests to touch (expected):**

- `components/ui/__tests__/Badges.test.tsx`, `ui/badges/__tests__/ScorePill.test.tsx`
- `image-view/__tests__/ImageMetadataBadges.test.tsx`, `ImageTile.test.tsx`, `adapters.test.ts`
- `components/identity/BestPhotosGrid.test.tsx` (Posted count; may need **PerspectiveBadge** assertions)
- `DashboardPage.test.tsx` only if Top Photos region gains new text/role
- New unit tests for **`PerspectiveBadge`** and **`MatchGroupTile`** metadata row
- `InstagramTab.test.tsx` if chip row / API adapter behavior changes

---

### Risk Areas

- **Import scope:** **~17+** files reference `ui/Badge` variants; **badges** barrel and **ScorePill** direct import add a few more. Not huge, but **error-prone** if any `Badge/Badge` deep path is missed.
- **Structural tests:** **Snapshot**-like tests for class names on `ImageTypeBadge` / `VisionBadge` may need updates when switching to `Badge` wrappers.
- **API / adapter gaps (Instagram):** **No `instagram_posted` / `ai_analyzed`** on list JSON like catalog; **adapter** can set `ai_analyzed` from `description` length; **“Posted”** on Instagram tab may need **product** definition (e.g. show only for catalog-matched, or treat IG posts as “posted” by definition, or hide chip).
- **Match list payloads:** If **`catalog_image` is often missing** on `Match` for list performance, **filename** in D-08 may require **fallback to `catalog_key`** string or a **small API** extension — verify with real `GET /api/images/matches` payloads.
- **D-08 vs D-10 wording:** “Best candidate” filename vs “validated” catalog filename — **resolve in PLAN** to avoid building the wrong row.
- **VisionBadge duplication:** `MatchScoreBadges` inlines vision styling; consolidating may invite one pass to use **`VisionBadge`** (optional cleanup, not strictly required for folder move).
- **Perspective count:** `ImageDescription` documents three named perspectives; identity API may return **more slugs** — **color map** should be extensible (default `variant` or neutral).

---

*Research for Phase 6 — Images page visual consistency — 2026-04-22*
