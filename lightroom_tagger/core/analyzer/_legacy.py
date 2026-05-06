import contextlib
import json as _json
import os
from typing import Any

import ollama

from lightroom_tagger.core.config import get_description_model, get_vision_model, load_config
from lightroom_tagger.core.exceptions import ContextLengthError

from .description import build_description_prompt, describe_image
from .image_inspect import compute_phash, extract_exif
from .image_prep import RAW_EXTENSIONS, compress_image, get_viewable_path


def analyze_image(path: str) -> dict[str, Any]:
    """Analyze image and return all matching signals.

    Returns:
        {phash, exif, description (str summary), structured_description (full dict)}
    """
    phash = compute_phash(path)
    exif = extract_exif(path)
    structured = describe_image(path)

    return {
        'phash': phash,
        'exif': exif,
        'description': structured.get('summary', ''),
        'structured_description': structured,
    }


def run_local_agent(path: str, user_prompt: str | None = None) -> str:
    """Run local vision model (e.g., LLaVA) via Ollama Python client."""
    temp_files: list[str] = []
    viewable = get_viewable_path(path)
    if viewable != path:
        temp_files.append(viewable)

    compressed = compress_image(viewable)
    if compressed != viewable:
        temp_files.append(compressed)

    prompt_text = build_description_prompt()
    if user_prompt is not None and user_prompt.strip():
        prompt_text = user_prompt.strip()

    try:
        response = ollama.chat(
            model=get_description_model(),
            messages=[
                {
                    'role': 'user',
                    'content': prompt_text,
                    'images': [compressed],
                }
            ],
        )
        content = getattr(response.message, 'content', None) if response and response.message else None
        return content or ''
    except Exception as e:
        print(f"  Ollama description failed: {e}", flush=True)
        return ''
    finally:
        for f in temp_files:
            if os.path.exists(f):
                with contextlib.suppress(Exception):
                    os.unlink(f)

def run_external_agent(path: str) -> str:
    """Run external API (e.g., Claude, GPT-4V)."""
    return ""


def compare_with_vision(local_path: str, insta_path: str, log_callback=None,
                        cached_local_path: str | None = None, compressed_insta_path: str | None = None,
                        provider_id: str | None = None, model: str | None = None) -> dict:
    """Compare two images using a vision model with compression.

    When *provider_id* is supplied, routes through the multi-provider pipeline
    (retry + fallback via ``FallbackDispatcher``).  Otherwise falls back to the
    legacy Ollama-only path.

    Compresses images to max VISION_MAX_DIMENSION pixels before comparison
    to reduce bandwidth and processing time. Supports pre-compressed paths
    to avoid redundant compression.

    Args:
        local_path: Original path to catalog image (for error reporting and RAW conversion)
        insta_path: Original path to Instagram image (for error reporting)
        log_callback: Optional callback for logging
        cached_local_path: Pre-compressed catalog image path (optional, uses cache if available)
        compressed_insta_path: Pre-compressed Instagram image path (optional)
        provider_id: Provider to use (``None`` → legacy Ollama path)
        model: Model to use with the selected provider (``None`` → provider default)

    Returns:
        dict with keys ``confidence`` (0-100), ``verdict`` (``SAME`` | ``DIFFERENT`` | ``UNCERTAIN``),
        ``reasoning`` (str), and when using the multi-provider path, ``_provider`` and ``_model``.
    """
    # Track all temp files for cleanup
    temp_files = []
    compressed_local = None
    compressed_insta = None

    try:
        # Step 1: Handle catalog image (local_path)
        if cached_local_path and os.path.exists(cached_local_path):
            # Use pre-compressed cached image
            compressed_local = cached_local_path
            if log_callback:
                log_callback('info', f'Using cached compressed image for {os.path.basename(local_path)}')
        else:
            # Get viewable path (convert RAW/DNG if needed)
            viewable_local = get_viewable_path(local_path)
            if viewable_local != local_path:
                temp_files.append(viewable_local)
                # Log RAW conversion
                if log_callback:
                    ext = os.path.splitext(local_path)[1].lower()
                    if ext in RAW_EXTENSIONS and viewable_local.lower().endswith(('.jpg', '.jpeg')):
                        sidecar_path = local_path.rsplit('.', 1)[0] + '.JPG'
                        sidecar_path_lower = local_path.rsplit('.', 1)[0] + '.jpg'
                        if os.path.exists(sidecar_path) or os.path.exists(sidecar_path_lower):
                            log_callback('info', f'Using JPG sidecar for {os.path.basename(local_path)}')
                        else:
                            log_callback('info', f'Converted DNG to JPG: {os.path.basename(viewable_local)}')
            else:
                viewable_local = local_path

            # Compress the image
            compressed_local = compress_image(viewable_local)
            if compressed_local != viewable_local:
                temp_files.append(compressed_local)

        # Step 2: Handle Instagram image
        if compressed_insta_path and os.path.exists(compressed_insta_path):
            compressed_insta = compressed_insta_path
        else:
            viewable_insta = get_viewable_path(insta_path)
            if viewable_insta != insta_path:
                temp_files.append(viewable_insta)
            else:
                viewable_insta = insta_path

            compressed_insta = compress_image(viewable_insta)
            if compressed_insta != viewable_insta:
                temp_files.append(compressed_insta)

        # Step 3: Run vision comparison
        if provider_id is not None:
            result = _compare_via_provider(
                compressed_local, compressed_insta,
                provider_id, model, log_callback,
            )
        else:
            result = run_vision_ollama(compressed_local, compressed_insta, log_callback=log_callback)

        return result

    finally:
        # Clean up temp files we created (but not cached files)
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                with contextlib.suppress(Exception):
                    os.unlink(temp_file)


