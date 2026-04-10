# Phase 1: Catalog Management — Research

## Summary

The visualizer already lists catalog rows from the **library SQLite** (`LIBRARY_DB`) with posted/month filters, pagination in the UI, and thumbnails keyed by `images.key`. Gaps for Phase 1 are: **no UI for catalog path** (still `config.yaml` / `LIGHTRoom_CATALOG` + CLI scan), **`/images/catalog` loads the full `images` table into memory** before filtering, **search helpers in `core/database.py` are unused by the API**, **two different catalog connection implementations** (CLI vs `lightroom/reader.py`), and **identity split** between composite `key` (date+filename) and Lightroom `id_local`. Enforcing **read-only SQLite URIs** on every read path and unifying keys / promoting `id_local` are the main technical pillars for CAT-04/CAT-05.

## Current State Analysis

| Requirement | What exists | What’s missing / risk |
|-------------|-------------|------------------------|
| **CAT-01** Register `.lrcat` | `load_config()` reads `catalog_path` from `config.yaml` + env (`LIGHTRoom_CATALOG`). Visualizer `app.py` loads the same config for NAS env hints. | No settings UI or HTTP API to set path; user must edit files / env. No “active catalog” summary endpoint for the UI (path, exists, last scan). |
| **CAT-02** Browse + pagination | `GET /images/catalog` supports `limit`, `offset`, `posted`, `month`. `CatalogTab.tsx` uses `Pagination`, `LIMIT=50`. | Backend still runs `SELECT * FROM images` then filters/slices in Python — **O(n) memory and CPU per request**, will degrade on large libraries. |
| **CAT-03** Search / filter | `search_by_keyword`, `search_by_rating`, `search_by_date`, `search_by_color_label`, `search_by_instagram_posted` in `lightroom_tagger/core/database.py`. Posted + month filters already in API/UI. | Those five search functions are **not imported or used** in `apps/visualizer/backend/api/images.py`. No query params or UI for keyword, rating, color label, arbitrary date range (only month). Combining filters needs a defined semantics (AND vs OR). |
| **CAT-04** Stable identity | Reader sets `record["id"]` = `AgLibraryFile.id_local` and `record["key"]` via `generate_record_key` (date **YYYY-MM-DD** + filename). `store_image()` **recomputes** primary key with `generate_key()` using **full** `date_taken` string — so stored `key` follows DB helper, not reader’s `generate_record_key`. Thumbnails and matches use `key`. Frontend `CatalogImage.id` expects a number; DB column `id` is TEXT. | Unify secondary key format (CONTEXT D-06). Plan migration to **`id_local` (plus `catalog_path` when multi-catalog)** as canonical identity; today `matches`, `vision_cache`, `image_descriptions` all hang off TEXT `catalog_key` / `image_key`. |
| **CAT-05** Safe reads | `lightroom_tagger/lightroom/reader.py` documents WAL/NAS issues and sets `PRAGMA locking_mode=EXCLUSIVE` (optional via env). **`lightroom_tagger/catalog_reader.py`** (used by **`lightroom_tagger/cli.py` scan**) uses plain `sqlite3.connect(catalog_path)` — **no read-only URI, no EXCLUSIVE workaround**. `lightroom/writer.py` uses a **separate** `connect_catalog` — write path isolated. | Apply read-only + consistent connection policy to **all** catalog read entry points (`catalog_reader`, any scripts using raw `connect`). Document read vs write surfaces (reader vs writer vs `cleanup_wrong_links` etc.). |

## Technical Findings

### Current codebase — reader and scan pipeline

- **Canonical advanced reader:** `lightroom_tagger/lightroom/reader.py` — `connect_catalog()`, `generate_record_key()`, `get_image_records()`, per-image keyword fetch, NAS-oriented locking notes.
- **CLI scan path:** `lightroom_tagger/cli.py` imports `connect_catalog`, `get_image_records` from **`lightroom_tagger.catalog_reader`**, which duplicates reader logic with a **minimal** `connect_catalog` (no `mode=ro`, no `locking_mode` pragma).

```9:13:lightroom_tagger/catalog_reader.py
def connect_catalog(catalog_path: str) -> sqlite3.Connection:
    """Connect to Lightroom catalog."""
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    return conn
```

```10:30:lightroom_tagger/lightroom/reader.py
def connect_catalog(catalog_path: str) -> sqlite3.Connection:
    """Connect to Lightroom catalog.
    ...
    """
    conn = sqlite3.connect(catalog_path, timeout=30.0)
    if os.getenv("LIGHTRoom_CATALOG_LOCKING_MODE", "EXCLUSIVE").upper() == "EXCLUSIVE":
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
    conn.row_factory = sqlite3.Row
    return conn
```

