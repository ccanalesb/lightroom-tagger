"""Unit tests for :class:`lightroom_tagger.core.vision_comparator.VisionComparator`."""

from unittest.mock import MagicMock, patch

import openai as openai_sdk
import pytest

from lightroom_tagger.core.error_policy import (
    BATCH_MAX_TOKENS_ESCALATION,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.exceptions import ContextLengthError, PayloadTooLargeError
from lightroom_tagger.core.retry import CancelledRetryError
from lightroom_tagger.core.test_vision_helpers import fake_compare_client, fake_vision_registry
from lightroom_tagger.core.vision_comparator import VisionComparator


class TestVisionComparatorBatch:
    @patch("time.sleep")
    def test_primary_fails_fallback_succeeds(self, mock_sleep):
        providers_seen: list[str] = []

        def make_client(pid):
            client = MagicMock()
            client._provider_id = pid

            def _create(**_kwargs):
                providers_seen.append(pid)
                if pid == "ollama":
                    raise openai_sdk.RateLimitError("429", response=MagicMock(), body=None)
                return _batch_response({0: 85.0, 1: 85.0})

            client.chat.completions.create.side_effect = _create
            return client

        registry = fake_vision_registry(
            make_client("ollama"),
            provider_id="ollama",
            model="gemma3:27b",
            fallback_order=["ollama", "nvidia_nim"],
            models_by_provider={
                "ollama": [{"id": "gemma3:27b", "vision": True, "source": "config"}],
                "nvidia_nim": [{"id": "nim-vision", "vision": True, "source": "config"}],
            },
        )
        registry.get_client.side_effect = make_client

        comparator = VisionComparator(registry)
        chunk = [(0, "/tmp/a.jpg"), (1, "/tmp/b.jpg")]
        with patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"):
            result = comparator.compare_batch(
                "/tmp/ref.jpg",
                chunk,
                "ollama",
                "gemma3:27b",
            )

        assert result == {0: 85.0, 1: 85.0}
        assert providers_seen == ["ollama", "nvidia_nim"]

    @patch("time.sleep")
    def test_payload_too_large_splits_and_succeeds(self, mock_sleep):
        call_sizes: list[int] = []

        def mock_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
            call_sizes.append(len(cands))
            if len(cands) > 2:
                raise PayloadTooLargeError("413 payload too large")
            return {cid: 70.0 for cid, _ in cands}

        client = fake_compare_client(provider_id="ollama")
        registry = fake_vision_registry(client, provider_id="ollama", model="gemma3:27b")
        comparator = VisionComparator(registry)
        chunk = [(0, "/tmp/a.jpg"), (1, "/tmp/b.jpg"), (2, "/tmp/c.jpg"), (3, "/tmp/d.jpg")]

        with (
            patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"),
            patch(
                "lightroom_tagger.core.vision_comparator.compare_images_batch",
                side_effect=mock_batch,
            ),
        ):
            result = comparator.compare_batch("/tmp/ref.jpg", chunk, "ollama", "gemma3:27b")

        assert result == {0: 70.0, 1: 70.0, 2: 70.0, 3: 70.0}
        assert call_sizes == [4, 2, 2]

    @patch("time.sleep")
    def test_context_length_escalates_tokens_via_policy(self, mock_sleep):
        tokens_seen: list[int] = []
        attempts = {"n": 0}

        def mock_batch(client, model, ref, cands, log_callback=None, max_tokens=4096):
            tokens_seen.append(max_tokens)
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise ContextLengthError("budget too low")
            return {cid: 90.0 for cid, _ in cands}

        client = fake_compare_client(provider_id="ollama")
        registry = fake_vision_registry(client, provider_id="ollama", model="gemma3:27b")
        comparator = VisionComparator(registry, batch_policy=VisionBatchErrorPolicy())
        chunk = [(0, "/tmp/a.jpg")]

        with (
            patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"),
            patch(
                "lightroom_tagger.core.vision_comparator.compare_images_batch",
                side_effect=mock_batch,
            ),
        ):
            result = comparator.compare_batch("/tmp/ref.jpg", chunk, "ollama", "gemma3:27b")

        assert result == {0: 90.0}
        assert tokens_seen[0] == BATCH_MAX_TOKENS_ESCALATION[0]
        assert tokens_seen[1] == BATCH_MAX_TOKENS_ESCALATION[1]


class TestVisionComparatorSequential:
    @patch("time.sleep")
    def test_cancel_mid_backoff_short_circuits(self, mock_sleep):
        flag = {"cancel": False}
        registry = fake_vision_registry(
            fake_compare_client(provider_id="ollama"),
            provider_id="ollama",
            model="gemma3:27b",
        )
        registry.get_retry_config.return_value = {
            "max_retries": 2,
            "backoff_seconds": [5],
            "respect_retry_after": False,
        }

        def _create(**_kwargs):
            flag["cancel"] = True
            raise openai_sdk.RateLimitError("429", response=MagicMock(), body=None)

        registry.get_client.return_value.chat.completions.create.side_effect = _create
        comparator = VisionComparator(registry, cancel_check=lambda: flag["cancel"])

        with patch("lightroom_tagger.core.vision_client._encode_image", return_value="abc"):
            with pytest.raises(CancelledRetryError):
                comparator.compare_pair("/tmp/a.jpg", "/tmp/b.jpg", "ollama", "gemma3:27b")


def _batch_response(confidences: dict[int, float]):
    import json

    results = [{"id": cid, "confidence": conf} for cid, conf in confidences.items()]
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = json.dumps({"results": results})
    response.choices = [choice]
    return response
