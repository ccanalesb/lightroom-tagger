# Phase 2: NL filters — Research

## Summary

Phase 2 adds a **backend-only** `POST` endpoint that accepts a natural-language `query` string, calls an LLM through the same **ProviderRegistry + FallbackDispatcher** stack used for describe/score, validates the model output as a **strict Pydantic** filter object (allowlisted fields only, `extra="forbid"`), then runs `query_catalog_images` with those parameters and returns **`{ filters, results (images), total }`**. The database layer must gain **optional `dominant_colors` and `mood_tags` list parameters** that filter `image_descriptions` JSON array columns in SQLite (membership, not raw string SQL from users). There is no `ProviderRegistry.call()` in this codebase—the integration point is **`FallbackDispatcher.call_with_fallback`** plus **`vision_client.complete_chat_text`** for a text-only JSON response.

**Scope note vs roadmap:** `02-CONTEXT.md` **D-04** requires **always** calling the LLM (no “simple query” bypass). That overrides the generic ROADMAP line about optional bypass; plan for D-04.

## Existing Patterns to Follow

- **Flask route organization:** Catalog listing lives in `apps/visualizer/backend/api/images.py` on blueprint `images`, prefix `/api/images` (see `create_app` in `apps/visualizer/backend/app.py`). The new route should be a `@bp.route(..., methods=['POST'])` next to `list_catalog_images`, with `@with_db` and the same `try/except` pattern (`ValueError` → `error_bad_request`, broad `Exception` → `error_server_error`).
- **Catalog list enrichment:** `list_catalog_images` calls `query_catalog_images`, then reshapes rows (description fields, `ai_analyzed`, score columns). The NL endpoint should **reuse the same post-query shaping** (or extract a small shared helper) so response rows match `GET /api/images/catalog`.
- **Validation UX:** `error_bad_request` from `apps/visualizer/backend/utils/responses.py` returns `{"error": "<message>"}` with status 400—use this for empty query, bad JSON from LLM, and Pydantic validation failures (per D-09).
- **LLM + registry:** Jobs and services use `ProviderRegistry()` and `FallbackDispatcher(registry)`; see `lightroom_tagger/core/analyzer.py` (`_describe_image_via_provider`) and `lightroom_tagger/core/scoring_service.py` (`score_image_for_perspective`) for the full pattern. Handlers pass optional `provider_id` / `model` from job metadata; API defaults can read **`registry.defaults["description"]`** (same bucket as describe), consistent with `providers.json` / `update_defaults` in `ProviderRegistry`.
- **Structured JSON from LLM:** `lightroom_tagger/core/structured_output.py` already uses **Pydantic v2** with `ConfigDict(extra="forbid")`, `repair_json_text` (fence strip + trailing-comma fix), and `StructuredOutputError` for parse/validation errors—mirror this style for a new **`CatalogFilterPayload`** (or similar) model rather than ad hoc dict parsing. Reusing `repair_json_text` is recommended; an optional one-shot `complete_chat_text` “repair” pass is consistent with `parse_score_response_with_retry` but **not required** by NLS-01 if plain validation + 400 is enough.
- **Text-only OpenAI call:** `lightroom_tagger/core/vision_client.py` defines **`complete_chat_text(client, model, system=..., user=..., max_tokens=..., temperature=...)`**—this is the right primitive for NL→JSON (no image). It uses `client.chat.completions.create`, maps OpenAI errors via `_map_openai_error`, and applies Claude `extra_body` when the model name contains `claude`.

## LLM Call Architecture

