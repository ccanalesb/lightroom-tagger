# Provider Registry + Rate-Limit Resilience — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hardcoded Ollama-only vision pipeline with a multi-provider system (Ollama, NVIDIA NIM, OpenRouter) using a single OpenAI-compatible client, with per-job provider selection, smart fallback, retry with backoff, and proper error propagation.

**Architecture:** All three providers speak the same OpenAI `/v1/chat/completions` protocol. A provider is a `(base_url, api_key)` tuple. One `openai.OpenAI` client swaps between them. `providers.json` defines available providers/models. `ProviderRegistry` loads config + auto-discovers Ollama models. `FallbackDispatcher` wraps calls with retry + automatic cascade. Frontend gets a `<ProviderModelSelect>` component for per-job selection.

**Tech Stack:** Python 3.11+, `openai` SDK, Flask, React/TypeScript, Vitest, pytest

**Test commands:**
- Backend: `cd /Users/ccanales/personal/lightroom-tagger && python -m pytest <test_path> -v`
- Core lib: `cd /Users/ccanales/personal/lightroom-tagger && python -m pytest <test_path> -v`
- Frontend: `cd /Users/ccanales/personal/lightroom-tagger/apps/visualizer/frontend && npx vitest run`
- Type check: `cd /Users/ccanales/personal/lightroom-tagger/apps/visualizer/frontend && npx tsc --noEmit`

---

## Task 1: Add `openai` dependency

**Files:**
- Modify: `requirements.txt` (or pip install directly — no requirements.txt exists, uses pip freeze)

**Step 1: Install the dependency**

Run: `pip install openai`

**Step 2: Verify import works**

Run: `python -c "import openai; print(openai.__version__)"`
Expected: version string, no error

**Step 3: Commit**

```bash
git add -A && git commit -m "deps: add openai Python SDK for unified provider client"
```

---

## Task 2: Exception hierarchy

**Files:**
- Create: `lightroom_tagger/core/provider_errors.py`
- Test: `lightroom_tagger/core/test_provider_errors.py`

**Step 1: Write the failing test**

```python
# lightroom_tagger/core/test_provider_errors.py
from lightroom_tagger.core.provider_errors import (
    ProviderError, RateLimitError, TimeoutError, ConnectionError,
    ModelUnavailableError, ContextLengthError, AuthenticationError,
    InvalidRequestError, RETRYABLE_ERRORS, NOT_RETRYABLE_ERRORS,
)

def test_hierarchy():
    """All errors inherit from ProviderError."""
    for cls in (RateLimitError, TimeoutError, ConnectionError,
                ModelUnavailableError, ContextLengthError,
                AuthenticationError, InvalidRequestError):
        assert issubclass(cls, ProviderError)

def test_retryable_set():
    assert RateLimitError in RETRYABLE_ERRORS
    assert TimeoutError in RETRYABLE_ERRORS
    assert ConnectionError in RETRYABLE_ERRORS
    assert ModelUnavailableError in RETRYABLE_ERRORS
    assert AuthenticationError not in RETRYABLE_ERRORS
    assert InvalidRequestError not in RETRYABLE_ERRORS

def test_not_retryable_set():
    assert AuthenticationError in NOT_RETRYABLE_ERRORS
    assert InvalidRequestError in NOT_RETRYABLE_ERRORS
    assert RateLimitError not in NOT_RETRYABLE_ERRORS

def test_provider_error_carries_context():
    err = RateLimitError("too fast", provider="ollama", model="gemma3:27b")
    assert err.provider == "ollama"
    assert err.model == "gemma3:27b"
    assert "too fast" in str(err)

def test_context_length_is_conditionally_retryable():
    assert ContextLengthError in RETRYABLE_ERRORS
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest lightroom_tagger/core/test_provider_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lightroom_tagger.core.provider_errors'`

**Step 3: Write minimal implementation**

