"""Dispatcher integration tests for batch vision compare path."""

from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.error_policy import (
    BATCH_MAX_TOKENS_ESCALATION,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.exceptions import ContextLengthError, PayloadTooLargeError, RateLimitError
from lightroom_tagger.core.matcher.vision_batch import _call_batch_chunk


def _mock_registry(available_providers=None):
    if available_providers is None:
        available_providers = ["ollama", "nvidia_nim"]

    registry = MagicMock()
    registry.fallback_order = available_providers
    registry.list_providers.return_value = [
        {"id": pid, "name": pid, "available": True} for pid in available_providers
    ]
    registry.get_retry_config.return_value = {
        "max_retries": 0,
        "backoff_seconds": [],
        "respect_retry_after": False,
    }
    registry.list_models.side_effect = lambda pid: (
        [{"id": "gemma3:27b", "vision": True, "source": "config"}]
        if pid == "ollama"
        else [{"id": "nim-vision", "vision": True, "source": "config"}]
    )

    def get_client(pid):
        client = MagicMock()
        client._provider_id = pid
        return client

    registry.get_client.side_effect = get_client
    return registry


class TestBatchVisionDispatcherFallback:
    @patch("time.sleep")
    def test_primary_fails_fallback_succeeds(self, mock_sleep):
        registry = _mock_registry()
        chunk = [(0, "/tmp/a.jpg"), (1, "/tmp/b.jpg")]
        providers_seen: list[str] = []

        def mock_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
            providers_seen.append(getattr(client, "_provider_id", "unknown"))
            if getattr(client, "_provider_id", None) == "ollama":
                raise RateLimitError("429")
            return {cid: 85.0 for cid, _ in cands}

        with patch(
            "lightroom_tagger.core.vision_client.compare_images_batch",
            side_effect=mock_batch,
        ):
            result = _call_batch_chunk(
                registry,
                "ollama",
                "gemma3:27b",
                "/tmp/ref.jpg",
                chunk,
                None,
                "insta.jpg",
                1,
                1,
            )

        assert result == {0: 85.0, 1: 85.0}
        assert providers_seen == ["ollama", "nvidia_nim"]

    @patch("time.sleep")
    def test_payload_too_large_splits_and_succeeds(self, mock_sleep):
        registry = _mock_registry(["ollama"])
        chunk = [(0, "/tmp/a.jpg"), (1, "/tmp/b.jpg"), (2, "/tmp/c.jpg"), (3, "/tmp/d.jpg")]
        call_sizes: list[int] = []

        def mock_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
            call_sizes.append(len(cands))
            if len(cands) > 2:
                raise PayloadTooLargeError("413 payload too large")
            return {cid: 70.0 for cid, _ in cands}

        with patch(
            "lightroom_tagger.core.vision_client.compare_images_batch",
            side_effect=mock_batch,
        ):
            result = _call_batch_chunk(
                registry,
                "ollama",
                "gemma3:27b",
                "/tmp/ref.jpg",
                chunk,
                None,
                "insta.jpg",
                1,
                1,
            )

        assert result == {0: 70.0, 1: 70.0, 2: 70.0, 3: 70.0}
        assert call_sizes == [4, 2, 2]

    @patch("time.sleep")
    def test_context_length_escalates_tokens_via_policy(self, mock_sleep):
        registry = _mock_registry(["ollama"])
        chunk = [(0, "/tmp/a.jpg")]
        tokens_seen: list[int] = []
        attempts = {"n": 0}

        def mock_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
            tokens_seen.append(max_tokens)
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise ContextLengthError("budget too low")
            return {cid: 90.0 for cid, _ in cands}

        with patch(
            "lightroom_tagger.core.vision_client.compare_images_batch",
            side_effect=mock_batch,
        ):
            result = _call_batch_chunk(
                registry,
                "ollama",
                "gemma3:27b",
                "/tmp/ref.jpg",
                chunk,
                None,
                "insta.jpg",
                1,
                1,
                error_policy=VisionBatchErrorPolicy(),
            )

        assert result == {0: 90.0}
        assert tokens_seen[0] == BATCH_MAX_TOKENS_ESCALATION[0]
        assert tokens_seen[1] == BATCH_MAX_TOKENS_ESCALATION[1]
