# Phase 6: Similarity & Stack UI - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 12 (new/modified targets from CONTEXT + RESEARCH)
**Analogs found:** 12 / 12 (stack-specific DB reads are new but follow existing `database.py` + `identity_service` patterns)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `lightroom_tagger/core/clip_similarity.py` (new) | service | transform + DB read (KNN) | `lightroom_tagger/core/semantic_search.py` | exact (parallel to `knn_embedded_*`, different table) |
| `lightroom_tagger/core/database.py` (modify) | data layer | CRUD read / joins | `query_catalog_images_by_keys` + `image_stacks` DDL | exact + schema |
| `lightroom_tagger/core/identity_service.py` (modify) | service | transform + list pagination | `rank_best_photos` + `_image_meta_map` | role-match |
| `apps/visualizer/backend/api/images.py` (modify) | route / controller | request-response | `semantic_search_images`, `list_catalog_images` | exact |
| `apps/visualizer/backend/api/identity.py` (modify) | route / controller | request-response | `best_photos` | exact |
| `apps/visualizer/frontend/src/services/api.ts` (modify) | service client | request-response | `ImagesAPI.listCatalog`, `IdentityAPI.getBestPhotos` | exact |
| `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` (modify) | component + page | fetch + UI events | current `CatalogTab` + `useQuery` | exact |
| `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` (modify) | component | fetch + grid | same file’s existing `ImageTile` usage | exact |
| `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx` (optional touch) | component | presentational | self (`overlayBadges` / `footer`) | exact |
| `apps/visualizer/frontend/src/hooks/useSimilarImages.ts` or `useStackMembers.ts` (optional) | hook | event-driven + fetch | `useJobSocket` (callbacks) + `CatalogTab` data loading | role-match |
| `apps/visualizer/backend/tests/test_images_*_api.py` (new/extend) | test | request-response | `test_images_semantic_search_api.py` | exact |

## Pattern Assignments

### `lightroom_tagger/core/clip_similarity.py` (new) (service, KNN + hydrate)

**Analog:** `lightroom_tagger/core/semantic_search.py`

**KNN query shape** — copy the sqlite-vec pattern from `knn_embedded_catalog_keys` but target `image_clip_embeddings` (512-d) instead of `image_text_embeddings` (768-d):

```67:83:lightroom_tagger/core/semantic_search.py
def knn_embedded_catalog_keys(
    conn: sqlite3.Connection, query_vec_blob: bytes, *, k: int
) -> list[tuple[str, float]]:
    """KNN over ``image_text_embeddings`` (cosine distance); order preserved."""
    rows = conn.execute(
        """
        SELECT image_key, distance
        FROM image_text_embeddings
        WHERE embedding MATCH ?
          AND k = ?
        """,
        (query_vec_blob, k),
    ).fetchall()
```

**Distance → “similarity” string** (for optional `why_matched`-style text):

```86:98:lightroom_tagger/core/semantic_search.py
    similarity = (
        None
        if distance is None
        else max(0.0, min(1.0, 1.0 - float(distance)))
    )
```

**Post-KNN ordering + hydrate** — follow semantic-search route: ordered keys → `query_catalog_images_by_keys` → enrich rows (see `api/images.py` `semantic_search_images` below).

**Constants** — do not re-derive dimensions; align with:

```8:9:lightroom_tagger/core/clip_embedding_service.py
CLIP_EMBED_MODEL_ID = "clip-ViT-B-32"
CLIP_EMBED_DIM = 512
```

---

### `lightroom_tagger/core/database.py` (modify) (data layer, read paths)

**Analog:** `query_catalog_images_by_keys` (order-preserving hydrate)

```1382:1431:lightroom_tagger/core/database.py
def query_catalog_images_by_keys(
    db: sqlite3.Connection,
    keys: Sequence[str],
    *,
    score_perspective: str | None = None,
) -> list[dict]:
    """Load catalog rows for ``keys`` with the same columns/joins as :func:`query_catalog_images`.

    Preserves **input order** via ``ORDER BY CASE i.key WHEN …``. Empty ``keys`` → ``[]``.
    """
    if not keys:
        return []
    # ... IN (...) + CASE order ...
    rows = db.execute(
        f"SELECT {select_cols} {join_sql} {where_sql} {order_sql}",
        params,
    ).fetchall()
    return [_deserialize_row(r) for r in rows]
```

**Stack schema** — `image_stacks` / `image_stack_members` already migrated here; new helpers should join against these tables consistently with:

```819:843:lightroom_tagger/core/database.py
def _migrate_image_stacks(conn: sqlite3.Connection) -> None:
    ...
        CREATE TABLE IF NOT EXISTS image_stacks (
    ...
        CREATE TABLE IF NOT EXISTS image_stack_members (
    ...
```

