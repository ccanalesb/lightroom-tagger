# Phase 14: Database & Images API Split — Research

**Date:** 2026-05-06  
**Goal:** Answer “What do I need to know to PLAN this phase well?” for **REFACTOR-02** (database) and **REFACTOR-03** (images API), using the current repo (post–Phase 13 `jobs/handlers/` package).

**Sources:** `lightroom_tagger/core/database.py` (3,558 lines), `apps/visualizer/backend/api/images.py` (≈1,954 lines), `apps/visualizer/backend/app.py`, `apps/visualizer/backend/utils/db.py`, `14-CONTEXT.md`, Phase 13 `handlers` package, ripgrep over imports and frontend.

---

## Summary

- **`database.py`:** One monolithic module with clear **comment-anchored regions** (init/migrations, catalog query, stacks, instagram dump, matches, descriptions, embeddings, perspectives/scores, vision cache). `14-CONTEXT.md` **D-01** is directionally right but omits many symbols (matches/instagram dump/catalog bridge), and **misattributes** API-only names to `similarity.py`. **D-03 `__init__.py` must re-export the full public surface** so existing `from lightroom_tagger.core.database import …` call sites (dozens of files) stay unchanged.
- **`images.py`:** Single `bp` with **20 `@bp.route` entries**; `with_db` is **not** defined here — it lives in **`utils/db.py`** (`from utils.db import with_db`). Splitting into five Blueprints + `common.py` needs explicit decisions on **polymorphic** `GET /<image_type>/<path:key>` and **sibling paths** like `/catalog-similarity-groups` so Flask `url_prefix` values do not accidentally rewrite URLs (see §2 and §5).
- **Frontend “42” call sites:** `rg "/images/" apps/visualizer/frontend/src --glob "*.ts" --glob "*.tsx"` returns **42** lines, but **several are false positives** (imports of `../components/images/...`). Meaningful URL construction is concentrated in **`services/api.ts` (`request('/images/…')`)**, **`utils/imageUrl.ts`**, and a few **hardcoded `/api/images/...`** thumbnail `src`s. There are **no** current frontend callers of **`/images/nl-search`** or **`/images/semantic-search`** (those are exercised by **backend tests** and future UIs).
- **Phase 13 scaffold:** Production **`handlers/__init__.py`** now **imports handler callables from submodules** and assembles **`JOB_HANDLERS`** — it does **not** re-export handlers. Phase 14 **database** is the **inverse** (full re-export barrel per **14-CONTEXT D-02**). **`common.py`** in handlers is **cross-cutting helpers only**; database split explicitly avoids a `common.py` per **D-04**.

---

## 1. database.py Structure Audit

**File size:** 3,558 lines (last line `list_all_scores_for_image` ends ~3557).

### 1.1 Top-level symbols (grep `^def |^class `)

Rough **line bands** (use these to verify D-01; inclusive starts, next section begins after previous block):

