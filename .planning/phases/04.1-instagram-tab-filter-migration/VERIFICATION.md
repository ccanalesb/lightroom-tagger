---
phase: 4.1
title: InstagramTab filter migration
milestone: v2.1
inserted_after: 4
status: complete
verified_at: "2026-04-17T22:40:00.000Z"
---

# Phase 4.1 — Verification

Requirement coverage: **FILTER-02** (additional consumer of the Phase 4 framework).

## Plans executed

| Plan | Title | Commits | Status |
|------|-------|---------|--------|
| 01 | InstagramTab migration to useFilters + FilterBar | `01257d6`, `51c0ddf` | ✅ |

## Success criteria

1. **SC-1 — InstagramTab uses `FilterSchema` + `useFilters` + `<FilterBar>` with zero ad-hoc filter state.** ✅
   `rg -n "useState.*dateFilter|handleFilterChange|clearFilter" InstagramTab.tsx` → 0 matches. `rg -n "useFilters\\(" InstagramTab.tsx` → 1 match. `rg -n "<FilterBar" InstagramTab.tsx` → 1 match.
2. **SC-2 — Query-param parity preserved.** ✅
   `listInstagram` baseline call receives `{ limit: ITEMS_PER_PAGE, offset: 0 }` with no `date_folder` key (asserted in `InstagramTab.test.tsx`). When the user picks a month, `filters.toQueryParams()` emits `{ date_folder: 'YYYYMM' }` via the `select` descriptor's `paramName`.
3. **SC-3 — No regression to pagination / modal / skeleton behavior.** ✅
   Full frontend suite: 136/136 tests pass (was 134/134 pre-migration; the +2 are the new InstagramTab tests). `PageError`, `SkeletonGrid`, `Pagination`, and `ImageDetailsModal` rendering paths are byte-identical to the pre-migration file.

## Automated checks

| Command | Result |
|---------|--------|
| `cd apps/visualizer/frontend && npx vitest run src/components/images/__tests__/InstagramTab.test.tsx` | ✅ 2/2 |
| `cd apps/visualizer/frontend && npx vitest run` (full suite) | ✅ 26 files / 136 tests |
| `cd apps/visualizer/frontend && npm run lint` | ✅ exit 0 |
| `cd apps/visualizer/frontend && npx tsc --noEmit` | ✅ exit 0 |

## Notes

- **Legacy vs. new UX:** the legacy InstagramTab hid the filter entirely when `availableMonths.length === 0`. The migrated version always renders the `<select>` with just the "All dates" option when no months are loaded. This mirrors CatalogTab's behavior and is considered an acceptable UX shift for the consistency gain.
- **Clear-button copy:** changed from `FILTER_CLEAR` ("Clear") to `FILTER_CLEAR_ALL` ("Clear all"), matching Phase 4 D-17.
- **Remaining ad-hoc filter consumers** (still deferred to SEED-007 full rollout): `MatchesTab`, `DescriptionsTab`, `MatchingTab`, `AnalyticsPage` (apply-button mode would require a hook option), `UnpostedCatalogPanel`.

## Sign-off

Phase 4.1 meets all three success criteria. InstagramTab is now a framework consumer. Ready to mark Phase 4.1 done in ROADMAP.md / STATE.md.