---

### `lightroom_tagger/core/identity_service.py` (modify) (service, ranked lists)

**Analog:** `rank_best_photos` (pagination, enrichment, sort)

```285:327:lightroom_tagger/core/identity_service.py
def rank_best_photos(
    conn: sqlite3.Connection,
    *,
    limit: int,
    offset: int,
    min_perspectives: int | None = None,
    sort_by_date: str | None = None,
    posted: bool | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    ...
    total = len(enriched)
    page = enriched[offset : offset + limit]
    return page, total, meta
```

Phase 6 stack fields (`stack_id`, `stack_member_count`, `is_stack_representative`) should attach in the same enrichment pass style as `_image_meta_map` + row merge in this module.

---

### `apps/visualizer/backend/api/images.py` (modify) (routes)

**Analog:** `POST /semantic-search` — JSON body, `_clamp_pagination`, `query_catalog_images_by_keys`, `_rows_to_catalog_api_images`, per-image `thumbnail_url` + score metadata

**Pagination + error helpers:**

```201:218:apps/visualizer/backend/api/images.py
def _clamp_pagination(limit, offset, default_limit=50):
    ...
    limit = max(1, min(500, limit))
```

**Core merge pattern** (KNN-ordered keys → catalog rows → API dicts + extras):

```733:753:apps/visualizer/backend/api/images.py
        blob = embed_query_to_vec_blob(qstrip)
        rows, total, meta = run_semantic_hybrid_search(
            db,
            ...
        )

        keys = [r.image_key for r in rows]
        catalog_rows = query_catalog_images_by_keys(db, keys, score_perspective=score_perspective_arg)
        images = _rows_to_catalog_api_images(catalog_rows, score_perspective_arg)

        sem_by_key = {r.image_key: r for r in rows}
        for img in images:
            sem_row = sem_by_key.get(img['key'])
            if sem_row is not None:
                img['score'] = float(sem_row.rrf_score)
                img['why_matched'] = sem_row.why_matched
                img['thumbnail_url'] = f"/api/images/catalog/{sem_row.image_key}/thumbnail"
```

**Row normalization** — any new list endpoint should reuse:

```236:274:apps/visualizer/backend/api/images.py
def _rows_to_catalog_api_images(rows, score_perspective_arg: str | None) -> list[dict]:
    """Transform ``query_catalog_images`` rows to API image dicts (catalog list + NL search)."""
    ...
        images.append(out)
    return images
```

**GET catalog** — query-param validation style for a similar **GET** route:

```543:618:apps/visualizer/backend/api/images.py
@bp.route('/catalog', methods=['GET'])
@with_db
def list_catalog_images(db):
    ...
        limit, offset = _clamp_pagination(
            request.args.get('limit', 50, type=int),
            request.args.get('offset', 0, type=int),
        )
```

Imports already show blueprint + `with_db` + response helpers + `query_catalog_images` family — extend, don’t fork.

---

### `apps/visualizer/backend/api/identity.py` (modify) (routes)

**Analog:** `GET /best-photos` — uses `_clamp_pagination` from `api.images`, returns `{ items, total, meta }`

```62:89:apps/visualizer/backend/api/identity.py
@bp.route("/best-photos", methods=["GET"])
@with_db
def best_photos(db: sqlite3.Connection) -> ResponseReturnValue:
    """Paginated eligible catalog images ranked by aggregate perspective score."""
    try:
        limit, offset = _clamp_pagination(
            request.args.get("limit", 50, type=int),
            request.args.get("offset", 0, type=int),
        )
        ...
        items, total, meta = rank_best_photos(
            db,
            limit=limit,
            offset=offset,
            ...
        )
        return jsonify({"items": items, "total": total, "meta": meta})
```

---

### `apps/visualizer/frontend/src/services/api.ts` (modify) (API client + types)

**Analog:** `ImagesAPI.listCatalog` (URLSearchParams, typed response) and `IdentityAPI.getBestPhotos`

```294:343:apps/visualizer/frontend/src/services/api.ts
  listCatalog: (params?: {
    posted?: boolean
    ...
  }) => {
    const searchParams = new URLSearchParams()
    ...
    return request<{ total: number; images: CatalogImage[] }>(
      `/images/catalog${qs ? `?${qs}` : ''}`
    )
  },
```

```806:823:apps/visualizer/frontend/src/services/api.ts
  getBestPhotos: (params?: {
    limit?: number
    offset?: number
    ...
  }) => {
    const sp = new URLSearchParams()
    ...
    return request<IdentityBestPhotosResponse>(`/identity/best-photos${qs ? `?${qs}` : ''}`)
  },
```