| Lines (approx) | Domain | Notes |
|----------------|--------|--------|
| 17 | `StackMutationError` | stacks.py |
| 72–208 | `library_write`, `resolve_filepath` | **catalog.py** per D-05 |
| 209–332 | `_dict_factory`, sqlite-vec, row/json helpers, `build_description_search_document`, `build_description_fts_query`, `_coerce_*`, `_visual_attr_json`, `_perspective_seed_description`, **`seed_perspectives_from_prompts_dir`** | **db_init** + **descriptions** split (see §8) |
| 394–629 | **`init_database`** body (DDL + calls `_migrate_*`, **`seed_perspectives_from_prompts_dir`**) | **db_init.py** |
| 630–1012 | `_migrate_add_column`, `_migrate_images_schema`, `generate_key`, `_library_db_file_path`, backfills, FTS/vec/stack/unified-key migrations, **`migrate_unified_image_keys`** | **db_init.py** |
| 1018–1651 | Core catalog CRUD + `search_by_*`, `query_catalog_images` tree, `filter_order_keys_in_catalog`, `query_catalog_images_by_keys`, `catalog_key_is_primary_grid_row` | **catalog.py** (large) |
| 1653–2123 | `list_clip_embedded_catalog_keys_newest_first`, **catalog similarity job tables** (`clear_catalog_similarity_results`, `insert_catalog_similarity_group`), **stack** APIs (`list_catalog_stack_member_keys` … `stack_set_representative`), **`catalog_has_instagram_match_conflict`**, **`apply_instagram_match_to_stack_members`** | **similarity.py** (first two) + **stacks.py** + **matches.py** per CONTEXT — **note:** `apply_*` / `catalog_has_*` are **matches + stacks crossover**; follow “single primary consumer” rule from Phase 13 |
| 2125–2242 | `get_images_without_hash`, hash updates, **`init_catalog_table` / `store_catalog_image` / `get_catalog_images_*`** | **instagram.py** helpers for `get_images_without_hash` per D-01; **catalog** for `store_catalog_image` and LR catalog analysis helpers |
| 2243–2492 | Instagram **dump** pipeline (`init_instagram_dump_table` … `get_instagram_images_needing_analysis`) | **instagram.py** (far more than three functions — extend D-01) |
| 2493–2698 | Matches (`init_matches_table` … `get_rejected_pairs`) | **matches.py** |
| 2700–2826 | Vision cache/comparison | **vision_cache.py** |
| 2827–3271 | Image descriptions + undescribed helpers + **embedding metrics** (`count_*`, `list_*`, `upsert_*`, `_list_catalog_keys_*`, instagram dump embed filters) | **descriptions.py** + **embeddings.py** (`get_all_images_with_descriptions` **3273–3326** is descriptions-page helper — **descriptions.py**) |
| 3329–3557 | Perspectives + scores (`list_perspectives` … `list_all_scores_for_image`) | **scores.py** |

### 1.2 Corrections vs `14-CONTEXT.md` D-01

- **`similarity.py` in D-01** lists `get_catalog_image_similar` and `list_catalog_similarity_groups` — those names exist only as **Flask handlers** in **`apps/visualizer/backend/api/images.py`**, **not** in `database.py`. Database counterparts are **`insert_catalog_similarity_group`**, **`clear_catalog_similarity_results`**, **`list_clip_embedded_catalog_keys_newest_first`**, plus raw SQL in the API for listing groups.
- **`catalog_has_instagram_match_conflict` / `apply_instagram_match_to_stack_members`** sit **between** stack operations and instagram/match concerns — planner should assign a **single home** (CONTEXT puts them in **matches.py**).
- **`migrate_unified_image_keys`** (public) and large **`_migrate_unified_image_keys`** belong in **db_init.py** with other migrations.
- **Helpers:** `_append_query_catalog_image_filters`, `_non_empty_str_list_for_json_array_filter`, `_sort_catalog_key_rows_newest_first` — stay with **`query_catalog_images` / catalog** unless a submodule exceeds maintainability (per 14-CONTEXT “Claude’s Discretion”).

### 1.3 Domain boundary check vs CONTEXT approximate lines

| CONTEXT band | Verified |
|--------------|----------|
| init/migrations 1–630 | `init_database` starts **394**; migrations run from **637** onward; **630–680** is `_migrate_add_column` + start of `_migrate_images_schema` |
| catalog 681–1595 | `generate_key` **681**; `query_catalog_images` **1408**; region extends through **~1651** before clip/similarity stack |
| embeddings 2125–3275 | Starts at **2982** (`_embeddable_catalog_description_sql`) after descriptions/undescribed; **3273+** is `get_all_images_with_descriptions` (descriptions domain) |
| similarity 3276–3350 | **Misaligned** — those lines are **perspectives/scores** header + `list_perspectives`; DB “similarity **job**” DDL lives in **migrations** (**860+**) and mutators **1653–1718** |
| vision_cache 3351–3557 | **Misaligned** — vision cache is **2700–2826**; **3351+** is scores |

---

