"""Unit tests for compare_descriptions_batch (text-only batch comparison)."""

from unittest.mock import MagicMock

from lightroom_tagger.core.vision_client import compare_descriptions_batch


def _make_mock_client(response_text: str):
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = response_text
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client


def test_compare_descriptions_batch_empty_candidates_returns_empty_dict():
    client = _make_mock_client("{}")
    result = compare_descriptions_batch(client, "gpt-4o", "ref", [])
    assert result == {}
    assert len(result) == 0
    client.chat.completions.create.assert_not_called()


def test_compare_descriptions_batch_valid_parse_maps_confidence():
    client = _make_mock_client(
        '{"results": [{"id": 0, "confidence": 75}, {"id": 1, "confidence": 40}]}'
    )
    result = compare_descriptions_batch(
        client, "gpt-4o", "ref", [(0, "a"), (1, "b")]
    )
    assert result == {0: 75.0, 1: 40.0}


def test_compare_descriptions_batch_parse_failure_returns_all_zeros():
    client = _make_mock_client("not json")
    result = compare_descriptions_batch(
        client, "gpt-4o", "ref", [(0, "a"), (1, "b")]
    )
    assert result == {0: 0.0, 1: 0.0}


def test_compare_descriptions_batch_claude_sets_extra_body_reasoning_effort():
    client = _make_mock_client(
        '{"results": [{"id": 0, "confidence": 50}]}'
    )
    compare_descriptions_batch(
        client,
        "claude-sonnet-4-20250514",
        "ref text",
        [(0, "cand")],
    )
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs.get("extra_body") == {"reasoning_effort": "none"}
