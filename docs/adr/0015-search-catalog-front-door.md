# ADR-0015: Catalog search front door (`search_catalog`)

## Status
Superseded (2026-08-12) — chat / NL / semantic search and `search_catalog` removed in [#223](https://github.com/ccanalesb/lightroom-tagger/issues/223). Catalog keyword search over `image_descriptions_fts` via the Images `description_search` filter remains; CLIP similarity (`clip_similarity`, `image_clip_embeddings`) remains for catalog similarity ([#226](https://github.com/ccanalesb/lightroom-tagger/issues/226)).

## Context
Catalog search routing, query execution, and pin-to-similarity shaping were
smeared across Flask image blueprints. Four distinct LLM/search paths existed
(one-shot NL filter, multi-turn NL filter, tool-calling loop, semantic hybrid),
each with duplicated stitching between runner output, library-DB reads, and
per-row signals (`score`, `why_matched`). Parent initiative: one core front door
for natural-language catalog search (issue #140).

Slices 1–3 moved every visualizer search endpoint through
`lightroom_tagger.core.catalog_search.search_catalog` and removed the
`_RuntimeDeps` / `use_runtime_deps` ContextVar seam. This ADR sealed the boundary
so regressions were un-mergeable.

## Decision
1. **Single front door** — `search_catalog(db, message, …) → SearchResult` in
   `lightroom_tagger.core.catalog_search` owned strategy routing (`nl_filter` /
   multi-turn / tool-calling / semantic), library-DB query execution, and
   pin-to-similarity candidate restriction. It returned detached core image rows
   plus per-row signals and optional metadata — not API-shaped envelopes.
2. **Thin HTTP wrappers** — visualizer image search blueprints validated input,
   opened `library.db`, called `search_catalog`, and mapped `SearchResult` to the
   existing JSON contract. They did not import or call the underlying runners.
3. **Runners were internal** — NL/tool/semantic runners and
   `list_pin_similarity_candidate_keys` (in `clip_similarity`) were documented as
   internal to the front door. Only `catalog_search.py` orchestrated them.
4. **Read seam preserved** — per ADR-0008, `search_catalog` and its helpers
   returned detached `dict` rows from `core.database` read helpers, never live
   `sqlite3.Row` objects.
5. **Enforcement** — `test_search_catalog_guardrail.py` statically rejected any
   import or call of the forbidden runners under `apps/visualizer/backend/`
   (excluding tests).

## Consequences
- One place to audit catalog search orchestration while the chat surface existed.
- Blueprints stayed thin and contract-focused.
- The guardrail and front door became dead weight once the Search page and
  `search_catalog` were removed; keyword FTS search does not use this seam.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Rename runners with leading underscores** | Breaks established `unittest.mock.patch` targets in search API tests; churn without stronger enforcement than a guardrail. |
| **ContextVar runtime-deps seam** | Reintroduces hidden wiring; slices 1–3 already removed it. |
| **Guardrail only in core** | Web layer is the regression surface; `catalog_search.py` legitimately called runners. |
| **Return API envelopes from core** | Couples library to Flask response shapes; violates ADR-0008 detached-row seam. |