## 2. images.py Structure Audit

**Blueprint:** one `bp = Blueprint("images", __name__)` at line **60**, registered in **`app.py`** as `app.register_blueprint(images.bp, url_prefix='/api/images')` (line **132**).

### 2.1 Route inventory → D-08 submodule

| Route (`@bp.route`) | Suggested submodule (D-08) |
|---------------------|----------------------------|
| `GET /instagram` | instagram.py |
| `GET /instagram/months` | instagram.py |
| `GET /instagram/<path:image_key>/thumbnail` | instagram.py |
| `GET /catalog/<path:image_key>/thumbnail` | catalog.py |
| `GET /catalog/months` | catalog.py |
| `GET /catalog` | catalog.py |
| `GET /catalog/<path:image_key>/similar` | catalog.py |
| `GET /catalog-similarity-groups` | catalog.py |
| `GET /stacks/<int:stack_id>/members` | stacks.py |
| `POST /stacks/<int:stack_id>/split-member` | stacks.py |
| `POST /stacks/<int:target_stack_id>/merge` | stacks.py |
| `POST /stacks/<int:stack_id>/representative` | stacks.py |
| `POST /nl-search` | search.py |
| `POST /semantic-search` | search.py |
| `POST /chat-search` | search.py |
| `GET /dump-media` | instagram.py |
| `GET /matches` | matches.py |
| `PATCH /matches/<path>/<path>/validate` | matches.py |
| `PATCH /matches/<path>/<path>/reject` | matches.py |
| `GET /<string:image_type>/<path:image_key>` | **Planning decision:** polymorphic detail — D-08 assigns to **catalog.py**; implementation may need **split routes** on `catalog` vs `instagram` Blueprints (`/catalog/<key>`, `/instagram/<key>`) to preserve URLs **without** ambiguous overlapping prefixes. |

### 2.2 Cross-cutting helpers (move to `common.py` per D-08/D-10)

Defined in `images.py` today: pagination/path roots/filter/date helpers listed in **14-CONTEXT D-08**; **`with_db` is not among them** (see §7).

---

## 3. database.py Callers

All production and test files that use **`from lightroom_tagger.core.database import`** or import via **`lightroom_tagger.core.database`** (excluding `.planning/`, `docs/`, milestone markdown). **Barrel `lightroom_tagger/core/__init__.py` and `lightroom_tagger/database.py` must keep working** — they re-export a **subset**; the new **`database/__init__.py`** must expose **everything** externally referenced below.

### 3.1 Backend (visualizer)

- `apps/visualizer/backend/api/images.py`, `system.py`, `descriptions.py`, `scores.py`, `perspectives.py`
- `apps/visualizer/backend/utils/db.py` — **`init_database`**
- `apps/visualizer/backend/jobs/handlers/analyze.py`, `embed.py`, `instagram.py`, `matching.py`, `stacks.py`
- Tests: all `apps/visualizer/backend/tests/test_*.py` that grep matched (handlers, images, identity, analytics, matches, etc.)

### 3.2 Core library

- `lightroom_tagger/core/description_service.py`, `scoring_service.py`, `matcher.py`, `clip_similarity.py`, `semantic_search.py`, `search_tools.py`, `vision_cache.py`, `core/cli.py`, `path_utils.py`, `posting_analytics.py`
- `lightroom_tagger/lightroom/enricher.py`, `lightroom_tagger/instagram/crawler.py`

### 3.3 Scripts / dev entrypoints

- `lightroom_tagger/scripts/*.py` (benchmark, import, match, analyze, …), `scripts/sync_perspectives.py`, `lightroom_tagger/cli.py`, `test_direct_match.py`, root-level tests (`test_database*.py`)

**Planner action:** Generate **`__all__` or a grep-based checklist** from `database.py` public defs + symbols referenced in `lightroom_tagger/core/__init__.py` / `lightroom_tagger/database.py` to ensure **no export gaps**.

---

## 4. images.py / Blueprint Registration

**Current pattern** (`app.py` **119–140**):