**Planning implication:** Phase 1 should either **switch CLI to `lightroom.reader`** or **duplicate the same connection policy** in `catalog_reader.py` so scan and any other callers cannot open the catalog writable while claiming “safe read.”

### App DB schema and identity (`core/database.py`)

- `images` table: `key TEXT PRIMARY KEY`, `id TEXT` (Lightroom id), JSON-ish `keywords`, indexes on `filepath`, `date_taken`, `instagram_posted`, etc.
- `generate_key(record)` uses **full** `date_taken` + `filename` (no date truncation).
- `store_image` upserts on `key` and does **not** update `id` on conflict (ON CONFLICT clause omits `id`) — stale `id` possible if row existed; worth a quick audit when changing identity strategy.

**Secondary key inconsistency** (CONTEXT D-06):

```54:59:lightroom_tagger/lightroom/reader.py
def generate_record_key(record: dict) -> str:
    """Generate unique key: {date_taken}_{filename}"""
    date_taken = record.get("date_taken", "unknown")
    date_part = date_taken[:10] if date_taken else "unknown"
    filename = record.get("filename", "unknown")
    return f"{date_part}_{filename}"
```

```250:254:lightroom_tagger/core/database.py
def generate_key(record: dict) -> str:
    """Generate unique key from record: {date_taken}_{filename}"""
    date_taken = record.get('date_taken', 'unknown')
    filename = record.get('filename', 'unknown')
    return f"{date_taken}_{filename}"
```

### Visualizer `/images/catalog` and frontend

```263:294:apps/visualizer/backend/api/images.py
@bp.route('/catalog', methods=['GET'])
@with_db
def list_catalog_images(db):
    """List catalog images with optional filtering by posted status and date_taken month."""
    try:
        images = db.execute("SELECT * FROM images").fetchall()
        ...
        if month and len(month) == 6:  # YYYYMM format
            ...
        paginated = images[offset:offset+limit]
        return jsonify({
            'total': len(images),
            'images': paginated,
        })
```

- **Gap:** No use of `search_by_*` from `core/database.py`.
- **Performance:** Full-table load + Python filtering; same anti-pattern as Pitfall 7 in `.planning/research/PITFALLS.md`.

`CatalogTab.tsx` follows established patterns: `useState` / `useCallback` / `useEffect`, Tailwind (`border-border`, `rounded-base`, `focus:ring-accent`), paired `<select>` filters + clear, `Pagination` for grid. New filters should match this (inputs from `components/ui/` per CONTEXT).

**Thumbnail and identity in UI:** Cards use `image.key` in thumbnail URLs; React list key uses `image.id` — ensure uniqueness if `id` is null/duplicate during migration.

```20:24:apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx
        <img
          src={`/api/images/catalog/${encodeURIComponent(image.key)}/thumbnail`}
          alt={image.filename}
```

### SQLite read-only URI (`?mode=ro`)

