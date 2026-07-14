# ADR-0014: One vision-op-and-persist engine

## Status
Accepted (2026-07)

## Context
ADR-0007 unified provider/model *selection* (`resolve_model`) and ADR-0009 sealed
provider/LLM *calls* (`FallbackDispatcher.call_with_fallback` with `vision_client`
helpers inside `fn_factory`). Description, scoring, and vision-compare paths still
duplicated the same three-step orchestration at every call site:

1. `resolve_model(kind, …)`
2. `FallbackDispatcher(…).call_with_fallback(…)`
3. parse the raw response (often with provider/model-aware repair)

Each site re-wired `fn_factory`, error policy, logging, and persistence differently.
`describe_image` was a thin alias that obscured which layer owned orchestration vs
persistence. Parent initiative: one vision-op-and-persist engine (issue #139).

## Decision
1. **Single-call core** — `lightroom_tagger.core.vision_op.run_vision_op(spec)` is the
   only supported place for `resolve_model → FallbackDispatcher → parse`. Callers
   supply a `VisionOpSpec` (resolve kind, operation label, `fn_factory`, parser,
   optional `error_policy` / `abort_tracker`).
2. **Persist stage** — `run_vision_op_persist(spec, pre_check, accept_result, persist)`
   wraps the core with optional skip checks, result validation, and DB writes. Returns
   a uniform `VisionOpOutcome` (`written` | `skipped` | `failed`).
3. **Op definitions live in `analyzer`** — concrete specs are built by
   `build_description_op_spec`, `build_score_op_spec`, `build_compare_op_spec`, and
   `build_compare_batch_op_spec` (image prep + `fn_factory` + parser per operation).
   Services (`description_service`, `scoring_service`) and `VisionComparator` only
   assemble specs and call the engine.
4. **`describe_image` removed** — description flows use `build_description_op_spec` +
   `run_vision_op` / `run_vision_op_persist` directly.
5. **Error policy stays pluggable** on `VisionOpSpec` / `FallbackDispatcher` (issue
   #81); the engine does not hard-code escalation.
6. **Explicit non-goals (remain outside the engine):**
   - `nl_catalog_search` — text-only NL filter translation and multi-turn tool loop
     (different scope; allow-listed in the orchestration guardrail).
   - Embedding generation (`embedding_service`, `clip_embedding_service`) — not
     vision-op multimodal calls.

A static guardrail (`test_vision_op_guardrail.py`) rejects inline
`resolve_model → FallbackDispatcher → call_with_fallback` orchestration outside the
engine module (additive to ADR-0009's raw-SDK guardrail).

## Consequences
- One place to audit vision orchestration; new vision features add an op-spec builder
  + service wiring instead of copying dispatch boilerplate.
- Uniform `VisionOpOutcome` for batch workers and telemetry (written vs skipped vs
  failed) across description and scoring.
- `VisionComparator` becomes a thin facade over `run_vision_op` with compare op-specs.
- Slight indirection via `VisionOpSpec` dataclass; acceptable for a single seam.
- `nl_catalog_search` and embedding paths stay as-is until a separate initiative
  addresses them.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Return-contract only** — unify parsed return shapes without a shared orchestrator | Leaves duplicated resolve/dispatch/parse wiring; guardrail cannot enforce a seam. |
| **Compat shim** — keep `describe_image` as a permanent wrapper | Hides the engine boundary; two ways to run the same op. |
| **Whole-op core** — engine owns image prep, batching, and matcher loops | Too much scope; prep and batch strategy differ per caller; engine stays single-call. |
| **Pull NL catalog search into the engine** | Text-only + tool-loop semantics differ from one-shot vision ops; would bloat the engine and conflate ADR-0009 text paths with multimodal vision. |
