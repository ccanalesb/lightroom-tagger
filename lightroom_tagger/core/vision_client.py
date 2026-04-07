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


def compare_images_batch(
    client: openai_sdk.OpenAI,
    model: str,
    reference_path: str,
    candidates: list[tuple[int, str]],
    log_callback: LogCallback = None,
) -> dict[int, float]:
    """
    Compare one reference image against N candidates in a single API call.
    
    Parameters
    ----------
    client:
        OpenAI-compatible client
    model:
        Model identifier
    reference_path:
        Path to the reference (Instagram) image
    candidates:
        List of (candidate_id, candidate_path) tuples
    log_callback:
        Optional logging callback
    
    Returns
    -------
    dict[int, float]:
        Mapping of candidate_id -> confidence (0-100)
    
    Raises
    ------
    ProviderError:
        On API/model errors (mapped from openai SDK)
    """
    import json
    
    if not candidates:
        return {}
    
    # Encode reference image once
    ref_b64 = _encode_image(reference_path)
    
    # Build prompt for batch comparison with explicit JSON structure
    candidate_info = "\n".join([
        f"Candidate {cid}: (image attached)"
        for cid, _ in candidates
    ])
    
    batch_prompt = (
        "You are comparing ONE reference image against MULTIPLE candidate images.\n"
        "Determine if each candidate depicts the same photograph as the reference "
        "(possibly with different crops, compression, or processing).\n\n"
        f"Reference: (image attached)\n\n{candidate_info}\n\n"
        "Respond with ONLY valid JSON, no other text:\n"
        '{"results": [{"id": <int>, "confidence": <0-100>}, ...]}\n\n'
        "confidence: 0 = definitely different, 100 = definitely same.\n"
        "Focus on semantic content (subject, scene, composition), not pixel-level differences."
    )
    
    # Build message content: [prompt, ref_image, candidate1, candidate2, ...]
    content_parts: list[dict[str, Any]] = [
        {"type": "text", "text": batch_prompt},
        _image_url_part(ref_b64),
    ]
    
    for cid, cand_path in candidates:
        cand_b64 = _encode_image(cand_path)
        content_parts.append(_image_url_part(cand_b64))
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": content_parts,
            }],
            max_tokens=1024,
        )
    except Exception as exc:
        raise _map_openai_error(exc, provider=getattr(client, '_provider_id', None), model=model) from exc
    
    raw = response.choices[0].message.content or "{}"
    
    # Parse structured JSON response
    try:
        # Extract JSON from markdown code blocks if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        
        parsed = json.loads(raw)
        results_list = parsed.get("results", [])
        
        # Map results back to candidate IDs
        result_map: dict[int, float] = {}
        for item in results_list:
            cid = item.get("id")
            conf = item.get("confidence", 0)
            if cid is not None:
                result_map[cid] = float(conf)
        
        if log_callback:
            ref_name = os.path.basename(reference_path)
            log_callback(
                "debug",
                f"[vision_batch] {ref_name} vs {len(candidates)} candidates -> {len(result_map)} results"
            )
        
        return result_map
    
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Fallback: Return 0 confidence for all if parsing fails
        if log_callback:
            log_callback("warning", f"[vision_batch] JSON parse error: {e}, raw={raw[:100]}")
        return {cid: 0.0 for cid, _ in candidates}


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
