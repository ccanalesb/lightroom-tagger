# Phase 14 — Pattern mapping (database & images API split)

**Sources:** `14-CONTEXT.md`, `14-RESEARCH.md`, Phase 13 `13-PATTERNS.md`, `jobs/handlers/*`, `lightroom_tagger/core/database.py`, `apps/visualizer/backend/api/images.py`, `app.py`, `services/api.ts`, integration tests.

This document lists **files to create/modify**, **role + data flow**, **closest analogs**, and **concrete excerpts** so implementers can replicate patterns without spelunking.

---

## 1. File inventory (create / modify / delete)

### 1.1 `lightroom_tagger/core/database/` (REFACTOR-02, D-01–D-07)

| File | Role | Data flow |
|------|------|-----------|
| `__init__.py` | **Barrel** — re-exports **all** public symbols from submodules (D-02) so `from lightroom_tagger.core.database import X` stays valid everywhere. | Import-only; **no** `conn` — wires the public API surface. |
| `db_init.py` | Init, migrations, `_dict_factory`, sqlite-vec load, `_migrate_*`, `init_database`, `seed_perspectives_from_prompts_dir` (per RESEARCH §8). | Called at startup / tests; submodules **do not** import each other through `db_init` in a cycle. |
| `catalog.py` | Catalog CRUD/query, `library_write`, `resolve_filepath` (D-05), search helpers tied to catalog. | Functions take `conn: sqlite3.Connection`. |
| `instagram.py` | Instagram dump / status / hash helpers per D-01 (extend with full symbol list from RESEARCH §1). | `conn` in, mutations/queries out. |
| `matches.py` | Matches + crossover helpers (`get_rejected_pairs`, `apply_instagram_match_to_stack_members`, …) — **single home** per “primary consumer” rule. | `conn` param. |
| `descriptions.py` | Description rows, FTS builders, undescribed helpers. | `conn` param. |
| `scores.py` | Perspectives + scores CRUD (not filesystem seed — that stays `db_init`). | `conn` param. |
| `stacks.py` | Stack metadata/mutations, `StackMutationError`. | `conn` param. |
| `embeddings.py` | Embedding upserts/lists/counts and `_embeddable_*` helpers. | `conn` param. |
| `similarity.py` | Catalog similarity **job** tables: `insert_catalog_similarity_group`, `list_clip_embedded_catalog_keys_newest_first`, `clear_catalog_similarity_results` (DB layer — **not** Flask “get similar” handlers; RESEARCH §1.2). | `conn` param. |
| `vision_cache.py` | Vision cache/comparison tables and accessors. | `conn` param. |

**Deleted after migration:** flat `lightroom_tagger/core/database.py` — **cannot** coexist with package `database/` (same rule as Phase 13 `handlers.py` vs `handlers/`). Use scaffold: rename monolith → `_legacy.py` inside package or migrate in one shot per D-12.

### 1.2 Tests — `lightroom_tagger/core/` (D-06 / D-07)

| File | Role |
|------|--------|
| `test_database_db_init.py` | New — tests moved from `test_database.py` for init/migrations. |
| `test_database_catalog.py` | New — catalog-focused tests from `test_database.py`. |
| `test_database_instagram.py` | New |
| `test_database_matches.py` | New |
| `test_database_descriptions.py` | New |
| `test_database_scores.py` | **Existing** — update imports only if tests later import submodules directly; barrel re-exports mean minimal churn. |
| `test_database_stacks.py` | New name absorbing `test_database_stack_collapse.py`. |
| `test_database_embeddings.py` | New |
| `test_database_similarity.py` | New |
| `test_database_vision_cache.py` | New |
| `test_database_nl_filter_arrays.py` | **Keep filename** — update imports only (D-06). |
| `test_database.py` | **Shrinks or is removed** after cases move to per-module files. |

### 1.3 `apps/visualizer/backend/api/images/` (REFACTOR-03, D-08–D-11)

