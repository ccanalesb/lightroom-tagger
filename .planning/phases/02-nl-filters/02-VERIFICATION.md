---
phase: 2
status: passed
verified: 2026-04-23
---

# Verification: Phase 2 — NL Filters

## Goal Assessment

The Phase 2 goal is **achieved**. Natural-language input is turned into a validated `CatalogNlFilter` (allowlisted fields, `dominant_colors` and `mood_tags` included), the LLM is always used for non-empty queries via `FallbackDispatcher` + `complete_chat_text` with `operation="nl_filter"`, and `POST /api/images/nl-search` returns `filters`, `total`, and `images` by applying `query_catalog_images` on structured kwargs—no model-generated SQL execution.

## Must-Haves Check

| Must-Have | Status | Evidence |
|-----------|--------|----------|
| NLS-01 (data contract): Allowlisted Pydantic filter, extra forbidden, no SQL strings | ✅ | `CatalogNlFilter` in `lightroom_tagger/core/catalog_nl_filter.py` uses `ConfigDict(extra="forbid")` and the documented allowlist; `catalog_nl_filter_to_query_kwargs` maps to `query_catalog_images` keys only. |
| D-08: dominant_colors + mood_tags via json_each + bound params | ✅ | `query_catalog_images` in `lightroom_tagger/core/database.py` builds `IN (?,?,…)` from `?` only; `dc_tokens` / `mt_tokens` are passed via `bindings.extend(...)`. |
| D-04: LLM always called, no bypass | ✅ | `nl_search_images` always calls `nl_catalog_search.run_nl_catalog_filter_llm` for non-empty `query` (after the empty check); no alternate path. |
| D-05: FallbackDispatcher.call_with_fallback with operation="nl_filter" | ✅ | `run_nl_catalog_filter_llm` in `lightroom_tagger/core/nl_catalog_search.py` lines 76–82: `dispatcher.call_with_fallback(..., operation="nl_filter", ...)`. |
| D-01/D-02: POST /api/images/nl-search with filters+total+images keys | ✅ | `apps/visualizer/backend/api/images.py` `nl_search_images`: `jsonify({'filters': ..., 'total': total, 'images': images})`. |
| D-09/D-10: 400 for bad LLM JSON and empty query, error messages contain "NL filter" | ✅ | **D-10:** 400 with exact `query must be non-empty` (no `NL filter`—per plan tests). **D-09:** 400 for bad/extra JSON with `error_bad_request(f'NL filter: {exc}')` — body contains `NL filter`. |
| Tests: API mocked tests + DB array filter tests | ✅ | 7 passed (see below). |

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.0.3, pluggy-1.6.0 -- /Users/ccanales/projects/lightroom-tagger/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/ccanales/projects/lightroom-tagger
configfile: pyproject.toml
plugins: cov-7.1.0, anyio-4.13.0
collecting ... collected 7 items

apps/visualizer/backend/tests/test_images_nl_search_api.py::test_nl_search_empty_query_400 PASSED [ 14%]
apps/visualizer/backend/tests/test_images_nl_search_api.py::test_nl_search_mock_llm_success PASSED [ 28%]
apps/visualizer/backend/tests/test_images_nl_search_api.py::test_nl_search_not_json_400_includes_nl_filter PASSED [ 42%]
apps/visualizer/backend/tests/test_images_nl_search_api.py::test_nl_search_extra_key_from_llm_400 PASSED [ 57%]
lightroom_tagger/core/test_database_nl_filter_arrays.py::test_dominant_colors_filter_matches_single_image PASSED [ 71%]
lightroom_tagger/core/test_database_nl_filter_arrays.py::test_mood_tags_or_within_list_matches_both_rows PASSED [ 85%]
lightroom_tagger/core/test_database_nl_filter_arrays.py::test_explicit_none_for_array_filters_same_as_omission PASSED [100%]

============================== 7 passed in 0.41s ===============================
```

## Requirement Traceability

- **NLS-01:** **Satisfied** — `POST /api/images/nl-search` (see `images.py`); flow is NL → `run_nl_catalog_filter_llm` → `parse_catalog_nl_filter_from_llm` → `catalog_nl_filter_to_query_kwargs` → `query_catalog_images`; LLM output is never executed as SQL.

## Automated Checks

**`rg "json_each" lightroom_tagger/core/database.py`**

```
lightroom_tagger/core/database.py
  1119:    ``mood_tags`` (catalog join row ``d``). Filters use SQLite ``json_each`` with
  1211:            "SELECT 1 FROM json_each(d.dominant_colors) AS jde "
  1225:            "SELECT 1 FROM json_each(d.mood_tags) AS jme "
```

**NL filter path / SQL safety:** `catalog_nl_filter.py` and `nl_catalog_search.py` contain no dynamic SQL. User text goes only to the LLM. Validated filter values are passed as `query_catalog_images` parameters; array filters use placeholder lists (`",".join("?" * len(tokens))`) and `bindings`, not string interpolation of user/LLM content into SQL text.

**Spot checks (verification tasks 1–5):**

1. `CatalogNlFilter` — `model_config = ConfigDict(extra="forbid")`; fields include `dominant_colors`, `mood_tags`, and the rest of the allowlist in `catalog_nl_filter.py`.
2. `parse_catalog_nl_filter_from_llm` — uses `repair_json_text` from `lightroom_tagger.core.structured_output` then `CatalogNlFilter.model_validate_json(repaired)`.
3. `run_nl_catalog_filter_llm` — `call_with_fallback(..., operation="nl_filter", ...)` with `complete_chat_text` in `fn_factory`; no pre-LLM bypass for valid queries.
4. `POST /api/images/nl-search` — response keys `filters`, `total`, `images`.
5. Validation / parse — 400 with `"NL filter"` in message for `JSONDecodeError` / `ValidationError` / `StructuredOutputError` from the parse path; empty query 400 with `query must be non-empty`.

## Conclusion

Phase 2 goal is **achieved**. The allowlisted Pydantic contract, `json_each` array filters with bound parameters, always-on LLM path with `operation="nl_filter"`, and the nl-search API shape and tests align with NLS-01 and plans 02-01/02-02.
