"""Vision operation engine — single-call provider primitive and persist stage."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from lightroom_tagger.core.error_policy import ConsecutiveAbortTracker, ErrorPolicy
from lightroom_tagger.core.fallback import FallbackDispatcher
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.provider_resolution import Kind, resolve_model

LogCallback = Callable[[str, str], None] | None


@dataclass(frozen=True)
class VisionOpOutcome:
    status: Literal['written', 'skipped', 'failed']
    reason: str | None = None

    @property
    def wrote(self) -> bool:
        return self.status == 'written'


@dataclass
class VisionOpSpec:
    """Single vision-op invocation: resolve → fallback dispatch → parse."""

    resolve_kind: Kind
    operation: str
    provider_id: str | None
    model: str | None
    fn_factory: Callable[[], Callable]
    # Parsers take either ``(raw)`` or ``(raw, provider, model)`` — the extra
    # provider/model are supplied for ops (e.g. scoring) whose parser needs the
    # actual fallback-selected provider to build an LLM repair fixer.
    parse_response: Callable[..., Any]
    log_callback: LogCallback = None
    registry: ProviderRegistry | None = None
    error_policy: ErrorPolicy | None = None
    abort_tracker: ConsecutiveAbortTracker | None = None
    _cleanup: Callable[[], None] | None = field(default=None, repr=False)


def _parser_wants_provider_model(parse_response: Callable[..., Any]) -> bool:
    """True when *parse_response* accepts the ``(raw, provider, model)`` form.

    Determined by the parser's signature (positional params or ``*args``) rather
    than catching ``TypeError``, so a genuine ``TypeError`` raised *inside* the
    parser is never silently swallowed and re-dispatched with the wrong arity.
    """
    try:
        params = inspect.signature(parse_response).parameters.values()
    except (TypeError, ValueError):
        return False
    positional = [
        p for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    has_var_positional = any(p.kind is p.VAR_POSITIONAL for p in params)
    return has_var_positional or len(positional) >= 3


def run_vision_op(spec: VisionOpSpec) -> tuple[Any, str, str]:
    """Run one vision op: resolve_model → FallbackDispatcher → parse."""
    if spec.registry is None:
        resolved = resolve_model(
            kind=spec.resolve_kind,
            provider_id=spec.provider_id,
            model=spec.model,
        )
        registry = resolved.registry
        provider_id = resolved.provider_id
        model = resolved.model
    else:
        registry = spec.registry
        provider_id = spec.provider_id
        model = spec.model

    dispatcher = FallbackDispatcher(registry, error_policy=spec.error_policy)
    try:
        dispatcher_fn_factory = spec.fn_factory()
        raw, actual_provider, actual_model = dispatcher.call_with_fallback(
            operation=spec.operation,
            fn_factory=dispatcher_fn_factory,
            provider_id=provider_id,
            model=model,
            log_callback=spec.log_callback,
            abort_tracker=spec.abort_tracker,
        )
        if _parser_wants_provider_model(spec.parse_response):
            parsed = spec.parse_response(raw, actual_provider, actual_model)
        else:
            parsed = spec.parse_response(raw)
        return parsed, actual_provider, actual_model
    finally:
        if spec._cleanup is not None:
            spec._cleanup()


def run_vision_op_persist(
    spec: VisionOpSpec,
    *,
    pre_check: Callable[[], VisionOpOutcome | None] | None = None,
    accept_result: Callable[[Any], bool],
    persist: Callable[[Any, str, str], None],
) -> VisionOpOutcome:
    """Pre-checks → core → persist; returns outcome without swallowing exceptions."""
    if pre_check is not None:
        early = pre_check()
        if early is not None:
            return early

    parsed, provider, model = run_vision_op(spec)
    if not accept_result(parsed):
        return VisionOpOutcome(status='skipped', reason='invalid result')
    persist(parsed, provider, model)
    return VisionOpOutcome(status='written')
