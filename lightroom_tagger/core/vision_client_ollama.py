"""Ollama native ``/api/chat`` transport for vision ops.

Ollama serves an OpenAI-compatible surface at ``…/v1`` but only its native
``…/api/chat`` endpoint honours the ``think`` toggle. Through the OpenAI-compat
endpoint, ``think``/``reasoning_effort`` are silently ignored, so a thinking
model (e.g. ``kimi-k2.6``) burns the entire output-token budget on its reasoning
channel and returns empty ``content``. Routing Ollama through this native
transport with ``think=False`` yields the actual answer (and is a harmless no-op
for non-thinking Ollama models).

Split out of ``vision_client`` to keep that module within the core line budget,
mirroring the existing ``vision_client_batch`` split.
"""

from __future__ import annotations

from typing import Any

import httpx
import openai as openai_sdk

from lightroom_tagger.core.exceptions import (
    AuthenticationError,
    ConnectionError,
    InvalidRequestError,
    ModelUnavailableError,
    PayloadTooLargeError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)


def is_ollama_client(client: openai_sdk.OpenAI) -> bool:
    """True when ``client`` targets an Ollama provider.

    The registry stamps ``_provider_id`` on every client it builds
    (see ``ProviderRegistry.get_client``).
    """
    return getattr(client, "_provider_id", None) == "ollama"


def native_chat_url(base_url: str) -> str:
    """Derive Ollama's native ``/api/chat`` URL from its OpenAI-compat base URL."""
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        trimmed = trimmed[: -len("/v1")]
    return f"{trimmed}/api/chat"


def content_to_native(content: Any) -> tuple[str, list[str]]:
    """Convert OpenAI-style message content into ``(text, images)`` for Ollama.

    Accepts either a plain string or a list of ``{"type": ...}`` parts. Image
    parts carry a ``data:…;base64,<b64>`` URL; Ollama's native API wants the bare
    base64 payload in a separate ``images`` list.
    """
    if isinstance(content, str):
        return content, []
    text_chunks: list[str] = []
    images: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype == "text":
            text_chunks.append(str(part.get("text", "")))
        elif ptype == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            if "base64," in url:
                images.append(url.split("base64,", 1)[1])
            elif url:
                images.append(url)
    return "\n".join(text_chunks), images


def _to_native_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Convert OpenAI-style ``messages`` into Ollama native message dicts."""
    native: list[dict[str, Any]] = []
    for m in messages:
        text, images = content_to_native(m.get("content"))
        entry: dict[str, Any] = {"role": m.get("role", "user"), "content": text}
        if images:
            entry["images"] = images
        native.append(entry)
    return native


def _client_timeout(client: openai_sdk.OpenAI, default: float = 300.0) -> float:
    timeout = getattr(client, "timeout", None)
    if isinstance(timeout, (int, float)):
        return float(timeout)
    return default


def _map_status_error(exc: httpx.HTTPStatusError, model: str | None) -> ProviderError:
    status = exc.response.status_code
    if status == 429:
        return RateLimitError(str(exc), provider="ollama", model=model)
    if status in (401, 403):
        return AuthenticationError(str(exc), provider="ollama", model=model)
    if status == 413:
        return PayloadTooLargeError(str(exc), provider="ollama", model=model)
    if status == 503:
        return ModelUnavailableError(str(exc), provider="ollama", model=model)
    if status == 400:
        return InvalidRequestError(str(exc), provider="ollama", model=model)
    return ProviderError(str(exc), provider="ollama", model=model)


def native_chat(
    client: openai_sdk.OpenAI,
    model: str,
    messages: list[Any],
    *,
    max_tokens: int,
    think: bool = False,
) -> str:
    """Run a chat completion via Ollama's native ``/api/chat`` endpoint.

    Used instead of the OpenAI-compat endpoint specifically so ``think`` is
    honoured (see module docstring). Returns the assistant message ``content`` and
    maps transport/HTTP failures onto our ``ProviderError`` hierarchy so callers
    stay SDK-agnostic.
    """
    url = native_chat_url(str(client.base_url))
    payload = {
        "model": model,
        "messages": _to_native_messages(messages),
        "think": think,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }

    try:
        response = httpx.post(url, json=payload, timeout=_client_timeout(client))
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        raise _map_status_error(exc, model) from exc
    except httpx.TimeoutException as exc:
        raise TimeoutError(str(exc), provider="ollama", model=model) from exc
    except httpx.HTTPError as exc:
        raise ConnectionError(str(exc), provider="ollama", model=model) from exc
    except ValueError as exc:
        # response.json() on a non-JSON body (e.g. an HTML error page served with
        # a 2xx by a proxy) raises ValueError/JSONDecodeError, which isn't an
        # httpx error — normalize it onto our hierarchy like other transport faults.
        raise ProviderError(
            f"Ollama returned a non-JSON response: {exc}", provider="ollama", model=model
        ) from exc

    error = data.get("error")
    if error:
        raise ProviderError(str(error), provider="ollama", model=model)
    return (data.get("message") or {}).get("content", "") or ""
