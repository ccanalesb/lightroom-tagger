# Phase 10: MATCH-02 Quantitative Benchmark — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `10-CONTEXT.md` — this log preserves the alternatives considered and the scope-shift conversation that reframed the phase mid-discussion.

**Date:** 2026-04-29 → 2026-04-30
**Phase:** 10-match-02-quantitative-benchmark
**Areas presented (initial):** Baseline methodology · Dataset scope · `clip_top_k` sweep + recall floor · Code location + report format · Decision rule when ≥10× isn't met
**Areas discussed (after descope):** Phase scope (descope decision) · Dataset (Claude's discretion) · `clip_top_k` sweep · Recall threshold · Report/REQUIREMENTS update (Claude's discretion)

---

## Phase scope reframing

Mid-discussion (after Q2.1), the user asked "what is this? why this is even something?" and "i don't care about metric, why are we doing this?". This triggered a fundamental scope review. Claude offered three paths:

| Option | Description | Selected |
|--------|-------------|----------|
| Cancel Phase 10 entirely | Drop the ≥10× claim from REQUIREMENTS.md, close `benchmark-embedding-recall.md` as "won't do" | |
| Slim Phase 10 to recall-only | Skip cost-reduction baseline; recall safety check only (~50 lines, read-only) | ✓ |
| Run the full benchmark as scoped | Cost reduction + recall + sensitivity sweep | |

**User's choice:** "Slim Phase 10 to recall-only."
**Notes:** The cost-reduction (≥10×) claim is vanity; the user-value question is "does the prefilter silently hide true matches?". The descope keeps the recall safety check, drops everything else.

This descope **invalidated all 5 questions answered in Area 1 (Baseline methodology)** below. Those answers are preserved as a record of the conversation but DO NOT apply to the actual phase work. CONTEXT.md reflects only the post-descope decisions.

---

## Area 1 — Baseline methodology *(SUPERSEDED — descoped after this area completed)*

### Q1.1 — Which baseline strategy to measure "without prefilter" LLM-call counts?

| Option | Description | Selected |
|--------|-------------|----------|
| `clip_top_k=500` | Run with the upper clamp on existing prefilter code; cheapest path | ✓ |
| Temporary `--prefilter=off` toggle | Cleanest comparison, invasive throwaway code | |
| Pre-Phase-8 commit on a worktree | Most authentic baseline, most setup | |
| You decide | | |

**User's choice:** `clip_top_k=500` *(superseded by descope)*

### Q1.2 — DB isolation: how to keep baseline and prefilter-on runs comparable without polluting real data?

| Option | Description | Selected |
|--------|-------------|----------|
| Copy library DB to benchmark DB | Cleanest, leaves live DB untouched | ✓ |
| Live DB with `force_reprocess=True` | Simpler, but rewrites real `matches` rows | |
| Live DB constrained to a small time slice | Compromise | |
| You decide | | |

**User's choice:** Copy library DB *(superseded by descope — recall check is read-only, no isolation needed)*

### Q1.3 — Edge case: `clip_top_k=500` is the hard cap. What if benchmark rows have date windows with >500 candidates?

| Option | Description | Selected |
|--------|-------------|----------|
| Spot-check first | Cheap insurance | |
| Bump `KNN_K_MAX` to 10_000 temporarily | Lets us measure true uncapped baseline | |
| Filter benchmark set to <500-candidate rows | Clean comparison, accept selection bias | ✓ |
| Switch baseline to `--prefilter=off` toggle | Abandon clip_top_k=500 path | |
| Combine spot-check + bump cap | | |
| You decide | | |

**User's choice:** Filter benchmark set to <500-candidate rows *(superseded by descope — no cap concern at clip_top_k=50)*

### Q1.4 — Provider/model pinning for the benchmark runs?

| Option | Description | Selected |
|--------|-------------|----------|
| Pin to current default | Cheapest | |
| Pin to a fast/cheap model explicitly | Minimizes wall-clock + cost | |
| Don't pin, just record per run | Call count is the metric | |
| You decide | Claude picks fast local model, records what was used | ✓ |

**User's exchange:** Asked "why does this matter?". Claude explained: barely matters for the metric (call counts are model-independent), matters for benchmark wall-clock cost and report fidelity. User responded "yes" to "lock as Claude's discretion: pick fast local model + record what was used".
**User's choice:** Claude's discretion *(superseded by descope — no LLM calls fire in the recall check)*

