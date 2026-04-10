# Technology Stack

## Languages

- **Python** — CLI package (`lightroom_tagger`), vision/matching core, Flask visualizer API, background jobs, tests (`pytest`).
- **TypeScript / TSX** — Visualizer SPA (`apps/visualizer/frontend/src/`).
- **SQL** — SQLite DDL and queries (library DB + visualizer jobs DB).
- **YAML** — Project runtime config (`config.yaml` at repo root).
- **JSON** — Vision provider registry (`lightroom_tagger/core/providers.json`; seeded from `providers.example.json` when missing).
- **Shell** — Local dev orchestration (`scripts/dev-up.sh`).

## Runtime Environment

- **Python** — `requires-python = ">=3.10"` in `pyproject.toml`; classifiers include 3.10–3.12. Tooling targets 3.10+ (`black`, `ruff`, `mypy` in `pyproject.toml`).
- **Node.js** — `apps/visualizer/frontend/.nvmrc` pins **24** (use with `nvm use` before `npm install` / `vite`).
- **Package / env managers** — Root Python project uses **setuptools** (`pyproject.toml`); repo includes `uv.lock` for **uv**-based installs. Backend also lists `apps/visualizer/backend/requirements.txt` for a minimal Flask stack.

## Core Frameworks

| Area | Stack | Config / entry |
|------|--------|----------------|
| CLI & library | setuptools package `lightroom_tagger` | `pyproject.toml` (`[project.scripts]` → e.g. `lightroom-tagger`, `lightroom-match-dump`) |
| Vision / matching | Plain modules + `openai` SDK (OpenAI-compatible clients) | `lightroom_tagger/core/vision_client.py`, `lightroom_tagger/core/provider_registry.py` |
| Visualizer API | **Flask** + **Flask-CORS** + **Flask-SocketIO** | `apps/visualizer/backend/app.py`, `apps/visualizer/backend/config.py` |
| Visualizer UI | **React 19** + **React Router 6** + **Vite 5** | `apps/visualizer/frontend/vite.config.ts`, `apps/visualizer/frontend/package.json` |
| UI styling | **Tailwind CSS 3** + PostCSS + Autoprefixer | `apps/visualizer/frontend/tailwind.config.js`, `postcss.config.js` |
| Client realtime | **socket.io-client** | Used with Vite proxy to Flask-SocketIO (`vite.config.ts`) |

**Example — Flask app factory and blueprints** (`apps/visualizer/backend/app.py`):

- Registers `/api/jobs`, `/api/images`, `/api/descriptions`, `/api/providers`, and `/api/*` (system).
- Starts a daemon thread for the job queue processor.
- Runs with `socketio.run(...)` when executed as `__main__`.

**Example — Vite dev server** (`apps/visualizer/frontend/vite.config.ts`):

- Dev port **5173**; proxies `/api` and `/socket.io` to `http://localhost:${VITE_BACKEND_PORT || '5001'}`.

## Dependencies

### Python — root package (`pyproject.toml`)

Runtime highlights:

- `openai` — Chat completions for vision compare / describe (any OpenAI-compatible endpoint).
- `ollama` — Present in dependencies (local model ecosystem; registry also probes Ollama HTTP API).
- `requests` — HTTP (e.g. Instagram scraper paths).
- `pillow`, `ImageHash` — Images and perceptual hashing.
- `pyyaml`, `python-dotenv` — `config.yaml` and environment overrides.
- `flask`, `flask-socketio`, `flask-cors`, `python-socketio` — Optional overlap with visualizer; core library imports may share this stack.

Dev: `pytest`, `pytest-cov`, `black`, `ruff`, `mypy`.

### Python — visualizer backend (`apps/visualizer/backend/requirements.txt`)

Minimal set: `flask`, `flask-cors`, `flask-socketio`, `pillow`, `python-dotenv`, `pytest`. The app extends `sys.path` to the **repo root** so it can import the `lightroom_tagger` package (`apps/visualizer/backend/app.py`).

### JavaScript — visualizer frontend (`apps/visualizer/frontend/package.json`)

Runtime: `react`, `react-dom`, `react-router-dom`, `socket.io-client`, `zustand`.

Dev: `vite`, `@vitejs/plugin-react`, `typescript`, `tailwindcss`, `eslint`, `@typescript-eslint/*`, `vitest`, `@testing-library/react`, `jsdom`.

## Configuration

### Lightroom tagger (`config.yaml` + env)

- **File** — `config.yaml` at repo root (user-specific paths; not committed the same everywhere). Loaded by `lightroom_tagger/core/config.py` via `load_config("config.yaml")`.
- **Fields** — e.g. `catalog_path`, `db_path` (SQLite library DB), `mount_point`, `vision_model`, `matching_workers`, `vision_batch_size`, weights, `ollama_host`, Instagram-related defaults.
- **Environment overrides** — `load_config` merges `os.environ` using mappings such as `OLLAMA_HOST` → `ollama_host`, `LIGHTRoom_CATALOG` → `catalog_path` (see `lightroom_tagger/core/config.py` `_load_from_env`). Note: env var prefix is spelled `LIGHTRoom_*` in code.

### Visualizer backend (`.env`)

- **Template** — `apps/visualizer/backend/.env.example` (also `example.env` with a shorter set).
- **Variables** — `LIBRARY_DB`, `INSTAGRAM_DUMP_PATH`, `OLLAMA_HOST`, optional `NVIDIA_NIM_API_KEY`, `OPENCODE_GO_API_KEY`, `DATABASE_PATH`, `FLASK_HOST`, `FLASK_PORT`, `FLASK_DEBUG`, `FRONTEND_URL`, `INSTAGRAM_DIR`, `THUMBNAIL_DIR`.
- **Loaded in** — `apps/visualizer/backend/config.py` (`load_dotenv()` then `os.getenv(...)`).

### Vision providers

- **File** — `lightroom_tagger/core/providers.json` (runtime). If missing, copied from `lightroom_tagger/core/providers.example.json` (`ProviderRegistry` in `provider_registry.py`).
- **Content** — Provider definitions (`base_url`, `api_key_env`, `auto_discover`, models, retry), `defaults` for `vision_comparison` / `description`, and `fallback_order`.

### Frontend env

- **`VITE_BACKEND_PORT`** — Used in `vite.config.ts` for proxy target port (default `5001`).
- **`VITE_API_URL`** — Optional override for API base in `apps/visualizer/frontend/src/services/api.ts` (defaults to `/api`, which the dev proxy forwards).

### Tooling config

- **Python** — `pyproject.toml`: `[tool.black]`, `[tool.ruff]`, `[tool.mypy]`.
- **Frontend** — `tsconfig.json`, `tsconfig.node.json`, `eslint` (via `package.json` script), Vitest in `vite.config.ts` (`test` block).

### Local dev script

- **`scripts/dev-up.sh`** — Ensures `npm install --legacy-peer-deps` in frontend if needed, picks Python from `.venv` or `python3`, reads `FLASK_PORT` from backend `.env`, starts backend and Vite.