```python
# lightroom_tagger/core/provider_errors.py
"""Exception hierarchy for vision provider errors."""


class ProviderError(Exception):
    """Base for all provider errors."""
    def __init__(self, message: str, provider: str | None = None, model: str | None = None):
        super().__init__(message)
        self.provider = provider
        self.model = model


class RateLimitError(ProviderError):
    """429 — quota exceeded."""

class TimeoutError(ProviderError):
    """Request timed out."""

class ConnectionError(ProviderError):
    """Can't reach provider (Ollama not running, DNS failure)."""

class ModelUnavailableError(ProviderError):
    """503 — server overloaded or model not loaded."""

class ContextLengthError(ProviderError):
    """Token/context limit exceeded — retry with smaller image."""

class AuthenticationError(ProviderError):
    """401/403 — bad or missing API key."""

class InvalidRequestError(ProviderError):
    """400 — bad model name, unsupported input format."""


RETRYABLE_ERRORS: frozenset[type[ProviderError]] = frozenset({
    RateLimitError, TimeoutError, ConnectionError,
    ModelUnavailableError, ContextLengthError,
})

NOT_RETRYABLE_ERRORS: frozenset[type[ProviderError]] = frozenset({
    AuthenticationError, InvalidRequestError,
})
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest lightroom_tagger/core/test_provider_errors.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add lightroom_tagger/core/provider_errors.py lightroom_tagger/core/test_provider_errors.py
git commit -m "feat: add provider error hierarchy with retryable/non-retryable classification"
```

---

## Task 3: `providers.json` config + `ProviderRegistry`

**Files:**
- Create: `lightroom_tagger/core/providers.json`
- Create: `lightroom_tagger/core/provider_registry.py`
- Test: `lightroom_tagger/core/test_provider_registry.py`

**Step 1: Create `providers.json`**

```json
{
  "retry_defaults": {
    "max_retries": 3,
    "backoff_seconds": [2, 8, 32],
    "respect_retry_after": true
  },
  "providers": {
    "ollama": {
      "name": "Ollama (Local)",
      "base_url_env": "OLLAMA_HOST",
      "base_url_default": "http://localhost:11434/v1",
      "api_key": "ollama",
      "auto_discover": true,
      "extra_headers": {},
      "retry": { "max_retries": 2, "backoff_seconds": [1, 3] },
      "models": []
    },
    "nvidia_nim": {
      "name": "NVIDIA NIM",
      "base_url": "https://integrate.api.nvidia.com/v1",
      "api_key_env": "NVIDIA_NIM_API_KEY",
      "auto_discover": false,
      "extra_headers": {},
      "retry": {},
      "models": [
        {"id": "meta/llama-4-maverick-17b-128e-instruct", "name": "Llama 4 Maverick 17B", "vision": true},
        {"id": "qwen/qwen3.5-397b-a17b", "name": "Qwen 3.5 397B VLM", "vision": true},
        {"id": "microsoft/phi-4-multimodal-instruct", "name": "Phi-4 Multimodal", "vision": true},
        {"id": "microsoft/phi-3.5-vision-instruct", "name": "Phi-3.5 Vision 4.2B", "vision": true},
        {"id": "nvidia/llama-3.1-nemotron-nano-vl-8b-v1", "name": "Nemotron Nano VL 8B", "vision": true},
        {"id": "google/paligemma", "name": "PaLiGemma", "vision": true}
      ]
    },
    "openrouter": {
      "name": "OpenRouter",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key_env": "OPENROUTER_API_KEY",
      "auto_discover": false,
      "extra_headers": {
        "HTTP-Referer": "lightroom-tagger",
        "X-Title": "Lightroom Tagger"
      },
      "retry": {},
      "models": [
        {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "vision": true},
        {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "vision": true},
        {"id": "openai/gpt-4.1", "name": "GPT-4.1", "vision": true},
        {"id": "meta-llama/llama-4-maverick", "name": "Llama 4 Maverick", "vision": true},
        {"id": "qwen/qwen-2.5-vl-72b-instruct", "name": "Qwen 2.5 VL 72B", "vision": true}
      ]
    }
  },
  "defaults": {
    "vision_comparison": {"provider": "ollama", "model": null},
    "description": {"provider": "ollama", "model": null}
  },
  "fallback_order": ["ollama", "nvidia_nim", "openrouter"]
}
```

**Step 2: Write the failing test**

