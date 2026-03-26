# Lightroom Tagger

A Python tool to read Lightroom catalog (`.lrcat` SQLite database), index metadata to a local SQLite database, and export/search your photo library. Includes Instagram matching with vision model support.

## Installation

```bash
pip install pyyaml python-dotenv
```

## Quick Start - Instagram Matching Flow

Match Instagram photos to your Lightroom catalog using vision AI:

```bash
# 1. Scan your Lightroom catalog (only needed once)
python -m lightroom_tagger scan --catalog "/path/to/Catalog.lrcat" --db library.db

# 2. Crawl Instagram images
python -m lightroom_tagger crawl-instagram --db library.db --output-dir /tmp/instagram_images

# 3. Run vision-based matching
python -m lightroom_tagger match --db library.db --threshold 0.2

# 4. Write matches to Lightroom (adds keyword to matched images)
python -m lightroom_tagger instagram-sync --db library.db --from-matches \
    --catalog "/path/to/Catalog.lrcat" --keyword "posted"
```

### Parameters Explained

| Command | Parameter | Description |
|---------|-----------|-------------|
| `scan` | `--catalog` | Path to your Lightroom .lrcat file |
| `scan` | `--db` | Path to SQLite database (will be created) |
| `crawl-instagram` | `--db` | Database with catalog images |
| `crawl-instagram` | `--output-dir` | Where to save downloaded Instagram images |
| `crawl-instagram` | `--limit` | Limit number of posts to download |
| `match` | `--db` | Database with catalog and Instagram images |
| `match` | `--threshold` | Minimum score to consider a match (0.0-1.0, default 0.7) |
| `match` | `--vision-model` | Override vision model (default: gemma3:27b) |
| `instagram-sync` | `--from-matches` | Read matches from 'matches' table instead of re-matching |
| `instagram-sync` | `--catalog` | Lightroom catalog to write keywords to |
| `instagram-sync` | `--keyword` | Keyword to add to matched images |
| `instagram-sync` | `--dry-run` | Preview changes without applying |

### Matching Configuration

Edit `config.yaml` or use environment variables to tune matching:

```yaml
# Matching weights (must sum to ~1.0)
phash_weight: 0.4      # Perceptual hash similarity
desc_weight: 0.3      # Description text similarity  
vision_weight: 0.3     # Vision model similarity
match_threshold: 0.7  # Minimum score to accept match

# Vision model (requires Ollama)
vision_model: "gemma3:27b"  # Best for accuracy, requires 17GB RAM
# Alternative: "qwen2.5-vl:7b" - faster but less consistent
```

Environment variables:
- `VISION_MODEL` - Override vision model
- `PHASH_WEIGHT`, `DESC_WEIGHT`, `VISION_WEIGHT` - Override weights
- `MATCH_THRESHOLD` - Override threshold

### Vision Model Requirements

