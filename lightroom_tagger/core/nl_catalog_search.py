"""LLM runner for natural-language → structured catalog filter JSON (text-only)."""

from __future__ import annotations

from collections.abc import Callable

from lightroom_tagger.core.fallback import FallbackDispatcher
from lightroom_tagger.core.provider_errors import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import complete_chat_messages, complete_chat_text

LogCallback = Callable[[str, str], None] | None

NL_CATALOG_FILTER_SYSTEM_PROMPT = """You are a filter translator for a Lightroom photo catalog search API.
Return only a single JSON object with no markdown fences and no text before or after the JSON.

The object may use only these field names (omit any you do not need; use null only where a field is explicitly unused — prefer omitting keys):
posted, month, keyword, min_rating, date_from, date_to, score_perspective, min_score, sort_by_score, sort_by_date, description_search, dominant_colors, mood_tags.

Do not include any other keys. Field meanings:
- posted: boolean, filter images marked posted/unposted to Instagram
- month: YYYYmm string
- keyword: exact Lightroom metadata keyword tag (e.g. "wedding", "portrait") — only use when the user refers to a specific tagged category, NOT for visual content descriptions
- date_from, date_to: date strings as needed
- min_rating, min_score: integers; min_score 1–10 and requires score_perspective when set
- score_perspective: lowercase slug [a-z][a-z0-9_]* for score-based filters
- sort_by_score: "asc" or "desc" (requires score_perspective)
- sort_by_date: "newest" or "oldest"
- description_search: free-text search on AI-generated image descriptions — use this for ANY query about visual content, subjects, scenes, actions, gestures, objects, mood, or composition
- dominant_colors: JSON array of hex color codes (e.g. ["#ff0000","#c62828"]) extracted from images — ONLY use when the user provides an explicit hex code; do NOT use for color names like "red" or "blue" since the DB stores hex values, not names
- mood_tags: JSON array of mood strings (e.g. ["melancholic","energetic"]) — only use when the user explicitly mentions mood

IMPORTANT: When the user asks about what is visually in photos (people, objects, actions, scenes, lighting, colours by name, etc.) always use description_search, not keyword or dominant_colors.
"""


def _normalize_nl_messages(messages: list[dict]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role_raw = str(m.get("role", "")).strip().lower()
        if role_raw not in ("user", "assistant"):
            continue
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        out.append({"role": role_raw, "content": content})
    return out


def run_nl_catalog_filter_llm(
    user_text: str,
    *,
    provider_id: str | None,
    model: str | None,
    log_callback: LogCallback = None,
) -> str:
    """Call the LLM to produce a JSON string matching :class:`CatalogNlFilter` (no bypass)."""
    registry = ProviderRegistry()
    dispatcher = FallbackDispatcher(registry)
    desc_defaults = registry.defaults.get("description", {}) or {}

    resolved_provider = provider_id if provider_id is not None else desc_defaults.get("provider")
    if not resolved_provider:
        raise ModelUnavailableError(
            "No provider configured for NL filter — set defaults.description.provider",
            provider=None,
            model=None,
        )

    resolved_model: str | None = model
    if resolved_model is None:
        resolved_model = desc_defaults.get("model")
    if resolved_model is None:
        models = registry.list_models(resolved_provider)
        if not models:
            raise ModelUnavailableError(
                f"No models available for provider {resolved_provider!r} — check provider config",
                provider=resolved_provider,
                model=None,
            )
        resolved_model = models[0]["id"]

    def fn_factory(client, mdl: str):
        return lambda: complete_chat_text(
            client,
            mdl,
            system=NL_CATALOG_FILTER_SYSTEM_PROMPT,
            user=user_text,
            max_tokens=1024,
            temperature=0.0,
        )

    raw, _pid, _mid = dispatcher.call_with_fallback(
        operation="nl_filter",
        fn_factory=fn_factory,
        provider_id=resolved_provider,
        model=resolved_model,
        log_callback=log_callback,
    )
    return raw


def run_nl_catalog_filter_llm_multi_turn(
    messages: list[dict],
    *,
    provider_id: str | None = None,
    model: str | None = None,
    log_callback: LogCallback = None,
) -> str:
    """Call the LLM with conversation history; returns raw JSON string for :class:`CatalogNlFilter`."""
    registry = ProviderRegistry()
    dispatcher = FallbackDispatcher(registry)
    desc_defaults = registry.defaults.get("description", {}) or {}

    resolved_provider = provider_id if provider_id is not None else desc_defaults.get("provider")
    if not resolved_provider:
        raise ModelUnavailableError(
            "No provider configured for NL filter — set defaults.description.provider",
            provider=None,
            model=None,
        )

    resolved_model: str | None = model
    if resolved_model is None:
        resolved_model = desc_defaults.get("model")
    if resolved_model is None:
        models = registry.list_models(resolved_provider)
        if not models:
            raise ModelUnavailableError(
                f"No models available for provider {resolved_provider!r} — check provider config",
                provider=resolved_provider,
                model=None,
            )
        resolved_model = models[0]["id"]

    def fn_factory(client, mdl: str):
        return lambda: complete_chat_messages(
            client,
            mdl,
            system=NL_CATALOG_FILTER_SYSTEM_PROMPT,
            messages=_normalize_nl_messages(messages),
            max_tokens=1024,
            temperature=0.0,
        )

    raw, _pid, _mid = dispatcher.call_with_fallback(
        operation="nl_filter",
        fn_factory=fn_factory,
        provider_id=resolved_provider,
        model=resolved_model,
        log_callback=log_callback,
    )
    return raw
