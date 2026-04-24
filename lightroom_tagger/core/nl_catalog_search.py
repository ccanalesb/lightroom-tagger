"""LLM runner for natural-language → structured catalog filter JSON (text-only)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable

from lightroom_tagger.core.fallback import FallbackDispatcher
from lightroom_tagger.core.provider_errors import ModelUnavailableError
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.search_tools import ALL_TOOLS, execute_tool
from lightroom_tagger.core.vision_client import complete_chat_messages, complete_chat_text

LogCallback = Callable[[str, str], None] | None

_NL_CATALOG_FILTER_SYSTEM_PROMPT_TEMPLATE = """You are a filter translator for a Lightroom photo catalog search API.
Return only a single JSON object with no markdown fences and no text before or after the JSON.

The object may use only these field names (omit any you do not need; use null only where a field is explicitly unused — prefer omitting keys):
posted, month, min_rating, date_from, date_to, score_perspective, min_score, sort_by_score, sort_by_date, description_search, dominant_colors, mood_tags.

Do not include any other keys. Field meanings:
- posted: boolean, filter images marked posted/unposted to Instagram
- month: YYYYmm string
- date_from, date_to: date strings as needed
- min_rating: integer star rating filter (1–5)
- min_score: integer 1–10; always pair with score_perspective when used
- score_perspective: one of the available scoring perspectives — VALID VALUES: {score_perspective_slugs}; pick the closest match to the user's intent (e.g. "street" for street photography, "documentary" for reportage)
- sort_by_score: "asc" or "desc" (requires score_perspective)
- sort_by_date: "newest" or "oldest"
- description_search: free-text search on AI-generated image descriptions — use this for ANY query about visual content, subjects, scenes, actions, gestures, objects, mood, colour names, or composition
- dominant_colors: JSON array of hex color codes (e.g. ["#ff0000","#c62828"]) extracted from images — ONLY use when the user provides an explicit hex code; do NOT use for color names like "red" or "blue" since the DB stores hex values, not names
- mood_tags: JSON array of mood strings (e.g. ["melancholic","energetic"]) — only use when the user explicitly mentions mood

IMPORTANT: When the user asks about what is visually in photos (people, objects, actions, scenes, lighting, colours by name, etc.) always use description_search, not dominant_colors.
"""


def build_nl_catalog_filter_prompt(score_perspective_slugs: list[str] | None = None) -> str:
    """Build the system prompt with real perspective slugs so the LLM never invents one."""
    slugs = score_perspective_slugs or []
    slug_str = ", ".join(f'"{s}"' for s in slugs) if slugs else "(none available — omit score_perspective)"
    return _NL_CATALOG_FILTER_SYSTEM_PROMPT_TEMPLATE.format(score_perspective_slugs=slug_str)


# Backward-compat alias used by tests and any code that imported this directly
NL_CATALOG_FILTER_SYSTEM_PROMPT = build_nl_catalog_filter_prompt()


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
    score_perspective_slugs: list[str] | None = None,
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

    system_prompt = build_nl_catalog_filter_prompt(score_perspective_slugs)

    def fn_factory(client, mdl: str):
        return lambda: complete_chat_text(
            client,
            mdl,
            system=system_prompt,
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
    score_perspective_slugs: list[str] | None = None,
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

    system_prompt = build_nl_catalog_filter_prompt(score_perspective_slugs)

    def fn_factory(client, mdl: str):
        return lambda: complete_chat_messages(
            client,
            mdl,
            system=system_prompt,
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


def _messages_for_openai_tool_loop(messages: list[dict]) -> list[dict]:
    """Build an OpenAI Chat Completions message list with tool turns preserved."""
    out: list[dict] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role_raw = str(m.get("role", "")).strip().lower()
        if role_raw == "system":
            c = m.get("content")
            if c is not None and str(c).strip():
                out.append({"role": "system", "content": str(c)})
            continue
        if role_raw == "user":
            content = m.get("content", "")
            if not str(content).strip():
                continue
            out.append({"role": "user", "content": str(content)})
            continue
        if role_raw == "assistant":
            item: dict = {"role": "assistant"}
            if m.get("content") is not None:
                item["content"] = m.get("content")
            tcs = m.get("tool_calls")
            if tcs:
                item["tool_calls"] = tcs
            if "content" not in item and not tcs:
                continue
            if "content" not in item and tcs is not None:
                item["content"] = None
            out.append(item)
            continue
        if role_raw == "tool":
            tcid = m.get("tool_call_id")
            if not tcid:
                continue
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tcid),
                    "content": m.get("content", "") if m.get("content") is not None else "",
                }
            )
    return out


def run_tool_calling_search(
    messages: list[dict],
    *,
    provider_id: str | None = None,
    model: str | None = None,
    db: sqlite3.Connection,
    log_callback: LogCallback = None,
    max_tool_rounds: int = 5,
) -> tuple[str, list[dict]]:
    """Run multi-turn tool-calling search loop.

    Returns (assistant_text, updated_messages_with_tool_turns).
    The returned messages list includes tool_call and tool_result turns
    so the frontend can persist them for multi-turn continuity.
    """
    registry = ProviderRegistry()
    desc_defaults = registry.defaults.get("description", {}) or {}
    resolved_provider = provider_id or desc_defaults.get("provider")
    if not resolved_provider:
        raise ModelUnavailableError(
            "No provider configured for tool-calling search",
            provider=None,
            model=None,
        )
    resolved_model = model or desc_defaults.get("model")
    if not resolved_model:
        models = registry.list_models(resolved_provider)
        if not models:
            raise ModelUnavailableError(
                f"No models for provider {resolved_provider!r}",
                provider=resolved_provider,
                model=None,
            )
        resolved_model = models[0]["id"]

    client = registry.get_client(resolved_provider)
    conv = _messages_for_openai_tool_loop(messages)
    if not any(m.get("role") == "user" for m in conv):
        raise ValueError("tool-calling search requires at least one user message")
    updated_messages: list[dict] = list(messages)

    for _round in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=resolved_model,
            messages=conv,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            text = (msg.content or "") if msg.content is not None else ""
            updated_messages.append({"role": "assistant", "content": text})
            return text, updated_messages

        tool_calls_payload = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments or ""},
            }
            for tc in msg.tool_calls
        ]
        asst_tool = {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": tool_calls_payload,
        }
        conv.append(asst_tool)
        updated_messages.append(asst_tool)

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            result = execute_tool(tc.function.name, args, db)
            result_str = json.dumps(result)

            tool_msg = {"role": "tool", "tool_call_id": tc.id, "content": result_str}
            conv.append(tool_msg)
            updated_messages.append(tool_msg)

            if log_callback:
                log_callback("tool_result", f"{tc.function.name}: {result_str[:200]}")

    return "", updated_messages
