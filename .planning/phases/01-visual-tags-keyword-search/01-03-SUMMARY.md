---
plan: "01-03"
title: "description_search query builder, catalog query, API, and CatalogTab UI"
status: complete
completed: "2026-04-23"
---

## What Was Built

`build_description_fts_query` builds a bound FTS5 `MATCH` string from user input: ASCII alphanumeric tokens (length ≥ 2), AND-joined, each token double-quoted so FTS5 reserved words (e.g. `OR`) are literals. `query_catalog_images` accepts `description_search` and restricts matches to catalog description rows via `image_descriptions_fts` joined on `rowid`. `GET /api/images/catalog` reads `description_search` (empty → no filter; one character after trim → 400). The catalog UI adds a separate description search field (`description_search` query param) with debounced `useFilters` wiring and an RTL test.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| T01 | `build_description_fts_query` + unit tests (injection-style input) | bc60841 |
| T02 | `query_catalog_images` + catalog-only FTS `MATCH ?` | 826e472 |
| T03 | Flask catalog API, integration tests, FTS5 quoting fix | 78d2ebd |
| T04 | `listCatalog`, strings, `CatalogTab` descriptor, RTL test | 332b3cc |

## Key Files Modified

- `lightroom_tagger/core/database.py` — `build_description_fts_query`; `query_catalog_images(..., description_search=...)` with `image_descriptions_fts` subquery and bound `MATCH ?`
- `lightroom_tagger/core/test_database.py` — `TestBuildDescriptionFtsQuery` cases
- `apps/visualizer/backend/api/images.py` — `description_search` query param handling
- `apps/visualizer/backend/tests/test_images_catalog_api.py` — catalog FTS + 400 + injection-style URL tests
- `apps/visualizer/frontend/src/services/api.ts` — `description_search` on `listCatalog`
- `apps/visualizer/frontend/src/constants/strings.ts` — `FILTER_DESCRIPTION_SEARCH_*`
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — `descriptionSearch` filter + `listParams` / page-reset effects
- `apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx` — debounced `description_search` assertion

## Issues Encountered

- **FTS5 `MATCH` alias:** A short table alias before `MATCH` was parsed incorrectly (`no such column: f`). Replaced with `image_descriptions_fts MATCH ?` on the joined virtual table.
- **Reserved tokens:** Unquoted `OR` in the match string caused `fts5: syntax error near "OR"`. Tokens are now emitted as quoted literals (e.g. `"hello" AND "OR"`).
- **Tokenization vs. D-11 whitespace split:** Alphanumeric runs (plus per-token quoting) match the plan’s integration tests and NLS-02; punctuation never enters the `MATCH` bound parameter.

## Self-Check

- [x] All tasks executed
- [x] Each task committed individually
- [x] Tests pass (or documented)
- [x] SUMMARY.md created