- `from api import … images …`
- `app.register_blueprint(images.bp, url_prefix='/api/images')`

**Cross-imports of `api.images` helpers (not `bp`):**

- `api/identity.py` — `from api.images import _clamp_pagination`
- `api/analytics.py` — `from api.images import _clamp_pagination`

After package split, these should import from **`api.images.common`** (or the chosen common module path).

**Test-only:**

- `tests/test_images_chat_search_api.py` — `import api.images as api_images`

**Target pattern (D-11):** e.g. `from api.images import catalog_bp, stacks_bp, instagram_bp, matches_bp, search_bp` and **five** `register_blueprint(..., url_prefix=...)` calls. **`app.py`** must list **five** prefixes consistent with **D-09**; integration tests that assert full paths (many under `apps/visualizer/backend/tests/test_images_*.py`) must be updated **in lockstep** with the frontend.

---

## 5. Frontend Fetch Call Sites (42 references)

### 5.1 How “42” is produced

`rg "/images/" apps/visualizer/frontend/src --glob "*.ts" --glob "*.tsx"` → **42** lines. Not every line is a network call; **imports** like `'../components/images/CatalogTab'` match the pattern.

### 5.2 Hardcoded absolute `/api/images` (browser hits port origin, not `request()`)

| File | Current URL / pattern | After D-09 (if URLs unchanged — see §5.4) |
|------|-------------------------|----------------------------------------|
| `utils/imageUrl.ts` | `/api/images/${type}/${key}/${variant}` (thumbnail, full) | Same paths if blueprint layout preserves `/api/images/{catalog|instagram}/…` |
| `ImageTile.tsx`, `ImageDetailModal.tsx`, `PostNextSuggestionsPanel.tsx`, `MatchDetailModal.tsx` | Thumbnail URLs under `/api/images/.../thumbnail` | Same, coordinated with `imageUrl` |
| `utils/__tests__/imageUrl.test.ts`, `ImageTile.test.tsx` | Expectations on `/api/images/...` | Update expected strings if prefixes change |
| `services/api.ts` (comments) | Doc strings referencing `/api/images/...` | Doc-only |

### 5.3 `API_URL` + relative paths (`API_DEFAULT_URL = '/api'`)

Effective browser URL = `/api` + path from `request()`.

| File / API surface | Current `request()` path (representative) | Effective URL today | New path if **`search_bp`** uses prefix `/api/images/search` and routes `/nl-search`, `/semantic-search`, `/chat-search` (D-09) |
|--------------------|-------------------------------------------|---------------------|------------------------------------------------------------------|
| `ImagesAPI.listInstagram` | `/images/instagram?…` | `/api/images/instagram?…` | Unchanged if `instagram_bp` prefix + route preserve path |
| `ImagesAPI.getInstagramMonths` | `/images/instagram/months` | `/api/images/instagram/months` | Unchanged |
| `ImagesAPI.getCatalogMonths` | `/images/catalog/months` | `/api/images/catalog/months` | Unchanged |
| `ImagesAPI.listCatalog` | `/images/catalog?…` | `/api/images/catalog?…` | Unchanged |
| `ImagesAPI.getImageDetail` | `/images/${type}/${key}` | `/api/images/...` | Planner must keep polymorphic detail stable or update **`getImageDetail`** + tests |
| `ImagesAPI.listCatalogSimilarityGroups` | `/images/catalog-similarity-groups` | `/api/images/catalog-similarity-groups` | **Careful:** blueprint design must not turn this into `/api/images/catalog/catalog-similarity-groups` |
| Stack mutations / members | `/images/stacks/...` | `/api/images/stacks/...` | Unchanged if `stacks_bp` uses prefix `/api/images/stacks` and routes `/<id>/members`, etc. |
| `ImagesAPI.chatSearch` | `/images/chat-search` | `/api/images/chat-search` | **`/images/search/chat-search`** if D-09 strictly nests search |
| `MatchingAPI.*` | `/images/matches...` | `/api/images/matches...` | Unchanged if `matches_bp` prefix is `/api/images/matches` |
| System/dump (in `api.ts`) | `/images/dump-media` | `/api/images/dump-media` | Likely **instagram** submodule |

