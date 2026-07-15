import os
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import openai as openai_sdk
import pytest

from lightroom_tagger.core.exceptions import (
    AuthenticationError,
    ConnectionError,
    ContextLengthError,
    InvalidRequestError,
    ModelUnavailableError,
    PayloadTooLargeError,
    RateLimitError,
    TimeoutError,
)
from lightroom_tagger.core.vision_client import compare_images, generate_description
from lightroom_tagger.core.vision_client_ollama import (
    content_to_native as _ollama_content_to_native,
)
from lightroom_tagger.core.vision_client_ollama import (
    native_chat_url as _ollama_native_chat_url,
)


def _make_mock_client(response_text: str):
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = response_text
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


def _make_temp_image():
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.write(fd, b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")
    os.close(fd)
    return path


@pytest.fixture()
def temp_image():
    path = _make_temp_image()
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestCompareImages:
    def test_should_parse_json_confidence_response(self, temp_image):
        client = _make_mock_client('{"confidence": 85, "reasoning": "same scene"}')
        result = compare_images(client, "test-model", temp_image, temp_image)
        assert result["confidence"] == 85
        assert result["verdict"] == "SAME"
        assert result["reasoning"] == "same scene"

    def test_should_parse_low_confidence_as_different(self, temp_image):
        client = _make_mock_client('{"confidence": 15, "reasoning": "different scenes"}')
        result = compare_images(client, "test-model", temp_image, temp_image)
        assert result["verdict"] == "DIFFERENT"

    def test_should_parse_uncertain_range(self, temp_image):
        client = _make_mock_client('{"confidence": 50, "reasoning": "unclear"}')
        result = compare_images(client, "test-model", temp_image, temp_image)
        assert result["verdict"] == "UNCERTAIN"

    def test_should_send_two_images_in_message(self, temp_image):
        client = _make_mock_client('{"confidence": 90, "reasoning": "same"}')
        compare_images(client, "test-model", temp_image, temp_image)
        call_args = client.chat.completions.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        image_parts = [p for p in content if p.get("type") == "image_url"]
        assert len(image_parts) == 2

    def test_should_use_provided_model(self, temp_image):
        client = _make_mock_client('{"confidence": 90, "reasoning": "same"}')
        compare_images(client, "my-custom-model", temp_image, temp_image)
        call_args = client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "my-custom-model"

    def test_should_use_default_max_tokens(self, temp_image):
        client = _make_mock_client('{"confidence": 90, "reasoning": "same"}')
        compare_images(client, "test-model", temp_image, temp_image)
        call_args = client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 256

    def test_should_use_custom_max_tokens(self, temp_image):
        client = _make_mock_client('{"confidence": 90, "reasoning": "same"}')
        compare_images(client, "test-model", temp_image, temp_image, max_tokens=4096)
        call_args = client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 4096

    def test_should_invoke_log_callback(self, temp_image):
        client = _make_mock_client('{"confidence": 90, "reasoning": "same"}')
        log = MagicMock()
        compare_images(client, "test-model", temp_image, temp_image, log_callback=log)
        log.assert_called()


class TestGenerateDescription:
    def test_should_return_raw_text(self, temp_image):
        client = _make_mock_client('{"summary": "A landscape photo"}')
        result = generate_description(client, "test-model", temp_image)
        assert "landscape" in result

    def test_should_send_one_image_in_message(self, temp_image):
        client = _make_mock_client("some description text")
        generate_description(client, "test-model", temp_image)
        call_args = client.chat.completions.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        image_parts = [p for p in content if p.get("type") == "image_url"]
        assert len(image_parts) == 1

    def test_should_use_description_prompt(self, temp_image):
        client = _make_mock_client("ok")
        generate_description(client, "test-model", temp_image)
        call_args = client.chat.completions.create.call_args
        content = call_args.kwargs["messages"][0]["content"]
        text_parts = [p for p in content if p.get("type") == "text"]
        assert len(text_parts) == 1
        assert "photo editor" in text_parts[0]["text"]


class TestOllamaNativeHelpers:
    def test_native_url_strips_v1_suffix(self):
        assert (
            _ollama_native_chat_url("http://localhost:11434/v1")
            == "http://localhost:11434/api/chat"
        )

    def test_native_url_strips_trailing_slash(self):
        assert (
            _ollama_native_chat_url("http://localhost:11434/v1/")
            == "http://localhost:11434/api/chat"
        )

    def test_native_url_preserves_path_prefix(self):
        assert (
            _ollama_native_chat_url("http://host:1234/proxy/v1")
            == "http://host:1234/proxy/api/chat"
        )

    def test_content_splits_text_and_base64_images(self):
        content = [
            {"type": "text", "text": "describe this"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
        ]
        text, images = _ollama_content_to_native(content)
        assert text == "describe this"
        assert images == ["QUJD"]

    def test_content_handles_plain_string(self):
        assert _ollama_content_to_native("hello") == ("hello", [])

    def test_content_collects_multiple_images(self):
        content = [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAA"}},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,BBB"}},
        ]
        _, images = _ollama_content_to_native(content)
        assert images == ["AAA", "BBB"]


def _ok_native_response(content: str):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"message": {"content": content}}
    return resp


