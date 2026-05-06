# Phase 13 — Pattern mapping (handlers split)

**Source:** `13-CONTEXT.md`, `13-RESEARCH.md`, `handlers.py`, `checkpoint.py`, `runner.py`, `jobs/__init__.py`, selected tests.

This document tells planners/implementers **which files to touch**, **what role each plays**, **which existing module to imitate**, and **concrete import/registry patterns** to preserve.

---

## 1. File inventory (create / modify / delete)

### New package under `apps/visualizer/backend/jobs/handlers/`

| File | Role | Closest analog |
|------|------|----------------|
| `__init__.py` | **Registry assembler** — runs `path_setup` once; exposes **only** `JOB_HANDLERS` (and optional `__all__ = ("JOB_HANDLERS",)`). No handler re-exports. | Bottom of current `handlers.py` (`JOB_HANDLERS` dict) + **single** side-effect import (today line 51). |
| `common.py` | **Shared helpers/constants** — cross-family symbols per D-06 / RESEARCH (`_resolve_library_db_or_fail`, `_failure_severity_from_exception`, `_select_catalog_keys`, `_select_instagram_keys`, `_resolve_date_window`, `_CATALOG_NOT_VIDEO_SQL`, plus `_CHECKPOINT_MAX_ENTRIES`, `_INSTAGRAM_NOT_VIDEO_SQL`, `_LEGACY_DATE_FILTER_MONTHS`). Must **not** import family modules (avoid cycles). | `checkpoint.py` — focused module, stdlib + domain imports only; docstring at top. |
| `instagram.py` | **New submodule** — `handle_analyze_instagram`, `handle_instagram_import`. | `checkpoint.py` / `runner.py` file-level organization (one concern, explicit imports). |
| `matching.py` | **New submodule** — matching family + `_expand_matches_for_lightroom_writes`. | Same. |
| `analyze.py` | **New submodule** — describe/score/analyze handlers + analyze-local helpers including `_select_catalog_keys_missing_visual_tags` (D-05). | Same. |
| `embed.py` | **New submodule** — text/image embed + `_PREFLIGHT_RNG_SEED` and embed-only constants. **Leaf:** no imports from `stacks`/`matching`. | Same. |
| `stacks.py` | **New submodule** — stack/similarity/cache-build + `_CatalogCacheStageRunner`, `_catalog_cache_stage_mapped_progress`; may **import from `.embed`** for composite job inners (one-way). | Same. |
| `_legacy.py` | **Transitional monolith** — rename of current `handlers.py` body during migration; **shrinks** as families move out; **deleted** on final commit. | N/A (scaffold only). |

### Deleted after migration

| Path | Role |
|------|------|
| `apps/visualizer/backend/jobs/handlers.py` | **Replaced** by package `jobs/handlers/`; cannot coexist with package (Python resolution). |

### Modified — tests (D-03; ~313 `jobs.handlers` occurrences per RESEARCH)

| File | Role |
|------|------|
| `tests/test_handlers_batch_analyze.py` | **Modified test** — `from jobs.handlers.analyze import …`; `@patch('jobs.handlers.analyze.*')` (or upstream targets). |
| `tests/test_handlers_batch_describe.py` | Same pattern for analyze family. |
| `tests/test_handlers_batch_score.py` | Same. |
| `tests/test_handlers_batch_embed_image.py` | **Heavy** — `import jobs.handlers as job_handlers` must become **`jobs.handlers.embed`** for `monkeypatch.setattr` on `encode_images`, `resolve_filepath`, `_EMBED_*`, `_PREFLIGHT_*` (per RESEARCH). |
| `tests/test_handlers_batch_text_embed.py` | **`from jobs import handlers`** + `monkeypatch.setattr(handlers, "embed_texts", …)` — after split, use **`from jobs.handlers import embed as embed_mod`** (or similar) and setattr on **`embed_mod`** where `embed_texts` is imported. |
| `tests/test_handlers_batch_stack_detect.py` | `from jobs.handlers.stacks import …` for `_build_burst_segments`, `handle_batch_stack_detect`. |
| `tests/test_handlers_batch_catalog_similarity.py` | Stacks family. |
| `tests/test_handlers_catalog_cache_build.py` | `JOB_HANDLERS` import stays `from jobs.handlers import JOB_HANDLERS`; patch inner symbols on **stacks** / **embed** submodules. |
| `tests/test_handlers_single_match.py` | Matching family. |
| `tests/test_handlers_date_window.py` | **Mixed** — `_resolve_date_window` → `jobs.handlers.common`; handlers → `analyze`. |
| `tests/test_select_instagram_keys.py` | `_select_instagram_keys` → `jobs.handlers.common`. |
| `tests/test_stack_matching_integration.py` | Matching family entrypoints. |