### Q1.5 — What counts as "LLM calls" in the reduction ratio?

| Option | Description | Selected |
|--------|-------------|----------|
| `vision_judgments_total` only | Existing instrumentation, ratio is identical anyway | ✓ |
| Vision + description calls combined | More honest absolute number, ~10 lines new code | |
| Report both side-by-side | Most thorough | |
| You decide | | |

**User's choice:** `vision_judgments_total` only *(superseded by descope — no judgment counting)*

---

## Scope reset — user asked "what is this? why this is even something?"

After Area 1 closed and Area 2 (dataset scope) was opened, the user pushed back on the entire premise. Claude reframed: "this phase exists because the auditor flagged it, not because it solves user pain". Three paths offered (see top of log). User selected the recall-only slim path.

After the descope, the remaining gray areas reduced to:
1. Dataset scope
2. `clip_top_k` sweep
3. Recall threshold
4. REQUIREMENTS.md update wording
5. Output artifact + script location

User opted to lock 1, 4, 5 as Claude's discretion and discuss only 2 and 3.

---

## Locked as Claude's discretion (post-descope)

### Dataset scope
**Decision:** All user-validated pairs with IG-side CLIP embeddings. Build missing IG embeddings via existing `batch_embed_image image_type='catalog_and_instagram'` first. Skip pairs whose IG file is missing on disk (record "skipped" in report, distinct from "miss").

### REQUIREMENTS.md update
**Decision:** Replace MATCH-02 wording. Drop the unmeasured "≥10× LLM-call reduction" claim entirely. Keep the recall-preservation half, populated with the measured number, link to `10-RECALL.md`. Update traceability table to `Complete` once the recall result is recorded.

### Output artifact + script location
**Decision:** Runner script `lightroom_tagger/scripts/benchmark_clip_recall.py` (matches existing one-shot CLI pattern). Report `.planning/phases/10-match-02-quantitative-benchmark/10-RECALL.md`. Per-pair raw data `.planning/phases/10-match-02-quantitative-benchmark/10-recall-data.csv`.

---

## Q2 (post-descope) — `clip_top_k` sweep values?

| Option | Description | Selected |
|--------|-------------|----------|
| Just 50 | Answers "is the shipped default safe?" only | ✓ |
| 25 / 50 | Also checks if a tighter default would be safer | |
| 50 / 100 / 200 | Standard sweep; finds the recall floor if 50 fails | |
| Adaptive: 50 first, sweep upward only if it fails | Single safe-or-not answer with safety margin | |
| You decide | | |

**User's choice:** Just 50.
**Notes:** Single question — is the shipped default safe? No commitment to a sweep.

---

## Q3 (post-descope) — Recall threshold for "pass"?

| Option | Description | Selected |
|--------|-------------|----------|
| 100% | Any miss = broken, ship-blocking | |
| 99% | Todo's number, accepts ≤1% as background noise | |
| 95% | Pragmatic, prefilter cost win outweighs occasional miss | |
| No threshold — just report the number | User decides shipping action after | ✓ |
| You decide | | |

**User's choice:** No pre-committed threshold; report the number.
**Notes:** Smart minimal commitment. The miss table is the actionable output regardless of threshold.

---

## Claude's Discretion (full list captured in CONTEXT.md)

- Provider/model for the prerequisite IG-embed job (use existing `batch_embed_image` defaults — CLIP encoder is `clip-ViT-B-32`, deterministic).
- Whether to also write a `metadata.json` for machine-readable consumption (skip unless trivial).
- Wall-clock instrumentation in the runner (nice-to-have).
- Exact filename / no screenshot of recall summary required.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>`. Headline items:
- Cost-reduction (≥10×) benchmark — descoped 2026-04-29; may resurface under LLM-cost pressure.
- `clip_top_k` sensitivity sweep — only if recall fails at 50.
- DINOv2 / CLIP / SigLIP A/B — out of scope per ROADMAP, separate phase.
- Cosine similarity threshold tuning — superseded by top-k tuning in Phase 8.
- MATCH-03 wider-search fallback — only if recall report shows shortlist-empty cases are common.