class TestOllamaNativeRouting:
    def _ollama_client(self):
        client = MagicMock()
        client._provider_id = "ollama"
        client.base_url = "http://localhost:11434/v1"
        client.timeout = 120.0
        return client

    def test_routes_to_native_api_chat_with_thinking_disabled(self, temp_image):
        client = self._ollama_client()
        with patch(
            "lightroom_tagger.core.vision_client_ollama.httpx.post",
            return_value=_ok_native_response('{"summary": "x"}'),
        ) as post:
            out = generate_description(client, "kimi-k2.6:cloud", temp_image)

        assert out == '{"summary": "x"}'
        # Native path must NOT touch the OpenAI-compat surface.
        client.chat.completions.create.assert_not_called()

        url = post.call_args.args[0] if post.call_args.args else post.call_args.kwargs["url"]
        assert url == "http://localhost:11434/api/chat"
        payload = post.call_args.kwargs["json"]
        assert payload["think"] is False
        assert payload["stream"] is False
        assert payload["model"] == "kimi-k2.6:cloud"
        assert payload["options"]["num_predict"] == 2048
        msg = payload["messages"][0]
        assert len(msg["images"]) == 1
        assert "photo editor" in msg["content"]

    def test_non_ollama_client_uses_openai_sdk(self, temp_image):
        client = _make_mock_client('{"summary": "y"}')
        client._provider_id = "openai"
        with patch("lightroom_tagger.core.vision_client_ollama.httpx.post") as post:
            out = generate_description(client, "gpt-4o", temp_image)
        assert '"summary"' in out
        client.chat.completions.create.assert_called_once()
        post.assert_not_called()

    def test_native_connection_error_maps_to_connection_error(self, temp_image):
        client = self._ollama_client()
        with patch(
            "lightroom_tagger.core.vision_client_ollama.httpx.post",
            side_effect=httpx.ConnectError("refused"),
        ):
            with pytest.raises(ConnectionError):
                generate_description(client, "kimi-k2.6:cloud", temp_image)

    def test_native_timeout_maps_to_timeout_error(self, temp_image):
        client = self._ollama_client()
        with patch(
            "lightroom_tagger.core.vision_client_ollama.httpx.post",
            side_effect=httpx.ReadTimeout("slow"),
        ):
            with pytest.raises(TimeoutError):
                generate_description(client, "kimi-k2.6:cloud", temp_image)

    def test_native_non_json_body_maps_to_provider_error(self, temp_image):
        client = self._ollama_client()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.side_effect = ValueError("Expecting value: line 1 column 1")
        with patch("lightroom_tagger.core.vision_client_ollama.httpx.post", return_value=resp):
            with pytest.raises(Exception) as exc_info:
                generate_description(client, "kimi-k2.6:cloud", temp_image)
        assert "non-JSON" in str(exc_info.value)

    def test_native_error_field_raises_provider_error(self, temp_image):
        client = self._ollama_client()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"error": "model not found"}
        with patch("lightroom_tagger.core.vision_client_ollama.httpx.post", return_value=resp):
            with pytest.raises(Exception) as exc_info:
                generate_description(client, "missing:model", temp_image)
        assert "model not found" in str(exc_info.value)


class TestErrorMapping:
    def _make_api_error(self, error_cls, status_code):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.headers = {}
        return error_cls("err", response=mock_response, body=None)

    def test_should_map_rate_limit_error(self, temp_image):
        client = MagicMock()
        client.chat.completions.create.side_effect = self._make_api_error(
            openai_sdk.RateLimitError, 429
        )
        with pytest.raises(RateLimitError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_auth_error(self, temp_image):
        client = MagicMock()
        client.chat.completions.create.side_effect = self._make_api_error(
            openai_sdk.AuthenticationError, 401
        )
        with pytest.raises(AuthenticationError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_bad_request_error(self, temp_image):
        client = MagicMock()
        client.chat.completions.create.side_effect = self._make_api_error(
            openai_sdk.BadRequestError, 400
        )
        with pytest.raises(InvalidRequestError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_timeout_error(self, temp_image):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai_sdk.APITimeoutError(
            request=MagicMock()
        )
        with pytest.raises(TimeoutError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_connection_error(self, temp_image):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai_sdk.APIConnectionError(
            request=MagicMock()
        )
        with pytest.raises(ConnectionError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_503_to_model_unavailable(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.headers = {}
        client.chat.completions.create.side_effect = openai_sdk.APIStatusError(
            "overloaded", response=mock_response, body=None
        )
        with pytest.raises(ModelUnavailableError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_extract_retry_after_header(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "30"}
        client.chat.completions.create.side_effect = openai_sdk.RateLimitError(
            "rate limited", response=mock_response, body=None
        )
        with pytest.raises(RateLimitError) as exc_info:
            compare_images(client, "m", temp_image, temp_image)
        assert exc_info.value.retry_after == 30.0

    def test_should_map_413_to_payload_too_large(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 413
        mock_response.headers = {}
        client.chat.completions.create.side_effect = openai_sdk.APIStatusError(
            "Request Entity Too Large", response=mock_response, body=None
        )
        with pytest.raises(PayloadTooLargeError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_thinking_budget_tokens_to_context_length(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        client.chat.completions.create.side_effect = openai_sdk.BadRequestError(
            "`max_tokens` must be greater than `thinking.budget_tokens`",
            response=mock_response,
            body=None,
        )
        with pytest.raises(ContextLengthError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_map_budget_tokens_to_context_length(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        client.chat.completions.create.side_effect = openai_sdk.BadRequestError(
            "budget_tokens exceeds max_tokens",
            response=mock_response,
            body=None,
        )
        with pytest.raises(ContextLengthError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_still_map_context_length_patterns(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        client.chat.completions.create.side_effect = openai_sdk.BadRequestError(
            "maximum context length exceeded",
            response=mock_response,
            body=None,
        )
        with pytest.raises(ContextLengthError):
            compare_images(client, "m", temp_image, temp_image)

    def test_should_still_map_generic_bad_request_to_invalid(self, temp_image):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        client.chat.completions.create.side_effect = openai_sdk.BadRequestError(
            "invalid model name",
            response=mock_response,
            body=None,
        )
        with pytest.raises(InvalidRequestError):
            compare_images(client, "m", temp_image, temp_image)
