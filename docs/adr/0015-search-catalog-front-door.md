# ADR-0015: Catalog search front door (`search_catalog`)

## Status
Accepted (2026-07)

## Context
Catalog search routing, query execution, and pin-to-similarity shaping were
smeared across Flask image blueprints. Four distinct LLM/search paths existed
(one-shot NL filter, multi-turn NL filter, tool-calling loop, semantic hybrid),
each with duplicated stitching between runner output, library-DB reads, and
per-row signals (`score`, `why_matched`). Parent initiative: one core front door
for natural-language catalog search (issue #140).

Slices 1–3 moved every visualizer search endpoint through
`lightroom_tagger.core.catalog_search.search_catalog` and removed the
`_RuntimeDeps` / `use_runtime_deps` ContextVar seam. This ADR seals the boundary
so regressions are un-mergeable.

## Decision
1. **Single front door** — `search_catalog(db, message, …) → SearchResult` in
   `lightroom_tagger.core.catalog_search` owns strategy routing (`nl_filter` /
   multi-turn / tool-calling / semantic), library-DB query execution, and
   pin-to-similarity candidate restriction. It returns detached core image rows
   plus per-row signals and optional metadata — not API-shaped envelopes.
2. **Thin HTTP wrappers** — visualizer image search blueprints validate input,
   open `library.db`, call `search_catalog`, and map `SearchResult` to the
   existing JSON contract. They must not import or call the underlying runners.
3. **Runners are internal** — `run_nl_catalog_filter_llm`,
   `run_nl_catalog_filter_llm_multi_turn`, `run_tool_calling_search` (in
   `nl_catalog_search`), `run_semantic_hybrid_search` (in `semantic_search`), and
   `list_pin_similarity_candidate_keys` (in `clip_similarity`) are documented as
   internal to the front door. Only `catalog_search.py` may orchestrate them.
   Names are not underscore-prefixed so existing test patch targets stay stable.
4. **Read seam preserved** — per ADR-0008, `search_catalog` and its helpers
   return detached `dict` rows from `core.database` read helpers, never live
   `sqlite3.Row` objects.
5. **Enforcement** — `apps/visualizer/backend/tests/test_search_catalog_guardrail.py`
   statically rejects any import or call of the forbidden runners under
   `apps/visualizer/backend/` (excluding tests).

## Consequences
- One place to audit catalog search orchestration; new search modes extend
  `catalog_search` instead of growing blueprint logic.
- Blueprints stay thin and contract-focused; strategy changes do not require
  touching HTTP handlers.
- Test patches may continue to target runners on `catalog_search` or
  `nl_catalog_search` module paths where slice tests already mock internals.
- Slight indirection via `SearchResult`; acceptable for a single seam.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Rename runners with leading underscores** | Breaks established `unittest.mock.patch` targets in search API tests; churn without stronger enforcement than a guardrail. |
| **ContextVar runtime-deps seam** | Reintroduces hidden wiring; slices 1–3 already removed it. |
| **Guardrail only in core** | Web layer is the regression surface; `catalog_search.py` legitimately calls runners. |
| **Return API envelopes from core** | Couples library to Flask response shapes; violates ADR-0008 detached-row seam. |