### Modified — other

| File | Role |
|------|------|
| `lightroom_tagger/scripts/test_import_instagram_dump.py` | Docstring/comment path `…jobs.handlers…` → update when symbol moves (RESEARCH). |
| `.cursor` / hooks referencing `handlers.py` | **job-ui-contract** / `job-handler-flag.sh` may reference file path — confirm after package exists (RESEARCH). |

### Unchanged (stable public API)

| File | Role |
|------|------|
| `app.py` | **Consumer** — `from jobs.handlers import JOB_HANDLERS` (lines ~213, ~283) unchanged if `__init__.py` exports registry. |

### Parent package `jobs/__init__.py`

| File | Role |
|------|------|
| `apps/visualizer/backend/jobs/__init__.py` | Currently a **minimal stub** (`# Job runner package` only). **No** pattern for aggregating subpackages — sibling modules (`checkpoint.py`, `runner.py`) are imported by **direct** `from jobs.checkpoint` / `from jobs.runner` / `from jobs.handlers`. New work does **not** require changing this file unless you explicitly want a barrel export (out of scope for D-02). |

---

## 2. Analog: `checkpoint.py` (separated domain module)

**Pattern:** module docstring, `from __future__ import annotations`, focused imports, **public** `CHECKPOINT_VERSION` and functions; no package `__init__` re-exports.

```1:51:apps/visualizer/backend/jobs/checkpoint.py
"""Job checkpoint helpers for persisting resume state in ``jobs.metadata[\"checkpoint\"]``.
...
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from lightroom_tagger.core.clip_embedding_service import CLIP_EMBED_DIM, CLIP_EMBED_MODEL_ID
from lightroom_tagger.core.embedding_service import TEXT_EMBED_DIM, TEXT_EMBED_MODEL_ID

CHECKPOINT_VERSION: int = 1
```

**Apply to family modules:** each submodule imports **only** the `checkpoint` symbols it needs (as `handlers.py` does today at lines 52–61), not the whole fingerprint surface area.

---

## 3. Analog: `runner.py` (class + integration imports)

**Pattern:** package-relative import of sibling module; **no** `path_setup` here.

```1:12:apps/visualizer/backend/jobs/runner.py
import threading

from database import (
    add_job_log,
    get_job,
    job_log_has_message,
    make_connection_for_path,
    update_job_field,
    update_job_status,
)

from .checkpoint import merge_checkpoint_into_metadata
```

**Apply to handlers submodules:** use **relative** imports inside `jobs.handlers` (e.g. `from .common import _resolve_library_db_or_fail`), and absolute **`database` / `library_db` / `lightroom_tagger.*`** as today.

---

## 4. Current `handlers.py` — side effect, constants, registry

### Side-effect import (exactly once in new `handlers/__init__.py`)

```51:61:apps/visualizer/backend/jobs/handlers.py
from . import path_setup as _path_setup  # noqa: F401
from .checkpoint import (
    fingerprint_batch_describe,
    fingerprint_batch_embed_image,
    fingerprint_batch_score,
    fingerprint_batch_stack_detect,
    fingerprint_batch_text_embed,
    fingerprint_catalog_cache_build,
    fingerprint_catalog_keys,
    fingerprint_vision_match,
)
```