```python
# lightroom_tagger/core/test_provider_registry.py
import os
from unittest.mock import patch, MagicMock
from lightroom_tagger.core.provider_registry import ProviderRegistry

def test_should_load_providers_from_config():
    registry = ProviderRegistry()
    providers = registry.list_providers()
    ids = [p["id"] for p in providers]
    assert "ollama" in ids
    assert "nvidia_nim" in ids
    assert "openrouter" in ids

def test_should_list_static_models_for_nvidia():
    registry = ProviderRegistry()
    models = registry.list_models("nvidia_nim")
    model_ids = [m["id"] for m in models]
    assert "meta/llama-4-maverick-17b-128e-instruct" in model_ids

def test_should_mark_provider_unavailable_without_api_key():
    with patch.dict(os.environ, {}, clear=True):
        registry = ProviderRegistry()
        providers = {p["id"]: p for p in registry.list_providers()}
        assert providers["nvidia_nim"]["available"] is False

def test_should_mark_provider_available_with_api_key():
    with patch.dict(os.environ, {"NVIDIA_NIM_API_KEY": "test-key"}):
        registry = ProviderRegistry()
        providers = {p["id"]: p for p in registry.list_providers()}
        assert providers["nvidia_nim"]["available"] is True

def test_should_return_openai_client_for_provider():
    with patch.dict(os.environ, {"NVIDIA_NIM_API_KEY": "test-key"}):
        registry = ProviderRegistry()
        client = registry.get_client("nvidia_nim")
        assert client.base_url.host == "integrate.api.nvidia.com"

def test_should_get_retry_config_with_provider_override():
    registry = ProviderRegistry()
    config = registry.get_retry_config("ollama")
    assert config["max_retries"] == 2
    assert config["backoff_seconds"] == [1, 3]

def test_should_get_retry_config_with_global_defaults():
    registry = ProviderRegistry()
    config = registry.get_retry_config("nvidia_nim")
    assert config["max_retries"] == 3
    assert config["backoff_seconds"] == [2, 8, 32]

def test_should_return_fallback_order():
    registry = ProviderRegistry()
    assert registry.fallback_order == ["ollama", "nvidia_nim", "openrouter"]

def test_should_auto_discover_ollama_models(monkeypatch):
    """Mock Ollama /api/tags response."""
    import urllib.request, json
    fake_response = json.dumps({
        "models": [
            {"name": "gemma3:27b", "details": {"family": "gemma"}},
            {"name": "qwen3-vl:235b", "details": {"family": "qwen"}},
        ]
    }).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        registry = ProviderRegistry()
        models = registry.list_models("ollama")
        model_ids = [m["id"] for m in models]
        assert "gemma3:27b" in model_ids
        assert "qwen3-vl:235b" in model_ids
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest lightroom_tagger/core/test_provider_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Implement `ProviderRegistry`**

Create `lightroom_tagger/core/provider_registry.py`:
- `__init__`: load `providers.json` from same directory as this file
- `list_providers()`: iterate providers, check availability (API key env set or provider is Ollama)
- `list_models(provider_id)`: return static models + auto-discovered (for Ollama, call `GET {ollama_host}/api/tags`)
- `get_client(provider_id)`: return `openai.OpenAI(base_url=..., api_key=..., default_headers=...)`
- `get_retry_config(provider_id)`: merge provider-specific `retry` with `retry_defaults`
- `fallback_order` property

Key implementation details:
- Ollama base_url: `os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1"` (append `/v1` since OLLAMA_HOST doesn't include it)
- Ollama auto-discover: `urllib.request.urlopen(f"{ollama_host}/api/tags")` — NOT `/v1/api/tags`, the tags endpoint is on the native API
- API key resolution: check `api_key_env` env var, or use static `api_key` field

**Step 5: Run tests to verify they pass**

Run: `python -m pytest lightroom_tagger/core/test_provider_registry.py -v`
Expected: 9 PASSED

**Step 6: Commit**

```bash
git add lightroom_tagger/core/providers.json lightroom_tagger/core/provider_registry.py lightroom_tagger/core/test_provider_registry.py
git commit -m "feat: add ProviderRegistry with config loading, Ollama auto-discover, and OpenAI client factory"
```

---

## Task 4: Unified client functions (`compare_images` + `generate_description`)

**Files:**
- Create: `lightroom_tagger/core/vision_client.py`
- Test: `lightroom_tagger/core/test_vision_client.py`

**Step 1: Write the failing test**

Test `compare_images` with a mocked OpenAI client that returns "SAME":