Extend `CatalogImage` / best-photo item types with optional `stack_id`, `stack_member_count`, `is_stack_representative` next to existing optional fields (same style as `catalog_perspective_score`).

---

### `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` (modify) (page tab)

**Analog:** current file — `useQuery` + `ImagesAPI` + `ImageTile` + `ImageDetailModal`

```1:7:apps/visualizer/frontend/src/components/images/CatalogTab.tsx
import { useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ImagesAPI, PerspectivesAPI, type CatalogImage } from '../../services/api';
import { ImageDetailModal, ImageTile, fromCatalogListRow } from '../image-view';
```

Add “more like this” and stack UI using the same data-fetch and modal flow; keep filter keys stable (see `stableSerializeRecord` / `useQuery` key patterns in this file).

---

### `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` (modify) (grid)

**Analog:** same component family as Catalog — `ImageTile` with `overlayBadges` / `footer` for stack count + expand affordance (props already exist on `ImageTile`).

---

### `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx` (reference)

**Analog:** `ImageTile` — overlay and footer extension points (no new primitives required unless design system demands it; follow `apps/visualizer/frontend/DESIGN.md`).

```8:23:apps/visualizer/frontend/src/components/image-view/ImageTile.tsx
interface ImageTileProps {
  image: ImageView
  variant: ImageTileVariant
  primaryScoreSource: PrimaryScoreSource
  onClick: () => void
  ...
  overlayBadges?: ReactNode
  /** Content rendered below the metadata row ... */
  footer?: ReactNode
```

---

### Optional `useSimilarImages` / `useStackMembers` (hook)

**Analog:** `useJobSocket` for `useCallback`/`useEffect` wiring; or keep logic inline like `CatalogTab` with `useQuery` for fetches. Prefer a small hook only if two surfaces share identical loading/error state.

```12:25:apps/visualizer/frontend/src/hooks/useJobSocket.ts
export function useJobSocket({
  onJobCreated,
  onJobUpdated,
  onJobsRecovered,
}: UseJobSocketOptions = {}) {
  const socket = useSocketStore((s) => s.socket)
  ...
  const [jobListRevision, setJobListRevision] = useState(0)
```

---

### Backend tests (new/extend)

**Analog:** `apps/visualizer/backend/tests/test_images_semantic_search_api.py` — `create_app`, `init_database` fixture, `test_client` POST JSON, monkeypatch core call

```1:6:apps/visualizer/backend/tests/test_images_semantic_search_api.py
"""Tests for POST /api/images/semantic-search (mocked embed + hybrid search)."""

from __future__ import annotations

import pytest
from app import create_app
```

## Shared Patterns

### Flask JSON errors

**Source:** `apps/visualizer/backend/utils/responses.py`  
**Apply to:** New routes in `api/images.py`, `api/identity.py`, stack/members routes

```44:46:apps/visualizer/backend/utils/responses.py
def error_bad_request(message='Invalid request'):
    """Return 400 error."""
    return _make_json_response({'error': message}, 400)
```

### Reuse `error_not_found` for missing CLIP row / unknown stack

**Source:** `apps/visualizer/backend/utils/responses.py`

```30:41:apps/visualizer/backend/utils/responses.py
def error_not_found(resource_type='resource'):
    """Return 404 error for resource not found."""
    messages = {
        'image': ERROR_IMAGE_NOT_FOUND,
```

### Do not use text embedding for SIM-02

**Anti-pattern source:** `semantic_search.py` uses `embed_query_to_vec_blob` + `image_text_embeddings` for hybrid search. Phase 6 similar-images must read seed vectors **only** from `image_clip_embeddings` per CONTEXT D-05; keep CLIP KNN in a dedicated module or clearly separated functions.

## No Analog Found

| File / concern | Role | Data Flow | Reason |
|----------------|------|-----------|--------|
| Dedicated `GET /stacks/.../members` | route | request-response | No existing stack list route; follow `list_catalog_images` + thin handler pattern (not a gap in patterns—new endpoint, old style). |
| N+1-safe stack batch on catalog | data layer | batch read | No prior helper; implement with batched `IN` queries or joins mirroring `query_catalog_images` style. |

## Metadata

**Analog search scope:** `lightroom_tagger/core/semantic_search.py`, `lightroom_tagger/core/database.py`, `lightroom_tagger/core/clip_embedding_service.py`, `lightroom_tagger/core/identity_service.py`, `apps/visualizer/backend/api/images.py`, `apps/visualizer/backend/api/identity.py`, `apps/visualizer/backend/utils/responses.py`, `apps/visualizer/frontend/src/services/api.ts`, `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`, `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx`, `apps/visualizer/frontend/src/hooks/useJobSocket.ts`, `apps/visualizer/backend/tests/test_images_semantic_search_api.py`  
**Pattern extraction date:** 2026-04-25
