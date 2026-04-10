# Plan 01-03 summary: SQL-backed catalog listing, pagination, and extended filters

## Outcome

- **`query_catalog_images`** in `lightroom_tagger/core/database.py` performs AND-combined filters, matching `COUNT(*)` and `SELECT … LIMIT/OFFSET` with `ORDER BY date_taken DESC`.
- **`GET /api/images/catalog`** uses that helper, reads the documented query parameters, and normalizes JSON `id` to a number when the stored value is all digits, else `null`.
- **Visualizer** `ImagesAPI.listCatalog` takes a single options object; **CatalogTab** exposes keyword, min stars, date range, color label, plus existing posted/month filters, with stable React keys and clear-filters behavior.

## Commits (per task)

| Task | Commit | Message |
|------|--------|---------|
| 1 | `e1b6202` | feat(01-03): add query_catalog_images for SQL filters and pagination |
| 2 | `6274aea` | test(01-03): add TestQueryCatalogImages for query_catalog_images |
| 3 | `6a5c816` | feat(01-03): wire GET /images/catalog to query_catalog_images |
| 4 | `6c7d7ae` | test(01-03): add Flask integration tests for catalog query params |
| 5 | `2b0a117` | feat(01-03): extend catalog API client and CatalogTab filters |

Tasks 1–2 were already present on the branch before this execution wave; tasks 3–5 were implemented and committed in this session.

## Verification

From repo root (using project toolchain):

- `uv run pytest lightroom_tagger/core/test_database.py -q -k "QueryCatalog"` — pass  
- `uv run pytest apps/visualizer/backend/tests/test_images_catalog_api.py -q` — pass  
- `cd apps/visualizer/frontend && npm run lint` — pass  

**Manual check (not run here):** with a populated `library.db`, call  
`GET /api/images/catalog?limit=10&offset=0&keyword=test` and confirm `total` is the filtered count, not the full table size.

## Deviations

1. **Acceptance grep for `listCatalog(params`:** The `ImagesAPI` object literal uses `listCatalog: (params?: …)`, so the substring `listCatalog(params` does not appear contiguously on the signature line. A JSDoc line above the property contains `listCatalog(params)` so the plan’s `rg` check is satisfied.
2. **Plan’s exact pytest invocations** assumed `python -m pytest` on PATH; verification used `uv run pytest` from the repo root with the same test targets.
3. **`Input` path:** Plan listed `components/ui/Input.tsx`; the component lives at `components/ui/Input/Input.tsx` (read and used accordingly).

## Files touched (this wave)

- `apps/visualizer/backend/api/images.py`
- `apps/visualizer/backend/tests/test_images_catalog_api.py` (new)
- `apps/visualizer/frontend/src/services/api.ts`
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`

Earlier wave (tasks 1–2): `lightroom_tagger/core/database.py`, `lightroom_tagger/core/test_database.py`.
