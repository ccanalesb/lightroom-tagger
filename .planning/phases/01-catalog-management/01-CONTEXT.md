# Phase 1: Catalog Management - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Register `.lrcat` files, browse and search photos safely with stable identity across sessions. Most browsing/pagination infrastructure is already built — this phase closes gaps in catalog registration UI, search depth, photo identity robustness, and read-only safety.

</domain>

<decisions>
## Implementation Decisions

### Catalog Registration (CAT-01)
- **D-01:** Config-driven catalog path stays as the source of truth (CLI unchanged). Add a UI settings panel in the visualizer that reads and writes the same config the CLI uses — no new "registration" concept, just surfacing the existing config.

### Search & Filter Depth (CAT-03)
- **D-02:** Expose all existing `core/database.py` search functions in the visualizer API and frontend: keyword text search, minimum star rating, date range, color label, and posted status (already present).
- **D-03:** The core library already implements these (`search_by_keyword`, `search_by_rating`, `search_by_date`, `search_by_color_label`, `search_by_instagram_posted`) — the work is wiring them into the `/images/catalog` endpoint and adding filter UI controls.

### Photo Identity Strategy (CAT-04)
- **D-04:** Switch primary identity to Lightroom's `id_local` (from `AgLibraryFile.id_local`). The reader already fetches this as the `id` field. Keep the `date_taken + filename` key as a secondary/display field.
- **D-05:** `id_local` is catalog-scoped (different catalog = different ID for the same photo). This is correct behavior since each catalog entry is distinct.
- **D-06:** Fix the inconsistency between `reader.py`'s `generate_record_key` (uses `date_taken[:10]`) and `core/database.py`'s `generate_key` (uses full `date_taken` string) — unify to one format for the secondary key.

### Read-Only Enforcement (CAT-05)
- **D-07:** Change `connect_catalog()` in `lightroom_tagger/lightroom/reader.py` to use SQLite read-only mode: `sqlite3.connect(f"file:{catalog_path}?mode=ro", uri=True, timeout=30.0)`. This guarantees the catalog can't be modified through the reader connection, even by accident.
- **D-08:** The writer (`lightroom_tagger/lightroom/writer.py`) keeps its own separate read-write connection — unaffected by this change.

### Claude's Discretion
- Filter UI layout and control placement in CatalogTab
- Whether to refactor `list_catalog_images` to use SQL-level filtering (instead of Python-level) as part of this phase or defer scalability improvements

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Catalog reader
- `lightroom_tagger/lightroom/reader.py` — Lightroom SQLite reader, `connect_catalog()`, `generate_record_key()`, `get_image_records()`
- `lightroom_tagger/core/database.py` — App database with search functions (`search_by_keyword`, `search_by_rating`, `search_by_date`, `search_by_color_label`), `generate_key()`, `init_database()` schema

### Visualizer backend
- `apps/visualizer/backend/api/images.py` — `/images/catalog` endpoint, current posted+month filtering
- `apps/visualizer/backend/config.py` — Environment-based config (`LIBRARY_DB`, `DATABASE_PATH`)

### Visualizer frontend
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — Catalog browsing UI with pagination and current filters
- `apps/visualizer/frontend/src/services/api.ts` — API client (`ImagesAPI.listCatalog`)

### Writer (reference only — not modified in this phase)
- `lightroom_tagger/lightroom/writer.py` — Keyword writeback connection (separate from reader)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CatalogTab.tsx` — Full browsing grid with pagination, posted/month filters; extend with new filter controls
- `Pagination.tsx` — Generic pagination component, already working
- `CatalogImageCard.tsx` / `CatalogImageModal.tsx` — Image display components
- `Input`, `Badge`, `Button`, `Card` — UI component library in `frontend/src/components/ui/`
- `search_by_*` functions in `core/database.py` — All search logic exists, just not wired to the API

### Established Patterns
- Backend: Flask blueprints with `@with_db` decorator for connection management
- Frontend: React with hooks, Tailwind CSS, Vite
- Config: Environment variables via `.env` / `dotenv`
- DB access: `with_db` provides SQLite connection per request

### Integration Points
- `/images/catalog` endpoint — add query params for keyword, rating, color_label, date_from, date_to
- `CatalogTab.tsx` — add filter controls above the image grid
- `api.ts` `ImagesAPI.listCatalog()` — extend params to include new filters
- `connect_catalog()` — single-line change for read-only mode
- `images` table schema — primary key migration from `key TEXT` to `id_local INTEGER` (or add `lr_id` column)

</code_context>

<specifics>
## Specific Ideas

- Settings panel should modify the same config the CLI reads — not a separate config store
- All five search dimensions available in v1: keyword, rating, date range, color label, posted status

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-catalog-management*
*Context gathered: 2026-04-10*