- **`ProviderRegistry`** (`lightroom_tagger/core/provider_registry.py`) loads `providers.json`, exposes `get_client`, `list_models`, `fallback_order`, `get_retry_config`, and **`defaults["description"]` / `defaults["vision_comparison"]`**. It does **not** expose a single `call()`; callers compose **`FallbackDispatcher.call_with_fallback`**.
- **`FallbackDispatcher.call_with_fallback`** (`lightroom_tagger/core/fallback.py`) runs `fn_factory(client, model)()` with **`retry_with_backoff`**, then cascades to other **vision-marked** models on the same provider, then to the first vision model of each fallback provider. For NL search, wrap **`lambda: complete_chat_text(client, mdl, system=SYSTEM_PROMPT, user=user_query)`** in `fn_factory`. **Gotcha:** only models with **`"vision": true`** in the registry participate in the cascade; ensure the default description model is vision-capable (typical in this project) or extend/tune the fallback builder for a dedicated “text” operation in a follow-up.
- **Operation label:** Use a new log label (e.g. `"nl_filter"`) in `call_with_fallback(operation=..., ...)` for clear logs (parallel to `"describe"`, `"compare"`, `"score"`).
- **Errors:** Retryable errors trigger fallback; `ModelUnavailableError` and exhausted fallbacks should surface as **500** with a clear message unless classified as user-fixable (align with existing API error handling). **Malformed / invalid JSON or schema** after the call should be **400** (D-09), not 500.
- **No bypass:** D-04—every request that passes empty-query validation goes through the LLM path (no “keyword-only” shortcut in this phase).

## Pydantic Filter Model

- **Dependencies:** `pydantic>=2.0,<3` is already in `pyproject.toml`. Prefer **`model_config = ConfigDict(extra="forbid")`** so any LLM-invented key fails validation.
- **Field alignment (from `02-CONTEXT` D-07):** All optional with `None` defaults where not set by the model:
  - `posted`: `bool | None`
  - `month`: `str | None` (6-digit `YYYYmm`, consistent with `query_catalog_images`)
  - `keyword`: `str | None`
  - `min_rating`: `int | None`
  - `date_from` / `date_to`: `str | None`
  - `score_perspective`: slug string or `None` (reuse the same regex as `list_catalog_images` for API-level validation: `^[a-z][a-z0-9_]{0,63}$`)
  - `min_score`: `int | None` with `ge=1`, `le=10` if present
  - `sort_by_score`: `Literal["asc", "desc"] | None`
  - `sort_by_date`: `Literal["newest", "oldest"] | None`
  - `description_search`: `str | None` (downstream will enforce FTS rules via `build_description_fts_query` / `ValueError` → 400)
  - `dominant_colors`: `list[str] | None`
  - `mood_tags`: `list[str] | None`
- **Serialization for response:** `model.model_dump(exclude_none=True)` (or `exclude_unset` per product choice) for the **`filters`** key in the JSON response.
- **Cross-field rules:** `query_catalog_images` **requires** `score_perspective` when `min_score` or `sort_by_score` is set—either validate in a `@model_validator` on the Pydantic model or catch `ValueError` from `query_catalog_images` and return 400. Same for `description_search` length (minimum 2 characters) and FTS errors.

## query_catalog_images Extensions

- **Current signature** (`lightroom_tagger/core/database.py`): `query_catalog_images(db, posted=, month=, keyword=, min_rating=, date_from=, date_to=, color_label=, analyzed=, score_perspective=, min_score=, sort_by_score=, sort_by_date=, description_search=, limit=, offset=)`. **No `dominant_colors` / `mood_tags` yet**—both must be added as optional `list[str] | None` (or `None` / empty = no filter).
- **Storage:** `image_descriptions.dominant_colors` and `mood_tags` are **TEXT** columns holding JSON arrays (see schema/migrations in `database.py`); joined row already available via `LEFT JOIN image_descriptions d ... AND d.image_type = 'catalog'`.
- **SQL semantics (recommended):** For each non-empty list of request tokens, add a clause that the stored column’s JSON array **contains at least one** matching element (OR within the list). Combine **AND** with other filters (a row must satisfy dominant-color predicate **and** mood predicate **and** the rest of the `WHERE`).

  **SQLite implementation (preferred):** use **`json_each`** on the column (SQLite JSON1 extension, enabled in standard builds):

  ```sql
  EXISTS (
    SELECT 1 FROM json_each(d.dominant_colors) AS je
    WHERE je.value IN (?, ?, ...)
  )
  ```

  Use **`json_valid`** or `d.dominant_colors IS NOT NULL` guards if needed for legacy/null rows. Bind each token as a separate parameter to avoid string concatenation. **Do not** interpolate user/LLM strings into SQL except as bound values.

