# Plan 03-06 — Summary

**Title:** Posted visibility end-to-end and catalog API regression  
**Phase:** 03 — Instagram sync  
**Requirements:** IG-06  
**Completed:** 2026-04-10

## Outcome

- **Backend:** `test_images_catalog_api` fixture seeds one catalog row with `instagram_posted: True` and one without; `test_catalog_posted_filter_true` / `test_catalog_posted_filter_false` assert `GET /api/images/catalog?posted=true` and `?posted=false` totals and `instagram_posted` on returned rows.
- **Frontend:** `CatalogTab` documents IG-06 traceability (`images.instagram_posted` → `listCatalog` `posted` → `?posted=`); `CatalogImageCard` and `CatalogImageModal` already show `Badge variant="success"` for **Posted** / **Posted to Instagram** when `image.instagram_posted` is truthy.
- **Stats:** `GET /api/stats` continues to expose `posted_to_instagram`; handler now uses `SELECT COUNT(*) FROM images WHERE instagram_posted = 1` instead of scanning all image rows in Python.

## Commits

| Commit   | Message |
|----------|---------|
| `d6c0af1` | `test(03-06): add catalog posted filter integration tests` |
| `f4d8b6a` | `docs(03-06): document IG-06 catalog posted filter traceability` |
| `e6f49cd` | `refactor(03-06): compute posted_to_instagram via SQL count in stats` |

## Verification

- `pytest apps/visualizer/backend/tests/test_images_catalog_api.py` — exit 0.
- Plan greps: `posted=true` / `posted=false` in catalog API tests; `instagram_posted` in `CatalogTab.tsx`; `Posted</Badge>` in `CatalogImageCard.tsx`; `Posted to Instagram` in `CatalogImageModal.tsx`; `posted_to_instagram` in `system.py`.

## Notes

- IG-06 aligns catalog UI filtering with library `images.instagram_posted` and the documented `Stats.posted_to_instagram` field in `api.ts`.
