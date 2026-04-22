---
phase: 6
status: clean
reviewed: 2026-04-22
---

# Phase 6 review — Images page visual consistency

## Overall

Phase 6 matches the stated goals: badge barrel under `ui/badges/`, Instagram adapter + tab overlay cleanup, `MatchGroupTile` footer behavior, and dominant perspective footers on best/top photo surfaces. No legacy `components/ui/Badge` module remains; imports consistently target `../ui/badges` (or relative equivalents). TypeScript shapes for identity perspectives align with `IdentityPerPerspectiveScore` in `api.ts`.

**Verdict:** **clean** — no blocking bugs found. A few edge cases and test gaps are noted below for optional hardening.

## What looks good

- **`fromInstagramRow`:** `ai_analyzed` is derived only from a non-empty trimmed `description` string, which matches how `ImageMetadataBadges` gates the AI chip (`image.ai_analyzed`). Whitespace-only descriptions correctly stay “not analyzed.”
- **`InstagramTab`:** Overlay is limited to the matched state; description/AI is delegated to `ImageMetadataBadges`, avoiding duplicate “Described”/AI labeling.
- **`MatchGroupTile`:** Validated path shows catalog filename (with `catalog_key` fallback) plus validated badge; unvalidated path shows only the candidate count string and deliberately does not leak the top candidate’s filename (covered by tests).
- **`pickDominantPerspective`:** Ignores non-finite scores when comparing; ties keep the first entry (stable, documented in tests).
- **`PerspectiveBadge`:** Slugs are normalized with `toLowerCase()` and hyphen→underscore mapping; known slugs get tinted classes; unknown slugs fall back to default `Badge` styling. Integer scores render without a forced decimal; fractional scores use one decimal place.

## Minor concerns and edge cases

### 1. Non-finite scores → odd badge text (low probability)

If every `per_perspective` entry has a non-finite `score` (`NaN`/`Infinity`), `pickDominantPerspective` returns the **first** row (the reducer never prefers a later row when no finite score wins). `PerspectiveBadge` then formats with `score.toFixed(...)`, which yields `"NaN"` or `"Infinity"` strings in JS engines — a confusing UI if bad data ever appears.

**Files:** `apps/visualizer/frontend/src/components/identity/pickDominantPerspective.ts`, `apps/visualizer/frontend/src/components/ui/badges/PerspectiveBadge.tsx`

**Suggestion:** After picking a winner, skip rendering when `!Number.isFinite(score)`, or filter non-finite entries before reducing.

### 2. `msgMatchGroupCandidates(0)`

If `has_validated` is false and `candidate_count` is `0`, the footer would show `0 candidates`. That would indicate inconsistent API/group data rather than a logic bug in the component.

**File:** `apps/visualizer/frontend/src/constants/strings.ts` (`msgMatchGroupCandidates`)

### 3. Test coverage gaps for `pickDominantPerspective`

Existing tests cover empty/undefined, max score, and ties. They do not cover `null` (runtime-safe today via `!entries`) or “all non-finite scores” / “mix of NaN and finite” (finite should win — worth one test to prevent regressions).

**Files:** `apps/visualizer/frontend/src/components/identity/pickDominantPerspective.ts`, `pickDominantPerspective.test.ts`

### 4. Duplicated `BadgeVariant` type in `PerspectiveBadge`

`PerspectiveBadge.tsx` declares a local `BadgeVariant` union that mirrors `Badge.tsx`. Harmless but could drift; optional refactor is to import/share the type from `Badge` if you want a single source of truth.

**File:** `apps/visualizer/frontend/src/components/ui/badges/PerspectiveBadge.tsx`

## Verification performed

- Repo search for imports of `ui/Badge` (path segments): **no matches**.
- Grep for `ui/badges` usage: all consumers import from the new barrel.
- Read-through of adapters, Instagram tab, match tile, identity grids, `PerspectiveBadge`, `pickDominantPerspective`, strings helper, API types, `ImageTile` footer wiring, and `MatchGroupTile` / `pickDominantPerspective` tests.

## File index (phase touchpoints)

| Area | Path |
|------|------|
| Badge barrel | `apps/visualizer/frontend/src/components/ui/badges/*` |
| Instagram adapter | `apps/visualizer/frontend/src/components/image-view/adapters.ts` |
| Instagram tab | `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` |
| Match group tile | `apps/visualizer/frontend/src/components/images/MatchGroupTile.tsx` |
| Dominant perspective | `apps/visualizer/frontend/src/components/identity/pickDominantPerspective.ts`, `BestPhotosGrid.tsx` |
| Top photos | `apps/visualizer/frontend/src/components/insights/TopPhotosStrip.tsx` |
| Copy helpers | `apps/visualizer/frontend/src/constants/strings.ts` |
