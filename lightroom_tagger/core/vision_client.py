"""Unified vision client functions using OpenAI-compatible API.

Two plain functions — ``compare_images`` and ``generate_description`` — that
accept any ``openai.OpenAI`` client (Ollama, NVIDIA NIM, OpenRouter) and a
model identifier.  All provider-specific SDK errors are mapped into our
``ProviderError`` hierarchy so callers never depend on the SDK directly.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Callable

import openai as openai_sdk

from lightroom_tagger.core.analyzer import (
    build_description_prompt,
    parse_vision_response,
)
from lightroom_tagger.core.provider_errors import (
    AuthenticationError,
    ConnectionError,
    ContextLengthError,
    InvalidRequestError,
    ModelUnavailableError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)

COMPARISON_PROMPT = (
    "You are comparing two images to determine if they depict the same photograph "
    "(possibly with different crops, compression, or processing).\n\n"
    "Respond with ONLY valid JSON, no other text:\n"
    '{"confidence": <0-100>, "reasoning": "<one sentence>"}\n\n'
    "confidence: 0 = definitely different photos, 100 = definitely the same photo.\n"
    "Focus on semantic content (subject, scene, composition), not pixel-level differences."
)

LogCallback = Callable[[str, str], None] | None


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _image_url_part(b64: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}


def _map_openai_error(
    exc: Exception,
    provider: str | None = None,
    model: str | None = None,
) -> ProviderError:
    """Map openai SDK exceptions to our ProviderError hierarchy.

    Parameters
    ----------
    exc:
        The original SDK exception.
    provider:
        Provider id to attach as context on the mapped error.
    model:
        Model name to attach as context on the mapped error.
    """
    retry_after = None
    if hasattr(exc, "response") and exc.response is not None:
        raw = exc.response.headers.get("retry-after")
        if raw:
            try:
                retry_after = float(raw)
            except (ValueError, TypeError):
                pass

    if isinstance(exc, openai_sdk.RateLimitError):
        return RateLimitError(str(exc), provider=provider, model=model, retry_after=retry_after)
    if isinstance(exc, openai_sdk.AuthenticationError):
        return AuthenticationError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.BadRequestError):
        msg = str(exc).lower()
        if "context length" in msg or "too many tokens" in msg or "maximum" in msg:
            return ContextLengthError(str(exc), provider=provider, model=model)
        return InvalidRequestError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.APITimeoutError):
        return TimeoutError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.APIConnectionError):
        return ConnectionError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.APIStatusError):
        status = getattr(exc.response, "status_code", 0) if exc.response else 0
        msg = str(exc).lower()
        if "multimodal" in msg or "image_url" in msg or "modality" in msg:
            return InvalidRequestError(str(exc), provider=provider, model=model)
        if status == 503:
            return ModelUnavailableError(str(exc), provider=provider, model=model)
        return ProviderError(str(exc), provider=provider, model=model)

    return ProviderError(str(exc), provider=provider, model=model)


def compare_images(
    client: openai_sdk.OpenAI,
    model: str,
    local_path: str,
    insta_path: str,
    log_callback: LogCallback = None,
) -> dict[str, Any]:
    """Compare two images via chat completions. Returns parsed result dict."""
    local_b64 = _encode_image(local_path)
    insta_b64 = _encode_image(insta_path)

    try:
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
            max_tokens=256,
        )
    except Exception as exc:
        raise _map_openai_error(exc, provider=getattr(client, '_provider_id', None), model=model) from exc

    raw = response.choices[0].message.content or ""
    result = parse_vision_response(raw)

    if log_callback:
        local_name = os.path.basename(local_path)
        insta_name = os.path.basename(insta_path)
        log_callback(
            "debug",
            f"[vision] {local_name} vs {insta_name} -> {result['verdict']} "
            f"({result['confidence']}%) model={model}",
        )

    return result


def generate_description(
    client: openai_sdk.OpenAI,
    model: str,
    image_path: str,
    log_callback: LogCallback = None,
) -> str:
    """Generate a structured description for a single image. Returns raw text."""
    img_b64 = _encode_image(image_path)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": build_description_prompt()},
                    _image_url_part(img_b64),
                ],
            }],
            max_tokens=2048,
        )
    except Exception as exc:
        raise _map_openai_error(exc, provider=getattr(client, '_provider_id', None), model=model) from exc

    raw = response.choices[0].message.content or ""

    if log_callback:
        log_callback("debug", f"[describe] {os.path.basename(image_path)} -> {len(raw)} chars")

    return raw
