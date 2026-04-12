"""Unified vision client functions using OpenAI-compatible API.

Two plain functions — ``compare_images`` and ``generate_description`` — that
accept any ``openai.OpenAI`` client (Ollama, NVIDIA NIM, OpenRouter) and a
model identifier.  All provider-specific SDK errors are mapped into our
``ProviderError`` hierarchy so callers never depend on the SDK directly.
"""

from __future__ import annotations

import base64
import contextlib
import os
from collections.abc import Callable
from typing import Any, cast

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
    PayloadTooLargeError,
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

SCORE_JSON_REPAIR_SYSTEM = (
    "You are a JSON repair tool. Output analysis is forbidden; emit data only.\n"
    "Return a single JSON object with exactly these keys:\n"
    '- "perspective_slug" (string)\n'
    '- "score" (integer from 1 through 10 inclusive)\n'
    '- "rationale" (string)\n'
    "Do not wrap the JSON in markdown fences. Do not add any text before or after the object."
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
            with contextlib.suppress(ValueError, TypeError):
                retry_after = float(raw)

    if isinstance(exc, openai_sdk.RateLimitError):
        return RateLimitError(str(exc), provider=provider, model=model, retry_after=retry_after)
    if isinstance(exc, openai_sdk.AuthenticationError):
        return AuthenticationError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.BadRequestError):
        msg = str(exc).lower()
        if "context length" in msg or "too many tokens" in msg or "maximum" in msg:
            return ContextLengthError(str(exc), provider=provider, model=model)
        if "budget_tokens" in msg or "thinking" in msg:
            return ContextLengthError(str(exc), provider=provider, model=model)
        return InvalidRequestError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.APITimeoutError):
        return TimeoutError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.APIConnectionError):
        return ConnectionError(str(exc), provider=provider, model=model)
    if isinstance(exc, openai_sdk.APIStatusError):
        status = getattr(exc.response, "status_code", 0) if exc.response else 0
        msg = str(exc).lower()
        if status == 413:
            return PayloadTooLargeError(str(exc), provider=provider, model=model)
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
    max_tokens: int = 256,
) -> dict[str, Any]:
    """Compare two images via chat completions. Returns parsed result dict."""
    local_b64 = _encode_image(local_path)
    insta_b64 = _encode_image(insta_path)

    kwargs: dict[str, Any] = {}
    if "claude" in model.lower():
        kwargs["extra_body"] = {"reasoning_effort": "none"}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": COMPARISON_PROMPT},
                            _image_url_part(local_b64),
                            _image_url_part(insta_b64),
                        ],
                    }
                ],
            ),
            max_tokens=max_tokens,
            **kwargs,
        )
    except Exception as exc:
        raise _map_openai_error(
            exc, provider=getattr(client, "_provider_id", None), model=model
        ) from exc

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
    max_tokens: int = 4096,
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
    candidate_info = "\n".join([f"Candidate {cid}: (image attached)" for cid, _ in candidates])

    batch_prompt = (
        "CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no prose, ONLY JSON.\n\n"
        "Task: Compare the FIRST image (reference) against the remaining candidate images.\n"
        "For each candidate, determine if it depicts the SAME photograph as the reference.\n\n"
        f"Reference image: First image\n"
        f"Candidates to compare:\n{candidate_info}\n\n"
        "REQUIRED OUTPUT FORMAT (copy this structure exactly):\n"
        '{"results": [{"id": 1, "confidence": 85}, {"id": 2, "confidence": 10}, ...]}\n\n'
        "Rules:\n"
        "- confidence: 0-100, where 0=completely different, 100=definitely same photo\n"
        "- Compare semantic content: subject, scene, composition, angle\n"
        "- Ignore: crops, quality, filters, color vs B&W\n"
        "- Include ALL candidate IDs in results\n\n"
        "RESPOND WITH ONLY THE JSON OBJECT. DO NOT ADD ANY OTHER TEXT."
    )

    # Build message content: [prompt, ref_image, candidate1, candidate2, ...]
    content_parts: list[dict[str, Any]] = [
        {"type": "text", "text": batch_prompt},
        _image_url_part(ref_b64),
    ]

    for _cid, cand_path in candidates:
        cand_b64 = _encode_image(cand_path)
        content_parts.append(_image_url_part(cand_b64))

    kwargs: dict[str, Any] = {}
    if "claude" in model.lower():
        kwargs["extra_body"] = {"reasoning_effort": "none"}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {
                        "role": "system",
                        "content": "You are a JSON-only API. You respond exclusively with valid JSON. Never include explanations or prose.",
                    },
                    {
                        "role": "user",
                        "content": content_parts,
                    },
                ],
            ),
            max_tokens=max_tokens,
            temperature=0.1,
            **kwargs,
        )
    except Exception as exc:
        raise _map_openai_error(
            exc, provider=getattr(client, "_provider_id", None), model=model
        ) from exc

    raw = response.choices[0].message.content or "{}"

    if log_callback:
        log_callback("debug", f"[vision_batch] Raw response length: {len(raw)} chars")
        log_callback("debug", f"[vision_batch] Raw response (first 500 chars): {raw[:500]}")
        if len(raw) > 500:
            log_callback("debug", f"[vision_batch] Raw response (last 200 chars): ...{raw[-200:]}")

    # Parse structured JSON response
    try:
        # Extract JSON from markdown code blocks if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        results_list = parsed.get("results", [])

        if log_callback:
            log_callback("debug", f"[vision_batch] Parsed JSON: results_list={results_list}")

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
                f"[vision_batch] {ref_name} vs {len(candidates)} candidates -> {len(result_map)} results",
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
    *,
    user_prompt: str | None = None,
) -> str:
    """Generate a structured description for a single image. Returns raw text."""
    img_b64 = _encode_image(image_path)
    text_prompt = build_description_prompt()
    if user_prompt is not None and user_prompt.strip():
        text_prompt = user_prompt.strip()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_prompt},
                            _image_url_part(img_b64),
                        ],
                    }
                ],
            ),
            max_tokens=2048,
        )
    except Exception as exc:
        raise _map_openai_error(
            exc, provider=getattr(client, "_provider_id", None), model=model
        ) from exc

    raw = response.choices[0].message.content or ""

    if log_callback:
        log_callback("debug", f"[describe] {os.path.basename(image_path)} -> {len(raw)} chars")

    return raw


