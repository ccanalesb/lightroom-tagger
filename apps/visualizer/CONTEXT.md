# Context: Visualizer (Flask API + React UI)

## Purpose

The visualizer is the web product that surfaces library data to the user. It consists of a Flask backend (`apps/visualizer/backend/`) and a React SPA (`apps/visualizer/frontend/`). They are developed and deployed together — backend and frontend share the same domain model and API contracts. The visualizer consumes the `lightroom_tagger` library as a dependency.

## Domain language

| Term | Meaning |
|---|---|
| **job** | A background task (e.g. run matching, score images, generate descriptions). Stored in `visualizer.db`. Has a lifecycle: `pending → running → completed / failed / cancelled`. |
| **job runner** | `JobRunner` in `jobs/runner.py` — coordinates job lifecycle, progress hooks, cancellation events, and thread-local DB connections for worker threads. |
| **job processor** | Daemon thread started at app startup that drains the job queue and dispatches to handlers. |
| **handler** | A function in `jobs/handlers.py` that implements a specific job type (e.g. `handle_single_match`, `handle_describe`). |
| **checkpoint** | Persisted job progress snapshot merged into job metadata so interrupted jobs can resume. |
| **emit_progress** | SocketIO callback passed into job runner and handlers to push real-time progress to the frontend. |
| **visualizer DB** | `visualizer.db` — SQLite database holding jobs, logs, and visualizer-specific state. Separate from `library.db`. |
| **library DB** | `library.db` — the shared library database (images, scores, descriptions, matches). The visualizer reads/writes this via the `lightroom_tagger` library. |
| **blueprint** | A Flask blueprint under `apps/visualizer/backend/api/`. One per domain area (jobs, images, descriptions, providers, scores, analytics, identity, system). |
| **response helpers** | `utils/responses.py` — `error_not_found`, `error_bad_request`, `success_paginated`, etc. Always use these for consistent JSON shapes. |
| **WebSocket / SocketIO** | Real-time job progress pushed from backend to frontend via Flask-SocketIO + socket.io-client. |
| **perspective** | Named scoring lens shown in the UI (matches the library concept). |
| **identity** | Photographer style fingerprint and suggestions page (`IdentityPage.tsx`). |
| **search** | NL catalog search surface (`SearchPage.tsx`) backed by `api/lt_config.py` and library NL filter. |

## Key files

### Backend

| File | Role |
|---|---|
| `app.py` | `create_app()` factory — registers blueprints, CORS, SocketIO, DB init, starts job processor daemon |
| `config.py` | `load_dotenv()` + `os.getenv` for `LIBRARY_DB`, `FLASK_PORT`, `OLLAMA_HOST`, etc. |
| `database.py` | Visualizer DB schema and helpers (jobs, logs, checkpoints) |
| `library_db.py` | Thin wrapper for opening `library.db` connections from the backend |
| `jobs/runner.py` | `JobRunner` — lifecycle, cancellation, thread-local DB, progress hooks |
| `jobs/handlers.py` | Per-job-type handler functions |
| `jobs/checkpoint.py` | Checkpoint merge logic |
| `api/jobs.py` | REST endpoints for job CRUD and cancellation |
| `api/images.py` | Image listing, detail, thumbnail endpoints |
| `api/descriptions.py` | Description fetch/trigger endpoints |
| `api/scores.py` | Score endpoints per image/perspective |
| `api/analytics.py` | Posting analytics endpoints |
| `api/identity.py` | Identity/suggestions endpoints |
| `api/providers.py` | Provider availability endpoints |
| `api/system.py` | Health, config, system info |
| `websocket/` | SocketIO event handlers |
| `utils/responses.py` | Shared JSON response helpers |

### Frontend

| File / Dir | Role |
|---|---|
| `src/App.tsx` | Route definitions (React Router 6) |
| `src/pages/` | Page components: Dashboard, Images, Processing, Analytics, Identity, Search |
| `src/components/` | Shared UI components |
| `src/services/` | API client (`api.ts`) and WebSocket service |
| `src/hooks/` | Custom hooks (e.g. `useJobSocket`) |
| `src/stores/` | Zustand stores (minimal — mainly WebSocket state) |
| `src/constants/` | UI strings and other constants |
| `src/types/` | Shared TypeScript types |

## Architectural constraints

- **Frontend and backend are one unit**: changes to API shape must be reflected in both the Flask blueprint and the TypeScript service layer.
- **SocketIO for job progress**: never poll for job status — use the WebSocket channel.
- **Always use `utils/responses.py` helpers**: never return raw `jsonify(...)` with ad-hoc status codes from blueprints.
- **Thread-local DB connections in job workers**: workers must call `runner.thread_db()` rather than using the runner's `self.db` directly.
- **`sys.path` includes repo root**: `app.py` inserts the monorepo root so `lightroom_tagger.*` imports resolve from the backend.
- **Dev proxy**: Vite proxies `/api` and `/socket.io` to `localhost:5001`; don't hardcode backend URLs in frontend code.
- **Design system**: all UI work must follow `apps/visualizer/frontend/DESIGN.md` (Tailwind semantic classes, 8px grid, Inter font, single blue accent).
