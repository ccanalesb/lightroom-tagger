"""Per-perspective scoring vision operation."""

from __future__ import annotations

import contextlib
import functools
import os
from typing import Any

from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.structured_output import parse_score_response_with_retry
from lightroom_tagger.core.vision_client import (
    complete_chat_text,
    generate_description,
    make_score_json_llm_fixer,
)

from .image_prep import compress_image, get_viewable_path_managed


def parse_score_vision_response(
    raw: str,
    provider: str,
    model: str,
    *,
    registry: ProviderRegistry | None = None,
    log_callback=None,
) -> tuple[Any, bool]:
    """Parse score model output with optional LLM JSON repair."""
    reg = registry or ProviderRegistry()
    client = reg.get_client(provider)

    def _log_repair(msg: str) -> None:
        if log_callback is not None:
            log_callback("info", msg)

    llm_fixer = make_score_json_llm_fixer(
        functools.partial(complete_chat_text, client, model),
    )
    return parse_score_response_with_retry(
        raw,
        llm_fixer=llm_fixer,
        log_repair=_log_repair,
    )


def build_score_op_spec(
    path: str,
    *,
    user_prompt: str,
    provider_id: str | None = None,
    model: str | None = None,
    log_callback=None,
    silent_compression: bool = False,
    registry: ProviderRegistry | None = None,
):
    """Build a :class:`VisionOpSpec` for the scoring vision operation."""
    from lightroom_tagger.core.vision_op import VisionOpSpec

    temp_files: list[str] = []

    def prepare_fn_factory():
        viewable, viewable_is_temp = get_viewable_path_managed(path)
        if viewable_is_temp:
            temp_files.append(viewable)

        if silent_compression:
            compressed = viewable
        else:
            compressed = compress_image(viewable)
            if compressed != viewable:
                temp_files.append(compressed)

        def fn_factory(client, mdl):
            return lambda: generate_description(
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

    def parse_response(raw: str, provider: str, model: str):
        return parse_score_vision_response(
            raw,
            provider,
            model,
            registry=registry,
            log_callback=log_callback,
        )

    return VisionOpSpec(
        resolve_kind="description",
        operation="score",
        provider_id=provider_id,
        model=model,
        fn_factory=prepare_fn_factory,
        parse_response=parse_response,
        log_callback=log_callback,
        registry=registry,
        _cleanup=cleanup,
    )
