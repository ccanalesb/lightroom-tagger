# Architecture

## Pattern

The repository is a **monolith Python library** (`lightroom_tagger`) with an optional **companion web app** under `apps/visualizer/`. The library owns domain logic, SQLite persistence for the photo library, CLI entry points, and Instagram/Lightroom integrations. The visualizer is a **thin orchestration layer**: Flask REST APIs, a background job queue in its own SQLite file, and a React SPA that drives long-running work (matching, descriptions) without reimplementing core algorithms.

There is intentional **duplication at the package root** (`lightroom_tagger/catalog_reader.py`, `lightroom_tagger/cli.py`, `lightroom_tagger/lr_writer.py`, `lightroom_tagger/config.py`) versus the **canonical `lightroom_tagger/core/` and `lightroom_tagger/lightroom/`** tree. New code and the published CLI (`python -m lightroom_tagger`, `lightroom-tagger` script) use **`core.cli`** and **`lightroom.reader` / `lightroom.writer`**. Root modules remain for backward compatibility and older import paths.

**Stack summary**

| Area | Technology |
|------|------------|
| Library | Python 3.10+, SQLite, OpenAI-compatible HTTP APIs (`openai` SDK) |
| CLI | `argparse` in `lightroom_tagger/core/cli.py` |
| Visualizer API | Flask + Flask-CORS + Flask-SocketIO |
| Visualizer UI | React, React Router, Vite |
| Dev orchestration | `scripts/dev-up.sh` starts backend + frontend |

## Layers

1. **Presentation**
   - **CLI**: `lightroom_tagger/core/cli.py` — `scan`, `match`, `crawl-instagram`, `instagram-sync`, search/export/stats, etc.
   - **Web UI**: `apps/visualizer/frontend/src/` — pages (`DashboardPage`, `ImagesPage`, `ProcessingPage`), feature components under `components/`, shared UI under `components/ui/`.
   - **HTTP/WebSocket**: Flask blueprints under `apps/visualizer/backend/api/`, Socket.IO registration in `apps/visualizer/backend/websocket/events.py`.

2. **Application / orchestration (visualizer only)**
   - **Job model**: `apps/visualizer/backend/database.py` — `jobs` table (pending → running → completed/failed), logs, metadata, optional `provider_models` cache.
   - **Job execution**: `apps/visualizer/backend/jobs/runner.py` + `jobs/handlers.py` — background thread in `app.py` polls pending jobs and dispatches by `type` via `JOB_HANDLERS`.
   - **Handlers** call into **`lightroom_tagger`** (e.g. `lightroom_tagger.scripts.match_instagram_dump.match_dump_media`) with progress/log callbacks wired to the job row and Socket.IO emits.

3. **Domain / business logic** (`lightroom_tagger/core/`, `lightroom_tagger/instagram/`, `lightroom_tagger/lightroom/`)
   - **Matching**: `core/matcher.py` — candidate filtering (e.g. EXIF), phash + text scoring, vision-augmented scoring, persistence of matches and vision comparison rows via `core/database.py`.
   - **Vision**: `core/vision_client.py` — `compare_images`, `generate_description` using any OpenAI-compatible client; errors mapped to `core/provider_errors.py`.
   - **Providers**: `core/provider_registry.py` reads `core/providers.json` (and optional auto-discovery), builds `openai.OpenAI` clients; `core/fallback.py` (`FallbackDispatcher`) applies retry + provider cascade.
   - **Descriptions**: `core/analyzer.py` (prompts/parsing), `core/description_service.py` (orchestrates describe + DB writes for catalog/Instagram paths).
   - **Hashing**: `core/hasher.py`, `core/phash.py` — perceptual hashes for similarity.
   - **Caching**: `core/vision_cache.py` — filesystem-backed cache for resized/derived assets used in vision workflows.
   - **Instagram**: `instagram/scraper.py`, `crawler.py`, `dump_reader.py`, `deduplicator.py`, `browser.py` — acquisition and normalization of dump/sidecar data into the library DB.
   - **Lightroom catalog I/O**: `lightroom/reader.py` — read `.lrcat` (SQLite) with WAL/NAS-aware `connect_catalog`; `lightroom/writer.py` — keyword writes and related catalog mutations.

4. **Data access**
   - **Library database** (single conceptual “library” DB path from `config.yaml` / `LIBRARY_DB`): `lightroom_tagger/core/database.py` — images, matches, descriptions, Instagram dump media, vision comparison cache tables, JSON columns deserialized in helpers like `_deserialize_row`, path resolution via `resolve_filepath` for UNC → local mount.
   - **Visualizer database**: separate SQLite file (see `apps/visualizer/backend/config.py` / `DATABASE_PATH`) — jobs and UI-adjacent state only; **not** a second copy of catalog rows.

5. **Cross-cutting**
   - **Configuration**: `lightroom_tagger/core/config.py` — `Config` dataclass, YAML + environment overrides (weights, thresholds, Ollama host, parallel matching settings, etc.).
   - **Retry**: `core/retry.py` — backoff used by `FallbackDispatcher` and vision paths.

## Data Flow

### End-to-end: catalog → index → Instagram → match → optional Lightroom keyword

1. **Catalog scan (CLI)**  
   User runs `lightroom-tagger scan` (or `python -m lightroom_tagger scan`).  
   `lightroom.reader.connect_catalog` opens the `.lrcat`; `get_image_records` (and related queries) produce normalized records; `core.database.init_database` / `store_images_batch` persist rows into the library SQLite DB (including keywords, EXIF JSON, paths).