```python
# lightroom_tagger/core/test_vision_client.py
import os, tempfile
from unittest.mock import MagicMock, patch
from lightroom_tagger.core.vision_client import compare_images, generate_description

def _make_mock_client(response_text: str):
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = response_text
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client

def _make_temp_image():
    """Create a tiny valid JPEG for testing."""
    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    # Minimal JPEG: FF D8 FF E0 ... FF D9
    f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9')
    f.close()
    return f.name

def test_should_return_same_when_model_says_same():
    client = _make_mock_client("SAME")
    img = _make_temp_image()
    try:
        result = compare_images(client, "test-model", img, img)
        assert result == "SAME"
    finally:
        os.unlink(img)

def test_should_return_different_when_model_says_different():
    client = _make_mock_client("DIFFERENT")
    img = _make_temp_image()
    try:
        result = compare_images(client, "test-model", img, img)
        assert result == "DIFFERENT"
    finally:
        os.unlink(img)

def test_should_return_uncertain_for_ambiguous_response():
    client = _make_mock_client("I'm not sure, maybe similar?")
    img = _make_temp_image()
    try:
        result = compare_images(client, "test-model", img, img)
        assert result == "UNCERTAIN"
    finally:
        os.unlink(img)

def test_should_send_two_images_in_message():
    client = _make_mock_client("SAME")
    img = _make_temp_image()
    try:
        compare_images(client, "test-model", img, img)
        call_args = client.chat.completions.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        image_parts = [p for p in content if p.get("type") == "image_url"]
        assert len(image_parts) == 2
    finally:
        os.unlink(img)

def test_should_generate_description_text():
    client = _make_mock_client('{"summary": "A landscape photo"}')
    img = _make_temp_image()
    try:
        result = generate_description(client, "test-model", img)
        assert "landscape" in result
    finally:
        os.unlink(img)

def test_should_map_openai_rate_limit_to_provider_error():
    import openai
    from lightroom_tagger.core.provider_errors import RateLimitError
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {}
    client.chat.completions.create.side_effect = openai.RateLimitError(
        "rate limited", response=mock_response, body=None,
    )
    img = _make_temp_image()
    try:
        try:
            compare_images(client, "test-model", img, img)
            assert False, "Should have raised"
        except RateLimitError as e:
            assert e.provider is None  # caller sets this
    finally:
        os.unlink(img)

def test_should_map_openai_auth_error_to_provider_error():
    import openai
    from lightroom_tagger.core.provider_errors import AuthenticationError
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.headers = {}
    client.chat.completions.create.side_effect = openai.AuthenticationError(
        "bad key", response=mock_response, body=None,
    )
    img = _make_temp_image()
    try:
        try:
            compare_images(client, "test-model", img, img)
            assert False, "Should have raised"
        except AuthenticationError:
            pass
    finally:
        os.unlink(img)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest lightroom_tagger/core/test_vision_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement `vision_client.py`**

Create `lightroom_tagger/core/vision_client.py`:
- `compare_images(client, model, local_path, insta_path, log_callback=None) -> str`
  - Read both images, base64 encode, compress if needed (reuse existing `compress_image`)
  - Build message with two `image_url` parts + the SAME/DIFFERENT/UNCERTAIN prompt (reuse from `analyzer.py`)
  - Call `client.chat.completions.create(model=model, messages=..., max_tokens=64)`
  - Parse response: extract SAME/DIFFERENT/UNCERTAIN from text
  - Wrap `openai.*Error` exceptions into our `ProviderError` hierarchy
- `generate_description(client, model, image_path, log_callback=None) -> str`
  - Read image, base64 encode, compress
  - Build message with one `image_url` part + the description prompt (reuse `build_description_prompt()`)
  - Call `client.chat.completions.create(model=model, messages=..., max_tokens=2048)`
  - Return raw text content
  - Same error mapping

Error mapping helper `_map_openai_error(e)`:
- `openai.RateLimitError` -> `RateLimitError`
- `openai.AuthenticationError` -> `AuthenticationError`
- `openai.BadRequestError` -> `InvalidRequestError`
- `openai.APITimeoutError` -> `TimeoutError`
- `openai.APIConnectionError` -> `ConnectionError`
- `openai.APIStatusError` with 503 -> `ModelUnavailableError`

**Step 4: Run tests**

Run: `python -m pytest lightroom_tagger/core/test_vision_client.py -v`
Expected: 7 PASSED

**Step 5: Commit**

```bash
git add lightroom_tagger/core/vision_client.py lightroom_tagger/core/test_vision_client.py
git commit -m "feat: unified compare_images + generate_description via OpenAI SDK with error mapping"
```

---

## Task 5: `retry_with_backoff` wrapper

**Files:**
- Create: `lightroom_tagger/core/retry.py`
- Test: `lightroom_tagger/core/test_retry.py`

**Step 1: Write the failing test**

Tests should cover: retryable errors get retried N times, non-retryable errors raise immediately, backoff timing, success after transient failure.

**Step 2: Implement**

`retry_with_backoff(fn, retry_config, log_callback=None)`:
- Takes a zero-arg callable `fn` (caller binds args via `functools.partial` or lambda)
- `retry_config` dict: `{max_retries, backoff_seconds, respect_retry_after}`
- On `RETRYABLE_ERRORS`: sleep backoff, retry
- On `NOT_RETRYABLE_ERRORS`: raise immediately
- After exhaustion: raise last error
- Returns fn's return value on success

**Step 3-5: Run, verify, commit**

```bash
git commit -m "feat: configurable retry_with_backoff with retryable/non-retryable error handling"
```

---

## Task 6: `FallbackDispatcher`

**Files:**
- Create: `lightroom_tagger/core/fallback.py`
- Test: `lightroom_tagger/core/test_fallback.py`

**Step 1: Write the failing test**

Tests: primary succeeds (no fallback), primary fails + fallback succeeds, all fail (raises last error), non-retryable skips fallback, returns `(result, actual_provider, actual_model)`.

**Step 2: Implement**

`FallbackDispatcher(registry: ProviderRegistry)`:
- `call_with_fallback(operation, provider_id, model, fallback_order, log_callback, **kwargs) -> (result, provider, model)`
  - `operation` is `"compare"` or `"describe"`
  - Builds ordered list: `[selected] + [others from fallback_order]`
  - For each: get client, get retry config, call `retry_with_backoff(fn, config)`
  - On `NOT_RETRYABLE_ERRORS`: raise immediately (don't try next provider)
  - On exhausted retryable errors: log, try next provider
  - If all fail: raise last error

**Step 3-5: Run, verify, commit**

```bash
git commit -m "feat: FallbackDispatcher with smart cascade across providers"
```

---

## Task 7: Wire into existing code

**Files:**
- Modify: `lightroom_tagger/core/analyzer.py` — replace `run_vision_ollama`, `run_local_agent`, `run_external_agent`, `describe_image`, `compare_with_vision`
- Modify: `lightroom_tagger/core/description_service.py` — use new `generate_description` via dispatcher
- Modify: `lightroom_tagger/core/matcher.py` — use new `compare_images` via dispatcher, add circuit breaker

Key changes:
- `compare_with_vision()` now accepts `provider_id` + `model` params (optional, defaults from config)
- Internally calls `FallbackDispatcher.call_with_fallback("compare", ...)`
- `describe_image()` now accepts `provider_id` + `model` params
- Internally calls `FallbackDispatcher.call_with_fallback("describe", ...)`
- Old functions (`run_vision_ollama`, `run_local_agent`) kept as private fallbacks but no longer in the main path
- `score_candidates_with_vision` catches `RateLimitError` separately, tracks consecutive rate-limit failures per image, breaks after 3

**Important:** Run existing tests after each file change to ensure no regressions.

Run: `python -m pytest lightroom_tagger/core/ -v`
Run: `python -m pytest apps/visualizer/backend/tests/ -v`

```bash
git commit -m "refactor: wire analyzer, matcher, description_service through unified provider pipeline"
```

---

## Task 8: Circuit breakers in job handlers

**Files:**
- Modify: `apps/visualizer/backend/jobs/handlers.py`
- Test: `apps/visualizer/backend/tests/test_handlers_vision_match_ratelimit.py`

Add to `handle_vision_match`:
- Track `rate_limited` count from matcher results
- If 3 consecutive images are fully rate-limited: pause 60s, retry one
- If still limited: fail job with clear "Rate limited by {provider}" message
- Add `rate_limited` to result dict

```bash
git commit -m "feat: circuit breaker in handle_vision_match — fail job after sustained rate limiting"
```

---

## Task 9: Providers API

**Files:**
- Create: `apps/visualizer/backend/api/providers.py`
- Modify: `apps/visualizer/backend/app.py` — register blueprint
- Test: `apps/visualizer/backend/tests/test_providers_api.py`

Endpoints:
- `GET /api/providers` — list all with availability status
- `GET /api/providers/<id>/models` — merged model list
- `POST /api/providers/<id>/models` — add user model (body: `{id, name, vision}`, stored in DB)
- `DELETE /api/providers/<id>/models/<model_id>` — remove user model
- `GET /api/providers/fallback-order` — current order
- `PUT /api/providers/fallback-order` — update order (body: `{order: ["ollama", ...]}`, stored in DB)

DB table `provider_models` in `visualizer.db`:
```sql
CREATE TABLE IF NOT EXISTS provider_models (
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    vision INTEGER DEFAULT 1,
    PRIMARY KEY (provider_id, model_id)
);
```

```bash
git commit -m "feat: /api/providers endpoints for listing, model management, and fallback order"
```

---

## Task 10: Error propagation in descriptions endpoint

**Files:**
- Modify: `apps/visualizer/backend/api/descriptions.py`
- Test: `apps/visualizer/backend/tests/test_descriptions_api.py` (add cases)

Changes to `/generate`:
- Catch `RateLimitError` -> 429 `{error: "rate_limit", message: "..."}`
- Catch `AuthenticationError` -> 401 `{error: "auth_error", message: "..."}`
- Catch `ModelUnavailableError` / `ConnectionError` -> 503 `{error: "provider_unavailable", message: "..."}`
- On success: include `provider` and `model` in response
- Accept `provider` and `model` in POST body (optional, uses defaults)

```bash
git commit -m "feat: propagate provider errors from /generate endpoint with proper HTTP status codes"
```

---

## Task 11: Frontend — error feedback in DescriptionsPage

**Files:**
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx`
- Modify: `apps/visualizer/frontend/src/services/api.ts` (handle non-2xx)
- Modify: `apps/visualizer/frontend/src/constants/strings.ts` (error message constants)

