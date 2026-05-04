---
plan: 02-02
status: complete
completed: 2026-04-23
---

# Summary: NL Search LLM Runner + POST /api/images/nl-search

## What was built

- **`lightroom_tagger.core.nl_catalog_search`**: `NL_CATALOG_FILTER_SYSTEM_PROMPT` lists the allowlisted `CatalogNlFilter` field names; `run_nl_catalog_filter_llm` resolves `provider` / `model` from `ProviderRegistry().defaults["description"]` (with the same “first model if default model is null” rule as describe), then calls `FallbackDispatcher.call_with_fallback(operation="nl_filter", ...)` with a `fn_factory` that returns `complete_chat_text` (text-only, `max_tokens=1024`, `temperature=0.0`). No fast path that skips the LLM for non-empty queries.
- **`POST /api/images/nl-search`**: JSON body (`query` required; optional `limit`, `offset`, `provider_id`, `model`). Returns `{"filters", "total", "images"}` with the same per-row shape as `GET /api/images/catalog` via shared `_rows_to_catalog_api_images`. LLM output is passed through `parse_catalog_nl_filter_from_llm` → `catalog_nl_filter_to_query_kwargs` → `query_catalog_images`. Parse/validation errors return **400** with messages containing the substring `NL filter`; the route imports `lightroom_tagger.core.nl_catalog_search` as a module so tests can patch `lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm`.
- **Tests** (`test_images_nl_search_api.py`): empty/whitespace query → 400 with exact `query must be non-empty`; mocked LLM success → 200 and `filters` / `images` / `total`; `not-json` and extra-key LLM output → 400 with `NL filter` in the error body.

## Key files created/modified

- `lightroom_tagger/core/nl_catalog_search.py` — `NL_CATALOG_FILTER_SYSTEM_PROMPT`, `run_nl_catalog_filter_llm` (`operation="nl_filter"`, `complete_chat_text` from `vision_client`).
- `apps/visualizer/backend/api/images.py` — `_rows_to_catalog_api_images` (shared with `list_catalog_images`); `nl_search_images` POST route.
- `apps/visualizer/backend/tests/test_images_nl_search_api.py` — four API tests with mocked `run_nl_catalog_filter_llm` and `LIBRARY_DB` temp library.

## Test results

```
$ python -m pytest apps/visualizer/backend/tests/test_images_nl_search_api.py -q
....                                                                     [100%]
4 passed in ~0.4s

$ python -m pytest lightroom_tagger/core/test_database_nl_filter_arrays.py -q
...                                                                      [100%]
3 passed in ~0.06s
```

## Deviations

- **Route import style:** The plan showed `from ... import run_nl_catalog_filter_llm`. Implementation uses `from lightroom_tagger.core import nl_catalog_search` and `nl_catalog_search.run_nl_catalog_filter_llm(...)` so `monkeypatch` can target `lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm` (required for tests when using `from import` of a function).

## Self-Check: PASSED

- `POST` route on `/api/images/nl-search` with `query must be non-empty` and `NL filter` in 400 parse messages; `jsonify` uses `'images'`.
- `call_with_fallback(..., operation="nl_filter", ...)` in `nl_catalog_search.py`.
- No NL fast path: every non-empty `query` goes through `run_nl_catalog_filter_llm`.
- Pytest: `test_images_nl_search_api.py` and `test_database_nl_filter_arrays.py` exit 0.
- `rg` acceptance: nl-search route, `NL filter`, `nl_catalog_search.run_nl_catalog_filter_llm`, `'images':`, `operation="nl_filter"`.
