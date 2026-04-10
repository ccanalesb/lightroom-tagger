---
status: issues_found
phase: 01
depth: quick
findings_count: 9
severity_summary:
  critical: 0
  warning: 5
  info: 4
---

# Phase 01 Code Review

## Summary
Production code is generally sound (parameterized SQL, path checks on catalog updates), but there are a few correctness and security-footgun issues: split config modules, a wrong type coercion for `match_threshold` from the environment, duplicate DB connections in schema CLIs, and thumbnail endpoints that trust filesystem paths stored in SQLite.

## Findings

### 1. warning — `lightroom_tagger/core/config.py` (lines 174–176)
**Description:** `MATCH_THRESHOLD` is applied with `int(value)`, while `match_threshold` is a float everywhere else (default `0.7`). Non-integer env values raise `ValueError`; integers silently change semantics.
**Suggestion:** Use `float(value)` for `match_threshold`, or parse explicitly and validate range.

### 2. warning — `lightroom_tagger/lightroom/schema.py` and `lightroom_tagger/schema_explorer.py` (`main`, ~134–148 / ~134–148)
**Description:** After `conn = connect_catalog(catalog_path)`, the non-`--all-tables` branch calls `explore_catalog(catalog_path)`, which opens a second connection. That wastes resources and can interact badly with `locking_mode=EXCLUSIVE` on the catalog.
**Suggestion:** Pass the existing `conn` into exploration (e.g. `get_key_tables(conn)` + wrap in the same try/finally), or drop the outer `connect_catalog` in that branch.

### 3. warning — `apps/visualizer/backend/api/images.py` (lines 191–196, 224–242)
**Description:** `send_file` uses `file_path` / resolved catalog paths from the library DB. Anyone who can alter the database (or a bug that writes attacker-controlled paths) could attempt arbitrary file reads via path traversal or absolute paths.
**Suggestion:** Resolve with `Path.resolve()`, enforce a prefix allowlist (e.g. under known photo roots or cache dir), or stat+reject paths outside expected roots.

### 4. warning — `apps/visualizer/backend/api/lt_config.py` (lines 31–45)
**Description:** `PUT /api/config/catalog` rewrites repo `config.yaml` with no authentication in this layer. Fine for trusted local use; risky if the backend is reachable on a network without other controls.
**Suggestion:** Gate behind auth, bind to localhost only, or document as a trusted-admin-only endpoint.

### 5. warning — `lightroom_tagger/catalog_reader.py` (line 6) vs `lightroom_tagger/cli.py` / `lightroom_tagger/core/config.py`
**Description:** `catalog_reader` and `schema_explorer` import `lightroom_tagger.config.load_config`, while the main CLI uses `lightroom_tagger.core.config`. The legacy `config` module is a different `Config` (fewer fields, different NAS rules, required `catalog_path`/`db_path` in the dataclass). Behavior and env coverage diverge; minimal YAML can fail `Config(**data)` on the legacy class.
**Suggestion:** Standardize on `core.config` for all entry points or make `lightroom_tagger.config` a thin re-export of `core.config`.

### 6. info — `lightroom_tagger/lightroom/reader.py` (lines 194–235)
**Description:** `get_image_records(..., workers=4)` documents parallel workers, but both branches perform the same sequential per-image fetches. The parameter is misleading dead API surface.
**Suggestion:** Remove `workers` until real parallelism exists, or implement safe batching (single connection or pooled read-only connections).

### 7. info — `apps/visualizer/backend/api/images.py` (lines 105–106, 143–144)
**Description:** Instagram listing loads all `instagram_dump_media` rows into memory before filtering/pagination. Large libraries risk high memory and slow responses. `success_paginated` is called and its return value is ignored—dead code.
**Suggestion:** Push filters/pagination to SQL; remove or use the `success_paginated` helper consistently.

### 8. info — `lightroom_tagger/lightroom/reader.py` (`main`, ~292–326)
**Description:** Only `sqlite3.Error` is caught. If `json.dump` or file I/O fails after `connect_catalog`, `conn.close()` may not run.
**Suggestion:** Use `try`/`finally` or context manager for the connection.

### 9. info — `apps/visualizer/backend/app.py` (lines 31–34, 58)
**Description:** Unconditional `DEBUG` prints may leak paths/config in logs. `SocketIO(..., cors_allowed_origins="*")` is permissive relative to the narrower Flask CORS list.
**Suggestion:** Use logging at DEBUG level behind a flag; align SocketIO CORS with `config.FRONTEND_URL`.
