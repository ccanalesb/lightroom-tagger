# Directory Structure

## Overview

Top-level layout (conceptual; omitting generated caches and local venv):

```
lightroom-tagger/
├── lightroom_tagger/          # Installable Python package (domain + CLI)
├── apps/visualizer/
│   ├── backend/               # Flask + Socket.IO + job SQLite
│   └── frontend/              # React + Vite SPA
├── scripts/                   # Repo-level dev helpers (e.g. dev-up.sh)
├── docs/                      # Design notes, plans, ad-hoc writeups
├── pyproject.toml             # Package metadata, dependencies, console_scripts
├── README.md
└── config.yaml                # Runtime config (typical local path; not always committed)
```

The **authoritative application code** for tagging/matching lives under `lightroom_tagger/`. The **visualizer** is an optional sibling application that depends on the editable/same-repo package and environment variables (e.g. `LIBRARY_DB`) to point at your library SQLite file.

## Key Locations

### Python package: `lightroom_tagger/`

| Path | Purpose |
|------|---------|
| `lightroom_tagger/__main__.py` | Delegates to `core.cli` for `python -m lightroom_tagger`. |
| `lightroom_tagger/core/cli.py` | Main CLI: subcommands for scan, search, export, Instagram crawl, match, sync. |
| `lightroom_tagger/core/config.py` | `Config` + `load_config()` — YAML and env. Prefer this over root `config.py` for new work. |
| `lightroom_tagger/core/database.py` | Library SQLite schema and queries (images, matches, descriptions, dump media, vision rows). |
| `lightroom_tagger/core/matcher.py` | Matching scoring, candidate queries, vision-aware paths. |
| `lightroom_tagger/core/vision_client.py` | OpenAI-compatible vision calls; SDK error mapping. |
| `lightroom_tagger/core/provider_registry.py` | Provider/model registry; `get_client`. |
| `lightroom_tagger/core/providers.json` | Default provider config (copy from `providers.example.json` if missing). |
| `lightroom_tagger/core/fallback.py` | `FallbackDispatcher` — cascade across providers with retry. |
| `lightroom_tagger/core/analyzer.py` | Prompt building and response parsing for descriptions/analysis. |
| `lightroom_tagger/core/description_service.py` | High-level “describe this catalog/IG row if needed”. |
| `lightroom_tagger/core/vision_cache.py` | Filesystem cache for vision pipeline inputs. |
| `lightroom_tagger/core/hasher.py`, `core/phash.py` | Hashing and Hamming distance utilities. |
| `lightroom_tagger/lightroom/reader.py` | **Preferred** `.lrcat` read path (WAL/NAS-aware `connect_catalog`). |
| `lightroom_tagger/lightroom/writer.py` | Keyword and catalog write helpers. |
| `lightroom_tagger/instagram/` | Scraper, crawler, dump reader, deduplication, browser automation pieces. |
| `lightroom_tagger/scripts/` | Long-running or report-oriented entry modules (matching, import, reports). |
| `lightroom_tagger/core/test_*.py` | Pytest modules colocated with core. |

**Legacy / compatibility (package root)**

| Path | Note |
|------|------|
| `lightroom_tagger/cli.py` | Older CLI implementation; **do not use** for new entry — use `core/cli.py`. |
| `lightroom_tagger/catalog_reader.py` | Older catalog reader; superseded by `lightroom/reader.py` for NAS/WAL behavior. |
| `lightroom_tagger/config.py` | Older config dataclass; `core/config.py` is the extended version used by CLI and backend. |
| `lightroom_tagger/database.py` | Re-exports `core.database` for backward-compatible imports. |
| `lightroom_tagger/lr_writer.py` | Legacy writer imports; prefer `lightroom/writer.py`. |
| `lightroom_tagger/schema_explorer.py` | Utility to inspect `.lrcat` schema. |
| `lightroom_tagger/tagger.py`, `lightroom/tagger.py` | Tagging-related logic (see imports from CLI/scripts). |

### Visualizer backend: `apps/visualizer/backend/`

