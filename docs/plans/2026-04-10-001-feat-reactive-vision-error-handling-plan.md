---
title: "feat: Reactive error handling for vision API pipeline"
type: feat
status: active
date: 2026-04-10
---

# Reactive Error Handling for Vision API Pipeline

## Overview

Make the vision matching pipeline reactive to provider-specific errors instead of treating all failures uniformly. Today, a Claude 4.5 extended thinking error kills the entire job because it's misclassified as non-retryable. A 413 payload error wastes the batch attempt because batch_size is ignored when building API requests. The fix is to detect these error patterns at the boundary and let the existing retry/fallback machinery handle them.

## Problem Frame

When running vision matches against providers like GitHub Copilot (Claude 4.5 Sonnet):
1. **Batch API fails with 413** — all 50 candidates are sent in one call despite `vision_batch_size=5` in config. The `batch_size` parameter gates whether to use batching but never chunks the actual request.
2. **Sequential fallback fails with 400** — `max_tokens=256` is too small for Claude models with extended thinking. The model requires `max_tokens > thinking.budget_tokens`.
3. **Error misclassification** — the extended thinking error message (`thinking.budget_tokens`) doesn't match any detection patterns in `_map_openai_error`, so it becomes `InvalidRequestError` (not retryable, no fallback). Every single comparison fails silently.

These are not bugs in every model — Ollama/Gemma works fine with `max_tokens=256`. The fix must be **reactive**: detect specific failure patterns and adapt, without changing defaults for models that work.

## Requirements Trace

- R1. Extended thinking errors must be classified as retryable so retry/fallback can handle them
- R2. The batch API must respect `vision_batch_size` config by chunking requests
- R3. 413 errors must be classified as retryable (payload too large = try smaller)
- R4. `max_tokens` must adapt on retry when the error indicates the value is too small
- R5. Existing behavior for models that work (Ollama, Gemma, GPT-4) must not change
- R6. All error classification changes must have test coverage

## Scope Boundaries

- No new UI changes — the existing retry/fallback system handles recovery transparently
- No new config knobs — use existing `vision_batch_size` properly and detect errors reactively
- No changes to the FallbackDispatcher or retry_with_backoff core logic — only error classification and call-site adaptation
- No provider-specific config files or model databases

## Context & Research

### Relevant Code and Patterns

- `lightroom_tagger/core/provider_errors.py` — Error hierarchy with `RETRYABLE_ERRORS` / `NOT_RETRYABLE_ERRORS` frozensets
- `lightroom_tagger/core/vision_client.py` — `_map_openai_error()` maps SDK exceptions to our hierarchy; `compare_images()` with `max_tokens=256`; `compare_images_batch()` with `max_tokens=2048`
- `lightroom_tagger/core/retry.py` — `retry_with_backoff()` retries on `RETRYABLE_ERRORS`, aborts on `NOT_RETRYABLE_ERRORS`
- `lightroom_tagger/core/fallback.py` — `FallbackDispatcher.call_with_fallback()` cascades across providers on retryable failures
- `lightroom_tagger/core/matcher.py` — `score_candidates_with_vision()` calls batch API then falls back to sequential; `batch_size` parameter is never used to chunk requests
- `lightroom_tagger/core/analyzer.py` — `_compare_via_provider()` wraps `compare_images` with FallbackDispatcher
- `lightroom_tagger/core/config.py` — `vision_batch_size=20` (config.yaml has 5), `vision_batch_threshold=5`

### Existing Error Mapping (`_map_openai_error`)

| SDK Exception | Pattern Match | Mapped To |
|---|---|---|
| `openai.RateLimitError` | — | `RateLimitError` (retryable) |
| `openai.AuthenticationError` | — | `AuthenticationError` (not retryable) |
| `openai.BadRequestError` | "context length", "too many tokens", "maximum" | `ContextLengthError` (retryable) |
| `openai.BadRequestError` | (anything else) | `InvalidRequestError` (not retryable) |
| `openai.APIStatusError` 503 | — | `ModelUnavailableError` (retryable) |
| `openai.APIStatusError` (other) | — | `ProviderError` (not in either set) |

### Gap Analysis

| Error Pattern | Today's Classification | Correct Classification |
|---|---|---|
| `thinking.budget_tokens` (400) | `InvalidRequestError` → not retryable | Retryable with parameter adaptation |
| 413 Request Entity Too Large | `ProviderError` → not in retry/fallback sets | Retryable (reduce payload) |
| Base `ProviderError` | Not in either frozenset | Should be retryable (safe default) |

