# Phase 10: MATCH-02 Quantitative Benchmark — Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

> **Scope shift during discussion (2026-04-29):** The phase was renamed-in-spirit from "quantitative benchmark" to "recall-only safety check". The cost-reduction (≥10×) baseline is dropped per user decision; only the recall safety check is retained. The phase directory and roadmap entry still use the original name `match-02-quantitative-benchmark`. Downstream agents: read the boundary below, not the phase title.

<domain>
## Phase Boundary

**What this phase delivers:** A read-only recall safety check that verifies the shipped `clip_top_k=50` CLIP cosine prefilter does not silently hide user-validated true-positive matches.

**Concretely:**
- For every user-validated `(insta_key, catalog_key)` pair (`matches WHERE validated_at IS NOT NULL`) with an IG-side CLIP embedding available, run `shortlist_catalog_candidates_by_clip(db, insta_key, candidate_keys, top_k=50)` over the same date-windowed representative-only candidate set the matcher uses, and tally whether the validated `catalog_key` is in the returned shortlist.
- Build IG-side CLIP embeddings via the existing `batch_embed_image` job (`image_type='catalog_and_instagram'`) before running the recall sweep.
- Produce a markdown report (`10-RECALL.md`) with the measured recall percentage, miss list, and per-pair CSV (`10-recall-data.csv`) for traceability.
- Update REQUIREMENTS.md MATCH-02 to drop the unmeasured "≥10× LLM-call reduction" claim and replace it with the measured recall number, linking to `10-RECALL.md`.
- Move `.planning/todos/pending/benchmark-embedding-recall.md` → `.planning/todos/done/` with a link to the report.

**What this phase does NOT do (descoped 2026-04-29):**
- No cost-reduction baseline run (no `clip_top_k=500` baseline, no library DB copy, no `vision_match` job invocations, no LLM calls).
- No sensitivity sweep across `clip_top_k` values (50 only).
- No pre-committed recall pass/fail threshold (report the number, decide shipping action after).
- No embedding model A/B (DINOv2 / SigLIP) — out of scope per ROADMAP, separate follow-up.
- No FAISS migration, no MATCH-03 wider-search fallback, no new prefilter parameters.

**Why this descope:** User decision on 2026-04-29 — the ≥10× cost claim is vanity; the only real-user-value question is whether the prefilter silently hides true matches. The recall check answers that question with ~50 lines of read-only Python and produces a defensible REQUIREMENTS.md update.

</domain>

<decisions>
## Implementation Decisions

### Scope & deliverables
- **D-01:** Phase scope is **recall-only**. No cost-reduction baseline. The runner does not invoke `vision_match`, makes no LLM calls, and does not write to the library DB.
- **D-02:** Single deliverable triplet — runner script, markdown report, per-pair CSV — plus a REQUIREMENTS.md edit and a todo file move.

### Dataset
- **D-03:** Benchmark set = **all user-validated pairs with IG-side CLIP embeddings available after the prerequisite embed run**. Source: `SELECT catalog_key, insta_key FROM matches WHERE validated_at IS NOT NULL`.
- **D-04:** Prerequisite step: run `batch_embed_image image_type='catalog_and_instagram'` once before the recall sweep so missing IG embeddings get populated. Wait for completion before invoking the recall script.
- **D-05:** Pairs whose IG row has no embedding after the prerequisite run (e.g., file missing on disk, image unreadable) are reported as **skipped**, not as misses. Report shows `total_validated, embedded, skipped_no_embedding, hits, misses`.

