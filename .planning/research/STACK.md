# Stack Research

**Domain:** Photography analysis tools with Lightroom Classic catalog integration (SQLite), Instagram export-dump matching, multi-perspective AI image critique, and analytics dashboards — *not* generic CRUD web apps.

**Researched:** 2026-04-10

**Overall confidence:** **MEDIUM–HIGH** for data/AI layers (verified package versions on PyPI/npm); **MEDIUM** for API framework choice (this repo still ships Flask + Socket.IO; FastAPI is the stronger default for *new* greenfield services in 2026).

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | **3.12+** (3.10 minimum acceptable) | Catalog tooling, matching, AI orchestration, backend API | Lightroom-adjacent work is file- and CPU-bound (thumbnails, hashing); a single language for SQLite access, image prep, and LLM clients keeps operational complexity low. Prefer 3.12 for performance and typing ergonomics. |
| **`sqlite3` (stdlib)** | ships with Python | Read/write `.lrcat` and app-side job DBs | Lightroom Classic catalogs *are* SQLite files. Stdlib `sqlite3` is the most transparent, dependency-free way to run explicit SQL against Adobe’s schema and to control transactions for risky writes. |
| **Pillow** | **12.2.0** | Decode, normalize orientation, resize for hashing and vision payloads | De-facto imaging stack in Python; broad format support for both catalog previews and Instagram dump JPEGs. Keeps you out of native OpenCV unless you need CV-heavy features. |
| **ImageHash** | **4.3.2** | Perceptual / difference hashes for catalog ↔ dump image matching | Standard choice for “same photo, different export” problems at low cost and no GPU. Pairs with Hamming-distance thresholds; fits the project’s export-based Instagram workflow. |
| **`openai`** | **2.31.0** | Chat / vision calls to OpenAI-compatible and OpenAI endpoints | Maintained first-party client; async support, retries patterns, and broad examples. Use for OpenRouter-style gateways via base URL + key if you stay OpenAI-API-shaped. |
| **Ollama Python client** | **0.6.1** | Local / cheap cloud models for descriptions and critique experiments | Official client; aligns with PROJECT.md’s testing on Ollama before stepping up to hosted vision models. |
| **LiteLLM** | **1.83.4** (optional but valuable) | Unified calls + routing across many providers (OpenAI, Anthropic, Gemini, Ollama, …) | When you outgrow a single SDK, LiteLLM reduces bespoke adapter code for multi-provider critique and A/B model quality. **Confidence: MEDIUM** — heavier dependency surface; pull in when you actually run 3+ providers in production. |
| **FastAPI** | **0.135.3** | HTTP API + background-task friendly ASGI app | OpenAPI generation, native Pydantic validation, and async I/O suit on-demand analysis jobs and concurrent thumbnail reads. **Rationale vs current repo:** Flask + Socket.IO still works, but FastAPI + structured schemas is the mainstream 2025–2026 default for new Python APIs that coordinate LLMs and long-running work. |
| **Uvicorn** | **0.44.0** | ASGI server for FastAPI | Standard pairing; use `uvicorn[standard]` for production-oriented extras. |
| **React** | **19.2.5** | Dashboard UI (catalogs, jobs, critique, analytics) | Ecosystem scale for data-dense UIs; matches the direction of the existing visualizer frontend. |
| **Vite** | **8.0.8** | Frontend build / dev server | Current major line on npm; fast HMR for iterative dashboard work. **Note:** This repo’s `package.json` may still pin Vite 5 — treat 8.x as the target when you modernize the lockfile. |
| **TypeScript** | **5.8+** (track latest stable) | Type-safe UI and API contracts | Reduces regressions when critique payloads and analytics shapes evolve. |
| **Recharts** | **3.8.1** | Analytics charts (Instagram metrics, posting cadence, model scores) | Declarative React charts without owning a full D3 pipeline; adequate for dashboard-style analytics tied to dump-derived series. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Pydantic** | **2.12.5** | Strict schemas for multi-perspective critique JSON, job payloads, provider configs | Always — especially when you ask models for structured fields (scores, rationales per persona). |
| **httpx** | latest stable with your resolver | Async-capable HTTP for non-OpenAI providers | When LiteLLM is too much but you still need custom REST (e.g. niche vision API). |
| **tenacity** | latest stable | Retries with backoff for flaky AI and storage paths | Long-running batch jobs against NAS-hosted previews. |
| **python-socketio** + **socket.io-client** | **5.x** / **4.8.3** | Live job progress and log streaming | Already matches the project’s job/processing UX; keep if you stay on Socket.IO semantics. |
| **Zustand** | **5.0.12** | Lightweight client state | Fine for catalog context switching and job UI without Redux boilerplate. |
| **Polars** | latest stable (optional) | Columnar analytics over exported metrics tables | When Instagram dump tables grow large and you want fast aggregations in the backend or notebooks — not required for MVP charts fed by pre-aggregated API endpoints. |
| **pytest** + **ruff** + **mypy** | per `pyproject.toml` | Tests and quality gates | Protect SQLite write paths and hashing/matching invariants. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** or **pip** + **venv** | Python env and lockfile | Repo already uses `uv.lock`; keep one lockfile per deployable. |
| **npm / pnpm** | Frontend installs | Pin major versions; run `npm audit` on dashboard dependencies. |
| **SQLite CLI** | Forensics on `.lrcat` copies | Practice on *copies* only; never attach tools to a catalog Lightroom has open. |
| **Catalog backup discipline** | Risk control for writes | Adobe’s DB is undocumented; backups before keyword writes are part of the “stack,” not optional tooling. |

