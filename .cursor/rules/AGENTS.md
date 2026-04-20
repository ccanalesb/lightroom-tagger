<!-- gsd-project-start source:PROJECT.md -->
## Project

**Lightroom Tagger & Analyzer**

A web application that connects your Lightroom catalog with Instagram to track what you've published and provides AI-powered artistic analysis of your photography. It helps you understand your work from multiple critical perspectives, identify patterns in what performs well, and decide what to shoot or post next.

**Core Value:** Know which catalog images are posted on Instagram and get artistic critique that helps you understand your photographic voice and posting strategy.

### Constraints

- **Database**: Lightroom catalogs are SQLite files — read-only except for keyword writes
- **AI Providers**: Currently Ollama (local/cloud), may expand to OpenRouter/GPT for better analysis
- **Instagram Sync**: Export-based workflow (no API access) — user provides dumps
- **Architecture**: Web application accessed via browser
- **Analysis Approach**: On-demand job triggers, not batch processing
- **Multi-catalog**: Must support switching between multiple .lrcat files while maintaining unified photographer identity view
<!-- gsd-project-end -->

<!-- gsd-stack-start source:codebase/STACK.md -->
## Technology Stack

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
- Registers `/api/jobs`, `/api/images`, `/api/descriptions`, `/api/providers`, and `/api/*` (system).
- Starts a daemon thread for the job queue processor.
- Runs with `socketio.run(...)` when executed as `__main__`.
- Dev port **5173**; proxies `/api` and `/socket.io` to `http://localhost:${VITE_BACKEND_PORT || '5001'}`.
## Dependencies
### Python — root package (`pyproject.toml`)
- `openai` — Chat completions for vision compare / describe (any OpenAI-compatible endpoint).
- `ollama` — Present in dependencies (local model ecosystem; registry also probes Ollama HTTP API).
- `requests` — HTTP (e.g. Instagram scraper paths).
- `pillow`, `ImageHash` — Images and perceptual hashing.
- `pyyaml`, `python-dotenv` — `config.yaml` and environment overrides.
- `flask`, `flask-socketio`, `flask-cors`, `python-socketio` — Optional overlap with visualizer; core library imports may share this stack.
### Python — visualizer backend (`apps/visualizer/backend/requirements.txt`)
### JavaScript — visualizer frontend (`apps/visualizer/frontend/package.json`)
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
<!-- gsd-stack-end -->

<!-- gsd-conventions-start source:CONVENTIONS.md -->
## Conventions