**Not present in frontend TS today:** `/images/nl-search`, `/images/semantic-search` (still used in **pytest** only).

### 5.4 Planner warning (D-09 vs Flask routing)

Naive `url_prefix='/api/images/catalog'` for all “catalog” endpoints can **break** paths that today sit **beside** `/catalog/` (e.g. **`/api/images/catalog-similarity-groups`** is **not** under the `catalog/` **folder** segment). The plan should either:

- Use **multiple registrations** from `catalog` module (different prefixes for subtree vs sibling paths), or  
- Normalize route strings so **final URLs** stay identical while Blueprints split.

---

## 6. Test Files Inventory

### 6.1 `lightroom_tagger/core/`

| File | Scope |
|------|--------|
| `test_database.py` (~1,074 lines) | Broad integration of DB operations — split across **`test_database_*.py`** per **D-06**; imports can stay **`lightroom_tagger.core.database`** if barrel re-exports |
| `test_database_scores.py` | Perspectives / scores — becomes/scores stays **`test_database_scores.py`** (update imports if tests import submodule symbols directly) |
| `test_database_stack_collapse.py` | Absorbed into **`test_database_stacks.py`** per D-06/D-07 |
| `test_database_nl_filter_arrays.py` | `query_catalog_images` NL filter arrays — keep filename per D-06; update imports only |

**Related tests outside `test_database*.py`:** `test_semantic_rrf.py`, `test_clip_similarity.py`, `test_description_service.py`, `test_scoring_service.py`, `test_vision_cache.py`, `test_identity_service.py`, `test_posting_analytics.py` — import **`database`** symbols; **no rename required** if **`database/__init__.py`** re-exports.

### 6.2 `apps/visualizer/backend/tests/` (images API)

- `test_images_catalog_api.py`, `test_images_detail_api.py`, `test_images_clip_similar_api.py`, `test_images_stacks_api.py`, `test_images_nl_search_api.py`, `test_images_semantic_search_api.py`, `test_images_chat_search_api.py`
- Plus: `test_match_groups.py`, `test_match_validation.py`, `test_matches_descriptions.py`, `test_catalog_score_query.py` (assert `/api/images/...` paths)

**Co-split:** Prefer **mirror** `test_api_images_<area>.py` only if you split test files for clarity; otherwise **same files**, update URLs when D-09 lands.

---

## 7. with_db Decorator Location

- **Current:** `from utils.db import with_db` at top of **`api/images.py`**. Implementation: **`apps/visualizer/backend/utils/db.py`** (`with_db` wraps **`lightroom_tagger.core.database.init_database`** for the library DB path from **`LIBRARY_DB`**).
- **After split:** Each route module should **`from utils.db import with_db`** (or re-export once from **`api/images/common.py`** if you want a single import line — optional). **Do not duplicate** the decorator implementation.

---

## 8. seed_perspectives_from_prompts_dir Placement

**Location today:** `database.py` **334–391**; **`init_database` calls it** at **625**.

**Behavior:** Reads markdown files from `prompts/perspectives`, inserts into **`perspectives`** table when empty — **one-time schema/seed side effect** tied to DB initialization, not scoring logic. Private helper **`_perspective_seed_description`** (lines **315–332**) is only used by this seed.

**Recommendation:** **`db_init.py`** alongside **`init_database`** (and keep **`_perspective_seed_description`** next to the seed, or private inside the same module). **`scores.py`** should own CRUD for perspectives when the table already exists (`list_perspectives`, `insert_perspective`, …), not filesystem seeding.

---

## 9. Circular Import Risk Analysis

