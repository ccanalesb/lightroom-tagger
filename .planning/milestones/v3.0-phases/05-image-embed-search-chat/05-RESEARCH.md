# Phase 5 Research: Image Embed & Search Chat

## RESEARCH COMPLETE

## Summary

Phase 5 splits cleanly into a **catalog-side batch job** (mirror `batch_text_embed`) and a **visualizer orchestration + UI** path. The job adds a **second sqlite-vec virtual table** with **512-dimensional cosine vectors** (CLIP) alongside the existing **768-dim text** table—vec0 tables are homogeneous in dimension, so a separate `CREATE VIRTUAL TABLE … vec0(float[512]…)` migration is required, ideally gated by **`PRAGMA user_version`** (next bump after the current `4` used by text embeddings). The **CLIP encoder** should live in a sibling module to `embedding_service.py` (e.g. `clip_embedding_service.py`) using the same lazy singleton `SentenceTransformer` pattern, **`normalize_embeddings=True`**, and **`sqlite_vec.serialize_float32`** for blobs. The **chat search** endpoint should **compose** existing primitives: extend the NL path to accept **multi-turn messages** (today `complete_chat_text` is fixed **system + single user**), run **`parse_catalog_nl_filter_from_llm` → `catalog_nl_filter_to_query_kwargs`**, then treat **“no effective filters”** as the trigger for **`run_semantic_hybrid_search`** (same as `POST /api/images/semantic-search`) using the **latest user utterance** (or full thread flattened—planner choice) as the semantic query string. The frontend adds **`/search`** with **`Layout` nav + `App.tsx` route**, a **split flex/grid layout** (~40/60), **client-side `messages` state**, and a results pane that **reuses `TileGrid` + `ImageTile` + `fromCatalogListRow`** from `CatalogTab.tsx` (without the heavy `FilterBar`).

## 1. Codebase Patterns

### batch_text_embed Pattern (replicate for batch_embed_image)

**Registration:** `JOB_HANDLERS` in `apps/visualizer/backend/jobs/handlers.py` maps `'batch_text_embed': handle_batch_text_embed`. **`JOB_TYPES_REQUIRING_CATALOG`** in `apps/visualizer/backend/library_db.py` must include any new job type that calls `init_database` on the library path.

**Outer handler:**

```2283:2286:apps/visualizer/backend/jobs/handlers.py
def handle_batch_text_embed(runner, job_id: str, metadata: dict) -> None:
    """Embed catalog description text into ``image_text_embeddings`` (sqlite-vec)."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_text_embed_inner(runner, job_id, metadata)
```

**Inner flow (`_handle_batch_text_embed_inner`):**

- Enforces `metadata['image_type'] == 'catalog'` (non-catalog → `fail_job` warning).
- `_resolve_library_db_or_fail` → `init_database(db_path)`.
- `_resolve_date_window(metadata)` + optional `min_rating` (same knobs as describe/embed jobs).
- **`force`:** `list_catalog_keys_for_text_embed_force` vs incremental **`list_catalog_keys_needing_text_embedding`**.
- **`fingerprint_batch_text_embed(metadata, full_list)`** then checkpoint restore: `checkpoint_version == 1`, `job_type == 'batch_text_embed'`, matching `fingerprint` → restore `processed_pairs` set; else log `checkpoint mismatch: batch_text_embed fingerprint changed, starting fresh`.
- **`pair_label(key, itype)`** = `f'{key}|{itype}'`; remaining work = keys not in `processed_pairs`.
- Progress: **5%** after work discovery; **5–95%** linear in `embedded / total_at_start`; completion **clears checkpoint**.
- **`persist_checkpoint`:** `job_type`, `fingerprint`, **`processed_pairs`** (sorted on persist), `total_at_start`; cap **`_CHECKPOINT_MAX_ENTRIES` (100_000)** or `fail_job`.
- Batch size **16** in current code; each item: load text from `image_descriptions`, skip if no embeddable document (`skipped++`, still add to `processed_pairs`).
- **`flush_batch`:** `embed_texts` → `numpy_to_vec_blob` → `library_write` + **`upsert_image_text_embedding`** per row.
- **`complete_job` result keys:** `embedded`, `skipped`, `failed`, `total` (same shape should be mirrored for image embed, adjusting semantics).

### sqlite-vec Migration Pattern

**Extension load** (already global for the connection):

```206:209:lightroom_tagger/core/database.py
def _ensure_sqlite_vec_loaded(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
```

**Text embeddings migration** (user_version gate **3 → 4**): drop + create vec0, then bump version.

