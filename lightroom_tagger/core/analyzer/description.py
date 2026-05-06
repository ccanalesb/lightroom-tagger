"""Structured image description pipeline (OpenAI-compat providers only)."""

import contextlib
import json as _json
import os
import re
from typing import Any

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.provider_registry import ProviderRegistry

from .image_prep import compress_image, get_viewable_path

# Legacy monolithic prompt; prefer prompt_builder + DB perspectives when available.
DESCRIPTION_PROMPT = """You are an experienced photo editor reviewing images for a photography portfolio. Be direct and constructive. State clearly what works and what doesn't — no flattery, no sugarcoating, but also no performative negativity. Every image has strengths and weaknesses; identify both with specifics.

Analyze this photograph from three expert perspectives and return a structured JSON response.

## Perspectives (each gets its own score — an image can be a 7 for street but a 3 for publishing)
1. **Street Photographer**: Is there a decisive moment or is the timing off? Evaluate geometry, light, and candid quality. What would make this frame stronger? Score how well it works AS street photography.
2. **Documentary Photographer**: Does this tell a story? Is there emotional weight? What narrative is present or missing? How could the storytelling improve? Score how well it works AS documentary work.
3. **Publisher**: What's the realistic use case? (magazine cover, editorial feature, blog post, social media, stock, none). What audience would this serve? What limits its usability? Score its commercial value.

Also choose which single perspective fits this image best (best_perspective).

## Composition Analysis
Identify:
- **Layers**: List distinct depth layers (foreground, midground, background) and what occupies each. Note if layers are weak or missing.
- **Techniques**: Which composition techniques are present (rule_of_thirds, leading_lines, symmetry, framing, diagonal, golden_ratio, negative_space, repetition).
- **Problems**: Specific composition weaknesses (cluttered, no clear subject, awkward crop, distracting elements, missed focus). Empty list if none.
- **Depth**: shallow, moderate, or deep
- **Balance**: symmetric, asymmetric, or radial

## Technical Analysis
- **Dominant colors**: Up to 5 hex codes
- **Mood**: One word (contemplative, energetic, melancholic, joyful, tense, serene, dramatic, mysterious, flat, dull, chaotic, intimate, raw, quiet)
- **Lighting**: (natural_front, natural_side, natural_back, golden_hour, blue_hour, overcast, artificial, mixed, low_light, high_key, low_key)
- **Time of day** if discernible: (dawn, morning, midday, afternoon, golden_hour, blue_hour, night, unknown)

## Scoring Rubric (use the FULL range honestly — most photos land between 4-6)
- **1-2**: Technically broken or no photographic intent. Accidental shot.
- **3-4**: Snapshot with some intent but weak execution or no clear subject.
- **5**: Competent but forgettable. Technically fine, nothing memorable.
- **6**: Above average. One strong element (light, moment, composition) but doesn't fully come together.
- **7**: Good. Clear intent, solid execution. Minor issues hold it back.
- **8**: Strong. Portfolio-worthy. Would make someone pause and look twice.
- **9**: Excellent. Gallery-level. Distinctive voice, memorable image.
- **10**: Masterwork. Iconic potential. Rare.

## Required JSON format (respond with ONLY this JSON, no other text):
{
  "summary": "1-2 sentence objective description of the image content",
  "dominant_colors": [],
  "mood_tags": [],
  "has_repetition": false,
  "composition": {
    "layers": ["foreground: <description>", "midground: <description>", "background: <description>"],
    "techniques": ["technique1", "technique2"],
    "problems": ["specific issue 1", "specific issue 2"],
    "depth": "shallow|moderate|deep",
    "balance": "symmetric|asymmetric|radial"
  },
  "perspectives": {
    "street": {
      "analysis": "2-3 sentences — what works, what doesn't, what would improve it",
      "score": 1-10
    },
    "documentary": {
      "analysis": "2-3 sentences — what works, what doesn't, what would improve it",
      "score": 1-10
    },
    "publisher": {
      "analysis": "2-3 sentences — realistic use case and what limits usability",
      "score": 1-10
    }
  },
  "technical": {
    "dominant_colors": ["#hex1", "#hex2"],
    "mood": "one_word",
    "lighting": "lighting_type",
    "time_of_day": "time_period"
  },
  "subjects": ["subject1", "subject2"],
  "best_perspective": "street|documentary|publisher"
}"""