## Key Technical Decisions

- **New error type `PayloadTooLargeError`**: For 413 errors. Added to `RETRYABLE_ERRORS`. This lets the batch caller detect "split and retry" semantics vs generic retry.
- **Detect extended thinking at the boundary**: Add `"thinking.budget_tokens"` and `"budget_tokens"` to the pattern match in `_map_openai_error` → `ContextLengthError`. This is semantically correct: the model needs more token budget, same as context length exceeded.
- **Adaptive `max_tokens` in `compare_images`**: Accept an optional `max_tokens` parameter (default 256). On `ContextLengthError` retry, the retry-aware caller bumps it. The function itself stays stateless.
- **Chunk by `batch_size` in `matcher.py`**: Split `batch_candidates` into chunks of `batch_size` before calling `compare_images_batch`. Each chunk is an independent API call. On `PayloadTooLargeError`, halve the chunk size and retry that chunk.

## Open Questions

### Resolved During Planning

- **Should we add a model-specific config for max_tokens?** No — detect reactively from errors. Models that work with 256 keep 256. Models that need more get retried with a higher value.
- **Should base `ProviderError` be retryable?** No — keep it out of both sets. The specific subtypes carry the retry/no-retry policy. Unknown errors should surface, not retry silently.

### Deferred to Implementation

- Exact `max_tokens` escalation values (256 → 4096 → 16384) — tune based on what models actually need
- Whether `compare_images_batch` needs the same adaptive max_tokens — likely yes, but verify with actual 400 errors

## Implementation Units

- [ ] **Unit 1: Add `PayloadTooLargeError` and fix error classification**

**Goal:** Correctly classify 413 and extended thinking errors so retry/fallback can handle them.

**Requirements:** R1, R3, R6

**Dependencies:** None

**Files:**
- Modify: `lightroom_tagger/core/provider_errors.py`
- Modify: `lightroom_tagger/core/vision_client.py`
- Modify: `lightroom_tagger/core/test_provider_errors.py`
- Modify: `lightroom_tagger/core/test_vision_client.py`

**Approach:**
- Add `PayloadTooLargeError` to `provider_errors.py` and to `RETRYABLE_ERRORS`
- In `_map_openai_error`: detect 413 status → `PayloadTooLargeError`; detect `"thinking.budget_tokens"` or `"budget_tokens"` in BadRequestError message → `ContextLengthError`
- Add base `ProviderError` 413 detection in the `APIStatusError` branch

**Patterns to follow:**
- Existing error types in `provider_errors.py`
- Existing test patterns in `test_provider_errors.py` and `test_vision_client.py`

**Test scenarios:**
- Happy path: 413 APIStatusError maps to `PayloadTooLargeError`
- Happy path: BadRequestError with "thinking.budget_tokens" maps to `ContextLengthError`
- Happy path: BadRequestError with "budget_tokens" maps to `ContextLengthError`
- Edge case: BadRequestError with "maximum" still maps to `ContextLengthError` (no regression)
- Edge case: Generic BadRequestError still maps to `InvalidRequestError`
- Happy path: `PayloadTooLargeError` is in `RETRYABLE_ERRORS`

**Verification:**
- All existing tests pass
- New tests for 413 and extended thinking error patterns pass

---

- [ ] **Unit 2: Adaptive `max_tokens` in `compare_images`**

**Goal:** Allow `compare_images` to accept a configurable `max_tokens` so callers can escalate on `ContextLengthError`.

**Requirements:** R4, R5

**Dependencies:** Unit 1

**Files:**
- Modify: `lightroom_tagger/core/vision_client.py`
- Modify: `lightroom_tagger/core/analyzer.py`
- Modify: `lightroom_tagger/core/test_vision_client.py`

**Approach:**
- Add `max_tokens: int = 256` parameter to `compare_images()`
- Add `max_tokens: int = 4096` parameter to `compare_images_batch()`
- In `_compare_via_provider`, wrap the `fn_factory` to escalate `max_tokens` on `ContextLengthError` retry. Use a simple closure that tracks attempt count and bumps max_tokens (256 → 4096 → 16384)
- The `retry_with_backoff` already retries on `ContextLengthError` — the adaptation happens in the fn_factory closure before the next attempt

