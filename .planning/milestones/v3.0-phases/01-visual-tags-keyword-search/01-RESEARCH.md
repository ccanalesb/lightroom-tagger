# Phase 1 — Visual tags & keyword search — Research

**Purpose:** Answer “What do I need to know to PLAN this phase well?” from the actual codebase and locked context (VIS-01, NLS-02).  
**Date:** 2026-04-23

---

## 1. Codebase Findings

### 1.1 `image_descriptions` schema (today)

Defined in `init_database` (`lightroom_tagger/core/database.py`):

- **PK:** `image_key TEXT PRIMARY KEY` (single key per row; `image_type` is **not** part of the PK — catalog and Instagram keys live in different namespaces in practice).
- **Columns:** `image_type`, `summary`, `composition`, `perspectives`, `technical`, `subjects`, `best_perspective`, `model_used`, `described_at`.
- **JSON stored as TEXT:** `composition`, `perspectives`, `technical`, `subjects` — via `_serialize_json` on write; `get_image_description` deserializes those four only.

There is **no** FTS5, no `search_text`, and no visual-tag columns yet (`grep` shows zero `fts5` / `FTS` in Python).

### 1.2 `store_image_description` (today)

```1801:1836:lightroom_tagger/core/database.py
def store_image_description(db: sqlite3.Connection, record: dict) -> str:
    ...
    with library_write(db):
        db.execute("""
            INSERT INTO image_descriptions
                (image_key, image_type, summary, composition, perspectives,
                 technical, subjects, best_perspective, model_used, described_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(image_key) DO UPDATE SET
                image_type=excluded.image_type, summary=excluded.summary,
                composition=excluded.composition, perspectives=excluded.perspectives,
                technical=excluded.technical, subjects=excluded.subjects,
                best_perspective=excluded.best_perspective, model_used=excluded.model_used,
                described_at=excluded.described_at
        """, (...))
```

- **Single write path** for library DB descriptions, already wrapped in `library_write` — correct place to add FTS sync (per locked D-04).
- **Extension:** new nullable columns + optional denormalized search document column; extend `INSERT`/`UPDATE` column lists accordingly.

### 1.3 `_store_structured` (today)

```143:160:lightroom_tagger/core/description_service.py
def _store_structured(
    db: sqlite3.Connection,
    image_key: str,
    image_type: str,
    structured: dict,
    model_used: str | None = None,
) -> None:
    store_image_description(db, {
        'image_key': image_key,
        'image_type': image_type,
        'summary': structured.get('summary', ''),
        'composition': structured.get('composition', {}),
        'perspectives': structured.get('perspectives', {}),
        'technical': structured.get('technical', {}),
        'subjects': structured.get('subjects', []),
        'best_perspective': structured.get('best_perspective', ''),
        'model_used': model_used or get_description_model(),
    })
```

- Confirmed extension point for VIS-01: map new LLM keys → `store_image_description` record fields here.

### 1.4 `query_catalog_images` (today)

```942:1099:lightroom_tagger/core/database.py
def query_catalog_images(
    db: sqlite3.Connection,
    *,
    posted: bool | None = None,
    month: str | None = None,
    keyword: str | None = None,
    ...
) -> tuple[list[dict], int]:
```

- **`keyword`:** `LIKE` on `images` table only (`keywords`, `filename`, `title`, `description`) — must remain unchanged for NLS-02 / locked D-09.
- **Join:** `LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog'`.
- **Extension:** add optional parameter (e.g. `description_search: str | None`). When non-empty after validation, constrain catalog rows by FTS-derived keys or rowids (see Implementation Approach). All dynamic SQL for this path should still use **bound parameters** for any user-derived fragments that end up as values; the FTS query string itself should be assembled only from sanitized tokens (never raw substring of user input pasted into SQL).

### 1.5 Prompt and structured output (today)

