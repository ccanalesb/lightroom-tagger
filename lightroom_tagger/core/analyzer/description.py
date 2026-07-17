"""Structured image description pipeline (OpenAI-compat providers only)."""

import contextlib
import json as _json
import os
import re
from typing import Any

from lightroom_tagger.core.provider_registry import ProviderRegistry

from .image_prep import compress_image, get_viewable_path, get_viewable_path_managed

# Legacy monolithic prompt; prefer prompt_builder.build_description_user_prompt when available.
DESCRIPTION_PROMPT = """You are an experienced photo editor reviewing images for a photography portfolio. Be direct and constructive. State clearly what works and what doesn't — no flattery, no sugarcoating, but also no performative negativity. Every image has strengths and weaknesses; identify both with specifics.

Analyze this photograph and return a structured JSON response with descriptive and technical fields only — do not score the image.

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
  "technical": {
    "dominant_colors": ["#hex1", "#hex2"],
    "mood": "one_word",
    "lighting": "lighting_type",
    "time_of_day": "time_period"
  },
  "subjects": ["subject1", "subject2"]
}"""

_DESCRIPTION_FALLBACK: dict[str, Any] = {
    'summary': '',
    'dominant_colors': [],
    'mood_tags': [],
    'has_repetition': False,
    'composition': {},
    'technical': {},
    'subjects': [],
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


def build_description_op_spec(
    path: str,
    *,
    provider_id: str | None = None,
    model: str | None = None,
    log_callback=None,
    user_prompt: str | None = None,
    silent_compression: bool = False,
    registry: ProviderRegistry | None = None,
):
    """Build a :class:`VisionOpSpec` for the description vision operation."""
    from lightroom_tagger.core.vision_client import generate_description as _gen
    from lightroom_tagger.core.vision_op import VisionOpSpec

    temp_files: list[str] = []

    def prepare_fn_factory():
        viewable, viewable_is_temp = get_viewable_path_managed(path)
        if viewable_is_temp:
            temp_files.append(viewable)

        # Vision-cache hits are already compressed JPEGs; re-running compress_image
        # on restart/resume only adds CPU work and noisy stdout during startup.
        if silent_compression:
            compressed = viewable
        else:
            compressed = compress_image(viewable)
            if compressed != viewable:
                temp_files.append(compressed)

        def fn_factory(client, mdl):
            return lambda: _gen(
                client,
                mdl,
                compressed,
                log_callback=log_callback,
                user_prompt=user_prompt,
            )

        return fn_factory

    def cleanup():
        for f in temp_files:
            if os.path.exists(f):
                with contextlib.suppress(Exception):
                    os.unlink(f)

    return VisionOpSpec(
        resolve_kind="description",
        operation="describe",
        provider_id=provider_id,
        model=model,
        fn_factory=prepare_fn_factory,
        parse_response=parse_description_response,
        log_callback=log_callback,
        registry=registry,
        _cleanup=cleanup,
    )


def run_description_vision_op(
    path: str,
    *,
    provider_id: str | None = None,
    model: str | None = None,
    log_callback=None,
    user_prompt: str | None = None,
    silent_compression: bool = False,
    registry: ProviderRegistry | None = None,
) -> dict:
    """Run the description vision op and return the parsed dict with provider metadata."""
    from lightroom_tagger.core.vision_op import run_vision_op

    spec = build_description_op_spec(
        path,
        provider_id=provider_id,
        model=model,
        log_callback=log_callback,
        user_prompt=user_prompt,
        silent_compression=silent_compression,
        registry=registry,
    )
    parsed, provider, model_used = run_vision_op(spec)
    result = dict(parsed)
    result["_provider"] = provider
    result["_model"] = model_used
    return result


def run_external_agent(_path: str) -> str:
    """Run external API (e.g., Claude, GPT-4V)."""
    return ""