**Patterns to follow:**
- Existing `fn_factory` pattern in `_compare_via_provider` and `_describe_image_via_provider`

**Test scenarios:**
- Happy path: `compare_images` called with default `max_tokens=256` sends 256 to API
- Happy path: `compare_images` called with `max_tokens=4096` sends 4096 to API
- Edge case: `compare_images_batch` default sends 4096
- Integration: `_compare_via_provider` escalates max_tokens on ContextLengthError

**Verification:**
- Models that work with 256 tokens still get 256 (no unnecessary cost increase)
- Claude models that fail with 256 succeed on retry with 4096

---

- [ ] **Unit 3: Chunk batch requests by `batch_size`**

**Goal:** Split batch API calls into chunks respecting `vision_batch_size` config to avoid 413 errors.

**Requirements:** R2, R5

**Dependencies:** Unit 1

**Files:**
- Modify: `lightroom_tagger/core/matcher.py`
- Modify: `lightroom_tagger/core/test_matcher.py`

**Approach:**
- In `score_candidates_with_vision`, after preparing `batch_candidates`, split into chunks of `batch_size`
- Call `compare_images_batch` for each chunk, merging results into `batch_results`
- On `PayloadTooLargeError` for a chunk: halve the chunk size and retry that chunk only
- Log chunk progress: "Processing N candidates in M batches of K"

**Patterns to follow:**
- Existing batch/sequential fallback logic in `score_candidates_with_vision`
- Existing log_callback pattern for progress reporting

**Test scenarios:**
- Happy path: 50 candidates with batch_size=20 results in 3 API calls (20+20+10)
- Happy path: 10 candidates with batch_size=20 results in 1 API call
- Error path: `PayloadTooLargeError` on a chunk halves the chunk and retries
- Edge case: batch_size=1 falls through to sequential mode
- Integration: Results from multiple chunks are correctly merged

**Verification:**
- No single API call sends more than `batch_size` candidates
- Jobs that previously failed with 413 now complete successfully

---

- [ ] **Unit 4: Adaptive `max_tokens` in batch path**

**Goal:** Apply the same adaptive max_tokens escalation to the batch API path in `matcher.py`.

**Requirements:** R4, R5

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Modify: `lightroom_tagger/core/matcher.py`

**Approach:**
- When calling `compare_images_batch` per chunk, catch `ContextLengthError` and retry the chunk with escalated `max_tokens`
- Use the same escalation values as the sequential path (4096 → 8192 → 16384)
- If max_tokens escalation exhausts, fall back to sequential for that chunk (which has its own retry via FallbackDispatcher)

**Patterns to follow:**
- Existing RateLimitError handling and sequential fallback in `score_candidates_with_vision`

**Test scenarios:**
- Happy path: Batch call succeeds with default max_tokens
- Error path: ContextLengthError triggers retry with higher max_tokens
- Error path: All max_tokens escalations fail → falls back to sequential for that chunk
- Edge case: Only one chunk fails, others succeed — partial batch results preserved

**Verification:**
- Claude models that fail batch with default tokens succeed after escalation
- Ollama/Gemma batch calls are unaffected

## System-Wide Impact

- **Error propagation:** New error types flow through existing `retry_with_backoff` → `FallbackDispatcher` → job handler pipeline unchanged
- **State lifecycle risks:** None — all changes are stateless parameter adaptation at call time
- **API surface parity:** Both `compare_images` (sequential) and `compare_images_batch` get the same adaptive behavior
- **Unchanged invariants:** FallbackDispatcher, retry_with_backoff, job handlers, frontend — all unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| max_tokens escalation increases API cost for expensive models | Only escalates after failure; default stays at 256 for models that work |
| Chunking adds latency (N sequential batch calls instead of 1) | Existing behavior sends 1 call that fails; N smaller calls that succeed is strictly better |
| Some providers may have different 413 thresholds | Chunking + halving on 413 adapts dynamically |

## Sources & References

- Related plan: `docs/plans/2026-04-06-parallel-batch-vision-matching.md` (batch API implementation)
- Related plan: `docs/plans/2026-03-30-provider-registry.md` (error hierarchy, retry, fallback)
- Job logs: `737b06af-da17-45b2-bd1f-8a2bf76f908a` (413 + extended thinking failures)