The vision matching requires [Ollama](https://ollama.ai) to be installed:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the recommended model (17GB)
ollama pull gemma3:27b
```

## Basic Usage

```bash
# Set PYTHONPATH if running from source
export PYTHONPATH=/path/to/lightroom-tagger

# Scan a catalog
python -m lightroom_tagger scan --catalog "/path/to/Catalog.lrcat" --db ~/lightroom_tagger/library.db

# Search indexed images
python -m lightroom_tagger search --keyword "landscape" --db ~/lightroom_tagger/library.db

# Export to CSV or JSON
python -m lightroom_tagger export --db ~/lightroom_tagger/library.db --output export.csv --format csv

# View stats
python -m lightroom_tagger stats --db ~/lightroom_tagger/library.db
```

## Project Structure

### `lightroom_tagger/config.py`
Configuration module that loads settings from `config.yaml` or environment variables. Handles NAS path resolution (e.g., `//nas/...` → `/mnt/nas/...`) and provides defaults for all settings.

### `lightroom_tagger/schema_explorer.py`
Explores the Lightroom catalog schema. Connects to the SQLite database and lists all tables with their columns. Useful for understanding the catalog structure.

### `lightroom_tagger/catalog_reader.py`
Reads metadata from the Lightroom catalog. Queries the SQLite database and joins these key tables:
- `AgLibraryFile` + `AgLibraryFolder` + `AgLibraryRootFolder` - file paths
- `Adobe_images` - ratings, pick flag, color labels
- `AgLibraryKeywordImage` + `AgLibraryKeyword` - keywords/tags
- `AgHarvestedExifMetadata` - EXIF data (camera, lens, date, GPS)
- `AgLibraryIPTC` - caption, copyright

### `lightroom_tagger/database.py`
SQLite operations for storing and querying indexed images (WAL mode for concurrency). Provides functions for:
- `store_image()` / `store_images_batch()` - save records (upsert)
- `get_image()` / `get_all_images()` - retrieve records
- `search_by_keyword()`, `search_by_rating()`, `search_by_date()` - query filters
- Unique key format: `{date_taken}_{filename}`

### `lightroom_tagger/cli.py`
Command-line interface with subcommands:
- `scan` - Scan catalog, index all images to SQLite
- `search` - Search indexed images by keyword, rating, date, color label
- `export` - Export to JSON or CSV format
- `init` - Initialize empty database
- `stats` - Show database statistics

### `lightroom_tagger/tagger.py`
Main entry point that ties everything together.

### `lightroom_tagger/__main__.py`
Enables running as: `python -m lightroom_tagger`

## Configuration

Edit `config.yaml` or use environment variables:

```yaml
catalog_path: "/path/to/Catalog.lrcat"
db_path: "~/lightroom_tagger/library.db"
mount_point: "/mnt/nas"
workers: 4

# Matching configuration
vision_model: "gemma3:27b"
phash_weight: 0.4
desc_weight: 0.3
vision_weight: 0.3
match_threshold: 0.7
```

## Data Extracted

Each image record contains:
- `id` - Internal Lightroom ID
- `filename`, `filepath` - File location
- `date_taken` - Capture date (ISO format)
- `rating` - Star rating (0-5)
- `pick` - Pick flag (True/False)
- `color_label` - Color label (Red, Yellow, Green, Blue, Purple)
- `keywords` - List of keywords/tags
- `caption`, `copyright` - IPTC metadata
- `camera_make`, `camera_model`, `lens` - Camera info
- `focal_length`, `aperture`, `shutter_speed`, `iso` - EXIF settings
- `gps_latitude`, `gps_longitude` - GPS coordinates
- `width`, `height` - Image dimensions
- `key` - Unique identifier (`{date_taken}_{filename}`)

---

## Visualizer (Web UI)

A React 19 + Flask web interface for monitoring and controlling Lightroom Tagger workflows.

### Architecture

```
frontend/                    # React 19 + TypeScript + Vite + Tailwind
├── src/
│   ├── components/         # Reusable UI components
│   ├── pages/              # Page components (Dashboard, Jobs, etc.)
│   ├── services/api.ts     # REST API client
│   ├── stores/             # Zustand state (WebSocket connection)
│   ├── constants/          # All UI strings (DRY)
│   └── types/              # TypeScript interfaces

backend/                     # Flask + Flask-SocketIO
├── app.py                  # Flask app factory
├── database.py             # SQLite operations for jobs
├── api/                    # REST API blueprints
│   ├── jobs.py             # Job CRUD endpoints
│   ├── images.py           # Instagram images
│   └── system.py           # System status
├── websocket/              # WebSocket handlers
│   └── events.py           # Job subscriptions
└── jobs/                   # Job execution
    ├── runner.py           # Job runner framework
    └── handlers.py         # Job type handlers
```

### Quick Start

```bash
# 1. Create a virtual environment (required on macOS with system Python)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install the project and all dependencies
pip install -e .
pip install imagehash   # required but not in pyproject.toml yet

# 3. Scan your Lightroom catalog to create library.db
python3 -m lightroom_tagger scan \
  --catalog "/path/to/Lightroom Catalog.lrcat" \
  --db library.db

# 4. Import your Instagram data dump (Meta data export)
#    Pass the dump ROOT directory (the one containing media/, your_instagram_activity/, etc.)
#    NOT the media/ subdirectory itself — the importer appends /media internally
python3 -m lightroom_tagger.scripts.import_instagram_dump \
  --db library.db \
  --dump-path "/path/to/instagram-username-date-hash"

# 5. Configure backend environment
cp apps/visualizer/backend/.env.example apps/visualizer/backend/.env
# Edit .env and set LIBRARY_DB to the absolute path of your library.db

# 6. Install frontend dependencies
cd apps/visualizer/frontend && npm install --legacy-peer-deps && cd ../../..

# 7. Start backend + frontend
make dev
# or: ./scripts/dev-up.sh

# Open: http://localhost:5173 (or 5174 if 5173 is taken)

# Stop both services
make dev-down
# or: ./scripts/dev-down.sh
```

**macOS Note:** Port 5000 is used by AirPlay Receiver. Either disable it in
System Settings > General > AirDrop & Handoff, or set `FLASK_PORT=5001` in
the backend `.env` and update the frontend `.env` to match:
```
# apps/visualizer/frontend/.env
VITE_API_URL=http://localhost:5001/api
VITE_WS_URL=http://localhost:5001
```

**Environment Variables:**
- `LIBRARY_DB` (required) - Absolute path to your library.db file
- `DATABASE_PATH` - Path to visualizer database (default: ../visualizer.db)
- `FLASK_HOST` - Backend host (default: localhost)
- `FLASK_PORT` - Backend port (default: 5000, use 5001 on macOS)
- `INSTAGRAM_DIR` - Path to Instagram dump root directory
- `INSTAGRAM_DUMP_PATH` - Alternative env var for import script

### Available Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Overview and stats |
| Instagram | `/instagram` | Instagram image management |
| Matching | `/matching` | Run vision matching workflows |
| Jobs | `/jobs` | View and manage background jobs |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/jobs/` | GET | List all jobs |
| `/api/jobs/` | POST | Create new job |
| `/api/jobs/<id>` | GET | Get job details |
| `/api/jobs/<id>` | DELETE | Cancel job |
| `/api/jobs/active` | GET | Get running jobs |

### WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Client → Server | Establish connection |
| `subscribe_job` | Client → Server | Subscribe to job updates |
| `job_created` | Server → Client | New job created |
| `job_updated` | Server → Client | Job status/progress updated |

### Testing

```bash
# Backend tests
cd backend && PYTHONPATH=. pytest ../tests/ -v

# Frontend tests
cd frontend && npm test -- --run

# All tests
cd backend && PYTHONPATH=. pytest ../tests/ -v && cd ../frontend && npm test -- --run
```

---

## For Future Agents

### Project Context

This is a Lightroom catalog management tool with:
1. **Core CLI** - Catalog scanning, searching, exporting
2. **Instagram matching** - Vision-based matching with Ollama
3. **Visualizer** - Web UI (new, in development)

### Visualizer Development

The visualizer is developed in a **git worktree** at `.worktrees/visualizer` on the `feature/visualizer` branch.

```bash
# Working directory for visualizer
cd /home/cristian/lightroom_tagger/.worktrees/visualizer

# Key files
backend/           # Flask backend
frontend/          # React frontend
tests/             # Backend tests
docs/plans/        # Implementation plan
```

### Development Conventions

1. **TDD**: Write failing test → Verify fail → Implement → Verify pass → Commit
2. **All UI strings in constants**: Use `constants/strings.ts` (DRY principle)
3. **Container/Presenter pattern**: Pages fetch data, components receive props
4. **Minimal Zustand**: Only for WebSocket connection state
5. **No real paths in git**: Use `.env` files (gitignored)
6. **SQLite with WAL mode**: All databases use `sqlite3` (stdlib) with WAL for safe concurrent access. No TinyDB.

### Running Tests

```bash
# Backend (from .worktrees/visualizer)
cd backend && PYTHONPATH=. python3 -m pytest ../tests/ -v

# Frontend
cd frontend && npm test -- --run
```

### Adding New Features

1. Read the plan document first
2. Write failing tests (backend: `tests/test_*.py`, frontend: `src/**/__tests__/*.test.ts`)
3. Implement minimal code to pass
4. Run tests: `pytest -v` or `npm test`
5. Commit with conventional message: `feat(scope): description`

### Common Issues

| Issue | Solution |
|-------|----------|
| `RuntimeError: Werkzeug not designed for production` | Add `allow_unsafe_werkzeug=True` to `socketio.run()` |
| `Cannot find name 'global'` in tests | Use `(globalThis as any).fetch` instead of `global.fetch` |
| npm peer dep conflict | Use `npm install --legacy-peer-deps` |
| `import.meta.env` TypeScript errors | Add `/// <reference types="vite/client" />` to `vite-env.d.ts` |
| Port 5000 in use on macOS | AirPlay Receiver uses 5000. Set `FLASK_PORT=5001` in backend `.env` |
| `ModuleNotFoundError: imagehash` | Run `pip install imagehash` (missing from pyproject.toml) |
| `ImportError: find_matches from core.hasher` | It's in `core/phash.py`, not `core/hasher.py`. Check `core/__init__.py` |
| Instagram import finds 0 files | Pass the dump root dir, not `media/`. The reader appends `/media` itself |
| `externally-managed-environment` on pip install | Use a venv: `python3 -m venv .venv && source .venv/bin/activate` |

### OpenCLI Instagram Adapters

This project contains custom `opencli` adapters located in `.opencli/clis/instagram/` designed to scrape Instagram securely via a local Chrome extension bridge.
Future agents can use these commands natively from the project root instead of writing complex Python web scrapers:

```bash
# Get profile stats (Followers, Following, bio)
opencli instagram profile --username <username> -f json

# Get recent post URLs
opencli instagram posts --username <username> --limit <num_posts> -f json

# Get all image URLs from a specific post (auto-swipes carousels!)
opencli instagram images --post_url "<url>" -f json
```

*Note: To use these commands, the `opencli` daemon must be active and the Chrome extension must be installed and connected in the host browser. Use `opencli doctor --live` to verify bridge connectivity.*