After split: **`path_setup` only in `handlers/__init__.py`**. Fingerprint imports move **into each family module** that needs them (not duplicated in `__init__.py` unless required for a transitional shim).

### Module-level constants (split per RESEARCH / CONTEXT)

```63:76:apps/visualizer/backend/jobs/handlers.py
_CHECKPOINT_MAX_ENTRIES = 100_000
_BATCH_EMBED_IMAGE_SIZE = 8
_EMBED_PREFLIGHT_SAMPLE_SIZE = 25
_EMBED_PREFLIGHT_FAIL_RATIO = 0.5
_EMBED_SKIP_DETAIL_LOG_LIMIT = 5
_EMBED_SUMMARY_LOG_EVERY = 250
_CATALOG_SIMILARITY_SUMMARY_EVERY = 500
_STACK_DETECT_SUMMARY_EVERY = 500
_VISION_MATCH_PREFILTER_SUMMARY_EVERY = 40

# Test-only seed override for the embed preflight sampler. Setting this from a
# test gives deterministic random.sample() output without exposing the seed in
# production behaviour. ``None`` (default) uses real entropy.
_PREFLIGHT_RNG_SEED: int | None = None
```

### `JOB_HANDLERS` — single integration surface (lives only in `handlers/__init__.py` after split)

```3833:3849:apps/visualizer/backend/jobs/handlers.py
JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'instagram_import': handle_instagram_import,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
    'prepare_catalog': handle_prepare_catalog,
    'batch_describe': handle_batch_describe,
    'single_describe': handle_single_describe,
    'single_score': handle_single_score,
    'batch_score': handle_batch_score,
    'batch_analyze': handle_batch_analyze,
    'batch_stack_detect': handle_batch_stack_detect,
    'batch_catalog_similarity': handle_batch_catalog_similarity,
    'batch_text_embed': handle_batch_text_embed,
    'batch_embed_image': handle_batch_embed_image,
    'catalog_cache_build': handle_catalog_cache_build,
}
```

Handlers share the established signature:

- `def handle_*(runner, job_id: str, metadata: dict) -> None` (same as today throughout the monolith).

---

## 5. Test import and patch patterns (examples)

### Analyze tests — late import + `jobs.handlers.*` patches

```14:22:apps/visualizer/backend/tests/test_handlers_batch_analyze.py
@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_analyze_completes_with_zero_images(
    _mock_exists, _mock_getenv, mock_config, mock_init_db, _mock_add_log,
):
    from jobs.handlers import handle_batch_analyze
```

**Planner rule:** after split, either:

- **D-03:** `from jobs.handlers.analyze import handle_batch_analyze` and `@patch('jobs.handlers.analyze.add_job_log')`, etc., **or**
- Patch **upstream** (`database.add_job_log`, `lightroom_tagger.core.database.init_database`, …) to reduce churn.

**Fingerprint mock** today targets the **monolith module**:

```198:203:apps/visualizer/backend/tests/test_handlers_batch_analyze.py
@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers._score_single_image')
...
@patch('jobs.handlers.fingerprint_batch_describe', return_value='fp-describe-constant')
```

Prefer after split: `jobs.handlers.analyze.fingerprint_batch_describe` (if imported there) or **`jobs.checkpoint.fingerprint_batch_describe`** for stability.

### Describe tests — same `jobs.handlers` patch prefix

```12:20:apps/visualizer/backend/tests/test_handlers_batch_describe.py
@patch('jobs.handlers.add_job_log')
@patch('jobs.handlers.init_database')
@patch('jobs.handlers.load_config')
@patch('jobs.handlers.os.getenv', return_value='/tmp/library.db')
@patch('jobs.handlers.require_library_db', return_value='/tmp/library.db')
def test_batch_describe_should_complete_with_zero_images(
    _mock_exists, mock_getenv, mock_config, mock_init_db, _mock_add_log,
):
    from jobs.handlers import handle_batch_describe
```

### Embed image tests — package alias + `monkeypatch` on module attributes