- **`prompt_builder.build_description_user_prompt`** builds the multi-perspective user message and ends with a **JSON template** including `summary`, `composition`, `perspectives`, `technical` (with **`technical.dominant_colors`** and **`technical.mood`** already documented), `subjects`, `best_perspective`.
- **`analyzer.DESCRIPTION_PROMPT`** (legacy monolithic) mirrors the same shape; **`parse_description_response`** returns a dict or `_DESCRIPTION_FALLBACK` (empty summary, empty nested defaults).
- **`describe_image`** passes `user_prompt` into provider or Ollama path; structured output is always parsed JSON from the model.

**Important overlap:** VIS-01 asks for top-level **`dominant_colors`**, **`mood_tags`**, **`has_repetition`** columns on `image_descriptions`, while the prompt already asks for **`technical.dominant_colors`** (hex list) and **`technical.mood`** (single word). Planner must decide: **duplicate vs derive** (e.g. copy/normalize from `technical` in `_store_structured`), or **narrow the new fields** (e.g. `mood_tags` as multi-tag vs `technical.mood` as single).

### 1.6 Catalog API (today)

`GET /api/images/catalog` in `apps/visualizer/backend/api/images.py`:

- Reads `keyword`, `month`, score filters, etc., and calls `query_catalog_images`.
- Validates `score_perspective` with `_CATALOG_SCORE_PERSPECTIVE_SLUG_RE` (allowlist style).
- **No** description-text search parameter yet — add one (locked: e.g. `description_search`) with length/sanitization rules (D-11–D-13).

### 1.7 Migration pattern (today)

- **New tables:** `CREATE TABLE IF NOT EXISTS` in `init_database` executescript.
- **Additive columns:** `_migrate_add_column(conn, table, column, col_type)` + `PRAGMA table_info` guard; used for `images`, `matches`, `instagram_dump_media`, etc.
- **One-shot data migrations:** `PRAGMA user_version` gates (e.g. `_migrate_unified_image_keys`, `_backfill_matched_catalog_key_from_validated_matches`).
- **FTS virtual table:** not present yet; add `CREATE VIRTUAL TABLE IF NOT EXISTS ... USING fts5(...)` in `init_database` (or a dedicated helper called from there), plus a **one-shot** `INSERT INTO ..._fts(..._fts) VALUES('rebuild')` after backfilling any denormalized search column on existing rows (per D-05 / D-18 in CONTEXT).

### 1.8 Batch describe selection (today) — backfill implication

`_select_catalog_keys` / `get_undescribed_catalog_images` treat “needs describe” as **no `image_descriptions` row** (`d.image_key IS NULL`).  

**VIS backfill** needs images that **already have** a description but **`dominant_colors` (or equivalent) IS NULL**. That is **not** expressible with current helpers alone.

```113:167:apps/visualizer/backend/jobs/handlers.py
def _select_catalog_keys(..., undescribed_only: bool, ...) -> list[tuple[str, str]]:
    if undescribed_only:
        sql = (
            "SELECT i.key AS key FROM images i "
            "LEFT JOIN image_descriptions d "
            "  ON i.key = d.image_key AND d.image_type = 'catalog' "
            "WHERE d.image_key IS NULL"
        )
```

- **Finding:** implementing D-18 requires **new metadata flag and/or SQL branch** (and likely a **`fingerprint_batch_describe`** field bump if the flag changes who gets selected — see Open Questions).

### 1.9 Frontend filter framework (today)

- **`SearchFilterDescriptor`** (`type: 'search'`) supports `paramName`, `debounceMs`, placeholder, `ariaLabel`, etc. (`components/filters/types.ts`).
- **`useFilters` → `toQueryParams`:** for `search`, empty string → param omitted; non-empty → `{ [paramName]: trimmed string }` (`hooks/useFilters.ts`).
- **`CatalogTab`** already has two search descriptors: `keyword` (Lightroom metadata) and `colorLabel` → `color_label`. Pagination reset on committed keyword/colorLabel changes uses `useRef` + `useEffect` — **a third search field** should follow the same pattern for page reset and `listParams` dependency list (`components/images/CatalogTab.tsx`).

### 1.10 Direct `store_image_description` call sites