MAX_TOKENS_ESCALATION = [256, 4096, 32768, 65536]

# Shared across calls so that once a model needs higher max_tokens we
# remember it for subsequent candidates instead of re-discovering every time.
_model_min_tokens: dict[str, int] = {}

# Models where max_tokens escalation was fully exhausted and still fails.
# Keyed by "provider:model" — these are skipped immediately to avoid
# wasting minutes on retries that will never succeed.
_broken_provider_models: set[str] = set()


def _compare_via_provider(local_path: str, insta_path: str,
                          provider_id: str, model: str | None,
                          log_callback=None) -> dict:
    """Run vision comparison via the unified provider pipeline.

    Escalates ``max_tokens`` automatically on ``ContextLengthError``
    (e.g. Claude extended-thinking models that require ``max_tokens >
    thinking.budget_tokens``).  Models that succeed at 256 are never
    affected — escalation only triggers after failure.

    Discovered minimums are cached in ``_model_min_tokens`` so later
    candidates skip the failing lower values.
    """
    from lightroom_tagger.core.fallback import FallbackDispatcher
    from lightroom_tagger.core.provider_registry import ProviderRegistry
    from lightroom_tagger.core.vision_client import compare_images as _cmp

    registry = ProviderRegistry()
    dispatcher = FallbackDispatcher(registry)

    if model is None:
        models = registry.list_models(provider_id)
        if not models:
            from lightroom_tagger.core.exceptions import ModelUnavailableError
            raise ModelUnavailableError(
                f"No models available for provider '{provider_id}' — check provider config",
                provider=provider_id,
                model=None,
            )
        model = models[0]["id"]

    def fn_factory(client, mdl):
        from lightroom_tagger.core.exceptions import InvalidRequestError

        provider_key = f"{provider_id}:{mdl}"
        if provider_key in _broken_provider_models:
            def _skip():
                raise InvalidRequestError(
                    f"{mdl} is broken (max_tokens exhausted in prior call)",
                    provider=provider_id, model=mdl,
                )
            return _skip

        cached_min = _model_min_tokens.get(mdl, 0)
        start_idx = 0
        for i, val in enumerate(MAX_TOKENS_ESCALATION):
            if val >= cached_min:
                start_idx = i
                break
        state = {"idx": start_idx}

        def _call():
            tokens = MAX_TOKENS_ESCALATION[state["idx"]]
            try:
                return _cmp(client, mdl, local_path, insta_path,
                            log_callback=log_callback, max_tokens=tokens)
            except ContextLengthError:
                if state["idx"] < len(MAX_TOKENS_ESCALATION) - 1:
                    state["idx"] += 1
                    next_val = MAX_TOKENS_ESCALATION[state["idx"]]
                    _model_min_tokens[mdl] = next_val
                    if log_callback:
                        log_callback(
                            "warning",
                            f"[compare] Escalating max_tokens to "
                            f"{next_val} for {mdl}",
                        )
                else:
                    _broken_provider_models.add(provider_key)
                    if log_callback:
                        log_callback(
                            "warning",
                            f"[compare] max_tokens exhausted at {tokens} "
                            f"for {mdl}, blacklisting for session",
                        )
                raise

        return _call

    result, actual_provider, actual_model = dispatcher.call_with_fallback(
        operation="compare",
        fn_factory=fn_factory,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
    )
    result["_provider"] = actual_provider
    result["_model"] = actual_model
    return result


