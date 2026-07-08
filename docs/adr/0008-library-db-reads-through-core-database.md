# ADR-0008: Library-DB reads go through core.database

## Status
Accepted (2026-07)

## Context
Blueprints, job handlers, CLI tools, and the LLM search-tool executor issued raw
`db.execute(...)` SQL against `library.db` tables (`images`, `matches`,
`image_descriptions`, `instagram_dump_media`, `catalog_similarity_*`, etc.).
The same queries were duplicated across call sites, returned live `sqlite3.Row`
objects in some paths, and made it hard to evolve schema or add filtering
consistently. Parent initiative: route **all** library-DB reads through a typed
read seam in `lightroom_tagger.core.database` (issue #53).

## Decision
1. **All library-DB reads** from application code (visualizer blueprints, job
   handlers, `search_tools`, scripts) must go through typed helpers exported
   from `lightroom_tagger.core.database` — never ad-hoc SQL at call sites.
2. Read helpers live in focused sub-modules (`catalog_statistics`, `matches`,
   `instagram`, `descriptions`, `scores`, `similarity`, `stacks`, …) and are
   re-exported from the package `__init__.py` barrel so callers keep a single
   import path (see ADR-0002).
3. Every read helper returns **detached** data: `dict(row)`, scalars, `list`, or
   `set` — never a live `sqlite3.Row`.
4. Migration is **incremental**: add helpers first (no call-site changes), then
   migrate consumers slice-by-slice. Write paths continue to use existing write
   helpers and `library_write` (ADR-0002 / CONTEXT).

`catalog_schema_facets(db)` aggregates catalog statistics for NL search schema
discovery so `search_tools` can drop inline SQL entirely in a follow-up slice.

## Consequences
- One place to audit, test, and change library read queries.
- Call-site migrations are mechanical once the seam exists; behaviour is locked
  by co-located `test_*.py` fixtures against a seeded library DB.
- Slight indirection vs inline SQL; acceptable for consistency and testability.
- Raw SQL remains **inside** `core.database` only — the seam is the boundary.