```775:793:lightroom_tagger/core/database.py
def _migrate_image_text_embeddings_vec0(conn: sqlite3.Connection) -> None:
    """Create sqlite-vec vec0 table for catalog text embeddings (user_version 3 → 4)."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_uv = int(row["user_version"] if row else 0)
    if current_uv >= 4:
        return
    try:
        conn.execute("DROP TABLE IF EXISTS image_text_embeddings")
        conn.execute(
            """
            CREATE VIRTUAL TABLE image_text_embeddings USING vec0(
              embedding float[768] distance_metric=cosine,
              image_key TEXT
            );
            """
        )
    except sqlite3.OperationalError:
        return
    conn.execute("PRAGMA user_version = 4")
```

**Replication for CLIP:** add `_migrate_image_clip_embeddings_vec0` (name discretionary) with **`float[512]`**, distinct table name (e.g. `image_clip_embeddings`), gate **`current_uv >= 5`** (or next free integer after `4`), call from `init_database` **after** `_migrate_image_text_embeddings_vec0`. Do **not** mix 768- and 512-dim rows in one vec0 table.

### fingerprint_batch_text_embed Pattern

```81:102:apps/visualizer/backend/jobs/checkpoint.py
def fingerprint_batch_text_embed(
    metadata: dict[str, Any], ordered_pairs: list[tuple[str, str]]
) -> str:
    """SHA-256 hex of canonical JSON for batch_text_embed inputs and ordered pair list."""
    min_rating_raw = metadata.get("min_rating")
    min_rating: int | None
    try:
        min_rating = int(min_rating_raw) if min_rating_raw is not None else None
    except (TypeError, ValueError):
        min_rating = None
    pairs = sorted(f"{key}|{itype}" for key, itype in ordered_pairs)
    payload = {
        "date_filter": metadata.get("date_filter", "all"),
        "embedding_dim": TEXT_EMBED_DIM,
        "embedding_model_id": TEXT_EMBED_MODEL_ID,
        "force": bool(metadata.get("force", False)),
        "image_type": str(metadata.get("image_type", "catalog")),
        "min_rating": min_rating,
        "pairs": pairs,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**Replicate as `fingerprint_batch_embed_image`:** same JSON shape, but import **`CLIP_EMBED_DIM` / `CLIP_EMBED_MODEL_ID`** (512, `"clip-ViT-B-32"` per `05-CONTEXT.md`). Extend `checkpoint.py` module docstring with a **`batch_embed_image`** bullet (mirror `batch_text_embed`).

**SIM-01 “skip unchanged”:** today text embed skips when a vec row exists (incremental list) unless `force`; optional **per-image content fingerprint** (e.g. hash of `filepath` + `file_size` or `analyzed_at`) can be stored in a small relational side table or extra columns if product requires re-embed only when file changes—planner can scope minimal v1 as “same as text embed: skip if vec exists.”

### embedding_service.py Structure

```1:51:lightroom_tagger/core/embedding_service.py
from __future__ import annotations

import numpy as np
import sqlite_vec
from sentence_transformers import SentenceTransformer

TEXT_EMBED_MODEL_ID = "sentence-transformers/all-mpnet-base-v2"
TEXT_EMBED_DIM = 768

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(TEXT_EMBED_MODEL_ID)
    return _model


def embed_texts(texts: list[str], *, batch_size: int = 24) -> np.ndarray:
    raw = _get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return np.asarray(raw, dtype=np.float32)
// ... numpy_to_vec_blob asserts TEXT_EMBED_DIM, serialize_float32 ...
```

**Extension strategy:** add **`clip_embedding_service.py`** with `CLIP_EMBED_MODEL_ID` (`"clip-ViT-B-32"` or full HF id if needed), `CLIP_EMBED_DIM = 512`, lazy model, **`encode_images`** (PIL/bytes paths—batch), **`encode_texts_for_clip`** for query vectors, and **`numpy_to_vec_blob`** asserting **512**. Keeps mpnet and CLIP **separate singletons** and avoids dimension assert collisions.

### NL-Search Endpoint

**Route:** `POST /api/images/nl-search`  
**Request body:** JSON dict; required non-empty **`query`** string; optional **`provider_id`**, **`model`**, **`limit`**, **`offset`**.

```582:624:apps/visualizer/backend/api/images.py
@bp.route('/nl-search', methods=['POST'])
@with_db
def nl_search_images(db):
    """Natural language → LLM filter JSON → same row shape as GET /api/images/catalog."""
    try:
        body = request.get_json(silent=True)
        if not body or not isinstance(body, dict):
            return error_bad_request('JSON body required')

        query = (body.get('query') or '')
        if not str(query).strip():
            return error_bad_request('query must be non-empty')
        // ...
            raw = nl_catalog_search.run_nl_catalog_filter_llm(
                str(query).strip(),
                provider_id=body.get('provider_id'),
                model=body.get('model'),
                log_callback=None,
            )
            filters = parse_catalog_nl_filter_from_llm(raw)
        // ...
        return jsonify({
            'filters': filters.model_dump(exclude_none=True),
            'total': total,
            'images': images,
        })
