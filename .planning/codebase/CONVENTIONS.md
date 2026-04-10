# Coding Conventions

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

---

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

**Test naming (behavior-oriented):** Many pytest tests use **should_*** phrasing inside class methods (e.g. `test_should_load_all_providers_from_config` in `lightroom_tagger/core/test_provider_registry.py`) or short docstring-style descriptions on plain functions.

---

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

`lightroom_tagger/core/vision_client.py` defines `_map_openai_error`, which inspects OpenAI SDK exception types (`RateLimitError`, `AuthenticationError`, `BadRequestError`, `APITimeoutError`, `APIConnectionError`, `APIStatusError`) and returns the matching `ProviderError` subclass, optionally parsing `Retry-After` from the response headers.

Callers depend on **`ProviderError`** subclasses, not raw SDK types.

---

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

---

## Practical commands (quality gates)

```bash
# From repo root (with dev extras installed)
black .
ruff check .
mypy lightroom_tagger

# Frontend
cd apps/visualizer/frontend && npm run lint
```

Adjust paths if your venv or working directory differs; backend Flask code is often run with `PYTHONPATH=.` from `apps/visualizer/backend/`.