| Path | Purpose |
|------|---------|
| `app.py` | `create_app()` — CORS, Socket.IO, blueprint registration, job processor thread. |
| `config.py` | Backend-only settings (e.g. `FRONTEND_URL`, DB path for **jobs** DB). |
| `database.py` | **Visualizer** SQLite: `jobs`, optional `provider_models` — not the library catalog DB. |
| `api/jobs.py`, `api/images.py`, `api/descriptions.py`, `api/providers.py`, `api/system.py` | REST blueprints (`/api/...`). |
| `jobs/handlers.py` | Per-`job.type` implementations; bridge to `lightroom_tagger.*`. |
| `jobs/runner.py` | Job state transitions and progress updates. |
| `websocket/events.py` | Socket.IO event handlers. |
| `utils/db.py`, `utils/responses.py` | Shared Flask helpers. |
| `tests/` | Backend pytest suite. |
| `requirements.txt` | Backend-specific pins (use alongside root `pyproject.toml` library deps). |

### Visualizer frontend: `apps/visualizer/frontend/src/`

| Path | Purpose |
|------|---------|
| `main.tsx`, `App.tsx` | Bootstrap and router (`/`, `/images`, `/processing`). |
| `pages/` | Route-level screens: `DashboardPage`, `ImagesPage`, `ProcessingPage`. |
| `components/Layout.tsx` | App shell / navigation. |
| `components/images/` | Catalog / matches / Instagram tabs for the Images area. |
| `components/processing/` | Tabs for matching, descriptions, jobs, providers, cache. |
| `components/catalog/` | Catalog-specific cards/modals. |
| `components/matching/` | Match cards, detail modal, sliders, job status panels. |
| `components/ui/` | Reusable primitives (Button, Card, Tabs, Pagination, Thumbnail, etc.). |
| `services/api.ts` | Fetch wrappers for backend REST. |
| `hooks/` | `useJobSocket`, `useBatchJob`, `usePagination`, provider hooks, etc. |
| `stores/` | React context (e.g. match options, socket store). |
| `types/`, `utils/`, `constants/` | Shared TS types and helpers. |

### Repo scripts and docs

| Path | Purpose |
|------|---------|
| `scripts/dev-up.sh`, `scripts/dev-down.sh` | Start/stop local backend + frontend with sane defaults. |
| `docs/` | Plans, batch testing notes, architecture sketches — not runtime code. |

## Naming Conventions

### Python

- **Package**: `lightroom_tagger` uses underscores (PEP 8). Subpackages: `core`, `lightroom`, `instagram`, `scripts`.
- **Tests**: `test_<module>.py` beside or under the same package tree (e.g. `lightroom_tagger/core/test_matcher.py`, `apps/visualizer/backend/tests/test_jobs_api.py`).
- **Private helpers**: Leading underscore functions in modules (e.g. `_deserialize_row` in `core/database.py`).
- **CLI**: Subcommands are **kebab-case** strings in argparse (`scan`, `crawl-instagram`, `instagram-sync`).
- **Config keys**: Snake_case in YAML and `Config` fields (`match_threshold`, `vision_model`).

### TypeScript / React (`apps/visualizer/frontend`)

- **Components**: PascalCase files (`CatalogTab.tsx`, `MatchDetailModal.tsx`).
- **Hooks**: `use` prefix (`useJobSocket.ts`).
- **Utilities**: camelCase files (`imageUrl.ts`, `scoreColorClasses.ts`).
- **Feature folders**: Plural or domain names under `components/` (`matching/`, `providers/`, `images/`).
- **UI primitives**: Often folder + `index.ts` barrel (`components/ui/Button/Button.tsx`, `Button/index.ts`).

### Data and config files

- **SQLite**: Library DB path is user-defined (commonly `library.db`); visualizer jobs DB path from backend `config.py` (relative to backend dir).
- **Provider config**: `lightroom_tagger/core/providers.json` (gitignored or local; `providers.example.json` as template).

### Practical examples

- **Add a new CLI subcommand**: extend `create_parser()` and dispatch in `main()` in `lightroom_tagger/core/cli.py`; reuse `core.database` and `lightroom.reader` for I/O.
- **Add a new job type for the UI**: define handler in `apps/visualizer/backend/jobs/handlers.py`, register in `JOB_HANDLERS`, expose creation via `api/jobs.py`, and add a frontend call in `services/api.ts` + a tab or button in `components/processing/`.
- **Add a vision provider**: edit `lightroom_tagger/core/providers.json` (or runtime API if exposed); ensure `ProviderRegistry` can build `base_url` and `api_key`; no change to `vision_client.py` signatures required if the endpoint stays OpenAI-compatible.