| Risk | Assessment |
|------|------------|
| **`database/__init__.py` re-exports submodules** | **Low** — follow Phase-13-style **acyclic** graph: **`db_init`** has migrations + seed; leaf modules take `conn` and do not import siblings. **`__init__.py`** only imports submodules to re-export names (possible **one-time** cycle if a submodule imports package root — **avoid** `from lightroom_tagger.core.database import X` **inside** `database/catalog.py`; use **relative** imports within package). |
| **`embeddings.py` vs `descriptions.py`** | **`_embeddable_catalog_description_sql`** is_embedding helper — keep with **embeddings**; descriptions module imports only what it needs. |
| **Vision cache importing scores/catalog** | Current `database.py` is flat — when split, **avoid** `scores` ↔ `vision_cache` mutual imports; both should depend on **`db_init`** only if needed for types, not runtime cycles. |
| **Images API subpackages** | **`common.py`** must not import **`catalog`** / **`search`** (Flask blueprints that pull in heavy deps). Import **`utils.db`** from route modules, not from a barrel that re-imports all blueprints. |

---

## 10. Phase 13 Scaffold Pattern (Concrete Examples)

### 10.1 `apps/visualizer/backend/jobs/handlers/__init__.py` (registry assembler)

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

**Phase 14 database analogue:** same **package layout**, but **`__init__.py`** **re-exports public DB functions** (D-02), not a single dict registry.

### 10.2 Family module excerpt (`analyze.py`)

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

**Apply to `lightroom_tagger/core/database/catalog.py`:** module docstring, **`from __future__`**, stdlib + **`sqlite3`**, **relative** `from .db_init import _dict_factory` **only if** shared and cannot stay local — prefer **parametric** helpers receiving `conn` without importing sibling modules at runtime cycle points.

**Scaffold first commit (D-12):** optional **`_legacy.py`** or keep **`database.py` as file** until package **`database/`** exists — same constraint as Phase 13: **cannot have both `database.py` and `database/`** as sibling names; use **`database/` package + temporary shim file renamed** (see **13-PATTERNS §6**).

---

## 11. Test Fixture Analysis

- **Core DB tests** overwhelmingly use **`tmp_path` / in-memory path** + **`init_database(path)`**; no repo-wide **`conftest.py`** for DB found.
- **If `database/__init__.py` preserves re-exports:** Fixture and import **changes are unnecessary** for co-split — only **file moves** of test code when mirroring modules (**D-06**).
- **If tests later import submodules directly** (like Phase 13 **D-03** for handlers), pytest **patch paths** would need updates — **not required** by current **D-02** wording (callers stay on **`lightroom_tagger.core.database`**).
- **Visualizer API tests** that hardcode **`/api/images/...`:** must be edited when D-09 final URLs are fixed; **no pytest fixture** change beyond optional **Flask test client** base URL (not used today).

---

## Validation Architecture

| Layer | Command / intent |
|-------|------------------|
| **Python** | Full pytest (or project standard subset) **after every commit**; **Phase 14 zero-behavior-change** |
| **Types** | `tsc --noEmit` after frontend URL edits |
| **Contracts** | `.cursor/rules/job-log-contract.mdc` / `job-ui-contract.mdc` — **no new job types**; API response shapes unchanged except where URL strings appear **inside JSON** (e.g. `thumbnail_url` in `images.py` today builds **`/api/images/catalog/{key}/thumbnail`**) — **must stay consistent** with frontend `imageUrl` / img `src` |
| **Backend restart** | `.cursor/rules/backend-restart.mdc` after backend edits |

### Submodule checklist (sketch)

| Split | Verify |
|-------|--------|
| **database/db_init** | Fresh `init_database` on temp file; migrations idempotent; **seed** inserts perspectives when empty |
| **database/catalog** | `query_catalog_images` + filters; **`library_write` / `resolve_filepath`** |
| **database/embeddings** | Text/CLIP list + upsert helpers used by jobs |
| **database/scores** | Perspective + score CRUD |
| **images (per Blueprint)** | Hit representative GET/POST for each prefix; **`with_db`** still closes connections |

---

## RESEARCH COMPLETE
