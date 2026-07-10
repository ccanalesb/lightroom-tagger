"""Shared helpers for vision comparator integration tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel


def fake_vision_registry(
    client: MagicMock,
    *,
    provider_id: str = "ollama",
    model: str = "vision-model",
    fallback_order: list[str] | None = None,
    models_by_provider: dict[str, list[dict]] | None = None,
) -> MagicMock:
    """Build a registry that routes dispatcher calls through *client*."""
    fallback_order = fallback_order or [provider_id]
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = {}
    registry.fallback_order = fallback_order
    if models_by_provider is None:
        models_by_provider = {
            pid: [{"id": model, "vision": True, "source": "config"}]
            for pid in fallback_order
        }

    def list_models(pid: str) -> list[dict]:
        return models_by_provider.get(pid, [])

    registry.list_models.side_effect = list_models
    registry.list_providers.return_value = [
        {"id": pid, "name": pid, "available": True}
        for pid in fallback_order
    ]
    registry.get_retry_config.return_value = {
        "max_retries": 0,
        "backoff_seconds": [],
        "respect_retry_after": False,
    }
    registry.get_client.return_value = client
    return registry


def fake_compare_client(
    *,
    provider_id: str = "ollama",
    compare_result: dict | None = None,
    batch_confidences: dict[int, float] | None = None,
    create_side_effect: Callable | None = None,
) -> MagicMock:
    """Single injected client for sequential and batch vision compares."""
    if compare_result is None:
        compare_result = {"confidence": 90, "verdict": "SAME", "reasoning": "test"}

    client = MagicMock()
    client._provider_id = provider_id

    def _create(**kwargs):
        if create_side_effect is not None:
            return create_side_effect(**kwargs)

        messages = kwargs.get("messages") or []
        content = ""
        if messages:
            first = messages[0]
            if isinstance(first, dict):
                content = str(first.get("content", ""))
            else:
                content = str(getattr(first, "content", ""))

        for message in messages:
            msg_content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
            if isinstance(msg_content, list):
                for part in msg_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        content += str(part.get("text", ""))

        response = MagicMock()
        choice = MagicMock()
        if "Candidates to compare" in content or "REQUIRED OUTPUT FORMAT" in content and batch_confidences is not None:
            results = [{"id": cid, "confidence": conf} for cid, conf in batch_confidences.items()]
            choice.message.content = json.dumps({"results": results})
        elif batch_confidences is not None and len(messages) > 1:
            results = [{"id": cid, "confidence": conf} for cid, conf in batch_confidences.items()]
            choice.message.content = json.dumps({"results": results})
        else:
            choice.message.content = json.dumps(
                {
                    "confidence": compare_result.get("confidence", 90),
                    "reasoning": compare_result.get("reasoning", "test"),
                }
            )
        response.choices = [choice]
        return response

    client.chat.completions.create.side_effect = _create
    return client


@contextmanager
def vision_compare_test_context(
    *,
    client: MagicMock | None = None,
    registry: MagicMock | None = None,
    provider_id: str = "ollama",
    model: str = "vision-model",
    compare_result: dict | None = None,
    patch_compression: bool = True,
    resolve_target: str = "lightroom_tagger.core.analyzer.vision_compare.resolve_model",
):
    """Patch resolve_model + image prep; inject one fake client via registry."""
    from contextlib import ExitStack

    client = client or fake_compare_client(
        provider_id=provider_id,
        compare_result=compare_result,
    )
    registry = registry or fake_vision_registry(client, provider_id=provider_id, model=model)

    patches = [
        patch(
            resolve_target,
            return_value=ResolvedModel(provider_id, model, registry),
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.get_viewable_path_managed",
            side_effect=lambda path: (path, False),
        ),
    ]
    if patch_compression:
        patches.append(
            patch(
                "lightroom_tagger.core.analyzer.vision_compare.compress_image",
                side_effect=lambda path: path,
            ),
        )

    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        stack.enter_context(patch("os.path.exists", return_value=True))
        stack.enter_context(
            patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"),
        )
        yield registry, client


@contextmanager
def matcher_vision_test_context(
    *,
    client: MagicMock | None = None,
    registry: MagicMock | None = None,
    provider_id: str = "ollama",
    model: str = "gemma3:27b",
    compare_result: dict | None = None,
    batch_confidences: dict[int, float] | None = None,
    create_side_effect: Callable | None = None,
):
    """Inject one fake client for matcher vision scoring integration tests."""
    client = client or fake_compare_client(
        provider_id=provider_id,
        compare_result=compare_result,
        batch_confidences=batch_confidences,
        create_side_effect=create_side_effect,
    )
    registry = registry or fake_vision_registry(client, provider_id=provider_id, model=model)

    with (
        patch(
            "lightroom_tagger.core.provider_resolution.resolve_model",
            return_value=ResolvedModel(provider_id, model, registry),
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.resolve_model",
            return_value=ResolvedModel(provider_id, model, registry),
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.get_viewable_path_managed",
            side_effect=lambda path: (path, False),
        ),
        patch(
            "lightroom_tagger.core.analyzer.vision_compare.compress_image",
            side_effect=lambda path: path,
        ),
        patch("os.path.exists", return_value=True),
        patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"),
    ):
        yield registry, client