## Code Style
### Python
- **Formatter:** Black (`pyproject.toml` → `[tool.black]`): line length **100**, targets Python 3.10–3.12.
- **Linter:** Ruff (`[tool.ruff]` / `[tool.ruff.lint]`): same line length; rules **E, F, I, W, UP, B, C4, SIM**; **E501** ignored (line length enforced by Black instead).
- **Types:** Mypy (`[tool.mypy]`): `python_version = "3.10"`, `warn_return_any`, `warn_unused_configs`, **`disallow_untyped_defs = true`**. Package ships `py.typed` via setuptools package-data.
- **Modern typing:** Newer modules use `from __future__ import annotations` and built-in generics (`dict[str, Any]`, etc.) where appropriate.
### TypeScript / React (Visualizer)
- **Bundler / dev server:** Vite 5; `apps/visualizer/frontend/package.json` uses `"type": "module"`.
- **Lint:** ESLint 8 with `@typescript-eslint`, `eslint:recommended`, React Hooks; `react-refresh/only-export-components` as **warn**; **`--max-warnings 0`** on the lint script (CI-quality gate).
- **Styling:** Tailwind CSS + PostCSS; UI patterns favor functional components and hooks.
### Visualizer backend (Flask)
- Lives under `apps/visualizer/backend/`. Imports are often **relative to that directory** at runtime; tests prepend `sys.path` or set `PYTHONPATH=.` so `app`, `database`, `api.*` resolve.
- **App factory:** `create_app()` in `apps/visualizer/backend/app.py` registers blueprints under `/api/...`, wires CORS, SocketIO, and DB init.
- **Repo root on path:** `app.py` inserts the monorepo root into `sys.path` so `lightroom_tagger.*` can be imported from the backend.
## Naming Patterns
| Area | Convention | Examples |
|------|------------|----------|
| Python packages / modules | `snake_case` | `lightroom_tagger.core.matcher`, `provider_registry.py` |
| Python functions / variables | `snake_case` | `match_image`, `load_config` |
| Python classes | `PascalCase` | `ProviderError`, `ProviderRegistry` |
| Python tests | `test_*.py` next to or under package | `lightroom_tagger/core/test_matcher.py` |
| pytest tests | `test_*` functions or `Test*` classes | `test_match_filters_by_exif`, `class TestRetrySuccess` |
| TypeScript / React | `PascalCase` components, `camelCase` vars/functions | `JobsAPI`, `useJobSocket` |
| Frontend tests | `*.test.ts` / `*.test.tsx` in `__tests__` | `src/services/__tests__/api.test.ts` |
| CLI | `lightroom-*` entry points in `pyproject.toml` `[project.scripts]` | `lightroom-tagger`, `lightroom-match-dump` |
## Common Patterns
### Library layout
- **`lightroom_tagger/`** — installable package: `core/` (matching, vision, DB, config), `lightroom/`, `instagram/`, `scripts/`.
- **`apps/visualizer/`** — product UI: `backend/` (Flask), `frontend/` (React).
### CLI and configuration
- Main CLI: `lightroom_tagger/core/cli.py` — `argparse` subcommands, shared flags like `--catalog`, `--db`, `--config` (default `config.yaml`).
- Config loading centralized in `lightroom_tagger.core.config` (`load_config`); backend may call this to set env vars (e.g. NAS paths in `apps/visualizer/backend/app.py`).
### Provider / vision stack
- **OpenAI-compatible client** used for Ollama, NVIDIA NIM, OpenRouter; see `lightroom_tagger/core/vision_client.py`.
- **`ProviderRegistry`** (`lightroom_tagger/core/provider_registry.py`) loads provider definitions and env-based availability (e.g. API keys).
- **Retry + fallback:** `lightroom_tagger/core/retry.py` uses `RETRYABLE_ERRORS` / `NOT_RETRYABLE_ERRORS` from `provider_errors.py` to decide backoff vs immediate failure.
### API responses (Flask)
- Shared JSON helpers in `apps/visualizer/backend/utils/responses.py` — e.g. `error_not_found(...)`, `error_bad_request(...)`, `success_paginated(...)` returning `(response, status)` tuples tested in `apps/visualizer/backend/tests/test_responses.py`.
### Frontend architecture (documented in `README.md`)
- **Container/presenter:** pages fetch data; dumb components receive props.
- **Zustand:** minimal use (e.g. WebSocket-related state).
- **Copy:** prefer centralizing UI strings (project convention references `constants/strings.ts`).
### Example: mapping external errors to domain errors
## Error Handling
### Typed exception hierarchy (core)
- **`lightroom_tagger/core/provider_errors.py`:** Base `ProviderError` with optional `provider`, `model`, `retry_after`. Subclasses include `RateLimitError`, `TimeoutError`, `ConnectionError`, `ModelUnavailableError`, `ContextLengthError`, `AuthenticationError`, `InvalidRequestError`.
- **`RETRYABLE_ERRORS`** vs **`NOT_RETRYABLE_ERRORS`** are explicit `frozenset`s used by retry and fallback logic — not inferred ad hoc.
### Vision client
- **`_map_openai_error`** normalizes OpenAI SDK exceptions into the hierarchy above (including parsing `Retry-After` when present).
- Docstring in `vision_client.py` states the design goal: callers never depend on the SDK’s exception types directly.
### Retry behavior
- **`retry_with_backoff`** (`lightroom_tagger/core/retry.py`) takes a config dict (`max_retries`, `backoff_seconds`, `respect_retry_after`); uses **`pytest.raises`** and **`MagicMock.side_effect`** in `lightroom_tagger/core/test_retry.py` for contract tests.
### Flask / operational
- **Non-fatal config:** `create_app()` may `print` a warning if Lightroom-tagger config cannot be loaded for NAS env setup (`apps/visualizer/backend/app.py`) rather than failing startup.
- **HTTP layer:** Prefer `utils.responses` helpers for consistent `{"error": "..."}` JSON shapes and status codes.
### Logging in jobs
- Job handlers and tests sometimes **patch** `database.add_job_log` to avoid real side effects or JSON serialization issues when the runner is a `MagicMock` (see comment in `apps/visualizer/backend/tests/test_handlers_single_match.py`).
## Practical commands (quality gates)
<!-- gsd-conventions-end -->