| File | Role | Notes |
|------|------|--------|
| `__init__.py` | Re-exports **five** Blueprints: `catalog_bp`, `stacks_bp`, `instagram_bp`, `matches_bp`, `search_bp` (D-11). | No heavy imports from `common` that re-pull all route modules (RESEARCH §9). |
| `catalog.py` | Routes: `/catalog`, thumbnails, `/catalog/months`, `/catalog/.../similar`, `/catalog-similarity-groups`, polymorphic `GET /<image_type>/<key>` per plan. | Own `Blueprint`; helpers per D-10 stay here. |
| `stacks.py` | `/stacks/...` mutations + members. | Own `Blueprint`. |
| `instagram.py` | `/instagram...`, `/dump-media`, `_enrich_instagram_media`, `_deserialize_description` (D-10). | Own `Blueprint`. |
| `matches.py` | `/matches...` | Own `Blueprint`. |
| `search.py` | `/nl-search`, `/semantic-search`, `/chat-search` + chat/search-only helpers (D-10). | Own `Blueprint`. |
| `common.py` | Cross-cutting: `_clamp_pagination`, path roots, `_filter_by_date`, etc. (D-08). **`with_db` stays in `utils.db`** (RESEARCH §7). | Imported by route modules + **`api.identity`**, **`api.analytics`** (today they import `_clamp_pagination` from `api.images`). |

**Deleted after migration:** `apps/visualizer/backend/api/images.py` (monolith).

### 1.4 Modified elsewhere (integration)

| File | Role |
|------|------|
| `apps/visualizer/backend/app.py` | Replace single `images.bp` with **five** `register_blueprint` calls + imports from `api.images` (D-09 / D-11). |
| `apps/visualizer/backend/api/identity.py` | Change `from api.images import _clamp_pagination` → `from api.images.common import _clamp_pagination` (or chosen path). |
| `apps/visualizer/backend/api/analytics.py` | Same as identity. |
| `apps/visualizer/backend/tests/test_images_*.py` (and related) | Update hardcoded `/api/images/...` if final URLs change with D-09; lockstep with Flask routes + frontend. |
| `apps/visualizer/frontend/src/services/api.ts` | All `request(\`/images/...\`)` paths — effective base `/api` + path (see §5). |
| `apps/visualizer/frontend/src/utils/imageUrl.ts` | Hardcoded `/api/images/...` — must stay consistent with backend URL builder + JSON thumbnail URLs. |
| Components/tests referencing `/api/images` | Per RESEARCH §5 — audit `rg "/images/"` and fix non-import false positives. |

---

## 2. Database submodules — analog: Phase 13 **family handler module**

**Closest analog per submodule:** `apps/visualizer/backend/jobs/handlers/analyze.py` (one domain, explicit imports, **relative** imports to package siblings). **Not** the handlers package `__init__.py` — that assembles a **registry**; database `__init__.py` is a **full re-export barrel** (inverse pattern; D-02).

### 2.1 Family module pattern (docstring + imports) — `analyze.py`

```1:23:apps/visualizer/backend/jobs/handlers/analyze.py
"""Describe, score, and unified batch-analyze job handlers."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from database import add_job_log, get_job, update_job_field

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database

from ..checkpoint import fingerprint_batch_describe, fingerprint_batch_score

from .common import (
    _CHECKPOINT_MAX_ENTRIES,
    _CATALOG_NOT_VIDEO_SQL,
    ...
)
```

**Apply to `catalog.py`, `embeddings.py`, …:** module docstring; stdlib + `sqlite3` + `lightroom_tagger.*` as needed; **use relative imports** inside `database/` (`from . import …`) — **never** `from lightroom_tagger.core.database import …` from inside a submodule (avoids cycles / package shadowing).

### 2.2 Monolith head — `database.py` (class + imports style)

```1:22:lightroom_tagger/core/database.py
import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlite_vec


class StackMutationError(ValueError):
    """Invalid stack edit; ``status_code`` is intended for HTTP error mapping."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
```

**Apply:** keep **one** home for `StackMutationError` (`stacks.py` per D-01); re-export from `__init__.py`.

### 2.3 `__init__.py` re-export pattern — **contrast** with Phase 13 handlers

Phase 13 **`handlers/__init__.py`** assembles **`JOB_HANDLERS`** — **no** re-export of every handler symbol:

```1:38:apps/visualizer/backend/jobs/handlers/__init__.py
"""Job handler package — one module per job family."""
from .. import path_setup as _path_setup  # noqa: F401

from .analyze import (
    handle_batch_analyze,
    handle_batch_describe,
    handle_batch_score,
    handle_single_describe,
    handle_single_score,
)
from .embed import handle_batch_embed_image, handle_batch_text_embed
from .instagram import handle_analyze_instagram, handle_instagram_import
from .matching import handle_enrich_catalog, handle_prepare_catalog, handle_vision_match
from .stacks import (
    handle_batch_catalog_similarity,
    handle_batch_stack_detect,
    handle_catalog_cache_build,
)

JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    ...
}

__all__ = ('JOB_HANDLERS',)
```

**Phase 14 database `__init__.py` (target shape — illustrative):** import public callables/classes from **each** submodule and assign to module namespace + `__all__` (or wildcard re-export with discipline). **Goal:** grep-based parity with every symbol previously exported from monolithic `database.py` and every consumer listed in RESEARCH §3.

### 2.4 Submodule ↔ analog quick map

| New submodule | Analog file (pattern) |
|---------------|------------------------|
| `db_init.py` | **Depth:** migration-heavy slice of monolith + **`jobs/checkpoint.py`** style “focused module” (Phase 13 §2). |
| `catalog.py` | `handlers/analyze.py` — large domain module with local helpers. |
| `instagram.py` | `handlers/instagram.py` |
| `matches.py` | `handlers/matching.py` |
| `descriptions.py` | `handlers/analyze.py` (description-related density) |
| `scores.py` | `handlers/analyze.py` (score paths) + existing `test_database_scores.py` scope |
| `stacks.py` | `handlers/stacks.py` |
| `embeddings.py` | `handlers/embed.py` |
| `similarity.py` | `handlers/stacks.py` (job-pipeline adjacency) — **code is DB similarity tables**, not API handlers |
| `vision_cache.py` | `checkpoint.py`-like small surface + monolith tail |

---

## 3. Images subpackage — Blueprint registration analogs

### 3.1 Current monolith — single Blueprint

```58:60:apps/visualizer/backend/api/images.py
_CATALOG_SCORE_PERSPECTIVE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

bp = Blueprint("images", __name__)
```

### 3.2 **Reference** Blueprint — separate feature module (`descriptions.py`)

```1:22:apps/visualizer/backend/api/descriptions.py
import json
import os

from flask import Blueprint, jsonify, request
from lightroom_tagger.core.database import (
    get_all_images_with_descriptions,
    get_image_description,
)
from lightroom_tagger.core.description_service import (
    describe_instagram_image,
    describe_matched_image,
)
from utils.db import with_db
from utils.responses import error_server_error

bp = Blueprint('descriptions', __name__)
```

**Apply:** each of `catalog.py`, `stacks.py`, … defines **`catalog_bp = Blueprint("images_catalog", __name__)`** (unique names) or namespaced per team convention — avoid duplicate `"images"` string if Flask complains.

### 3.3 Route + `@with_db` stack (order: route **then** `with_db`)

```594:597:apps/visualizer/backend/api/images.py
@bp.route("/instagram", methods=["GET"])
@with_db
def list_instagram_images(db):
    """List Instagram images with filtering and pagination."""
```

**Apply after split:** `@instagram_bp.route("/instagram", methods=["GET"])` + `@with_db` — with `url_prefix='/api/images/instagram'`, the **relative** path stays `/instagram` **if** the goal is unchanged effective URL `/api/images/instagram` (RESEARCH §5.3). Confirm against D-09 table.

### 3.4 `with_db` import (unchanged location)

```12:12:apps/visualizer/backend/api/images.py
from utils.db import with_db
```

```33:45:apps/visualizer/backend/utils/db.py
def with_db(handler_func=None, *, require_exists=True):
    """Decorator that provides SQLite database connection to route handlers."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            db_path = LIBRARY_DB

            if require_exists and not os.path.exists(db_path):
                return _make_json_response({'error': ERROR_DB_NOT_FOUND}, 404)

            db = None
            try:
                db = init_database(db_path)
```

