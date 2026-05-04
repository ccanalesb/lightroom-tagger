---
plan: 02-01
status: complete
completed: 2026-04-23
---

# Summary: Pydantic NL Filter Model + DB Array Extensions

## What was built

- **`CatalogNlFilter`**: Pydantic v2 allowlisted filter fields with `extra="forbid"`, per-field validation (`min_score` 1–10, literal sorts), and an after-validator tying `min_score` / `sort_by_score` to a non-empty `score_perspective` slug matching `^[a-z][a-z0-9_]{0,63}$` (with `ValueError` messages containing `score_perspective` on failure).
- **`parse_catalog_nl_filter_from_llm`**: Uses `repair_json_text` + `model_validate_json`; propagates `StructuredOutputError`, `json.JSONDecodeError`, and `ValidationError` for HTTP 400 handling in 02-02.
- **`catalog_nl_filter_to_query_kwargs`**: `model_dump(exclude_none=True)` restricted to `query_catalog_images` parameter names (excludes pagination and fields not on the model).
- **`query_catalog_images`**: Optional `dominant_colors` and `mood_tags` (after `description_search`); non-empty lists add `AND` clauses with `json_type(...) = 'array'`, `json_each`, and bound `IN` placeholders. Blank list elements are stripped out; all-blank/empty list applies no filter.
- **Tests**: `test_database_nl_filter_arrays.py` seeds two catalog images with JSON list descriptions and asserts dominant-color filter, mood-tag OR-within-list behavior, and explicit `None` parity.

## Key files created/modified

- `lightroom_tagger/core/catalog_nl_filter.py` — `CatalogNlFilter`, `parse_catalog_nl_filter_from_llm`, `catalog_nl_filter_to_query_kwargs`, module contract docstring.
- `lightroom_tagger/core/database.py` — `_non_empty_str_list_for_json_array_filter`, `query_catalog_images` params + `json_each` EXISTS clauses + docstring.
- `lightroom_tagger/core/test_database_nl_filter_arrays.py` — three pytest cases for array filters and `None` parity.

## Test results

```
...                                                                      [100%]
3 passed in 0.07s
```

## Deviations

None — plan executed as written. A follow-up **`refactor(02-01)`** commit combines the `score_perspective` guard `if` for Ruff SIM102 (behavior unchanged).

## Self-Check: PASSED

**Plan verification**

- `python -m pytest lightroom_tagger/core/test_database_nl_filter_arrays.py -q` — exit **0** (3 passed).

**Acceptance checks (all PASS)**

- `rg -n "class CatalogNlFilter" lightroom_tagger/core/catalog_nl_filter.py` → match at line 41.
- `rg "parse_catalog_nl_filter_from_llm" lightroom_tagger/core/catalog_nl_filter.py` → match.
- `rg "json_each" lightroom_tagger/core/database.py` → ≥2 matches (dominant_colors + mood_tags `EXISTS` subqueries).
- `rg "dominant_colors" lightroom_tagger/core/database.py` → signature + WHERE `clauses` / `json_each` path (not signature-only).
- `rg "mood_tags" lightroom_tagger/core/database.py` → same.
- `python -c "from lightroom_tagger.core.catalog_nl_filter import CatalogNlFilter, parse_catalog_nl_filter_from_llm"` — success.
- `ruff check lightroom_tagger/core/catalog_nl_filter.py` — All checks passed.

**must_haves (NLS-01 data contract, D-08, tests, 02-02 wiring)**

- NLS-01: Allowlisted Pydantic type with `extra` forbidden; no SQL in the model.
- D-08: `query_catalog_images` accepts `dominant_colors` / `mood_tags` and filters via `json_each` + bound parameters.
- Tests: New module proves array filter narrows / broadens results on seeded rows.
- 02-02: `parse_catalog_nl_filter_from_llm` and `catalog_nl_filter_to_query_kwargs` provide kwargs compatible with `query_catalog_images`.