def complete_chat_text(
    client: openai_sdk.OpenAI,
    model: str,
    *,
    system: str,
    user: str,
    max_tokens: int = 512,
    temperature: float = 0.0,
) -> str:
    """Run a text-only chat completion (no images). Returns assistant message content."""
    kwargs: dict[str, Any] = {}
    if "claude" in model.lower():
        kwargs["extra_body"] = {"reasoning_effort": "none"}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            ),
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
    except Exception as exc:
        raise _map_openai_error(
            exc, provider=getattr(client, "_provider_id", None), model=model
        ) from exc

    return response.choices[0].message.content or ""


def make_score_json_llm_fixer(
    complete_text_fn: Callable[..., str],
    **kwargs: Any,
) -> Callable[[str, str], str]:
    """Build an ``llm_fixer`` for :func:`parse_score_response_with_retry`.

    The returned callable forwards to *complete_text_fn* with
    :data:`SCORE_JSON_REPAIR_SYSTEM` and a user message containing truncated raw
    output plus the validation error summary. Each invocation performs **at most
    one** repair attempt; callers must not loop unbounded.

    Phase 6 scoring handlers should pass a bound ``complete_chat_text`` (or
    equivalent) with the job's OpenAI-compatible client and model — there is no
    global default repair client in this module. Intended for use as the
    ``llm_fixer`` argument to
    ``lightroom_tagger.core.structured_output.parse_score_response_with_retry``.
    """

    def llm_fixer(raw: str, err: str) -> str:
        truncated = raw[:4096]
        user_msg = (
            "The previous output is not valid JSON for the required score schema.\n\n"
            f"Raw model output (first 4096 characters):\n{truncated}\n\n"
            f"Validation error summary:\n{err}\n\n"
            "Respond with ONLY the corrected JSON object. Keys must be exactly "
            "perspective_slug, score, and rationale."
        )
        return complete_text_fn(system=SCORE_JSON_REPAIR_SYSTEM, user=user_msg, **kwargs)

    return llm_fixer