### 3.5 Cross-package consumers of `_clamp_pagination` (must follow `common.py`)

**Identity:**

```16:16:apps/visualizer/backend/api/identity.py
from api.images import _clamp_pagination
```

**Analytics:**

```12:12:apps/visualizer/backend/api/analytics.py
from api.images import _clamp_pagination
```

After split: `from api.images.common import _clamp_pagination` (or the path you choose for `api.images` package).

---

## 4. `app.py` — current registration & five-Blueprint target

### 4.1 Current (single images Blueprint)

```119:140:apps/visualizer/backend/app.py
    from api import (
        analytics,
        descriptions,
        identity,
        images,
        jobs,
        lt_config,
        perspectives,
        providers,
        scores,
        system,
    )
    app.register_blueprint(jobs.bp, url_prefix='/api/jobs')
    app.register_blueprint(images.bp, url_prefix='/api/images')
    app.register_blueprint(analytics.bp, url_prefix='/api/analytics')
    app.register_blueprint(descriptions.bp, url_prefix='/api/descriptions')
    app.register_blueprint(providers.bp, url_prefix='/api/providers')
    app.register_blueprint(system.bp, url_prefix='/api')
    app.register_blueprint(lt_config.bp, url_prefix='/api/config')
    app.register_blueprint(perspectives.bp, url_prefix='/api/perspectives')
    app.register_blueprint(scores.bp, url_prefix='/api/scores')
    app.register_blueprint(identity.bp, url_prefix='/api/identity')
```

### 4.2 Target pattern (D-09 / D-11) — **illustrative**; adjust `url_prefix` + route paths so **effective URLs** match RESEARCH §5.4 (especially **`/catalog-similarity-groups`** vs nested catalog prefix)

```python
from api.images import (
    catalog_bp,
    stacks_bp,
    instagram_bp,
    matches_bp,
    search_bp,
)

app.register_blueprint(catalog_bp, url_prefix="/api/images/catalog")
app.register_blueprint(stacks_bp, url_prefix="/api/images/stacks")
app.register_blueprint(instagram_bp, url_prefix="/api/images/instagram")
app.register_blueprint(matches_bp, url_prefix="/api/images/matches")
app.register_blueprint(search_bp, url_prefix="/api/images/search")
```

**Planner rule:** If `search_bp` uses prefix `/api/images/search`, route functions should be `/nl-search`, `/semantic-search`, `/chat-search` so callers move from `/api/images/chat-search` → `/api/images/search/chat-search` **unless** you add a second registration or keep a compatibility route.

---

## 5. Frontend URL / `fetch` pattern

### 5.1 `request()` helper — paths are **relative to `API_URL`** (`/api` by default)

```7:31:apps/visualizer/frontend/src/services/api.ts
const API_URL = import.meta.env.VITE_API_URL || API_DEFAULT_URL

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  ...
  return response.json()
}
```

**Effective URL** = `API_URL` + `path`. With `API_DEFAULT_URL = '/api'`, `request('/images/catalog')` → **`/api/images/catalog`**.

### 5.2 `ImagesAPI` / `MatchingAPI` — representative paths (update in lockstep with Blueprint `url_prefix` + route strings)

```342:457:apps/visualizer/frontend/src/services/api.ts
export const ImagesAPI = {
  listInstagram: (params?: {
    ...
  }) => {
    ...
    return request<{
      total: number;
      images: InstagramImage[];
      pagination: PaginationMeta;
    }>(`/images/instagram?${searchParams.toString()}`)
  },

  getInstagramMonths: () =>
    request<{ months: string[] }>('/images/instagram/months'),

  getCatalogMonths: () =>
    request<{ months: string[] }>('/images/catalog/months'),

  listCatalog: (params?: CatalogListQueryParams) => {
    ...
    return request<{ total: number; images: CatalogImage[] }>(
      `/images/catalog${qs ? `?${qs}` : ''}`
    )
  },

  getImageDetail: (
    image_type: 'catalog' | 'instagram',
    image_key: string,
    params?: { score_perspective?: string },
  ) => {
    const qs = params?.score_perspective
      ? `?score_perspective=${encodeURIComponent(params.score_perspective)}`
      : ''
    return request<ImageDetailResponse>(
      `/images/${image_type}/${encodeURIComponent(image_key)}${qs}`,
    )
  },

  listCatalogSimilarityGroups: (params?: { limit?: number; offset?: number }) => {
    ...
    return request<CatalogSimilarityGroupsResponse>(
      `/images/catalog-similarity-groups${qs ? `?${qs}` : ''}`,
    )
  },

  getStackMembers: (stackId: number) =>
    request<{ items: CatalogImage[] }>(`/images/stacks/${stackId}/members`),
  ...
  chatSearch: (payload: ChatSearchRequest) =>
    request<ChatSearchResponse>('/images/chat-search', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
```

