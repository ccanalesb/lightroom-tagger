# ADR-0009: One dispatcher for all provider/LLM calls

## Status
Accepted (2026-07). Point 3 amended (2026-09) — see *Amendment*.

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

## Amendment (2026-09): point 3 was never implemented, and is withdrawn

The escalation policies existed but nothing ever ran them. `FallbackDispatcher`
stored the injected `ErrorPolicy` and never called `on_escalation_error`; no
production caller constructed a policy or a `ConsecutiveAbortTracker`, and the
only references to either were their own unit tests. The TypeScript port carried
the whole arrangement over faithfully, dispatcher field included, so it inherited
a subsystem that this ADR vouched for and the code never reached.

What actually happened on a context-length error was three retries at the same
`max_tokens`, then a cascade to the next provider — never a token bump, never a
payload split, never a session blacklist.

`ContextLengthEscalationPolicy`, `VisionBatchErrorPolicy`, `NoOpErrorPolicy` and
`ConsecutiveAbortTracker` are therefore deleted rather than wired: wiring them
would be adding unproven behaviour to a migration, and the ladder they implement
has never been measured against a real provider. Points 1, 2 and 4 stand —
`callWithFallback` remains the single seam, and it still owns retry, cascade and
cooperative cancellation.

The error *classes* the policies switched on (`ContextLengthError`,
`PayloadTooLargeError`, `RateLimitError`, `InvalidRequestError`) are unaffected:
`vision-client.ts` still maps HTTP statuses onto them and the retry classifier
still reads them. If token escalation is wanted later, it belongs in the
dispatcher loop with a test that proves it fires — not in a policy object the
dispatcher holds and ignores.