Besides `description_service._store_structured`, **`lightroom_tagger/scripts/match_instagram_dump.py`** builds description records inline — any new required fields should remain **optional** for backward compatibility, or that script must be updated to pass new keys.

### 1.11 API / UI description JSON helpers

`apps/visualizer/backend/api/images.py` uses `_DESC_JSON_COLS = ('composition', 'perspectives', 'technical', 'subjects')` for `_deserialize_description`. New **JSON** columns on `image_descriptions` would need to be added to this tuple (or a sibling helper) anywhere the API returns raw description blobs.

---

## 2. Implementation Approach

### 2.1 Schema (VIS-01 + FTS prep)

1. **`ALTER TABLE image_descriptions ADD COLUMN`** (via `_migrate_add_column` pattern):
   - `dominant_colors TEXT` (JSON array as string, nullable)
   - `mood_tags TEXT` (JSON array as string, nullable)
   - `has_repetition INTEGER` (0/1, nullable)
2. **Denormalized search text** (recommended for clean FTS5 external content): e.g. `description_search_document TEXT` (nullable) holding `summary` plus space-joined flattened `subjects` (and optionally normalized whitespace). Maintained **only** in `store_image_description` when persisting / updating. Raw `subjects` JSON is **not** ideal to index directly (brackets/quotes noise).
3. **FTS5 virtual table** (locked: external content, `tokenize='porter unicode61'`):
   - Define a **single-column** FTS table whose column name **matches** the real column on `image_descriptions` (e.g. both named `description_search_document`) and use `content='image_descriptions'`, `content_rowid='rowid'`.
   - On existing DBs: after migrations, `UPDATE` backfill of `description_search_document` from existing `summary` + `subjects`, then `INSERT INTO <fts>(<fts>) VALUES('rebuild')` (per CONTEXT).

### 2.2 Python-side FTS sync (D-04)

Inside `store_image_description`, **after** the main upsert (still within `library_write`):

1. Resolve **`rowid`** for the `image_key` (e.g. `SELECT rowid FROM image_descriptions WHERE image_key = ?`).
2. Apply FTS5 maintenance for **external content** tables as documented by SQLite (delete prior FTS row for that `rowid` if needed, then insert; or use the supported `delete` / `insert` operations for the FTS table name).  
   Planner should copy the exact FTS5 vtab maintenance statements from SQLite docs for **external content** + manual updates (no triggers).

### 2.3 Describe pipeline extension

1. **`prompt_builder.build_description_user_prompt`:** extend the JSON template with **`dominant_colors`**, **`mood_tags`**, **`has_repetition`** (and brief rubric lines) at the **top level** of the JSON object, consistent with locked D-15 (one LLM call).
2. **`analyzer.DESCRIPTION_PROMPT`** and **`_DESCRIPTION_FALLBACK`:** keep legacy path aligned so `run_local_agent` / tests without DB perspectives still request the same keys.
3. **`_store_structured`:** map new keys; normalize types (e.g. `has_repetition` bool/int → 0/1; lists → JSON via existing patterns).
4. **`get_image_description`:** extend JSON deserialization tuple if new columns are JSON strings.

### 2.4 `query_catalog_images` + NLS-02

1. Add **`description_search: str | None`** (or locked name).
2. **Validation** (API or DB layer): strip; if raw length `< 2` **and** user supplied a non-empty query string, return 400 with clear message (D-12); if empty after trim/sanitization, treat as **no FTS filter** (D-13).
3. **Sanitize** (D-11): split on whitespace; strip FTS5-special characters per CONTEXT (`"*()-+^` etc.); drop empty tokens; build **`token1 AND token2 AND ...`** string.
4. **Query:** e.g. subselect matching `rowid`s or `image_key`s from `image_descriptions_fts` with **`MATCH ?`** binding the **entire** constructed query string — **no** f-string embedding of user text into SQL.
5. **Catalog scope:** FTS should apply only to **`image_type = 'catalog'`** rows (Instagram descriptions may share FTS table if rows exist in same content table — filter in subquery or add `image_type` to indexed document / side table; planner decides minimal correct pattern).

