# Lightroom Tagger

A Python tool to read Lightroom catalog (`.lrcat` SQLite database), index metadata to TinyDB, and export/search your photo library. Includes Instagram matching with vision model support.

## Installation

```bash
pip install tinydb pyyaml python-dotenv
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
| `scan` | `--db` | Path to TinyDB database (will be created) |
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
TinyDB operations for storing and querying indexed images. Provides functions for:
- `store_image()` / `store_images_batch()` - save records
- `get_image()` / `get_all_images()` - retrieve records
- `search_by_keyword()`, `search_by_rating()`, `search_by_date()` - query filters
- Unique key format: `{date_taken}_{filename}`

### `lightroom_tagger/cli.py`
Command-line interface with subcommands:
- `scan` - Scan catalog, index all images to TinyDB
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
├── database.py             # TinyDB operations for jobs
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
# Terminal 1: Start backend (from project root)
cd backend
pip install -r requirements.txt  # or: pip install flask flask-cors flask-socketio tinydb pillow python-dotenv pytest
python3 app.py

# Terminal 2: Start frontend
cd frontend
npm install --legacy-peer-deps
npm run dev

# Open: http://localhost:5173
```

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