```

**Response:** `{ filters, total, images }` — **`images`** are catalog API rows via **`_rows_to_catalog_api_images`**.

**Multi-turn gap:** `run_nl_catalog_filter_llm` takes a **single `user_text`** and calls **`complete_chat_text(..., system=..., user=user_text)`** — no history. Phase 5 requires a **new** LLM entry (e.g. `complete_chat_messages` or overload) and a **`run_nl_catalog_filter_llm_multi`** that supplies **OpenAI-style `messages`**.

### Semantic Search Endpoint

**Route:** `POST /api/images/semantic-search`  
**Request:** JSON with non-empty **`query`** (≥2 chars after trim); optional **`limit`**, **`offset`**, **`score_perspective`** (slug validated).

```629:692:apps/visualizer/backend/api/images.py
@bp.route('/semantic-search', methods=['POST'])
@with_db
def semantic_search_images(db):
    """Hybrid FTS + embedding search with RRF; same catalog row shape as NL search + score / why_matched / thumbnail_url."""
    // ...
        blob = embed_query_to_vec_blob(qstrip)
        rows, total, meta = run_semantic_hybrid_search(
            db,
            user_query=qstrip,
            fts_match=match_str,
            query_vec_blob=blob,
            limit=limit,
            offset=offset,
        )
        // merge sem_row → score, why_matched, thumbnail_url per image
        return jsonify({
            'total': total,
            'images': images,
            'metadata': {
                'missing_embeddings_count': meta.missing_embeddings_count,
                'semantic_index_empty': meta.semantic_index_empty,
                'rrf_k': meta.rrf_k,
                'fts_no_match': meta.fts_no_match,
            },
        })
```

**Response:** `{ total, images, metadata }` — hybrid uses **mpnet** embedding via **`embed_query_to_vec_blob`** today; **CLIP text→image KNN** is explicitly optional for Phase 5 vs Phase 6 per `05-CONTEXT.md`.

### CatalogTab Grid Rendering

Key reuse for `/search` results pane:

- **`TileGrid`** wrapper, **`ImageTile`** with **`fromCatalogListRow(image)`**, **`variant="grid"`**, **`primaryScoreSource="catalog"`**, **`onClick`** → `ImageDetailModal` pattern.
- Loading: `useTransition` + opacity on grid (optional).
- Empty states: centered illustration + title + secondary line (two branches: no DB vs filtered empty).

```372:383:apps/visualizer/frontend/src/components/images/CatalogTab.tsx
          <div className={`relative transition-opacity duration-150${isPending ? ' opacity-50 pointer-events-none' : ''}`}>
            <TileGrid>
              {images.map((image) => (
                <ImageTile
                  key={image.id != null ? String(image.id) : image.key}
                  image={fromCatalogListRow(image)}
                  variant="grid"
                  primaryScoreSource="catalog"
                  onClick={() => setSelected({ key: image.key, initial: image })}
                />
              ))}
            </TileGrid>
          </div>
```

Extracting a thin **`CatalogResultGrid`** presentational component is optional; **do not** pull in `FilterBar` / `useFilters` for search chat.

### Layout Nav + Route Registration

**Nav items** are `{ to, label, exact? }` passed to **`NavLink`**:

```13:19:apps/visualizer/frontend/src/components/Layout.tsx
  const navItems = [
    { to: '/', label: NAV_INSIGHTS, exact: true },
    { to: '/images', label: NAV_IMAGES },
    { to: '/analytics', label: NAV_ANALYTICS },
    { to: '/identity', label: NAV_IDENTITY },
    { to: '/processing', label: NAV_PROCESSING },
  ];
```

Add **`{ to: '/search', label: NAV_SEARCH }`** (new string in `constants/strings.ts`) in the same array; desktop + mobile nav both map over `navItems`.

**Routes** nest under `Layout`:

```18:24:apps/visualizer/frontend/src/App.tsx
            <Route path="/" element={<Layout />}>
              <Route index element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
              <Route path="images" element={<ErrorBoundary><ImagesPage /></ErrorBoundary>} />
              <Route path="analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
              <Route path="identity" element={<ErrorBoundary><IdentityPage /></ErrorBoundary>} />
              <Route path="processing" element={<ErrorBoundary><ProcessingPage /></ErrorBoundary>} />
