# ADR-0009: One dispatcher for all provider/LLM calls

## Status
Accepted (2026-07)

## Context
Provider/LLM HTTP calls were scattered across scoring, description, vision compare,
NL search, and tool-calling paths. Each site reimplemented retry, fallback cascade,
and token/payload escalation differently. Model/provider *selection* was unified
in ADR-0007 (`provider_resolution.resolve_model`); the *call* side still leaked
raw `client.chat.completions.create` at orchestration sites and duplicated
escalation policy.

Parent initiative: one resilient dispatcher for all provider/LLM calls (issue #54).

## Decision
1. **All provider/LLM calls** go through `FallbackDispatcher.call_with_fallback`.
   Callers supply a `fn_factory(client, model)` that returns a zero-arg callable;
   the dispatcher owns retry, fallback cascade, and cooperative cancellation.
2. **No raw provider SDK calls** outside the seam: orchestration code must invoke
   typed helpers in `vision_client` / `vision_client_batch` (or future wrappers)
   inside `fn_factory` — never `client.chat.completions.create` (or equivalent)
   directly. A static guardrail test enforces this with an explicit allow-list.
3. **Escalation is pluggable policy**, not ad-hoc caller logic: token bumps,
   batch split, rate-limit abort, and broken-model skip live in `ErrorPolicy`
   implementations (`ContextLengthEscalationPolicy`, `VisionBatchErrorPolicy`, …)
   injected into the dispatcher. `VisionComparator` is the vision-compare facade
   over dispatcher + policy.
4. **Resolution and dispatch are paired seams**: ADR-0007 answers *which*
   `(provider_id, model)`; this ADR answers *how* the call is executed once
   resolved. Both must be used — no bypass around either.

Legitimate exceptions (allow-listed in the guardrail):
- `vision_client.py` / `vision_client_batch.py` — the HTTP wrapper layer.
- `provider_registry._probe_tool_calling` — one-shot capability probe, not a
  product call path.

## Consequences
- Uniform retry/fallback/escalation behaviour; policies are unit-testable in
  isolation.
- New LLM features add a `vision_client` helper + dispatcher wiring; the
  guardrail catches regressions.
- Slight indirection via `fn_factory`; acceptable for one place to audit calls.
- Tool-calling and multimodal paths share the same error-mapping and fallback
  story as text-only and vision paths.