```10:14:apps/visualizer/backend/tests/test_handlers_batch_embed_image.py
import sqlite_vec
from database import create_job, get_job, init_db, update_job_field
import jobs.handlers as job_handlers
from jobs.checkpoint import CHECKPOINT_VERSION, fingerprint_batch_embed_image
from jobs.runner import JobRunner
```

```94:102:apps/visualizer/backend/tests/test_handlers_batch_embed_image.py
@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_embed_image_zero_work_completes(
    mock_load_config, _mock_add_log, tmp_path, monkeypatch
) -> None:
    from jobs.handlers import handle_batch_embed_image

    ...
    monkeypatch.setattr(job_handlers, "encode_images", mock_enc)
```

**Critical:** `encode_images`, `resolve_filepath`, `_EMBED_PREFLIGHT_*`, `_EMBED_SKIP_DETAIL_LOG_LIMIT` must live on **`jobs.handlers.embed`** (change alias to `import jobs.handlers.embed as job_handlers` or patch `lightroom_tagger.core.clip_embedding_service.encode_images` once).

### Text embed — occasional `from jobs import handlers`

```19:22:apps/visualizer/backend/tests/test_handlers_batch_text_embed.py
@patch("jobs.handlers.add_job_log")
@patch("jobs.handlers.load_config")
def test_batch_text_embed_zero_work_completes(mock_load_config, _mock_add_log, tmp_path, monkeypatch):
    from jobs.handlers import handle_batch_text_embed
```

---

## 6. `_legacy.py` scaffold (before final deletion)

**Constraint:** `jobs/handlers.py` (file) and `jobs/handlers/` (package) **must not** both exist.

**Recommended sequence (RESEARCH + D-07–D-09):**

1. **Rename** `handlers.py` → `handlers/_legacy.py`.
2. Add `handlers/__init__.py` that:
   - imports **`from . import path_setup as _path_setup  # noqa: F401`** once;
   - builds **`JOB_HANDLERS`** either by:
     - **`from ._legacy import JOB_HANDLERS`**, or
     - importing handler callables from `_legacy` and assembling the dict explicitly (preferred once symbols are stable).
3. **First green commit:** `from jobs.handlers import JOB_HANDLERS` works; `app.py` unchanged.
4. **Per-family commits:** move code from `_legacy.py` into `instagram.py`, …; shrink `_legacy`; update tests for that family’s patch paths in the **same** commit.
5. **Final commit:** delete `_legacy.py` when empty (or only re-exports remain — then delete).

Optional temporary pattern inside `_legacy` during migration: re-import moved symbols from submodules **instead of duplicating** bodies, until the last functions are deleted from `_legacy`.

---

## 7. Module-level side effects and constants placement (checklist)

| Item | Placement |
|------|-----------|
| `path_setup` | **`handlers/__init__.py` only** (once). |
| Fingerprint imports from `.checkpoint` | **Per family module** that uses them. |
| `common.py` imports | Stdlib + `database` / `library_db` / `lightroom_tagger.core.*` as needed; **no** imports from `analyze`, `embed`, `stacks`, `matching`, `instagram`. |
| `_PREFLIGHT_RNG_SEED` | **`embed.py`** (tests may set on `jobs.handlers.embed._PREFLIGHT_RNG_SEED`). |
| Cross-family caps / SQL / date helpers | **`common.py`** per D-06 + RESEARCH additions (`_CHECKPOINT_MAX_ENTRIES`, `_INSTAGRAM_NOT_VIDEO_SQL`, …). |
| Throttle constants per family | **`matching.py`**, **`stacks.py`**, **`embed.py`** as in RESEARCH table. |

**No** `atexit`, thread starts, or logging config at import — only **`path_setup`** today.

---

## 8. `app.py` stable contract

```213:213:apps/visualizer/backend/app.py
    from jobs.handlers import JOB_HANDLERS
```

```283:283:apps/visualizer/backend/app.py
                handler = JOB_HANDLERS.get(job_type)
```

---

## PATTERN MAPPING COMPLETE
