# ADR-0002: Split database.py into focused store modules

**Status:** Accepted  
**Date:** 2026-04-29

## Context

`lightroom_tagger/core/database.py` (3553 lines) contained the entire library data layer: schema init, migrations, image CRUD, match storage, vision cache, description storage, score storage, perspective management, embedding helpers, stack operations, NL filter SQL builders, and the `library_write` serializer — all behind one flat namespace. Interface size was nearly equal to implementation size.

## Decision

Carve into focused sub-modules:

- `db_core.py` — `library_write` serializer, connection helpers, `resolve_filepath`
- `schema.py` — declarative CREATE TABLE statements only
- `migrations.py` — ordered `(version, fn)` list applied via `PRAGMA user_version` (no external deps)
- `image_store.py` — image CRUD (`store_image`, `get_image`, `get_all_images`, etc.)
- `catalog_query.py` — `query_catalog_images`, `_append_query_catalog_image_filters`, `filter_order_keys_in_catalog`, and related SQL builder helpers (counterpart to `catalog_nl_filter.py`)
- `score_store.py` — perspectives + `image_scores` CRUD
- `description_store.py` — descriptions, FTS, text/CLIP embeddings
- `match_store.py` — matches, vision cache, vision comparisons
- `stack_store.py` — stack split/merge/representative operations

`database.py` becomes the **permanent public re-export shim**. All callers import from `lightroom_tagger.core.database` — never from internal sub-modules. Internal structure can evolve without breaking callers.

Migration strategy: inline versioned migrations using `PRAGMA user_version`. Each migration is a `(version: int, fn: Callable[[Connection], None])` tuple in an ordered list. Applied once on `init_database`. No Alembic dependency.

## Consequences

- A bug in score storage is findable in ~200 lines, not 3500
- Each store module has a clean, independently testable interface
- `database.py` as stable public API means zero import churn for existing callers
- `PRAGMA user_version` approach is self-contained and appropriate for SQLite solo projects
