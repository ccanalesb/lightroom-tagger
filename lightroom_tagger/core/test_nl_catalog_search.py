"""Tests for :mod:`lightroom_tagger.core.nl_catalog_search`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.exceptions import ModelUnavailableError
from lightroom_tagger.core.nl_catalog_search import (
    run_nl_catalog_filter_llm,
    run_nl_catalog_filter_llm_multi_turn,
    run_tool_calling_search,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import ResolvedModel, resolve_model


def _fake_registry(
    *,
    defaults: dict | None = None,
    fallback_order: list[str] | None = None,
    models_by_provider: dict[str, list[dict]] | None = None,
) -> MagicMock:
    registry = MagicMock(spec=ProviderRegistry)
    registry.defaults = defaults or {}
    registry.fallback_order = fallback_order or []
    models_by_provider = models_by_provider or {}

    def list_models(provider_id: str) -> list[dict]:
        return models_by_provider.get(provider_id, [])

    registry.list_models.side_effect = list_models
    return registry


def test_run_nl_catalog_filter_llm_end_to_end() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "ollama", "model": "desc-model"}},
        fallback_order=["ollama"],
    )
    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = ('{"posted": false}', "ollama", "desc-model")

    with (
        patch(
            "lightroom_tagger.core.nl_catalog_search.resolve_model",
            return_value=ResolvedModel("ollama", "desc-model", registry),
        ),
        patch(
            "lightroom_tagger.core.nl_catalog_search.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
    ):
        raw = run_nl_catalog_filter_llm("unposted only", provider_id=None, model=None)

    assert raw == '{"posted": false}'
    mock_dispatcher.call_with_fallback.assert_called_once()
    call = mock_dispatcher.call_with_fallback.call_args
    assert call.kwargs["operation"] == "nl_filter"
    assert call.kwargs["provider_id"] == "ollama"
    assert call.kwargs["model"] == "desc-model"
    registry.get_client.assert_not_called()


def test_run_nl_catalog_filter_llm_multi_turn_end_to_end() -> None:
    registry = _fake_registry(
        defaults={"description": {"provider": "ollama", "model": "desc-model"}},
        fallback_order=["ollama"],
    )
    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = ('{"min_rating": 4}', "ollama", "desc-model")

    with (
        patch(
            "lightroom_tagger.core.nl_catalog_search.resolve_model",
            return_value=ResolvedModel("ollama", "desc-model", registry),
        ),
        patch(
            "lightroom_tagger.core.nl_catalog_search.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
    ):
        raw = run_nl_catalog_filter_llm_multi_turn(
            [{"role": "user", "content": "four stars or better"}],
        )

    assert raw == '{"min_rating": 4}'
    mock_dispatcher.call_with_fallback.assert_called_once()
    call = mock_dispatcher.call_with_fallback.call_args
    assert call.kwargs["operation"] == "nl_filter"
    assert call.kwargs["provider_id"] == "ollama"
    assert call.kwargs["model"] == "desc-model"


def test_nl_filter_honors_description_vision_model_env(monkeypatch) -> None:
    """NL filter must use resolve_model so DESCRIPTION_VISION_MODEL env is honoured."""
    monkeypatch.setenv("DESCRIPTION_VISION_MODEL", "env-desc-model")

    registry = _fake_registry(
        defaults={"description": {"provider": "ollama", "model": "json-default"}},
        fallback_order=["ollama"],
    )
    mock_dispatcher = MagicMock()
    mock_dispatcher.call_with_fallback.return_value = ("{}", "ollama", "env-desc-model")

    with (
        patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry",
            return_value=registry,
        ),
        patch(
            "lightroom_tagger.core.nl_catalog_search.resolve_model",
            wraps=resolve_model,
        ),
        patch(
            "lightroom_tagger.core.nl_catalog_search.FallbackDispatcher",
            return_value=mock_dispatcher,
        ),
    ):
        run_nl_catalog_filter_llm("test", provider_id="ollama", model=None)

    assert mock_dispatcher.call_with_fallback.call_args.kwargs["model"] == "env-desc-model"


def test_run_tool_calling_search_end_to_end(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))

    registry = _fake_registry(
        defaults={"description": {"provider": "ollama", "model": "tool-model"}},
        fallback_order=["ollama"],
    )
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.tool_calls = None
    mock_message.content = "Found 3 matching photos."
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=mock_message),
    ]
    registry.get_client.return_value = mock_client

    with patch(
        "lightroom_tagger.core.nl_catalog_search.resolve_model",
        return_value=ResolvedModel("ollama", "tool-model", registry),
    ):
        text, updated = run_tool_calling_search(
            [{"role": "user", "content": "show sunsets"}],
            db=conn,
        )

    assert text == "Found 3 matching photos."
    assert updated[-1] == {"role": "assistant", "content": "Found 3 matching photos."}
    registry.get_client.assert_called_once_with("ollama")
    create_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == "tool-model"


def test_run_tool_calling_search_honors_vision_model_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VISION_MODEL", "env-vision-model")

    conn = init_database(str(tmp_path / "library.db"))
    registry = _fake_registry(
        defaults={"description": {"provider": "ollama", "model": "json-default"}},
        fallback_order=["ollama"],
    )
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.tool_calls = None
    mock_message.content = "done"
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=mock_message),
    ]
    registry.get_client.return_value = mock_client

    with (
        patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry",
            return_value=registry,
        ),
        patch(
            "lightroom_tagger.core.nl_catalog_search.resolve_model",
            wraps=resolve_model,
        ),
    ):
        run_tool_calling_search(
            [{"role": "user", "content": "cats"}],
            db=conn,
            provider_id="ollama",
            model=None,
        )

    assert mock_client.chat.completions.create.call_args.kwargs["model"] == "env-vision-model"


def test_run_nl_catalog_filter_llm_no_provider_raises() -> None:
    registry = _fake_registry(defaults={}, fallback_order=[])
    with (
        patch(
            "lightroom_tagger.core.provider_resolution.ProviderRegistry",
            return_value=registry,
        ),
        patch(
            "lightroom_tagger.core.nl_catalog_search.resolve_model",
            wraps=resolve_model,
        ),
    ):
        with pytest.raises(ModelUnavailableError, match="No provider"):
            run_nl_catalog_filter_llm("test", provider_id=None, model=None)