- **Alternative (heavier):** `LIKE '%"moody"%'` on serialized JSON is simpler but more brittle (token boundaries, escaping); prefer `json_each` for correctness.

- **No new columns:** Filtering uses existing JSON text on `image_descriptions`.

## Endpoint Design

- **Route:** `POST /api/images/nl-search` (per D-01; `images` blueprint keeps all catalog concerns in one file).
- **Request JSON (suggested):** `{ "query": "...", "limit": 50, "offset": 0, "provider_id"?: "...", "model"?: "..." }` — only `query` is required; pagination mirrors GET catalog; optional provider overrides align with other APIs if desired.
- **Response JSON (per D-02):** `{ "filters": { ... }, "total": <int>, "images": [ ... ] }` — same image objects as `GET /api/images/catalog` for consistency. If **pagination** should be explicit, add a `pagination` object like `success_paginated` or document `limit`/`offset` echo only.
- **400 cases:** Whitespace-only or missing `query` (D-10); invalid JSON body; Pydantic validation; `ValueError` from `query_catalog_images` / FTS builder.

## Test Patterns

- **Location & style:** `apps/visualizer/backend/tests/test_images_catalog_api.py` uses `pytest`, `create_app()`, `init_database` + `store_image` / `store_image_description`, **`monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)`**, and `app.test_client()`. Add **`test_images_nl_search_api.py`** (or extend catalog tests) to avoid an oversized single file.
- **What to cover:**
  - **400** on empty/whitespace query.
  - **Mock LLM:** `monkeypatch` the function that calls `FallbackDispatcher` / `complete_chat_text` to return **fixed JSON** that validates as the Pydantic model, then assert **`query_catalog_images` receives the expected args** (use `mocker.patch` on `query_catalog_images` or the NL helper).
  - **Integration:** Seeded `image_descriptions` with `dominant_colors` / `mood_tags` JSON and assert the new SQL path returns the correct rows.
  - **400** on malformed LLM output (patch to return non-JSON or extra keys) if routed through validation.
- **Conftest:** `conftest.py` only adjusts `sys.path`; fixtures stay local to the test module (same as catalog tests).

## Risks & Gotchas

- **ProviderRegistry has no `call()` method** — plan around **`FallbackDispatcher` + `complete_chat_text`**, not a non-existent API.
- **Fallback list is vision-only** — if the team adds a text-only default model with `"vision": false`, it will be skipped; document or adjust fallback selection for NL search if that becomes common.
- **ROADMAP vs CONTEXT:** Phased decision **D-04** (always LLM) **wins** over the high-level roadmap bullet about optional bypass; do not plan a bypass in Phase 2.
- **`list_catalog_images` does not return `dominant_colors` / `mood_tags` in the row** unless selected—if Phase 5 needs them in the grid, the SELECT list in `query_catalog_images` may need to include `d.dominant_colors` / `d.mood_tags` and `images.py` may need to deserialize (similar to `_DESC_JSON_COLS` at top of `images.py`). Confirm product need; NLS-01 only requires “catalog results + derived filter object.”
- **Score sort dependencies:** LLM may emit `min_score` without `score_perspective`—must be rejected with 400, matching existing GET catalog behavior.
- **FTS:** `description_search` shorter than 2 characters raises `ValueError` in DB layer; treat as 400, consistent with `GET /catalog?description_search=a`.
- **Threading / DB:** Same `@with_db` contract as other routes; no long-holding connection during LLM call beyond existing patterns (consider timeout expectations for user-facing request).

## RESEARCH COMPLETE