Changes:
- `handleGenerate`: wrap in try/catch, detect 429/503/401, show inline error alert
- Add `generateError` state, render `<Alert>` with error message
- Clear error on next attempt

Run: `npx tsc --noEmit && npx vitest run`

```bash
git commit -m "feat: show error feedback in DescriptionsPage when generation fails"
```

---

## Task 12: Frontend — `ProviderModelSelect` component

**Files:**
- Create: `apps/visualizer/frontend/src/components/ui/ProviderModelSelect.tsx`
- Create: `apps/visualizer/frontend/src/services/providersApi.ts`
- Test: `apps/visualizer/frontend/src/components/ui/__tests__/ProviderModelSelect.test.tsx`
- Modify: `apps/visualizer/frontend/src/pages/MatchingPage.tsx` — add to job dialog
- Modify: `apps/visualizer/frontend/src/pages/DescriptionsPage.tsx` — add to batch + single generate

Component: two cascading dropdowns (provider -> model).
- Fetches providers from `GET /api/providers`
- On provider change, fetches models from `GET /api/providers/:id/models`
- Shows availability indicator (green/yellow/red dot)
- `onChange(provider, model)` callback
- Disabled models where `vision: false`

```bash
git commit -m "feat: ProviderModelSelect component with availability indicators"
```

