# Lightroom Tagger

Index a Lightroom catalog into a local SQLite database, generate AI descriptions and perspective scores, and browse your library in a web UI.

## Prerequisites

1. **Lightroom catalog** — a `.lrcat` file path. **Close Lightroom Classic** before scanning; an open catalog can cause `database is locked`.
2. **Vision provider** — local [Ollama](https://ollama.ai) (default model `gemma3:27b`: `ollama pull gemma3:27b`) or a cloud provider configured in `providers.json`.
3. **Backend port 5001** — the visualizer API listens on **5001**, not 5000. macOS AirPlay Receiver occupies 5000 and returns empty 200/403 responses that look like a broken backend. Vite proxies `/api` to 5001.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r apps/visualizer/backend/requirements.txt
```

## Quick Start (CLI)

```bash
# Initialize library.db (scan also creates it if missing)
lightroom-tagger init --db library.db

# Index catalog metadata into library.db
lightroom-tagger scan --catalog "/path/to/Catalog.lrcat" --db library.db

# Search by Lightroom metadata (keywords, filename, title, caption)
lightroom-tagger search --keyword "landscape" --db library.db

# Export or inspect
lightroom-tagger export --db library.db --output export.json
lightroom-tagger stats --db library.db
```

**CLI search limitation:** `search` queries Lightroom-side columns only. AI-generated descriptions are searchable on the **Images** page in the visualizer (FTS5). Wiring the CLI to `image_descriptions_fts` is tracked in [#247](https://github.com/ccanalesb/lightroom-tagger/issues/247).

Incremental catalog updates (additions only):

```bash
lightroom-tagger sync --catalog "/path/to/Catalog.lrcat" --db library.db
```

## Visualizer (Web UI)

```bash
cp apps/visualizer/backend/.env.example apps/visualizer/backend/.env
# Edit .env: set LIBRARY_DB to the absolute path of library.db

cd apps/visualizer/frontend && npm install --legacy-peer-deps && cd ../../..
make dev
# Open http://localhost:5173
```

Stop with `make dev-down`.

### Pages

| Page | URL | Purpose |
|------|-----|---------|
| Insights | `/` | Overview and stats |
| Images | `/images` | Browse, filter (including AI description search), catalog similarity |
| Identity | `/identity` | Style fingerprint and posting advisor |
| Processing | `/processing` | Describe, score, embed, stack detection, catalog similarity jobs |

Legacy URLs (`/search`, `/analytics`, `/instagram`, `/matching`, `/jobs`) redirect to the pages above.

### Typical workflow

1. **Scan** (CLI) or **Sync catalog** (Processing) — populate `library.db`.
2. **Embed catalog images** — CLIP embeddings power **catalog similarity** (`clip_similarity`).
3. **Stack detection** — group burst shots; the representative frame is described and scored.
4. **Batch describe / score** — AI descriptions and perspective scores via Ollama or configured providers.
5. **Catalog similarity** — review similar-image groups.
6. **Images** — browse, filter by description, inspect scores; mark posted (`instagram_posted`) in the detail modal.
7. **Identity** — Mirror (style fingerprint) and Advisor (what to post next).

## Configuration

Edit `config.yaml` at the repo root (or pass `--config`):

```yaml
catalog_path: "/path/to/Catalog.lrcat"
db_path: "./library.db"
mount_point: "/mnt/nas"
workers: 4
vision_model: "gemma3:27b"
ollama_host: "http://localhost:11434"
stack_burst_delta_ms: 2000
vision_cache_enabled: true
```

All keys above are fields on `Config` in `lightroom_tagger/core/config.py`. Unknown keys in an existing `config.yaml` are ignored with a warning.

Environment overrides (common): `VISION_MODEL`, `LIGHTRoom_CATALOG`, `LIGHTRoom_DB`, `OLLAMA_HOST`, `INSTAGRAM_DUMP_PATH`.

**NAS catalogs:** close Lightroom Classic if you see `database is locked`. See [docs/CATALOG_READ_WRITE.md](docs/CATALOG_READ_WRITE.md) and [docs/STORAGE_MOUNT_REQUIREMENTS.md](docs/STORAGE_MOUNT_REQUIREMENTS.md).

## Further reading

| Doc | Audience |
|-----|----------|
| [CONTEXT-MAP.md](CONTEXT-MAP.md) | Where to find library vs visualizer context |
| [lightroom_tagger/CONTEXT.md](lightroom_tagger/CONTEXT.md) | CLI, `library.db`, vision pipeline |
| [apps/visualizer/CONTEXT.md](apps/visualizer/CONTEXT.md) | Flask API, jobs, React SPA |
| [AGENTS.md](AGENTS.md) | Agent workflow and issue tracker |
| [docs/parked/](docs/parked/) | Retired capabilities (Instagram matching, etc.) |

## Development

```bash
# Backend tests (from apps/visualizer/backend)
cd apps/visualizer/backend && PYTHONPATH=. pytest tests/ -q

# Frontend tests
cd apps/visualizer/frontend && npm test -- --run

# README integrity check
python scripts/verify_readme.py
```