<!-- gsd-architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern
| Area | Technology |
|------|------------|
| Library | Python 3.10+, SQLite, OpenAI-compatible HTTP APIs (`openai` SDK) |
| CLI | `argparse` in `lightroom_tagger/core/cli.py` |
| Visualizer API | Flask + Flask-CORS + Flask-SocketIO |
| Visualizer UI | React, React Router, Vite |
| Dev orchestration | `scripts/dev-up.sh` starts backend + frontend |
## Layers
## Data Flow
### End-to-end: catalog → index → Instagram → match → optional Lightroom keyword
### Visualizer: UI → API → jobs → library DB
### Vision / provider path (conceptual)
```
```
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
<!-- gsd-architecture-end -->

<!-- gsd-skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.cursor/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- gsd-skills-end -->

<!-- project-design-system-start -->
## Design System Reference

**For any frontend/UI work** (planning, executing, reviewing, or generating UI-SPEC.md), read and follow the project design system:

**File:** `apps/visualizer/frontend/DESIGN.md`

This is the canonical design reference for all visual decisions including:
- Color palette (light + dark mode with warm neutrals)
- Typography (Inter font, specific scale with weights and letter-spacing)
- Component patterns (Button, Card, Badge, Input, Tabs)
- Shadow system (card, deep — multi-layer sub-0.05 opacity)
- Spacing (8px base grid)
- Tailwind semantic classes (`bg-bg`, `text-text`, `border-border`, `text-accent`, etc.)
- Single accent color (blue) for all interactive elements

**Rules for GSD agents:**
- When generating UI-SPEC.md, reference DESIGN.md tokens (not raw hex values)
- When planning frontend phases, ensure tasks reference existing component patterns
- When executing frontend code, use semantic Tailwind classes from the design system
- When reviewing UI, audit against DESIGN.md standards
- New components must support both light and dark mode via CSS variables
<!-- project-design-system-end -->

<!-- gsd-workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- gsd-workflow-end -->



<!-- gsd-profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- gsd-profile-end -->

## NEVER revert or discard the user's work without an explicit instruction

The user's work is sacred. When frustrated, stressed, or scolded, DO NOT react by:

- Running `git checkout --`, `git reset`, `git restore`, `git stash`, `git clean`, or deleting files to "undo" recent work.
- Reverting uncommitted changes because the user expressed displeasure (e.g. "this is awful", "you broke X", "STOP", "WHAT").
- Interpreting emotional or ambiguous feedback as a revert instruction.

Words like "stop", "wait", "this is wrong", "you broke it" mean **stop and ask**, never **undo**. Destructive git operations on uncommitted work are irrecoverable and cost the user tokens, time, and trust.

The ONLY acceptable triggers for destructive/reverting operations are:

1. An unambiguous, explicit instruction (e.g. "revert X", "undo the change to Y", "throw it all away", "git reset").
2. The user selecting a revert option from a list you offered.

When unsure: STOP and ASK. Do not guess. Do not be proactive. A one-line question costs far less than recreating lost work.