---

## Task 13: Frontend — Provider config page (follows existing architecture)

This task follows the established frontend patterns: **DRY** (reuse existing UI atoms, hooks pattern, shared API layer) and **separation of concerns** (domain folder with barrel, page orchestrates, components render, hook manages state).

### Architecture alignment

| Pattern | How this task follows it |
|---------|--------------------------|
| API services | Add `ProvidersAPI` namespace in `services/api.ts` (same `request<T>()` wrapper, same pattern as `JobsAPI`, `DescriptionsAPI`) |
| Constants | Add `// Providers Page` section in `constants/strings.ts` with `PROVIDER_*` SCREAMING_SNAKE exports |
| Domain folder | Create `components/providers/` with barrel `index.ts` — same as `descriptions/`, `jobs/`, `matching/` |
| Page composition | `ProvidersPage.tsx` owns state + effects, delegates to domain components |
| Hooks | Create `hooks/useProviders.ts` for fetching + caching provider/model data, reusable by both ProvidersPage and ProviderModelSelect |
| UI atoms | Reuse `Alert`, `StatCard`, `StatusBadge`, `PageLoading`, `PageError`, `EmptyState` from `ui/` |
| Root barrel | Add `export * from './providers'` to `components/index.ts` |

### Files

**Create:**
- `apps/visualizer/frontend/src/hooks/useProviders.ts`
- `apps/visualizer/frontend/src/hooks/__tests__/useProviders.test.ts`
- `apps/visualizer/frontend/src/components/providers/ProviderCard.tsx`
- `apps/visualizer/frontend/src/components/providers/ModelList.tsx`
- `apps/visualizer/frontend/src/components/providers/AddModelForm.tsx`
- `apps/visualizer/frontend/src/components/providers/FallbackOrderPanel.tsx`
- `apps/visualizer/frontend/src/components/providers/index.ts`
- `apps/visualizer/frontend/src/pages/ProvidersPage.tsx`