---

## Installation

```bash
# Core Python (example pins — align with your pyproject/uv.lock)
uv add "pillow>=12.2.0" "ImageHash>=4.3.2" "openai>=2.31.0" "ollama>=0.6.1" "pydantic>=2.12.5"
uv add "fastapi>=0.135.0" "uvicorn[standard]>=0.44.0"

# Optional: multi-provider routing
uv add "litellm>=1.83.0"

# Frontend (dashboard + analytics)
npm install react@^19 react-dom@^19 vite@^8 recharts@^3.8 zustand@^5 socket.io-client@^4.8

# Dev
uv add --dev pytest ruff mypy
npm install -D typescript @vitejs/plugin-react vitest
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **ImageHash (pHash/dHash)** | **CLIP / SigLIP embeddings** + vector index | Heavy crops, color grading, or collage borders break naive hashes; you need semantic “same scene” matching and can pay GPU + index maintenance. |
| **FastAPI + Uvicorn** | **Flask + Flask-SocketIO** (this repo today) | Team already standardized on Flask; lowest migration cost; synchronous style is acceptable at low concurrency. **Flask 3.1.3** + **Flask-SocketIO 5.6.1** are current PyPI versions if you stay. |
| **LiteLLM** | **Hand-rolled provider modules** | Only one provider forever, or you need minimal dependencies and full control over HTTP traces. |
| **Recharts** | **Observable Plot**, **ECharts**, **D3 direct** | You want richer interaction layers or non-React embedding; cost is more custom code. |
| **Stdlib sqlite3** | **sqlcipher** / encrypted catalogs | Rare; only if you encrypt catalog copies at rest yourself — not Adobe’s default. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **ORM (SQLAlchemy, etc.) mapped to Adobe `AgLibrary*` tables** | Undocumented, version-sensitive schema; migrations break between Lightroom releases. | Thin SQL modules + integration tests against catalog *copies*; document queries you rely on. |
| **Instagram Graph API as the primary sync path** | PROJECT.md explicitly scopes out API/scraping; permissions, rate limits, and product churn. | Export dumps + local ingest + hash matching. |
| **OpenCV as the default image stack** | Heavier native dependency for workflows that only need decode, resize, and hash. | Pillow + ImageHash; add OpenCV only for specific CV features (e.g. feature matching). |
| **Up-front embedding / critique of entire catalogs** | Conflicts with on-demand cost control and stated non-goals. | Job queue for single-image or time-window batches; cache results in *your* app DB, not inside `.lrcat`. |
| **Lightroom Classic SDK plugin as the web app substitute** | Different distribution, update model, and UX surface; PROJECT.md keeps Lightroom unchanged except keywords. | Web app + controlled SQLite keyword writes when Lightroom is closed (or documented safe windows). |
| **Writing to `.lrcat` while Lightroom has it open** | Risk of corruption and lock conflicts. | User workflow: quit Lightroom or use a documented read-only path; automate only with explicit safeguards. |

---

## Stack Patterns by Variant

**If you keep Flask for the visualizer backend:**

- Use **Flask 3.1.x** + **Flask-SocketIO 5.6.x** with explicit thread/process model docs for SQLite.
- Because migration is non-trivial and the current job runner already works.

**If you greenfield the API layer:**

- Use **FastAPI 0.135.x** + **Pydantic 2.12.x** + **Uvicorn 0.44.x**, keep Socket.IO or move progress to SSE/WebSockets with a single documented pattern.
- Because structured critique contracts and async file/AI I/O benefit most.

**If matching quality plateaus:**

- Add **embedding retrieval** for candidate shortlists only (e.g. same day or same album), not whole-catalog brute force.
- Because cost scales with corpus size; hashes stay the filter.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `openai` **2.31.x** | `pydantic` **2.12.x** | OpenAI SDK v2 expects Pydantic v2 models for structured parsing patterns. |
| `fastapi` **0.135.x** | `pydantic` **2.12.x**, `starlette` (transitive) | Let FastAPI resolve Starlette; avoid pinning Starlette manually unless tests fail. |
| `recharts` **3.8.x** | `react` **19.2.x** | Verify peer dependency range on install; Recharts 3.x targets React 18+ / 19. |
| `vite` **8.x** | `@vitejs/plugin-react` **current** | Bump plugin-react alongside Vite majors. |
| `ImageHash` **4.3.x** | `pillow` **12.x** | ImageHash lists Pillow as dependency; keep Pillow current for security fixes. |

---

## Confidence by Recommendation

| Area | Confidence | Reason |
|------|------------|--------|
| Pillow + ImageHash for dump ↔ catalog matching | **HIGH** | Industry-standard pipeline for perceptual dedup; low operational risk. |
| Stdlib `sqlite3` for `.lrcat` | **HIGH** | Matches Adobe’s on-disk format; maximum control for transactional keyword writes. |
| OpenAI SDK + optional LiteLLM for critique | **HIGH** (SDK), **MEDIUM** (LiteLLM) | SDK is stable; LiteLLM adds features and transitive weight. |
| FastAPI as preferred *new* API layer | **MEDIUM** | Strong ecosystem default, but this repository already invested in Flask + Socket.IO. |
| Recharts for analytics | **MEDIUM** | Good for standard dashboards; may need escape hatches for bespoke photo-centric viz. |
| Polars for analytics ETL | **LOW–MEDIUM** | Valuable at scale, not mandatory if Postgres/SQLite aggregations suffice. |

---

## Sources

- **PyPI JSON API** — verified 2026-04-10 versions: `fastapi` 0.135.3, `uvicorn` 0.44.0, `openai` 2.31.0, `pillow` 12.2.0, `ImageHash` 4.3.2, `ollama` 0.6.1, `litellm` 1.83.4, `pydantic` 2.12.5, `flask` 3.1.3, `flask-socketio` 5.6.1.
- **`npm view`** — verified 2026-04-10: `vite` 8.0.8, `react` 19.2.5, `recharts` 3.8.1, `socket.io-client` 4.8.3, `zustand` 5.0.12.
- [https://github.com/hfiguiere/lrcat-extractor/blob/master/doc/lrcat_format.md](https://github.com/hfiguiere/lrcat-extractor/blob/master/doc/lrcat_format.md) — community Lightroom catalog structure reference (**MEDIUM** confidence: unofficial but widely used).
- `.planning/PROJECT.md` — scope, constraints, and explicit out-of-scope items (Instagram API, batch whole-catalog analysis).

---
*Stack research for: photography analysis + Lightroom SQLite + Instagram dumps + AI critique + analytics dashboard*

*Researched: 2026-04-10*
