# ADR-0011: Managed library-DB and catalog lifecycle seam

**Status:** Accepted  
**Date:** 2026-07-12

## Context

Call sites opened `library.db` via `init_database(...)` and closed connections
manually (`try`/`finally`, bare `.close()`), and opened Lightroom catalogs via
`connect_catalog(...)` with the same hand-rolled pattern. Lifecycle rules
duplicated across CLI commands, visualizer job handlers, and scripts; leaks and
double-close bugs were easy to introduce when adding parallel worker paths.
Parent initiative: managed context managers for library-DB and catalog lifecycle
(issue #56).

Adjacent seams already lock neighbouring boundaries: [ADR-0006](0006-cli-command-registry.md)
(CLI dispatch registry — sibling deepening for command handlers),
[ADR-0008](0008-library-db-reads-through-core-database.md) (read seam — typed
queries once a connection is open; does not govern open/close).

## Decision

1. **Library-DB lifecycle** goes through `managed_library_db(path)` (exported from
   `lightroom_tagger.core.database`, implemented in `managed_connections.py`).
   Callers must not hand-roll `init_database(...)` + manual `close()` at
   orchestration sites.
2. **Catalog lifecycle** goes through `managed_catalog(path)` for read paths
   that need a short-lived `.lrcat` connection. Callers must not hand-roll
   `connect_catalog(...)` + manual `close()` at orchestration sites.
3. **Visualizer job handlers** use `make_managed_library_db(lambda p: init_database(p))`
   in `jobs/handlers/db_lifecycle.py` so unit tests can patch module-level
   `init_database` while still routing through the same CM shape.
4. **CLI commands** use `with_library_db` / direct `with managed_*` in
   `cli_library_db.py` and `cli.py` — not ad-hoc open/close in handlers.
5. `init_database` and `connect_catalog` remain the low-level openers **inside**
   the seam implementations (`managed_connections.py`, `db_init.py`,
   `lightroom/reader.py`) — not at product call sites.

Legitimate exceptions (allow-listed in the guardrail test):

- `managed_connections.py` and `jobs/handlers/db_lifecycle.py` — CM internals.
- `database/db_init.py` — defines `init_database`.
- Per-worker-thread sites that open a dedicated connection inside a pool worker
  (e.g. `sqlite3.connect` + `.close()` in a `ThreadPoolExecutor` callback) when
  the worker cannot share the coordinator connection.

A static guardrail test enforces (1)–(2) on migrated CLI and handler surfaces.

## Consequences

- One place to audit connection open/close semantics; parallel worker paths reuse
  the same CM or an explicitly allow-listed thread-local pattern.
- Slight indirection via `with managed_*`; acceptable for leak prevention and
  consistent PRAGMA setup through `init_database`.
- Scripts and legacy modules may still use hand-rolled lifecycle until migrated;
  the guardrail scans CLI/handler surfaces first and expands as migrations land.

## Alternatives considered

- **Hand-rolled `try`/`finally` at every call site** — rejected; duplicated,
  error-prone under parallel workers, and already the problem this seam fixes.
- **Single global connection** — rejected; visualizer workers and Flask request
  threads require per-thread connections (see `JobRunner.thread_db`).