- **Pattern:** `sqlite3.connect(path, uri=True)` with URI `file:...?mode=ro` (SQLite [URI documentation](https://www.sqlite.org/uri.html)).
- **Path safety:** Prefer `Path(catalog_path).resolve().as_uri()` then append `?mode=ro` so spaces and Unicode are encoded; on Windows you get `file:///C:/...`.
- **Interaction with current reader:** After opening RO, **`PRAGMA locking_mode=EXCLUSIVE` may be unnecessary or different in effect** — RO connections cannot mutate the DB; NAS/WAL behavior should be **re-tested** on the user’s failure modes (CONTEXT D-07). If EXCLUSIVE is still needed for WAL-without-shm, validate that it does not block legitimate concurrent read-only tools.
- **Lightroom lock:** Read-only does not remove `database is locked` if Lightroom holds an incompatible lock; product docs should still say “prefer catalog closed or expect lock errors.”
- **Gotcha:** Any code path that **creates** `-wal`/`-shm` or runs write PRAGMAs must stay on the writer connection only.

### Search / filter wiring

Existing functions (all return **full row lists**, no pagination):

- `search_by_keyword` — `LIKE` on `keywords`, `filename`, `title`, `description` (keywords stored as JSON string — substring match is brittle but matches current storage).
- `search_by_rating` — `rating >= min_rating`
- `search_by_date` — `date_taken` range (ISO string compare relies on consistent formatting)
- `search_by_color_label` — case-insensitive equality
- `search_by_instagram_posted` — boolean

**Wiring options for PLAN.md:**

1. **Minimal:** Call these from the route, **intersect** result sets in Python for AND semantics, then paginate — still needs a candidate set smaller than “all images” for scale, or accept Phase 1 scope for moderate catalogs only.
2. **Better:** Add one SQL builder / parameterized query in `core/database.py` (filter + count + `LIMIT/OFFSET`) and deprecate “load all” for `/images/catalog`.
3. **API shape:** Mirror existing query style: `keyword`, `min_rating`, `date_from`, `date_to`, `color_label`, `posted`, `month`, `limit`, `offset`.

Frontend: extend `ImagesAPI.listCatalog` in `api.ts` with the same query params; add controls in `CatalogTab.tsx`.

### Config-driven registration and settings UI

- **Library DB path:** `apps/visualizer/backend/config.py` — `LIBRARY_DB` (default `library.db`), `DATABASE_PATH` for jobs DB.
- **Catalog path:** Not in Flask `config.py`; comes from **`lightroom_tagger/core/config.py`** `load_config("config.yaml")` with cwd-dependent relative paths in YAML.
- **Visualizer** already calls `load_lt_config()` at startup for NAS env (`app.py`).

**For a settings panel (CONTEXT D-01):**

- Add authenticated or **local-trust-only** endpoints (this is a local dev app; document threat model) e.g. `GET/PUT /api/config/catalog` that read/write the **same** `config.yaml` the CLI uses — resolve **absolute path to repo root** `config.yaml` consistently from `apps/visualizer/backend` (same pattern as `REPO_ROOT` in `app.py`).
- Validate `.lrcat` exists and is a file; optionally stat size/mtime for UI.
- After path change, user still needs a **scan/import** to refresh `images` (unless Phase 1 adds “scan” job trigger from UI — optional scope).
- **Alternative:** Write only `LIGHTRoom_CATALOG` into `.env` — diverges from “single source of truth” unless CLI also prefers env (it already merges env into config).

### Writer separation (reference)

```6:10:lightroom_tagger/lightroom/writer.py
def connect_catalog(catalog_path: str) -> sqlite3.Connection:
    """Connect to Lightroom catalog."""
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    return conn
```

Reader read-only changes **must not** alter this module. `get_image_local_id` in `writer.py` still parses **`image_key` string** (`date_filename`) — migrating to `id_local` as primary will require **follow-up writer/match glue** in a later phase or coordinated changes; PLAN should sequence identity migration before IG writeback tests.

### Design system

`DESIGN.md`: Inter, warm neutrals, single accent, `Input` / `Button` / `Card` / `Badge` patterns. New settings and filters should reuse `components/ui/` and semantic Tailwind tokens (`border-border`, `text-text-secondary`, etc.).

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Two readers diverge** (CLI vs `lightroom.reader`) | Single implementation or shared `connect_catalog` helper used everywhere reads happen. |
| **Read-only URI breaks NAS/WAL edge case** | Test on user’s SMB/NAS catalog copies; keep env toggle to fall back (similar to `LIGHTRoom_CATALOG_LOCKING_MODE`). |
| **Primary key migration breaks matches/cache/descriptions** | Scripted migration: map old `key` → new key or add `lr_id_local` + `catalog_path` composite; update foreign references in one transaction; backup `library.db` first. |
| **Full-table `SELECT *` for browse** | Move filtering/pagination to SQL in Phase 1 or explicitly defer with documented catalog size limit. |
| **Keyword search on JSON text** | Acceptable for v1; later normalize to FTS or keyword table mirror if needed. |
| **Config write API** | Path validation, symlink hardening, and clear “restart scan” UX; avoid exposing arbitrary file write. |
| **Lightroom schema versions** | CONTEXT + SUMMARY: keep version matrix and test queries on real catalog copies (research/SUMMARY.md). |

## Implementation Recommendations

Suggested order (dependencies first):

1. **Unify catalog read connection** — Implement `file:…?mode=ro` + timeout in one place; switch `cli.py` (and any other imports) off `catalog_reader` duplicate or align `catalog_reader` with `lightroom.reader`.
2. **Unify `generate_key` / `generate_record_key`** — Pick one date format for the composite key; re-scan or one-off migration for existing rows if keys change.
3. **Promote stable Lightroom identity** — Backfill/use `id_local` in API responses and internal references; design DB migration for PK/FK (`matches`, `vision_cache`, `image_descriptions`, thumbnails route) — can be sub-phased if large.
4. **SQL-level list + filters** — Replace full load in `list_catalog_images` with filtered query + count; wire keyword, rating, date range, color label, posted.
5. **Frontend filters + `api.ts`** — Extend `listCatalog` params; mirror `CatalogTab` select/input patterns.
6. **Settings API + UI** — Read/write `catalog_path` via same `config.yaml` as CLI; show active path and link to re-scan workflow.
7. **Documentation** — Short developer note: read paths use RO SQLite; writes only via `lightroom/writer.py` (and backup policy in Phase 2).

## RESEARCH COMPLETE