### 2.5 API layer

- Parse new query param in `list_catalog_images`; delegate validation to a small pure function (easily unit-testable).
- Return `error_bad_request` for too-short queries; mirror existing patterns (`min_score`, `score_perspective`).

### 2.6 Frontend

- Add a **`search` descriptor** with `paramName: 'description_search'` (or final chosen name), label/placeholder/strings in `constants/strings.ts`.
- Extend **`ImagesAPI.listCatalog`** params and `URLSearchParams` wiring.
- Update **`CatalogTab`** `listParams` `useMemo` deps + debounced page-reset `useEffect` to include the new committed search value (same as keyword/color).

### 2.7 Backfill job (D-18)

- Add metadata flag e.g. **`backfill_visual_tags`** or **`require_null_dominant_colors`** that changes selection SQL to: has description row **and** `dominant_colors IS NULL` (catalog and/or instagram as needed).
- **`force=True`** path currently uses `_select_catalog_keys(..., undescribed_only=False)` which selects **all** keys in the window — too broad for targeted backfill; the new flag should narrow selection explicitly.
- Update **`fingerprint_batch_describe`** canonical payload in `checkpoint.py` if the new flag changes work selection (so checkpoints invalidate correctly).

---

## 3. Key Risks & Landmines

| Risk | Why it hurts | Mitigation |
|------|----------------|------------|
| **Duplicate color/mood semantics** | `technical.dominant_colors` / `technical.mood` already in JSON; new columns might drift | Define single source of truth in PLAN; consider normalizing in `_store_structured` from `technical` when model omits top-level keys |
| **`image_descriptions` PK is only `image_key`** | Unusual vs composite `(image_key, image_type)`; if a key collision ever occurred, type would be overwritten | Acknowledge invariant; no change required for Phase 1 if keys stay namespace-separated |
| **FTS / JSON column mismatch** | External content FTS expects real table columns; indexing raw `subjects` JSON is noisy | Use denormalized `description_search_document` (or two real TEXT columns) aligned with fts5 `content=` |
| **Parallel describe workers** | `library_write` serializes writes; FTS ops must stay inside same transaction as description upsert | Keep FTS maintenance inside existing `with library_write(db):` block |
| **Legacy DBs / missing columns** | `test_catalog_legacy_db_missing_columns_returns_200` pattern exists for `images` | Add analogous confidence: `query_catalog_images` + migrations must not 500 when new columns absent before migration runs |
| **Batch describe pre-filter** | `already_described` skip uses `SELECT image_key FROM image_descriptions` without type filter | Re-describe / backfill may need **`force=True`** or different skip logic when targeting NULL visual columns |
| **Injection / “SQL from model”** | NLS-02 requires no raw user SQL | FTS query built only from sanitized tokens; **single bound parameter** to `MATCH`; rest of query uses placeholders |
| **API detail / matches** | `_deserialize_description` omits new columns | Any endpoint returning full description dicts must deserialize new JSON fields or clients see strings |

---

## 4. Files to Modify

