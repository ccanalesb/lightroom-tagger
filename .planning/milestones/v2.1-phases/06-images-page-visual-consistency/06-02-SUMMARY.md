# Phase 6 — Plan 02: images-inline-chips-adapter

## Objective

Align Instagram (and match-list) tiles with Catalog/Best Photos metadata chips: `ImageView` from Instagram rows now sets `ai_analyzed` from non-empty `description`, Instagram tab drops the redundant “Described” overlay, and the match instagram path is covered by tests.

## Tasks completed

### Task 01 — `fromInstagramRow` + tests

- `ai_analyzed` is `true` when `row.description` is a string with `trim().length > 0`, else `false`.
- Unit tests: existing Instagram row case expects `ai_analyzed`; trimmed `'  hello  '`; missing / `''` / whitespace-only → false.

**Commit:** `feat(phase-6-02): set ai_analyzed in fromInstagramRow from description`

### Task 02 — Instagram tab overlay

- Removed `BADGE_DESCRIBED` overlay; **Matched** overlay unchanged.
- `Badge` import remains `../ui/badges`.

**Commit:** `feat(phase-6-02): remove Described overlay duplicating AI chip on Instagram tiles`

### Task 03 — Matches tab / `fromMatchSide`

- Confirmed `fromMatchSide(..., 'instagram')` calls `fromInstagramRow(embedded)` when `instagram_image` is present (no adapter change).
- Added unit test: embedded Instagram with description yields `ai_analyzed: true` on the resulting `ImageView`.

**Commit:** `feat(phase-6-02): test fromMatchSide instagram path inherits ai_analyzed`

## Verification

- `cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run` — exit 0 (224 tests).

## Self-Check: PASSED

- `fromInstagramRow` sets `ai_analyzed` from non-empty description string.
- Instagram tiles no longer duplicate Described vs AI chip (`ImageMetadataBadges`).
- `InstagramTab` imports `Badge` from `../ui/badges` only.
- Adapter tests cover `ai_analyzed` for Instagram and `fromMatchSide` instagram path.
- `tsc` and full `vitest run` pass.