def parse_vision_response(raw: str) -> dict:
    """Parse vision model response into structured result.

    Expects JSON: {"confidence": 0-100, "reasoning": "..."}
    Falls back to legacy SAME/DIFFERENT/UNCERTAIN parsing.
    """
    raw = raw.strip()

    try:
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        data = _json.loads(raw)
        confidence = int(data.get('confidence', 50))
        confidence = max(0, min(100, confidence))
        if confidence >= 70:
            verdict = 'SAME'
        elif confidence <= 30:
            verdict = 'DIFFERENT'
        else:
            verdict = 'UNCERTAIN'
        return {'confidence': confidence, 'verdict': verdict, 'reasoning': data.get('reasoning', '')}
    except (TypeError, ValueError, KeyError, _json.JSONDecodeError):
        pass

    upper = raw.upper()
    if upper.startswith('SAME') and 'DIFFERENT' not in upper[:20]:
        return {'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}
    elif 'DIFFERENT' in upper[:50]:
        return {'confidence': 0, 'verdict': 'DIFFERENT', 'reasoning': ''}
    return {'confidence': 50, 'verdict': 'UNCERTAIN', 'reasoning': ''}


def run_vision_ollama(local_path: str, insta_path: str, log_callback=None) -> dict:
    """Compare two images using Ollama HTTP API with base64-encoded images."""
    import base64
    import json
    import urllib.request

    prompt = (
        "You are comparing two images to determine if they depict the same photograph "
        "(possibly with different crops, compression, or processing).\n\n"
        "Respond with ONLY valid JSON, no other text:\n"
        '{"confidence": <0-100>, "reasoning": "<one sentence>"}\n\n'
        "confidence: 0 = definitely different photos, 100 = definitely the same photo.\n"
        "Focus on semantic content (subject, scene, composition), not pixel-level differences."
    )

    model = get_vision_model()

    images_b64 = []
    for path in (local_path, insta_path):
        with open(path, 'rb') as f:
            images_b64.append(base64.b64encode(f.read()).decode('utf-8'))

    payload = json.dumps({
        'model': model,
        'prompt': prompt,
        'images': images_b64,
        'stream': False,
    }).encode('utf-8')

    ollama_host = load_config().ollama_host
    req = urllib.request.Request(
        f'{ollama_host}/api/generate',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )

    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    if 'error' in data:
        raise RuntimeError(f"Ollama error: {data['error']}")

    raw_response = data.get('response', '').strip()
    result = parse_vision_response(raw_response)

    if log_callback:
        local_name = os.path.basename(local_path)
        insta_name = os.path.basename(insta_path)
        log_callback(
            'debug',
            f'[vision] {local_name} vs {insta_name} → {result["verdict"]} '
            f'({result["confidence"]}%) (model={model}, raw="{raw_response[:80]}")',
        )

    return result


def vision_score(result) -> float:
    """Convert vision result to 0.0-1.0 score.

    Accepts int confidence (0-100) or legacy string ('SAME'/'DIFFERENT'/'UNCERTAIN').
    """
    if isinstance(result, (int, float)):
        return max(0.0, min(1.0, result / 100))
    if isinstance(result, str):
        if result == 'SAME':
            return 1.0
        elif result == 'DIFFERENT':
            return 0.0
        return 0.5
    return 0.5