2. **Instagram media ingestion**  
   Crawl/import scripts (`core/cli` subcommands, or standalone scripts under `lightroom_tagger/scripts/`) populate Instagram-related tables in the **same library DB** via `core.database` (paths, hashes, captions, linkage fields).

3. **Matching**  
   Pipeline scripts (e.g. `lightroom_tagger/scripts/match_instagram_dump.py` → `match_dump_media`) use `core.matcher` scoring (phash, optional descriptions, optional vision), read/write `matches` and vision comparison state through `core.database`. Configuration drives weights and thresholds (`core.config.load_config`).

4. **Write-back to Lightroom**  
   `lightroom.writer.add_keyword_to_images_batch` (used from CLI `instagram-sync`) updates the `.lrcat` for matched files.

### Visualizer: UI → API → jobs → library DB

1. Browser calls REST endpoints on `apps/visualizer/backend` (e.g. `POST /api/jobs` to enqueue, `GET /api/images/...` for lists and thumbnails metadata).
2. `create_app()` starts a **daemon thread** that runs `_job_processor`, which uses `JobRunner` + `JOB_HANDLERS`.
3. A handler such as `handle_vision_match` resolves `LIBRARY_DB` or `config.db_path`, opens the library DB with `lightroom_tagger.core.database.init_database`, then invokes `match_dump_media(...)` with callbacks that update job progress and append structured logs.
4. Socket.IO emits `job_updated` (and related events) so the SPA reflects live status (`frontend` hooks like `useJobSocket`).

### Vision / provider path (conceptual)

```
ProviderRegistry.get_client(provider_id)
    → openai.OpenAI(base_url=..., api_key=...)
FallbackDispatcher.call_with_fallback(...)
    → retry_with_backoff + cascade on RETRYABLE_ERRORS
vision_client.compare_images(client, model, ...) / generate_description(...)
    → ProviderError subclasses on failure (no raw SDK leakage to UI)
```

Example: matching uses registry + fallback to obtain a client and model label, then persists scores and reasoning in the library DB for audit and UI display.

## Key Abstractions

| Abstraction | Role | Primary location |
|-------------|------|------------------|
| **`Config`** | Central tunables (paths, weights, models, workers) | `lightroom_tagger/core/config.py` |
| **`ProviderRegistry`** | JSON-driven provider/model list, `get_client`, fallback order | `lightroom_tagger/core/provider_registry.py`, `core/providers.json` |
| **`ProviderError` hierarchy** | Typed failures (rate limit, auth, timeout, model unavailable, …) | `lightroom_tagger/core/provider_errors.py` |
| **`FallbackDispatcher`** | Retry + multi-provider fallback for compare/describe | `lightroom_tagger/core/fallback.py` |
| **Vision API surface** | `compare_images`, `generate_description` — OpenAI-compatible, image base64 | `lightroom_tagger/core/vision_client.py` |
| **`resolve_filepath`** | UNC/NAS path → local mount for file reads | `lightroom_tagger/core/database.py` |
| **`init_database` / row helpers** | Library schema, WAL, JSON column (de)serialization | `lightroom_tagger/core/database.py` |
| **`lightroom_tagger.database` module** | **Re-export** of selected `core.database` symbols for legacy imports | `lightroom_tagger/database.py` |
| **Job runner** | Stateful job lifecycle + progress hooks | `apps/visualizer/backend/jobs/runner.py` |
| **Flask blueprints** | REST namespaces: jobs, images, descriptions, providers, system | `apps/visualizer/backend/api/*.py` |

**Practical example — where to add a new REST capability for the library DB:** implement route logic in `apps/visualizer/backend/api/` using `lightroom_tagger.core.database` (and optionally `utils/db.with_db` for connection handling). For long runs, enqueue a job type in `jobs/handlers.py` and register it in `JOB_HANDLERS`.

## Entry Points

### Published console scripts (`pyproject.toml` → `[project.scripts]`)

| Script | Module callable |
|--------|-----------------|
| `lightroom-tagger` | `lightroom_tagger.core.cli:main` |
| `lightroom-analyze-instagram` | `lightroom_tagger.scripts.analyze_instagram_images:main` |
| `lightroom-run-matching` | `lightroom_tagger.scripts.run_vision_matching:main` |
| `lightroom-generate-report` | `lightroom_tagger.scripts.generate_validation_report:generate_html_report` |
| `lightroom-import-dump` | `lightroom_tagger.scripts.import_instagram_dump:main` |
| `lightroom-match-dump` | `lightroom_tagger.scripts.match_instagram_dump:main` |

### Module execution

- `python -m lightroom_tagger` → `lightroom_tagger/__main__.py` → `core.cli.main()`.

### Visualizer backend

- Flask app factory: `apps/visualizer/backend/app.py` — `create_app()`.
- Typical local run: `scripts/dev-up.sh` (or manual `flask` / `python` invocation from `apps/visualizer/backend` per project conventions).

### Visualizer frontend

- Vite bootstrap: `apps/visualizer/frontend/src/main.tsx` → `App.tsx` (routes under `/`, `/images`, `/processing` with legacy redirects from `/matching`, `/providers`, etc.).

### Notable pipeline scripts (library)

- `lightroom_tagger/scripts/match_instagram_dump.py` — heavy matching entry used by both CLI and visualizer job handlers.