```

Add **`SearchPage`** lazy or static import + **`<Route path="search" element={…} />`** with **`ErrorBoundary`**, matching other pages.

## 2. sqlite-vec CLIP Table Design

- **Separate virtual table** from `image_text_embeddings` (768 vs 512).
- **Suggested DDL** (mirror text table, swap dim):

```sql
CREATE VIRTUAL TABLE image_clip_embeddings USING vec0(
  embedding float[512] distance_metric=cosine,
  image_key TEXT
);
```

- **Coexistence:** same DB file, same `sqlite_vec.load(conn)`; queries join **`images.key`** to **`image_clip_embeddings.image_key`** for Phase 6 similarity; **never** mix vec blobs across models in one vec0 column.
- **Upsert pattern:** identical to **`upsert_image_text_embedding`**: `DELETE … WHERE image_key = ?` then `INSERT INTO … (embedding, image_key) VALUES (?, ?)` inside **`library_write`**.
- **Migration:** bump **`user_version`** once per logical migration (e.g. **4 → 5** after text embed migration). Use **`DROP TABLE IF EXISTS`** only when acceptable for dev rebuild; production may prefer idempotent **`CREATE IF NOT EXISTS`** if vec0 supports it—match existing text migration style (Phase 3 used drop+create on upgrade).

## 3. sentence-transformers CLIP Usage

- **Model:** `SentenceTransformer('clip-ViT-B-32')` (see [Hugging Face card](https://huggingface.co/sentence-transformers/clip-ViT-B-32) and [image search examples](https://www.sbert.net/examples/applications/image-search/README.html)).
- **Image encode:** `model.encode(PIL.Image.open(path), normalize_embeddings=True, convert_to_numpy=True)` — batch with lists of PIL images for throughput.
- **Text encode (shared space):** `model.encode(["query string"], …)` — enables future **text→image** KNN; **Phase 3 hybrid** remains **mpnet + FTS** unless explicitly switched in a later plan.
- **Output shape:** **(512,) float32** when normalized; serialize with **`sqlite_vec.serialize_float32`** like text blobs.
- **Dependencies:** `sentence-transformers` / `torch` / `Pillow` already implied by stack; confirm **Pillow** import path for image decode failures.

## 4. Chat Search Endpoint Design

**Suggested route:** `POST /api/images/chat-search` (keeps all catalog search under `images` blueprint).

**Request schema (conceptual):**

```json
{
  "message": "current user utterance (required, non-empty)",
  "messages": [
    { "role": "user", "content": "…" },
    { "role": "assistant", "content": "…" }
  ],
  "limit": 50,
  "offset": 0,
  "provider_id": "optional",
  "model": "optional",
  "score_perspective": "optional slug"
}
```

- **`message`** is the new turn; **`messages`** is **prior** history (or full thread including current—planner normalizes). Client-side state per **D-08/D-09** in `05-CONTEXT.md`.

**Cascade logic:**

1. Call NL LLM with **full conversation** + system prompt unchanged in spirit (**`NL_CATALOG_FILTER_SYSTEM_PROMPT`** in `nl_catalog_search.py`).
2. `parse_catalog_nl_filter_from_llm` → `CatalogNlFilter`.
3. `kwargs = catalog_nl_filter_to_query_kwargs(filters)`.
4. **Effective filter test:** if **`kwargs` is empty** or only meaningless values (treat empty strings like absent—**`model_dump`** may retain `""`**), **or** planner-defined “no structured intent” → **`search_mode: "semantic"`**: run the same pipeline as **`semantic_search_images`** using **`message`** (or concatenated thread) as **`query`**.
5. Else **`search_mode: "nl_filter"`**: `query_catalog_images(db, **kwargs, limit, offset)` and shape like **`nl-search`**.
6. **Response:** unify shape for UI:

```json
{
  "search_mode": "nl_filter" | "semantic",
  "total": 0,
  "images": [ … ],
  "filters": { … } | null,
  "metadata": { … } | null
}
```

- When **`nl_filter`:** include **`filters`** (`model_dump`); **`metadata`** optional.  
- When **`semantic`:** include **`metadata`** from **`SemanticSearchMeta`** (missing embeddings, fts flags, rrf_k).

**Pitfall:** **`catalog_nl_filter_to_query_kwargs`** returning `{}` and calling `query_catalog_images` would paginate **unfiltered catalog** — the cascade **must** branch to **semantic** before querying when there are **no effective filters**.

## 5. Chat UI Design

- **Page:** `SearchPage` at `/search` — **`main` max-width** matches `Layout` (`max-w-7xl`); inner wrapper **`flex flex-col md:flex-row gap-6 min-h-[60vh]`**.
- **Left (~40%):** column with **message list** (scrollable), each bubble **`role`**-styled; optional **assistant summary** of filter JSON or “Showing semantic matches…” from **`search_mode`**.
- **Right (~60%):** **`TileGrid` / `ImageTile`** grid; **`search_mode` badge** or subtle caption for power users.
- **State:** `useState<{ role, content }[]>` for transcript; **`useState<CatalogImage[]>`** (or API type) for current **`images`**; **`useState<'idle'|'loading'|'error'>`**; store last **`metadata`** / **`filters`** for display.
- **Submit:** append user message → **`fetch('/api/images/chat-search')`** with **`messages` + `message`** → on success append assistant message (optional short text + **strip count**) and **replace** results array.
- **Empty:** prompt to type a question; **loading:** skeleton grid (reuse **`SkeletonGrid`** if available per `App` patterns) + disabled input; **error:** inline alert + retry.
- **API client:** add **`ImagesAPI.chatSearch`** in `api.ts` (currently **no** `nl-search` / `semantic-search` helpers—Phase 5 should centralize).

## 6. Proposed Plan Breakdown

Aligned with Phase **3** (six plans: schema → service → job → core search → API → tests) and Phase **4** (four plans: schema → config → handler → tests), Phase **5** fits **six plans in four waves**:

### Wave 1 (schema + service)

- **Plan 05-01:** **CLIP sqlite-vec migration** — `_migrate_image_clip_embeddings_vec0`, `user_version` bump, **`upsert_image_clip_embedding`**, **`list_catalog_keys_needing_clip_embedding` / force list**, optional **`count_*`**, wire **`init_database`**; tests mirroring `test_init_database_sqlite_vec_image_text_embeddings`.
- **Plan 05-02:** **`clip_embedding_service.py`** — model id, dim 512, encode image + encode text, vec blob helper, unit tests (mock `encode`).

### Wave 2 (job)

- **Plan 05-03:** **`fingerprint_batch_embed_image`**, **`handle_batch_embed_image`** (checkpoint `job_type`, `processed_pairs`, same progress band as text embed), **`JOB_HANDLERS` + `JOB_TYPES_REQUIRING_CATALOG`**, load image via **`images.filepath`**, skip missing/unreadable files with logs; tests mirroring **`test_handlers_batch_text_embed.py`** + checkpoint tests.

### Wave 3 (backend chat)

- **Plan 05-04:** **Multi-turn NL** — extend **`vision_client`** (or parallel helper) for **`messages[]`**, **`run_nl_catalog_filter_llm`** variant; **`POST /api/images/chat-search`** cascade + unified response; tests mirroring **`test_images_semantic_search_api.py`** / NL API tests.

### Wave 4 (frontend + integration)

- **Plan 05-05:** **`SearchPage`**, **`Layout` / `App` / strings**, **`ImagesAPI.chatSearch`**, split layout + grid + modal; RTL/unit tests for submit + empty/error.
- **Plan 05-06:** **Integration sweep** — `JOB_TYPES` / jobs API assertions, optional RRF-less smoke for chat payload; document **human UAT** for multi-turn refinement.

**Alternative (4 plans):** merge **05-01+05-02**, merge **05-05+05-06** — slightly larger diffs but fewer review cycles.

## Validation Architecture

| Area | Strategy |
|------|-----------|
| **Migration** | Init fresh DB + upgrade path from `user_version=4` fixture; assert vec table exists, **512-dim** blob length on insert round-trip. |
| **CLIP service** | Mock `SentenceTransformer.encode`; assert **normalize_embeddings** call and **float32** shape **(n, 512)**. |
| **batch_embed_image** | Zero-work, incremental skip, force rebuild, checkpoint resume + fingerprint mismatch, cancel mid-batch (if covered for text embed). |
| **chat-search** | **Unit:** effective-filter detection (`{}` → semantic). **API:** NL branch returns **`search_mode: nl_filter`**; stub LLM JSON with empty filter → **semantic** path; invalid JSON → 400. |
| **Frontend** | `vitest`: render `SearchPage`, mock API, assert **grid updates** on successful response; a11y: input labeled, message list **live region** optional. |
