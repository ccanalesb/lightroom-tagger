---
phase: 5
status: issues_found
files_reviewed: 19
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
---

## Findings

### Warning

1. **`TabNav` ARIA tab pattern is incomplete** (`apps/visualizer/frontend/src/components/ui/Tabs/Tabs.tsx`): Buttons use `role="tab"` and `aria-selected`, but there is no `role="tabpanel"`, no `aria-controls` / controlled `id` wiring, and no roving `tabIndex` for inactive tabs. Content is updated elsewhere (`TopPhotosStrip`), so assistive technologies do not get a standard tablist/tabpanel relationship. Consider either a full tab pattern (tabpanels + `aria-controls`) or using `role="navigation"` with plain buttons / `aria-current` instead of `role="tab"`.

### Info

2. **`rank_best_photos` meta vs. filtered `total`** (`lightroom_tagger/core/identity_service.py`): `meta` (e.g. `eligible_count`, `coverage_note`) is produced from `compute_image_aggregate_scores` before the optional `posted` filter runs. `total` reflects the filtered list. API clients must not treat `meta.eligible_count` as the count for the `posted=true|false` slice.

3. **Definition of “posted” for the new filter** (`identity_service.py`, `DashboardPage.tsx`, `api.ts`): The `posted` query parameter filters on `instagram_posted` from catalog rows (via `_image_meta_map`), consistent with `query_catalog_images`’s `posted` filter. Broader “posted” populations used in identity suggestions’ *theme* heuristics (`_posted_catalog_keys_sql`, documented in `posted_semantics`) are not applied here. Catalog images only “posted” via validated matches with `instagram_posted=0` can still appear under Unposted/All; callers should be aware of the column-based semantics.

## Residual risks

- End-to-end API tests do not assert `/api/identity/best-photos?posted=` filtering against seeded rows (service tests in `test_identity_service.py` do). Low risk given unit coverage.
- `TabNav` behavior is UX/a11y debt until pattern is aligned with content.

## Testing gaps

- Flask `test_identity_api.py`: add a small integration test that seeds posted/unposted images with scores and asserts `posted=true` / `posted=false` response counts or keys (mirrors `test_rank_best_photos_filters_by_posted` at HTTP boundary).
