# External Integrations

## APIs

### OpenAI-compatible vision / LLM (primary)

All remote/local vision comparison and description generation go through the **`openai` Python SDK** with a configurable `base_url` and API key — same pattern for multiple vendors (`lightroom_tagger/core/vision_client.py`, `lightroom_tagger/core/provider_registry.py`).

**Configured providers** (see `lightroom_tagger/core/providers.json`; template in `providers.example.json`):

| Provider id | Base URL (typical) | Auth |
|-------------|-------------------|------|
| `ollama` | `OLLAMA_HOST` → normalized to `.../v1` | Static placeholder key `"ollama"` |
| `nvidia_nim` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_NIM_API_KEY` |
| `opencode_go` | `https://opencode.ai/zen/go/v1` | `OPENCODE_GO_API_KEY` |

**Example — registry builds a client** (`lightroom_tagger/core/provider_registry.py`):

```python
client = openai.OpenAI(
    base_url=base_url,
    api_key=api_key,
    default_headers=extra_headers or None,
)
```

**Example — chat completion for image pair** (`lightroom_tagger/core/vision_client.py`):

```python
response = client.chat.completions.create(
    model=model,
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": COMPARISON_PROMPT},
            _image_url_part(local_b64),
            _image_url_part(insta_b64),
        ],
    }],
)
```

**Ollama model discovery** — When `auto_discover` is true, the registry performs HTTP requests against the Ollama host to list models (`provider_registry.py` uses `urllib.request` for `/api/tags`-style discovery).

**Optional OpenRouter (template only)** — `lightroom_tagger/core/providers.example.json` includes an `openrouter` block (`https://openrouter.ai/api/v1`, `OPENROUTER_API_KEY`, referer headers). The committed `providers.json` may differ; treat the example as a recipe for adding that provider.

### Instagram (live HTTP, optional)

**Purpose** — Fetch posts/media via Instagram’s web endpoints using a logged-in **session cookie**, not the official Meta Graph API.

**Implementation** — `lightroom_tagger/instagram/scraper.py` (and legacy `lightroom_tagger/instagram_scraper.py`): `requests.get` / GraphQL to `https://www.instagram.com/...` with headers from `get_session_headers(config)` using `config.instagram_session_id`.

**Configuration** — `instagram_url`, `instagram_session_id` from `config.yaml` / env (`INSTAGRAM_SESSION_ID` in `lightroom_tagger/core/config.py`).

**Example** — session header shape:

```python
{"User-Agent": "...", "Cookie": f"sessionid={config.instagram_session_id}"}
```

### Instagram (Meta data export, filesystem)

**Purpose** — Import and match against a **downloaded Instagram account export** (folders such as `media/`, `your_instagram_activity/`).

**Configuration** — `INSTAGRAM_DUMP_PATH` in `apps/visualizer/backend/.env` / `.env.example`; CLI scripts e.g. `lightroom_tagger/scripts/import_instagram_dump.py` accept `--dump-path` or env default.

### Cloudflare (config only)

`cloudflare_account_id` and `cloudflare_api_token` exist on `Config` in `lightroom_tagger/core/config.py` with env keys `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. They are **not** referenced elsewhere in the Python package under `lightroom_tagger/` for HTTP calls (reserved or legacy); scraper code uses direct `requests` to Instagram.

## Databases

### Library SQLite (`library.db`)

- **Role** — Canonical catalog of scanned Lightroom images, hashes, descriptions, matches (produced and updated by CLI / matching pipeline).
- **Path** — `db_path` in `config.yaml` or `LIGHTRoom_DB`; visualizer reads via `LIBRARY_DB` env (`apps/visualizer/backend/config.py`).

### Visualizer SQLite (`visualizer.db` or custom `DATABASE_PATH`)

- **Role** — Job queue: `jobs` table (status, progress, logs, metadata, result); `provider_models` for UI/provider state (`apps/visualizer/backend/database.py`).
- **Features** — `PRAGMA journal_mode=WAL`, `busy_timeout`; connection `check_same_thread=False` for Flask + background thread.

**Example — jobs table creation** (`apps/visualizer/backend/database.py`):

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    ...
);
```

### Lightroom catalog file

- **Adobe Lightroom Classic** catalog (`.lrcat`) is read as a **local file** (`catalog_path` in `config.yaml`) — not a network API. Path resolution includes NAS-style `//host/share` → local mount mapping in `lightroom_tagger/core/config.py`.

## Authentication

- **Visualizer app** — No user login, OAuth, or API keys for the Flask UI itself. CORS is restricted to origins from `FRONTEND_URL` (`apps/visualizer/backend/app.py`).
- **Vision providers** — API keys via environment variables named in `providers.json` (`api_key_env`) and optional entries in `apps/visualizer/backend/.env.example`.
- **Instagram scraping** — Authenticates as a **browser session** using `sessionid` cookie (`instagram_session_id`), not OAuth2 for the product.

## Webhooks & Events

### Inbound HTTP webhooks

None identified — the backend exposes REST under `/api` and Socket.IO; it does not register as a consumer of third-party webhook URLs.

### Realtime: Socket.IO (server → client)

- **Server** — `flask_socketio.SocketIO` in `apps/visualizer/backend/app.py` (`cors_allowed_origins="*"` on SocketIO).
- **Client** — `socket.io-client` in the React app; Vite proxies `/socket.io` to the Flask port.

**Server events** (`apps/visualizer/backend/websocket/events.py`):

- `connect` → emits `connected`
- `subscribe_job` / `unsubscribe_job` with `{ job_id }` → room `job_{job_id}`; emits `subscribed` / `unsubscribed`
- `cancel_job` → emits `job_cancel_requested` (client-side coordination signal)

**Job lifecycle broadcasts** — `app.py` job processor calls `socketio.emit('job_updated', get_job(...))` after state changes (global emit; rooms can be used via client subscriptions for filtering).

**Frontend usage** — Subscribe to job rooms and listen for `job_updated` / connection events (see `apps/visualizer/frontend` stores or hooks that attach to Socket.IO).

### Background jobs

Long-running work runs in a **daemon thread** inside the Flask process (`_job_processor` in `apps/visualizer/backend/app.py`), invoking handlers from `apps/visualizer/backend/jobs/handlers.py` — not an external queue service (e.g. not Redis/Celery).