### Measurement
- **D-06:** Test only `clip_top_k=50` (the current shipped default). No sweep.
- **D-07:** No pre-committed pass/fail threshold. Report the number; user decides shipping action after.
- **D-08:** For each pair, the candidate set fed to the shortlist must match the matcher's actual production candidate set: 90-day date-window (`find_candidates_by_date(db, dump_media, days_before=90)`) → drop rejected pairs (`get_rejected_pairs`) → representative-only filter (`catalog_key_is_primary_grid_row`). Reuse the existing functions; do not duplicate the candidate-construction logic.
- **D-09:** A "hit" means the validated `catalog_key` is present in the shortlist returned by `shortlist_catalog_candidates_by_clip`. A "miss" means the validated key was in the candidate set (passed all filters) but the CLIP shortlist truncated it. Pairs whose validated `catalog_key` is filtered out *before* the shortlist (e.g., it's not a representative because of stack changes since validation) are reported as **filtered_out**, not misses — these are not the prefilter's fault.

### Artifacts & locations
- **D-10:** Runner: `lightroom_tagger/scripts/benchmark_clip_recall.py`. Pattern follows `match_instagram_dump.py` — invokable as `python -m lightroom_tagger.scripts.benchmark_clip_recall --db library.db [--out-dir .planning/phases/10-...]`. Read-only over library DB.
- **D-11:** Report: `.planning/phases/10-match-02-quantitative-benchmark/10-RECALL.md` — markdown with: header counts, recall %, miss table (per-pair: insta_key, validated catalog_key, shortlist size, date-window size, why-missed-if-known), filter-funnel table (total validated → embedded → tested → hits/misses).
- **D-12:** Per-pair CSV: `.planning/phases/10-match-02-quantitative-benchmark/10-recall-data.csv` — columns: `insta_key, validated_catalog_key, date_window_size, candidates_after_filters, shortlist_size, shortlist_includes_validated, status` where `status` ∈ `{hit, miss, filtered_out, skipped_no_embedding}`.

### Documentation updates
- **D-13:** REQUIREMENTS.md MATCH-02 rewrite: drop the "≥10× LLM-call reduction" wording (unmeasured, not pursued), keep the recall-preservation half populated with the measured number, link to `10-RECALL.md`. Update traceability table for MATCH-02 to `Complete` once the recall result is recorded.
- **D-14:** Move `.planning/todos/pending/benchmark-embedding-recall.md` → `.planning/todos/done/benchmark-embedding-recall.md` with a closing line linking to `10-RECALL.md`. Note in the closing line: "Recall measurement only — cost-reduction benchmark and DINOv2/CLIP/SigLIP A/B comparison are deferred follow-ups."

### Claude's Discretion
- Exact provider/model used for the prerequisite IG embedding build (use whatever the existing `batch_embed_image` job defaults to — CLIP encoder is sentence-transformers `clip-ViT-B-32`, deterministic, no provider choice).
- Exact filename for screenshot of the recall summary (none required — the markdown numbers are sufficient).
- Whether to also write the recall % into a `metadata.json` for machine-readable consumption (skip unless trivial).
- Wall-clock instrumentation in the runner (nice-to-have, not required for the report).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` — Phase 10 entry under "v3.0 Intelligent Discovery" (gap closure scope, success criteria — note: the success criteria there assume the original cost-benchmark scope; this CONTEXT.md narrows it to recall-only)
- `.planning/REQUIREMENTS.md` — current MATCH-02 wording (line 41) that this phase rewrites; traceability table that flips MATCH-02 to Complete on phase close
- `.planning/v3.0-MILESTONE-AUDIT.md` — origin of this phase as a gap closure item; documents the "MATCH-02 quantitative claim unmeasured" finding

### Prior phase context
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-CONTEXT.md` — D-01..D-08 locked decisions: the prefilter implementation this phase verifies. Specifically: D-02 (`clip_top_k=50` default), D-03 (shortlist gates phash+desc+vision), D-07 (per-batch summary log shape)
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-VERIFICATION.md` — Phase 8 verification verdict that flagged the unmeasured ≥10× as the only deferred item
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-VALIDATION.md` §"Manual-Only Verifications" — the original manual benchmark instructions; this phase replaces those with a scripted recall check

### Inputs being closed
- `.planning/todos/pending/benchmark-embedding-recall.md` — the open todo this phase closes; note that the original todo proposed DINOv2/CLIP/SigLIP A/B comparison and cosine-threshold tuning, both of which are explicitly NOT done in this phase (deferred follow-ups)

### Codebase touchpoints
- `lightroom_tagger/core/clip_similarity.py` — `shortlist_catalog_candidates_by_clip` is the function under test; `KNN_K_MAX=500`; `NoClipEmbeddingError` raised when seed has no CLIP row (the runner must catch this for the skipped-no-embedding bucket)
- `lightroom_tagger/scripts/match_instagram_dump.py` — production candidate construction (`find_candidates_by_date` → rejected-pairs filter → `catalog_key_is_primary_grid_row` representative-only filter). The runner reuses these exact steps so its candidate set matches the live matcher's.
- `lightroom_tagger/core/database.py` — `matches` table (`validated_at` is the truth-set filter), `image_clip_embeddings` table (where IG embeddings land after the prerequisite job), `catalog_key_is_primary_grid_row` (representative filter)
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_embed_image` accepts `image_type='catalog_and_instagram'` (Phase 8 D-01); the runner does NOT invoke this directly — operator runs it as a job before invoking the recall script
- `apps/visualizer/frontend/src/services/api.ts` — `JobsAPI.create('batch_embed_image', { image_type: 'catalog_and_instagram' })` is the operator path to populate IG embeddings

### Codebase maps
- `.planning/codebase/CONVENTIONS.md` — coding/test/style conventions (Python: Black 100-col, Ruff, mypy strict for new code)
- `.planning/codebase/STRUCTURE.md` — `lightroom_tagger/scripts/` is the right home for one-shot CLI tools

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shortlist_catalog_candidates_by_clip(db, insta_media_key, candidate_keys, top_k)` in `clip_similarity.py` — the exact function the runner calls per pair. Signature is already perfect for benchmark use.
- `find_candidates_by_date(db, dump_media, days_before=90)` in `core/matcher.py` — production candidate query. Use as-is.
- `get_rejected_pairs(db)` + `catalog_key_is_primary_grid_row(db, key)` in `core/database.py` — the post-filters the matcher applies in `match_dump_media` lines 155–166. Reuse.
- `init_database(args.db)` opens the library DB read-only-ish; safe for the runner.
- `image_clip_embeddings` table is sqlite-vec-backed and already populated for catalog rows; the prerequisite step extends it to IG rows.

### Established Patterns
- One-shot scripts under `lightroom_tagger/scripts/` use `argparse`, accept `--db`, return non-zero exit on error. Mirror `match_instagram_dump.py` structure.
- Reports for the planning system live under `.planning/phases/<N>-.../` and are markdown-first.
- CSV alongside markdown is the standard pairing for "audit trail" data (see Phase 7/8 patterns).

### Integration Points
- The runner is operator-invoked, not job-system-invoked. No new `JOB_HANDLERS` entry, no API surface, no UI. Single-purpose CLI utility.
- The prerequisite IG-embed step IS the existing job system path — operator clicks "Build catalog cache" or runs `batch_embed_image` with `image_type='catalog_and_instagram'`. Phase 10 documents how to invoke it; doesn't ship new job code.

</code_context>

<specifics>
## Specific Ideas

- **The runner is read-only.** No writes to library DB, no `matches` mutations, no `apply_instagram_match_to_stack_members`, no LLM calls, no `vision_match` invocation. Pure read + compute + report.
- **Reuse production candidate query, do not duplicate.** Whatever `match_dump_media` does to build `candidates`, the runner does too. Extracting that into a shared helper is acceptable as a side-product (improves match_dump_media testability), but only if it stays trivial.
- **The miss list matters more than the headline number.** If recall=98% with 2 misses, the miss table tells the operator *which* IG/catalog pairs the prefilter would have hidden — that's the actionable output. The headline % is just a summary.
- **`filtered_out` (validated key dropped by date-window or representative filter, not by shortlist) is its own bucket** so the report doesn't blame the prefilter for misses caused by stack changes or rejected-pair entries since the original validation.
- **The phase directory name `10-match-02-quantitative-benchmark` is now misleading.** Downstream agents should treat the boundary above as canonical and ignore the directory naming. Do not rename the directory mid-phase — it would break ROADMAP refs.

</specifics>

<deferred>
## Deferred Ideas

These came up during discussion but belong in other phases:

- **Cost-reduction (≥10×) benchmark** — the original Phase 10 scope. Descoped 2026-04-29 because: (a) the operational PASS from Phase 8 is sufficient, (b) the user is not paying-API-cost-sensitive enough to need the audit closure, (c) the recall safety check delivers the only real-user-value answer. May resurface if a future milestone hits LLM-cost pressure.
- **`clip_top_k` sensitivity sweep** (25 / 100 / 200) — descoped to the single shipped default. Add later if recall is broken at 50 and we need to find the recovering floor.
- **Cosine similarity threshold tuning** (the original `benchmark-embedding-recall.md` todo's primary goal) — superseded by top-k tuning in Phase 8; no per-similarity threshold exists in production code. Closed as "approach changed".
- **DINOv2 / CLIP / SigLIP A/B comparison** — the original todo's secondary goal. Out of scope per ROADMAP. Separate phase if a model swap is ever motivated.
- **MATCH-03 wider-search fallback** (was dropped 2026-04-27) — only re-introduce if the recall report shows shortlist-empty cases are common.
- **Backend restart and compression fix** (`.planning/todos/pending/2026-04-26-plan-backend-restart-and-compression-fix.md`) — orthogonal infrastructure work, not touched.
- **Embed-job discoverability and path failures** (`.planning/todos/pending/2026-04-26-fixes-for-embed-job-discoverability-and-path-failures.md`) — relevant nearby work, slated for Phase 11 deferred polish, not Phase 10.

</deferred>

---

*Phase: 10-match-02-quantitative-benchmark*
*Context gathered: 2026-04-30*