| File | Change |
|------|--------|
| `lightroom_tagger/core/database.py` | Add columns + FTS vtab DDL/migration hooks; extend `store_image_description`; add FTS sync; extend `query_catalog_images`; optionally extend `get_image_description` deserialization; consider helper `build_description_search_document(summary, subjects)` |
| `lightroom_tagger/core/description_service.py` | Extend `_store_structured` for new fields |
| `lightroom_tagger/core/prompt_builder.py` | Extend JSON contract + instructions for visual tags |
| `lightroom_tagger/core/analyzer.py` | Align `DESCRIPTION_PROMPT` / `_DESCRIPTION_FALLBACK` with new keys |
| `apps/visualizer/backend/api/images.py` | New query param, validation, pass through to `query_catalog_images`; extend `_DESC_JSON_COLS` if API returns new JSON columns |
| `apps/visualizer/backend/jobs/handlers.py` | Backfill selection SQL / metadata branch for `dominant_colors IS NULL` (and Instagram parity if required) |
| `apps/visualizer/backend/jobs/checkpoint.py` | Extend `fingerprint_batch_describe` if new describe-selection metadata is introduced |
| `apps/visualizer/backend/tests/test_images_catalog_api.py` | Tests: FTS happy path, empty → no filter, short query → 400, injection-style inputs → no crash + parameterized `MATCH` |
| `lightroom_tagger/core/test_database.py` | Update `store_image_description` tests for new columns/FTS |
| `lightroom_tagger/core/test_description_service.py` | Mock/stub describe path if needed for new fields |
| `lightroom_tagger/scripts/match_instagram_dump.py` | If inline `store_image_description` dicts need new optional keys |
| `apps/visualizer/frontend/src/services/api.ts` | `listCatalog` param type + query string |
| `apps/visualizer/frontend/src/constants/strings.ts` | Labels/placeholders/aria for description search |
| `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` | New schema entry + `listParams` deps + page-reset effect |
| `apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx` | Assert `description_search` query param when typed (pattern from existing filter tests) |
| Optional UI | `DescriptionPanel` / `FullView.tsx` if product wants to **display** new tags in Phase 1 (VIS-02 is Phase 2 for facets; display may still be nice-to-have) |

---

## 5. Test Strategy

### 5.1 Backend (pytest)

- **`test_images_catalog_api.py`:**  
  - Insert rows with known `summary` / `subjects` / `description_search_document` and FTS rebuilt; `GET .../catalog?description_search=...` returns expected `total` / keys.  
  - **Too-short query** (e.g. 1 char) → **400**.  
  - **Omitted / empty** param → full catalog (or same as baseline).  
  - **Injection-ish strings** (quotes, `OR`, `;--`): assert **200** and stable results; optionally assert the executed statement never concatenates raw input (indirect: no `OperationalError`, predictable row count). Prefer a **unit test** on the sanitizer / query builder with golden outputs.
- **`test_database.py`:** `store_image_description` persists new columns; FTS row exists after write (if test uses in-memory DB + `init_database`).
- **Job handler tests (optional):** metadata flag selects only `dominant_colors IS NULL` rows when `force` + flag set.

### 5.2 Frontend (vitest)

- **`CatalogTab.test.tsx`:** new search field issues `listCatalog` with `description_search` (or final param name) in `URLSearchParams` after debounce/commit (mirror keyword test patterns).
- **`useFilters.test.ts`:** only if new edge cases (e.g. `paramName` override) appear.

### 5.3 Injection safety proof (planning requirement)

- Document invariant: **all** SQL uses `?` bindings for values; FTS **`MATCH`** receives **one** parameter assembled from **allowlisted/sanitized** tokens only.  
- Add at least one test proving malicious input does not broaden the result set via SQL injection (FTS syntax attacks may still change ranking/match — document as acceptable for Phase 1 or strip FTS operators per D-11).

---

## 6. Open Questions (for PLAN.md)

1. **Exact param name:** `description_search` vs `q` vs `desc_search` (CONTEXT defers).
2. **`dominant_colors` vs `technical.dominant_colors`:** single source of truth, or intentional duplication with normalization rules?
3. **`mood_tags` vs `technical.mood`:** multi-value tags vs one-word mood — prompt contract and fallback when model returns only `technical.mood`.
4. **FTS row scope:** index **catalog only** vs catalog + Instagram — NLS-02 speaks to catalog browse; confirm Instagram exclusion.
5. **FTS DDL column strategy:** one `description_search_document` vs multiple FTS columns; whether to expose BM25 `rank` in Phase 1 (CONTEXT defers ranking).
6. **Backfill metadata name & UX:** Analyze tab / job API: new checkbox vs implicit `force` + `min_rating` + filter flag; copy for users.
7. **`fingerprint_batch_describe`:** exact JSON key for the new selection mode so old checkpoints invalidate cleanly.
8. **400 vs silent ignore** for `< 2` chars: CONTEXT says “rejected at API with clear error” — confirm product preference vs strip to empty (no filter).

---

## RESEARCH COMPLETE
