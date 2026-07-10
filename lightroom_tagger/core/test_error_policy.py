"""Unit tests for pluggable ErrorPolicy escalation."""

import pytest

from lightroom_tagger.core.error_policy import (
    BATCH_MAX_TOKENS_ESCALATION,
    MAX_TOKENS_ESCALATION,
    ContextLengthEscalationPolicy,
    EscalationAction,
    NoOpErrorPolicy,
    VisionBatchErrorPolicy,
)
from lightroom_tagger.core.exceptions import ContextLengthError, PayloadTooLargeError, RateLimitError


class TestNoOpErrorPolicy:
    def test_should_always_retry_without_mutation(self):
        policy = NoOpErrorPolicy()
        state: dict = {}
        action = policy.on_escalation_error(
            ContextLengthError("too long"),
            provider_id="ollama",
            model="gemma",
            operation="describe",
            call_state=state,
        )
        assert action == EscalationAction.RETRY
        assert state == {}


class TestContextLengthEscalationPolicy:
    @pytest.fixture
    def policy(self):
        return ContextLengthEscalationPolicy()

    def test_should_start_at_first_ladder_rung(self, policy):
        assert policy.starting_index("ollama", "claude") == 0
        assert policy.max_tokens_at(0) == MAX_TOKENS_ESCALATION[0]

    def test_should_walk_ladder_on_context_length_errors(self, policy):
        provider_id, model = "ollama", "claude-thinking"
        state = {"token_index": policy.starting_index(provider_id, model)}

        for expected_idx in range(1, len(MAX_TOKENS_ESCALATION)):
            action = policy.on_escalation_error(
                ContextLengthError("budget too low"),
                provider_id=provider_id,
                model=model,
                operation="compare",
                call_state=state,
            )
            assert action == EscalationAction.RETRY
            assert state["token_index"] == expected_idx
            assert policy.max_tokens_at(state["token_index"]) == MAX_TOKENS_ESCALATION[expected_idx]

    def test_should_record_discovered_minimum_after_escalation(self, policy):
        provider_id, model = "nvidia_nim", "claude"
        state = {"token_index": 0}

        policy.on_escalation_error(
            ContextLengthError("budget too low"),
            provider_id=provider_id,
            model=model,
            operation="compare",
            call_state=state,
        )

        key = policy.provider_key(provider_id, model)
        assert policy.model_min_tokens[key] == MAX_TOKENS_ESCALATION[1]
        assert policy.starting_index(provider_id, model) == 1

    def test_should_skip_lower_rungs_when_minimum_cached(self, policy):
        provider_id, model = "ollama", "claude"
        key = policy.provider_key(provider_id, model)
        policy._model_min_tokens[key] = MAX_TOKENS_ESCALATION[2]

        assert policy.starting_index(provider_id, model) == 2

    def test_should_blacklist_after_ladder_exhausted(self, policy):
        provider_id, model = "openrouter", "claude-3"
        state = {"token_index": len(MAX_TOKENS_ESCALATION) - 1}

        action = policy.on_escalation_error(
            ContextLengthError("still too long"),
            provider_id=provider_id,
            model=model,
            operation="compare",
            call_state=state,
        )

        assert action == EscalationAction.GIVE_UP
        assert policy.is_broken(provider_id, model)
        assert policy.provider_key(provider_id, model) in policy.broken_provider_models

    def test_should_ignore_non_context_length_errors(self, policy):
        state = {"token_index": 0}
        action = policy.on_escalation_error(
            RateLimitError("429"),
            provider_id="ollama",
            model="gemma",
            operation="compare",
            call_state=state,
        )
        assert action == EscalationAction.RETRY
        assert state["token_index"] == 0
        assert policy.model_min_tokens == {}

    def test_should_emit_escalation_log_message(self, policy):
        state = {"token_index": 0}
        policy.on_escalation_error(
            ContextLengthError("budget"),
            provider_id="ollama",
            model="claude",
            operation="compare",
            call_state=state,
        )
        assert "Escalating max_tokens" in state["_log_message"]
        assert "4096" in state["_log_message"]

    def test_should_emit_blacklist_log_message_on_exhaustion(self, policy):
        state = {"token_index": len(MAX_TOKENS_ESCALATION) - 1}
        policy.on_escalation_error(
            ContextLengthError("budget"),
            provider_id="ollama",
            model="claude",
            operation="compare",
            call_state=state,
        )
        assert "blacklisting" in state["_log_message"]

    def test_full_error_sequence_walks_ladder_then_blacklists(self):
        """Feed a sequence of ContextLengthErrors through a pure policy object."""
        policy = ContextLengthEscalationPolicy()
        provider_id, model = "ollama", "thinking-model"
        state = {"token_index": policy.starting_index(provider_id, model)}

        actions = []
        for _ in range(len(MAX_TOKENS_ESCALATION)):
            action = policy.on_escalation_error(
                ContextLengthError("context"),
                provider_id=provider_id,
                model=model,
                operation="compare",
                call_state=state,
            )
            actions.append(action)

        assert actions[:-1] == [EscalationAction.RETRY] * (len(MAX_TOKENS_ESCALATION) - 1)
        assert actions[-1] == EscalationAction.GIVE_UP
        assert policy.is_broken(provider_id, model)
        key = policy.provider_key(provider_id, model)
        assert policy.model_min_tokens[key] == MAX_TOKENS_ESCALATION[-1]


class TestVisionBatchErrorPolicy:
    def test_should_split_payload_too_large_chunk(self):
        policy = VisionBatchErrorPolicy()
        state = {"candidates": [(0, "/a"), (1, "/b"), (2, "/c"), (3, "/d")]}

        action = policy.on_escalation_error(
            PayloadTooLargeError("413"),
            provider_id="ollama",
            model="gemma",
            operation="compare_batch",
            call_state=state,
        )

        assert action == EscalationAction.SPLIT
        assert state["_split_halves"] == ([(0, "/a"), (1, "/b")], [(2, "/c"), (3, "/d")])

    def test_should_give_up_on_single_item_payload_too_large(self):
        policy = VisionBatchErrorPolicy()
        state = {"candidates": [(0, "/a")]}

        action = policy.on_escalation_error(
            PayloadTooLargeError("413"),
            provider_id="ollama",
            model="gemma",
            operation="compare_batch",
            call_state=state,
        )

        assert action == EscalationAction.GIVE_UP

    def test_should_delegate_context_length_to_token_policy(self):
        policy = VisionBatchErrorPolicy()
        state = {"token_index": 0, "candidates": [(0, "/a")]}

        action = policy.on_escalation_error(
            ContextLengthError("budget"),
            provider_id="ollama",
            model="gemma",
            operation="compare_batch",
            call_state=state,
        )

        assert action == EscalationAction.RETRY
        assert state["token_index"] == 1
        assert policy.max_tokens_at(state["token_index"]) == BATCH_MAX_TOKENS_ESCALATION[1]