**Modify:**
- `apps/visualizer/frontend/src/services/api.ts` — add `ProvidersAPI` namespace + types
- `apps/visualizer/frontend/src/constants/strings.ts` — add `PROVIDER_*` constants
- `apps/visualizer/frontend/src/components/index.ts` — add `export * from './providers'`
- `apps/visualizer/frontend/src/App.tsx` — add `/providers` route wrapped in `ErrorBoundary`
- `apps/visualizer/frontend/src/components/Layout.tsx` — add nav link using `NAV_PROVIDERS` constant

### Step 1: Add API types and `ProvidersAPI` namespace to `services/api.ts`

Follow the existing pattern (e.g. `DescriptionsAPI`):

```typescript
// Types — add near other interfaces
export interface Provider {
  id: string;
  name: string;
  available: boolean;
}

export interface ProviderModel {
  id: string;
  name: string;
  vision: boolean;
  source: 'config' | 'discovered' | 'user';
}

// Namespace — add after existing API namespaces
export const ProvidersAPI = {
  list: () => request<Provider[]>('/api/providers'),
  listModels: (providerId: string) =>
    request<ProviderModel[]>(`/api/providers/${providerId}/models`),
  addModel: (providerId: string, model: { id: string; name: string; vision: boolean }) =>
    request<ProviderModel>(`/api/providers/${providerId}/models`, {
      method: 'POST',
      body: JSON.stringify(model),
    }),
  removeModel: (providerId: string, modelId: string) =>
    request<void>(`/api/providers/${providerId}/models/${encodeURIComponent(modelId)}`, {
      method: 'DELETE',
    }),
  getFallbackOrder: () => request<{ order: string[] }>('/api/providers/fallback-order'),
  setFallbackOrder: (order: string[]) =>
    request<{ order: string[] }>('/api/providers/fallback-order', {
      method: 'PUT',
      body: JSON.stringify({ order }),
    }),
};
```

### Step 2: Add constants to `constants/strings.ts`

```typescript
// Providers Page
export const NAV_PROVIDERS = 'Providers';
export const PROVIDER_TITLE = 'Provider Configuration';
export const PROVIDER_STATUS_AVAILABLE = 'Available';
export const PROVIDER_STATUS_MISSING_KEY = 'Missing API Key';
export const PROVIDER_STATUS_UNREACHABLE = 'Unreachable';
export const PROVIDER_MODELS_HEADING = 'Models';
export const PROVIDER_ADD_MODEL = 'Add Model';
export const PROVIDER_ADD_MODEL_PLACEHOLDER_ID = 'model-id (e.g. org/model-name)';
export const PROVIDER_ADD_MODEL_PLACEHOLDER_NAME = 'Display name';
export const PROVIDER_REMOVE_CONFIRM = 'Remove this model?';
export const PROVIDER_FALLBACK_HEADING = 'Fallback Order';
export const PROVIDER_FALLBACK_DESCRIPTION = 'When a provider fails, requests cascade in this order.';
export const PROVIDER_SOURCE_CONFIG = 'built-in';
export const PROVIDER_SOURCE_DISCOVERED = 'auto-discovered';
export const PROVIDER_SOURCE_USER = 'user-added';
```

### Step 3: Create `hooks/useProviders.ts`

Follows the same pattern as `useMatchOptions` / `useJobSocket`:

```typescript
// hooks/useProviders.ts
import { useState, useEffect, useCallback } from 'react';
import { ProvidersAPI, Provider, ProviderModel } from '../services/api';

export function useProviders() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [fallbackOrder, setFallbackOrder] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => { /* fetch list + fallback order */ }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const updateFallbackOrder = useCallback(async (order: string[]) => {
    /* call API, optimistic update */
  }, []);

  return { providers, fallbackOrder, loading, error, refresh, updateFallbackOrder };
}
```

### Step 4: Create domain components in `components/providers/`

**`ProviderCard.tsx`** — one card per provider. Reuses `StatusBadge` for availability. Shows provider name, status, model count.

**`ModelList.tsx`** — table/list of models for one provider. Shows `source` badge (config/discovered/user). Delete button only for `source: 'user'`.

**`AddModelForm.tsx`** — inline form (id + name inputs, vision checkbox, submit). Appears under model list.

**`FallbackOrderPanel.tsx`** — ordered list with up/down arrow buttons to reorder. Shows provider name + availability dot. Calls `updateFallbackOrder` on change.

**`index.ts`** — barrel:
```typescript
export { ProviderCard } from './ProviderCard';
export { ModelList } from './ModelList';
export { AddModelForm } from './AddModelForm';
export { FallbackOrderPanel } from './FallbackOrderPanel';
```

### Step 5: Create `ProvidersPage.tsx`

Follows DescriptionsPage composition pattern — page owns state, delegates rendering:

```typescript
// pages/ProvidersPage.tsx
import { useState } from 'react';
import { useProviders } from '../hooks/useProviders';
import { ProvidersAPI, ProviderModel } from '../services/api';
import { ProviderCard, ModelList, AddModelForm, FallbackOrderPanel } from '../components/providers';
import { PageLoading, PageError } from '../components/ui/page-states';
import { Alert } from '../components/ui/Alert';
import { PROVIDER_TITLE, PROVIDER_FALLBACK_HEADING } from '../constants/strings';

export default function ProvidersPage() {
  const { providers, fallbackOrder, loading, error, refresh, updateFallbackOrder } = useProviders();
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [models, setModels] = useState<Record<string, ProviderModel[]>>({});

  // expand/collapse loads models on demand
  // add/remove model calls API then refreshes local state

  if (loading) return <PageLoading />;
  if (error) return <PageError message={error} />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{PROVIDER_TITLE}</h1>
      <div className="grid gap-4">
        {providers.map(provider => (
          <ProviderCard key={provider.id} provider={provider} /* ... */ />
          {/* expanded: ModelList + AddModelForm */}
        ))}
      </div>
      <FallbackOrderPanel
        providers={providers}
        order={fallbackOrder}
        onReorder={updateFallbackOrder}
      />
    </div>
  );
}
```

### Step 6: Wire route + nav

In `App.tsx`: add `<Route path="/providers" element={<ErrorBoundary><ProvidersPage /></ErrorBoundary>} />`

In `Layout.tsx`: add nav link using `NAV_PROVIDERS` constant (same pattern as existing nav items).

### Step 7: Run verification

```bash
cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run
```

### Step 8: Commit

```bash
git add apps/visualizer/frontend/src/hooks/useProviders.ts \
  apps/visualizer/frontend/src/hooks/__tests__/useProviders.test.ts \
  apps/visualizer/frontend/src/components/providers/ \
  apps/visualizer/frontend/src/pages/ProvidersPage.tsx \
  apps/visualizer/frontend/src/services/api.ts \
  apps/visualizer/frontend/src/constants/strings.ts \
  apps/visualizer/frontend/src/components/index.ts \
  apps/visualizer/frontend/src/App.tsx \
  apps/visualizer/frontend/src/components/Layout.tsx
git commit -m "feat: Providers config page with status indicators, model management, and fallback ordering"
```

---

## Task 14: Update `.env.example` + final verification

**Files:**
- Modify: `apps/visualizer/backend/.env.example`

Add:
```env
# OPTIONAL: NVIDIA NIM API key (for cloud vision fallback)
NVIDIA_NIM_API_KEY=

# OPTIONAL: OpenRouter API key (for cloud vision fallback)
OPENROUTER_API_KEY=
```

**Final verification:**

Run all tests:
```bash
python -m pytest lightroom_tagger/core/ -v
python -m pytest apps/visualizer/backend/tests/ -v
cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run
```

```bash
git commit -m "docs: add NVIDIA_NIM_API_KEY and OPENROUTER_API_KEY to .env.example"
```