### 5.3 Hardcoded browser URLs — `imageUrl.ts` (not using `request()`)

```1:11:apps/visualizer/frontend/src/utils/imageUrl.ts
export type ImageType = 'catalog' | 'instagram'

function imageUrl(type: ImageType, key: string, variant: 'thumbnail' | 'full'): string {
  return `/api/images/${type}/${encodeURIComponent(key)}/${variant}`
}

export const thumbnailUrl = (type: ImageType, key: string): string =>
  imageUrl(type, key, 'thumbnail')
```

**Contract:** Backend JSON that embeds thumbnail paths must stay aligned with these helpers (RESEARCH validation table).

---

## 6. Test file co-split patterns

### 6.1 Focused DB test — imports from **`lightroom_tagger.core.database`**

```1:15:lightroom_tagger/core/test_database_scores.py
"""Tests for ``image_scores`` / ``perspectives`` schema and helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    init_database,
    insert_image_score,
    list_score_history_for_perspective,
    query_catalog_images,
    store_image,
    supersede_previous_current_scores,
)
```

**After barrel `__init__.py`:** imports can remain **unchanged** (D-02). Co-split only **moves** test bodies into new files.

### 6.2 Monolithic `test_database.py` — broad import list + `unittest`

```1:36:lightroom_tagger/core/test_database.py
import os
import tempfile
import unittest

import sqlite_vec

from lightroom_tagger.core.database import (
    batch_update_hashes,
    build_description_fts_query,
    clear_all,
    delete_image,
    generate_key,
    get_all_images,
    get_image,
    get_image_count,
    get_image_description,
    get_images_without_hash,
    get_instagram_by_date_filter,
    get_undescribed_catalog_images,
    get_vision_comparison,
    init_database,
    init_image_descriptions_table,
    init_vision_comparisons_table,
    library_write,
    list_instagram_dump_keys_needing_clip_embedding,
    migrate_unified_image_keys,
    query_catalog_images,
    store_image,
    store_image_description,
    store_images_batch,
    store_match,
    store_vision_comparison,
    update_image_hash,
    update_instagram_status,
    upsert_image_clip_embedding,
)
```

**Apply:** split into per-domain files; trim each file’s imports to **only** symbols the moved tests need.

### 6.3 Visualizer API tests — hardcoded full paths (update with D-09)

```1:13:apps/visualizer/backend/tests/test_images_catalog_api.py
"""Integration tests for GET /api/images/catalog query parameters."""

import sqlite3

import pytest

from app import create_app
from lightroom_tagger.core.database import (
    build_description_fts_query,
    init_database,
    store_image,
    store_image_description,
)
```

```155:156:apps/visualizer/backend/tests/test_images_catalog_api.py
    resp = client.get("/api/images/catalog?analyzed=true")
```

**Apply:** when Blueprint prefixes change, batch-replace `client.get("/api/images/...` strings to match **actual** mounted URLs.

---

## 7. Phase 13 scaffold reminder (database/images)

From `13-PATTERNS.md` §6: **cannot** have both `database.py` (file) and `database/` (package). Same for `api/images.py` vs `api/images/`. Recommended: rename monolith → `_legacy.py` under the new package, first green commit re-exports from `_legacy` in `__init__.py`, then per-domain commits until `_legacy` is deleted.

---

## PATTERN MAPPING COMPLETE