_DESCRIPTION_FALLBACK: dict[str, Any] = {
    'summary': '',
    'dominant_colors': [],
    'mood_tags': [],
    'has_repetition': False,
    'composition': {},
    'perspectives': {},
    'technical': {},
    'subjects': [],
    'best_perspective': '',
}


def build_description_prompt() -> str:
    """Return the image description prompt."""
    return DESCRIPTION_PROMPT


def parse_description_response(raw: str) -> dict:
    """Parse model response into structured description dict."""
    text = raw.strip()

    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed = _json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (_json.JSONDecodeError, ValueError):
        pass

    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            parsed = _json.loads(brace_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except (_json.JSONDecodeError, ValueError):
            pass

    return dict(_DESCRIPTION_FALLBACK)


def _resolve_default_description_provider(
    registry: ProviderRegistry,
    model: str | None,
) -> tuple[str | None, str | None]:
    desc_defaults = registry.defaults.get("description", {}) or {}
    provider_id: str | None = desc_defaults.get("provider")
    resolved_model = model if model is not None else desc_defaults.get("model")
    if provider_id is None:
        order = registry.fallback_order
        if order:
            provider_id = order[0]
    return provider_id, resolved_model


def describe_image(path: str, agent_type: str | None = None,
                    provider_id: str | None = None, model: str | None = None,
                    log_callback=None, user_prompt: str | None = None,
                    *,
                    silent_compression: bool = False) -> dict:
    """Generate structured description using the provider registry (OpenAI-compat).

    When *provider_id* is given, that provider is used. Otherwise *agent_type*
    is read from config when omitted: ``external`` returns an empty parsed
    structure; ``local`` (default) resolves ``defaults.description`` or
    ``fallback_order`` from ``providers.json``.
    """
    if provider_id is not None:
        return _describe_image_via_provider(
            path,
            provider_id,
            model,
            log_callback,
            user_prompt=user_prompt,
            silent_compression=silent_compression,
        )

    if agent_type is None:
        try:
            config = load_config()
            agent_type = getattr(config, 'agent_type', 'local')
        except Exception:
            agent_type = 'local'

    if agent_type == 'external':
        return parse_description_response('')

    registry = ProviderRegistry()
    resolved_pid, resolved_model = _resolve_default_description_provider(registry, model)
    if resolved_pid is None:
        from lightroom_tagger.core.exceptions import ModelUnavailableError
        raise ModelUnavailableError(
            'No provider configured for image description — set defaults.description in providers.json',
            provider=None,
            model=None,
        )

    return _describe_image_via_provider(
        path,
        resolved_pid,
        resolved_model,
        log_callback,
        user_prompt=user_prompt,
        silent_compression=silent_compression,
    )


def _describe_image_via_provider(path: str, provider_id: str,
                                  model: str | None, log_callback=None,
                                  user_prompt: str | None = None,
                                  *,
                                  silent_compression: bool = False) -> dict:
    """Generate description via the unified provider pipeline."""
    from lightroom_tagger.core.fallback import FallbackDispatcher
    from lightroom_tagger.core.vision_client import generate_description as _gen

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

    temp_files: list[str] = []
    viewable = get_viewable_path(path)
    if viewable != path:
        temp_files.append(viewable)

    compressed = compress_image(viewable, silent=silent_compression)
    if compressed != viewable:
        temp_files.append(compressed)

    try:
        def fn_factory(client, mdl):
            return lambda: _gen(
                client,
                mdl,
                compressed,
                log_callback=log_callback,
                user_prompt=user_prompt,
            )

        raw, actual_provider, actual_model = dispatcher.call_with_fallback(
            operation="describe",
            fn_factory=fn_factory,
            provider_id=provider_id,
            model=model,
            log_callback=log_callback,
        )
        result = parse_description_response(raw)
        result["_provider"] = actual_provider
        result["_model"] = actual_model
        return result
    finally:
        for f in temp_files:
            if os.path.exists(f):
                with contextlib.suppress(Exception):
                    os.unlink(f)
