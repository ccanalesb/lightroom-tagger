# Phase 8: Embedding pre-filter & catalog cache pipeline — Research

**Researched:** 2026-04-27  
**Domain:** `vision_match` CLIP shortlist, `batch_embed_image` Instagram extension, catalog cache job chain, Processing UI DRY (`AdvancedOptions`)  
**Confidence:** HIGH (integration points and contracts verified in source; chain handler choice is a design recommendation consistent with existing `JobRunner` / `cancel_scope` patterns)

<user_constraints>
## User Constraints (from 08-CONTEXT.md + 08-UI-SPEC.md)

### Locked decisions (verbatim)
- **D-01:** Extend `batch_embed_image` to also process `image_type='instagram'` rows. Instagram CLIP vectors live in `image_clip_embeddings` alongside catalog vectors, keyed by `image_type` + `image_key`. Matching reads pre-computed IG embeddings from the DB; no inline embed during `vision_match`.
- **D-02:** Pre-filter top-k default = 50. Exposed as a numeric UI override on the matching tab so the value can be tuned per run without redeploy.
- **D-03:** The CLIP cosine shortlist gates the entire scoring stack — phash, description, and the final visual LLM judgment all run only on the shortlist.
- **D-04:** `CatalogCacheTab` exposes one composite "Build cache" action that chains `batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`. The chain runs the embed step over both catalog and Instagram rows (per D-01).
- **D-05:** Individual stage triggers (including the legacy `prepare_catalog`) live under an Advanced section on `CatalogCacheTab`. The Advanced section **reuses** the existing `AdvancedOptions` component pattern from the matching tab (DRY mandate from Phase 7 retained).
- **D-06:** Stack-detect and catalog-similarity job triggers are removed from `MatchingTab`. Their canonical home is `CatalogCacheTab`.
- **D-07:** `vision_match` job log emits per-stage candidate counts: `date-window in → CLIP shortlist out → LLM judgments`. Counts are throttled per-batch summary, not per-image, to keep log volume reasonable.
- **D-08:** Cache-pipeline chain emits per-stage progress and skip reasons in the job log so operators can verify each step did or did not need to run.

### Claude's discretion (must resolve in research)
- Single composite chain handler vs sequential enqueue with dependencies.
- Behavior when a prior stage is missing/incomplete.
- Numeric min/max bounds on the per-run top-k override.
- Exact result-key shape for per-stage count metadata in `vision_match` results.

### Deferred / out of scope (do not plan)
- Wider-search fallback when shortlist is empty (was MATCH-03 — dropped).
- Embedding model A/B benchmark (DINOv2 / SigLIP) — separate todo.
- FAISS migration — sqlite-vec stays unless verification proves otherwise.
- Stack construction or stack-member matching changes (Phase 7 contract preserved).
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|------------|--------------|----------------|-----------|
| CLIP shortlist over date-window representatives | Core library (`clip_similarity` + `match_instagram_dump`) | sqlite-vec (`image_clip_embeddings`) | Shortlist is deterministic DB + vector math before any handler-specific I/O. |
| Gating phash + description + vision scoring | Core library (`match_instagram_dump` → `score_candidates_with_vision`) | Vision providers | D-03 is enforced by shrinking `candidates` / `vision_candidates` before `score_candidates_with_vision` is called. |
| `vision_match` checkpoint / fingerprint | Backend (`checkpoint.fingerprint_vision_match`, `handlers.handle_vision_match`) | — | Resume semantics already keyed on fingerprint + `processed_media_keys`. |
| Instagram rows in `batch_embed_image` | Backend handler + `database` list/upsert helpers | Filesystem (`resolve_filepath` / cache) | Same persistence path as catalog: `upsert_image_clip_embedding` / vec0. |
| Composite cache chain (embed → stack → similarity) | Backend (new or consolidated handler) | `library_db.JOB_TYPES_REQUIRING_CATALOG` | Single job aligns with `cancel_scope` and one progress bar; catalog DB is already the shared dependency. |
| Top-k UI + metadata plumbing | Frontend (`MatchingTab`, `JobsAPI.create`) | — | `JobsAPI.create` posts opaque `metadata` dict today — extend with bounded int. |
| DRY Advanced disclosure | Frontend (`AdvancedOptions`, `CatalogCacheTab`, `MatchingTab`) | `strings.ts` | One component, two parents; copy only via constants per UI-SPEC. |
| Per-stage observability | Backend job logs + optional `complete_job` result | — | Follow `job-log-contract.mdc` (throttled summaries). |
</architectural_responsibility_map>

<research_summary>
## Summary

**CLIP shortlist insertion point:** After the representative-only filter in `match_dump_media` (the block that increments `stats['non_representative_candidates_filtered']` and filters with `catalog_key_is_primary_grid_row`), and **before** the loop that builds `vision_candidates` and **before** `score_candidates_with_vision`. Today that loop begins at `vision_candidates = []` over `candidates` in `lightroom_tagger/scripts/match_instagram_dump.py` (immediately after optional phash on the dump row). The shortlist operates on the **catalog row dicts** from `find_candidates_by_date`, not on the flattened `vision_candidates` list.

**Instagram embeddings:** `image_clip_embeddings` is vec0 with columns `embedding`, `image_key` only (`database._migrate_image_clip_embeddings_vec0`). Instagram dump identities use `instagram_dump_media.media_key` as stable keys (same string space as catalog `images.key` but disjoint in practice). D-01’s “image_type + image_key” is a **logical** key for jobs and fingerprints; storage remains `image_key` only — extend `fingerprint_batch_embed_image` so the work-set identity includes which sources are included (e.g. catalog-only vs catalog+Instagram), otherwise a completed catalog-only checkpoint could incorrectly resume when Instagram rows are newly in scope.

**Cache chain:** The codebase has **no** job dependency graph in `api/jobs.py` / runner — only per-job `cancel_scope` and checkpoints. A **single new job type** (e.g. `catalog_cache_build`) that runs the three stages in-process is the cleanest way to preserve **one cancel**, **one log stream**, and **one progress narrative** (D-08). Sequential enqueue would require new orchestration, three user-visible jobs, and ambiguous “cancel the chain” semantics.

**Frontend:** `MatchingTab` currently owns the full “Catalog Discovery Jobs” card (`startStackDetection`, `startCatalogSimilarity`, `CatalogSimilarityGroupsPreview`, `useQuery` for similarity groups) — removal per D-06 should delete that card and relocate preview/query only if still required elsewhere (otherwise drop the query to avoid orphan API usage). `AdvancedOptions` is already a pure presentational bundle of sliders + `ProviderModelSelect`; lifting it is **import + props** from `CatalogCacheTab` for Advanced-only controls, or a thin wrapper that supplies stub/default handlers for matching-only fields if the cache tab does not need weights.

**Top-k API path:** Add `clip_top_k` (name aligned with UI-SPEC) to the `metadata` dict passed to `JobsAPI.create('vision_match', metadata)`; `handle_vision_match` reads it and passes through to `match_dump_media`. Extend `fingerprint_vision_match` in `checkpoint.py` to include this value so resume does not mix runs with different shortlist sizes.

**Primary recommendation:** Implement shortlist helper(s) in `clip_similarity.py` mirroring `list_pin_similarity_candidate_keys`’s pattern (global KNN then **intersect** with an allowed key set), wire `clip_top_k` end-to-end, extend embed job + fingerprint for Instagram scope, and add one composite catalog-cache job handler that calls existing inner stage logic with structured stage logs.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Module / surface | Role | Why standard here |
|------------------|------|-------------------|
| `lightroom_tagger/core/clip_similarity.py` | `knn_clip_catalog_keys`, `get_clip_embedding_blob_for_key`, KNN cap `KNN_K_MAX = 500` | Established SIM-02 / pin / catalog similarity path. |
| `lightroom_tagger/core/database.py` | `upsert_image_clip_embedding`, `list_catalog_keys_needing_clip_embedding`, vec0 table | Single write path for CLIP blobs. |
| `lightroom_tagger/scripts/match_instagram_dump.py` | `match_dump_media` orchestration | Required integration point per CONTEXT. |
| `apps/visualizer/backend/jobs/handlers.py` | `handle_vision_match`, `handle_batch_embed_image`, stage handlers | Job narrative + checkpoints. |
| `apps/visualizer/backend/jobs/checkpoint.py` | `fingerprint_*` | Idempotency and resume. |

### Supporting
| Mechanism | When to use |
|-----------|-------------|
| `cancel_scope.install(lambda: runner.is_cancelled(job_id))` | Long inner loops (`handlers.py` already wraps `batch_embed_image`, `batch_stack_detect`). |
| `_EMBED_SUMMARY_LOG_EVERY = 250` | Model for throttled embed summaries (`handlers.py` ~L61, ~L2726–2738). |
| `JOB_TYPES_REQUIRING_CATALOG` (`library_db.py`) | Any new catalog-touching job type must be added alongside handlers. |

### Alternatives considered
| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| In-process chain | Three `JobsAPI.create` calls + dependency metadata | **Rejected:** no dependency support today; poor cancel/resume story; noisier Job Queue. |
| Shortlist inside `score_candidates_with_vision` | Keep `match_dump_media` unchanged | **Rejected:** violates D-03 — description scoring (`_compute_desc_scores_for_candidates`) runs before vision and must see only shortlist. |
| New vec0 column `image_type` | Key namespace only | **Deferred:** not required if `media_key` ∩ `catalog key` = ∅; document invariant for planners. |
</standard_stack>

<architecture_patterns>
## Architecture Patterns (concrete references)

### Pattern A — Representative filter then scoring prep
`match_dump_media` already applies `catalog_key_is_primary_grid_row` and logs representative drops before building `vision_candidates`:

```152:165:lightroom_tagger/scripts/match_instagram_dump.py
        before_rep_filter = len(candidates)
        candidates = [
            c for c in candidates
            if c.get('key') and catalog_key_is_primary_grid_row(db, c['key'])
        ]
        removed_nr = before_rep_filter - len(candidates)
        if removed_nr:
            stats['non_representative_candidates_filtered'] += removed_nr
            if log_callback:
                log_callback(
                    'info',
                    f'[{media_key}] Representative-only: dropped {removed_nr} non-representative '
                    f'catalog candidate(s) ({before_rep_filter} → {len(candidates)})',
                )
```

**Shortlist step:** Insert immediately after this block (and after the `if not candidates: continue` path), mutating `candidates` to the top-`clip_top_k` keys by CLIP similarity to the Instagram seed embedding.

### Pattern B — KNN over-fetch + filter (reuse for shortlist)
`list_pin_similarity_candidate_keys` fetches a large KNN then filters to primary-grid rows — same idea as “KNN then intersect with date-window representative keys”:

```79:94:lightroom_tagger/core/clip_similarity.py
    max_candidates = max(1, int(max_candidates))
    need_neighbors = max(0, max_candidates - 1)
    knn_k = min(KNN_K_MAX, max(50, need_neighbors * 20)) if need_neighbors else 1
    knn_k = min(KNN_K_MAX, max(knn_k, 1))

    raw = knn_clip_catalog_keys(db, blob, k=knn_k)
    out: list[str] = [seed_key]
    for image_key, _dist in raw:
        if image_key == seed_key:
            continue
        if not catalog_key_is_primary_grid_row(db, image_key):
            continue
        out.append(image_key)
        if len(out) >= max_candidates:
            break
```

For matching, replace the primary-grid filter with **membership in the current `candidates` key set** (already representative-only). Seed blob: `get_clip_embedding_blob_for_key(db, dump_media['media_key'])`.

### Pattern C — `score_candidates_with_vision` is the gated scoring stack
Description batching happens first inside `score_candidates_with_vision`:

```232:241:lightroom_tagger/core/matcher.py
    desc_scores_by_idx = _compute_desc_scores_for_candidates(
        insta_image,
        candidates,
        batch_size,
        desc_weight,
        skip_undescribed,
        provider_id,
        model,
        log_callback,
    )
```

Therefore the shortlist must reduce `candidates` **before** this function runs (D-03).

### Pattern D — `handle_vision_match` → `match_dump_media` (plumb new kwargs + fingerprint)
`handle_vision_match` builds fingerprint via `fingerprint_vision_match` (must gain `clip_top_k`) and calls `match_dump_media` without `clip_top_k` today:

```432:568:apps/visualizer/backend/jobs/handlers.py
        fp_vm = fingerprint_vision_match(
            threshold=float(custom_threshold),
            weights=dict(custom_weights),
            month=metadata.get('month'),
            year=metadata.get('year'),
            last_months=metadata.get('last_months'),
            media_key=metadata.get('media_key'),
            force_reprocess=bool(metadata.get('force_reprocess', False)),
            force_descriptions=bool(force_descriptions),
            skip_undescribed=skip_undescribed,
            provider_id=provider_id,
            provider_model=provider_model,
            max_workers=max_workers,
        )
        ...
            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                weights=custom_weights,
                media_key=media_key,
                force_descriptions=force_descriptions,
                force_reprocess=force_reprocess,
                skip_undescribed=skip_undescribed,
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                should_cancel=lambda: runner.is_cancelled(job_id),
                resume_processed_keys=resume_media or None,
                on_media_complete=on_media_complete,
                batch_progress_callback=batch_progress_callback,
            )
```

### Pattern E — `batch_embed_image` catalog-only gate (extension point)
`_handle_batch_embed_image_inner` currently rejects non-catalog `image_type`:

```2560:2567:apps/visualizer/backend/jobs/handlers.py
        image_type = metadata.get('image_type', 'catalog')
        if image_type != 'catalog':
            runner.fail_job(
                job_id,
                'batch_embed_image only supports catalog images',
                severity='warning',
            )
            return
```

Planner replaces this with branching: catalog SQL path (`list_catalog_keys_needing_clip_embedding` / `list_catalog_keys_for_clip_embed_force`), Instagram dump path (new list helper over `instagram_dump_media` with filepath + missing vec0 rows), or **union** for D-04 chain.

### Pattern F — Fingerprint includes embed scope
`fingerprint_batch_embed_image` already serializes `image_type`:

```131:137:apps/visualizer/backend/jobs/checkpoint.py
    payload = {
        "embedding_dim": CLIP_EMBED_DIM,
        "embedding_model_id": CLIP_EMBED_MODEL_ID,
        "force": bool(metadata.get("force", False)),
        "image_type": str(metadata.get("image_type", "catalog")),
        "min_rating": min_rating,
        "pairs": pairs,
```

Use an explicit sentinel value for “catalog + Instagram” (e.g. `catalog_and_instagram`) **or** a dedicated boolean `include_instagram_dump` in the payload so ordered key lists remain comparable across runs.

### Pattern G — Frontend job create contract
`JobsAPI.create` posts `{ type, metadata }` — no schema change required for `clip_top_k`:

```151:159:apps/visualizer/frontend/src/services/api.ts
  create: async (type: string, metadata?: Record<string, any>) => {
    const job = await request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    })
    invalidateAll(['jobs.list'])
    invalidateAll(['jobs.health'])
    return job
  },
```

### Pattern H — Matching tab removal target
“Catalog Discovery Jobs” card and similarity preview live in `MatchingTab.tsx` (~L174–218 + preview component); stack/similarity state hooks at L41–47, L88–116 — all are removal candidates per D-06.

</architecture_patterns>

<integration_points>
## Integration Points (exact symbols)

| What | Where | Notes |
|------|-------|------|
| Shortlist | `match_dump_media` | After representative filter (`catalog_key_is_primary_grid_row`), before `vision_candidates = []` loop. |
| Pass top-k | `match_dump_media` signature | New parameter e.g. `clip_top_k: int = 50`. |
| Vision job metadata | `handle_vision_match` | Read `metadata.get('clip_top_k', 50)`, validate int, pass to `match_dump_media`. |
| Resume identity | `fingerprint_vision_match` | Add `clip_top_k` to payload in `checkpoint.py`. |
| CLIP helper | `clip_similarity.py` | New function e.g. `shortlist_catalog_candidates_by_clip(db, insta_key, candidate_rows, top_k)` returning ordered subset of rows or keys + optional diagnostics. |
| Instagram embed keys | `database.py` | New `list_instagram_dump_keys_needing_clip_embedding` / force list; filepath from `instagram_dump_media`; reuse `resolve_filepath` + cache path pattern from `_handle_batch_embed_image_inner.classify_path`. |
| Embed handler branch | `_handle_batch_embed_image_inner` | Replace catalog-only fail; union fingerprints per D-01 scope. |
| Cache chain | `handlers.py` + `JOB_HANDLERS` | New `handle_catalog_cache_build` (name TBD) calling embed → stack → similarity; register next to existing handlers ~L3415+. |
| Catalog job set | `library_db.JOB_TYPES_REQUIRING_CATALOG` | Add new chain job type. |
| UI top-k | `MatchingTab.startMatching` | Add `clip_top_k: number` to `metadata` after validation 1..500. |
| Advanced reuse | `CatalogCacheTab` | Render `AdvancedOptions` + cache-specific actions inside expanded region (D-05); strings from `strings.ts` (08-UI-SPEC). |
</integration_points>

## Validation Architecture

This section is the contract from which **Nyquist `VALIDATION.md`** should be derived.

### Requirement / wave map

| REQ-ID | Primary verification | Test layer | Automated command (typical) | Threat / regression focus |
|--------|---------------------|------------|-----------------------------|-----------------------------|
| **MATCH-02** shortlist reduces LLM work | Unit: CLIP shortlist helper returns ≤ `clip_top_k` and only keys from input set | `pytest` | `python -m pytest lightroom_tagger/core/test_clip_similarity.py -v` (extend) | Wrong-key leakage into scoring; KNN ignoring candidate filter |
| **MATCH-02** D-03 gating | Unit: mock `score_candidates_with_vision`, assert candidate count after shortlist | `pytest` | New tests in `lightroom_tagger/scripts/` or `test_handlers_single_match.py` patterns | Description stage run on full window (forbidden) |
| **MATCH-02** wiring | Integration: `match_dump_media` with fake DB + vec rows | `pytest` | Extend `apps/visualizer/backend/tests/test_handlers_single_match.py` / `test_stack_matching_integration.py` style | Representative filter ordering vs shortlist |
| **MATCH-02** fingerprint | Unit: `fingerprint_vision_match` changes when `clip_top_k` changes | `pytest` | `apps/visualizer/backend/tests/` (new case) | Stale resume mixing top-k |
| **MATCH-02** observability D-07 | Log fixture or handler test: batch summary lines present | `pytest` | Handler test with mocked `match_dump_media` or captured `add_job_log` | Log spam (per-image) |
| **CACHE-01** chain | Integration: composite handler runs stages in order, honors cancel | `pytest` | `apps/visualizer/backend/tests/test_handlers_*.py` (new file) | Stage skip after cancel |
| **CACHE-01** embed Instagram | Integration: `batch_embed_image` with `image_type` / scope includes dump rows | `pytest` | Extend `test_handlers_batch_embed_image.py` | Fingerprint idempotency when IG scope toggles |
| **D-06** UI | Component test: Matching tab has no stack/similarity CTAs | `vitest` | `cd apps/visualizer/frontend && npm test -- --run MatchingTab` | Orphan strings/types |
| **D-05** UI | Component test: `CatalogCacheTab` renders `AdvancedOptions` | `vitest` | `CatalogCacheTab.test.tsx` | Duplicate disclosure logic |

### End-to-end sampling (manual or scripted)

- **Wave 0 / infra:** `describe_library_db()` / health — catalog path present (`library_db.py` contract).
- **Manual UAT (document in VALIDATION.md):** Start `vision_match` with top-k 50 vs 200 on a small month slice; compare job log summaries (`calls/image` / batch counts) and Job Queue progress; run “Build catalog cache” once and confirm ordered stage logs (D-08).
- **LLM / live API:** Per `gsd-live-validation.mdc`, any **new** HTTP route or LLM integration introduced during execute-phase needs live validation — Phase 8 likely **reuses** existing vision batch endpoints inside `score_candidates_with_vision`; if no new LLM **surface** is added, note “no new LLM endpoint — regression via unit/integration only.”

### Sampling rate

- Automated: every CI run on affected tests.
- Manual UAT: one controlled batch per release candidate for MATCH-02 cost reduction sanity (compare LLM call counts in logs).

### Negative cases

- Instagram row **missing** CLIP embedding: expect explicit skip / log bucket (no inline embed per D-01); shortlist empty → no scoring calls for that media (MATCH-03 fallback explicitly out of scope).
- `clip_top_k` **out of range** from API: clamp or reject at handler with warning — UI validates 1..500 per 08-UI-SPEC.

</validation_architecture>

<threat_model_inputs>
## Threat Model Inputs (STRIDE-oriented)

| Surface | STRIDE categories | Notes |
|---------|-----------------|-------|
| **CLIP shortlist + scoring** | **T**ampering, **I**nformation disclosure | Malicious `metadata` could skew `clip_top_k` or weights if server trusts client without bounds. Mitigation: clamp `clip_top_k` to [1, 500] server-side; keep weights validation already implied by `MatchingTab` / handler. |
| **`clip_top_k` (1..500)** | **D**enial of service | Upper bound 500 aligns with `KNN_K_MAX` in `clip_similarity.py`; worst case still caps neighbor fetch. LLM cost scales with shortlist × batches — much lower than unbounded date window. |
| **Composite cache chain** | **E**levation of privilege (low), **D**enial of service | Same trust model as other jobs: anyone who can POST `/jobs/` triggers long CPU/GPU work. Mitigation: existing auth posture (if any); document operational cost; single job makes **one** cancellation point (`runner.signal_cancel`). |
| **Job metadata injection** | **S**poofing | If API is LAN-trusted, risk is low; if exposed, job metadata could specify aggressive `force` flags. Reuse existing patterns for `batch_stack_detect` / embed `force`. |
| **Log narrative (D-07/D-08)** | **I**nformation disclosure | Logs include counts and keys — acceptable for operator debugging; avoid logging full embedding blobs. |
| **Instagram + catalog shared vec table** | **T**ampering (integrity) | Key collision would overwrite vec row — rely on key namespace disjointness; optional future `image_type` column if collision risk appears. |
</threat_model_inputs>

<open_questions_resolved>
## Open Questions Resolved (Claude's discretion)

1. **Composite handler vs sequential enqueue**  
   **Pick: single composite job handler** that runs `batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity` logic in one process, one `job_id`, with stage-prefixed log lines and optional per-stage checkpoint blob. **Why:** No job-dependency feature exists; three separate jobs complicate cancel/resume; D-08 asks for a unified chain narrative. Refactor stage bodies into callables shared with standalone handlers to avoid duplication.

2. **Prior stage missing/incomplete**  
   **Pick: continue with explicit warnings + bucketed skip counts** (each stage already tracks skips — e.g. `batch_catalog_similarity` counts `skipped_no_embedding`). **Why:** Hard-blocking embeds is brittle (partial catalogs are normal); observability (D-08) makes “similarity ran with 40% missing embeddings” visible. Document recommended operator order in job log preamble.

3. **Top-k bounds**  
   **Confirm 1 ≤ k ≤ 500** per `08-UI-SPEC.md` and `clip_similarity.KNN_K_MAX = 500`. Server-side clamp to the same range even if API is called directly.

4. **Result-key shape for `vision_match`**  
   **Recommend cumulative job `result` + per-batch logs:**  
   - `clip_prefilter_candidates_in` (sum or final — prefer **sum** across media for cost analytics)  
   - `clip_prefilter_shortlist_total` (sum of shortlist sizes)  
   - `vision_judgments_total` (approximate LLM comparisons — derive from matcher batch stats if exposed, or count scored rows)  
   Per-batch log message (D-07) should repeat three integers: `date_window_in=N clip_shortlist_out=M judgments=J` using a module constant throttle (pattern: `_EMBED_SUMMARY_LOG_EVERY`).
</open_questions_resolved>

<decision_recommendations>
## Decision Recommendations (for PLAN.md)

1. **Chain:** Implement **`catalog_cache_build`** (name negotiable) composite handler; keep standalone `batch_*` jobs for Advanced reruns (D-04/D-05).
2. **Missing embeddings:** **Warn + proceed**; never silent no-ops — stage start logs include input counts from prior artifacts.
3. **Top-k:** **`clip_top_k` in `vision_match` metadata**, default **50**, bounds **1–500**, included in **`fingerprint_vision_match`**.
4. **Shortlist implementation:** New helper in **`clip_similarity.py`** using **`get_clip_embedding_blob_for_key`** + **`knn_clip_catalog_keys`** with over-fetch, intersect keys with **`candidates` list**, preserve KNN order.
5. **Instagram embed fingerprint:** Extend **`fingerprint_batch_embed_image`** payload with explicit **scope** covering Instagram inclusion so catalog-only resumes never skip new IG work.
6. **MatchingTab cleanup:** Remove **stack/similarity** handlers, state, `ImagesAPI.listCatalogSimilarityGroups` usage, and **CatalogSimilarityGroupsPreview**; add **link copy** to Catalog Cache tab per UI-SPEC; grep for orphan imports/strings.
7. **AdvancedOptions:** Import from **`apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx`** into **`CatalogCacheTab.tsx`**; pass only needed props (cache Advanced may omit weight sliders if design allows — if not allowed, keep full component for true reuse per D-05).
8. **Throttle constant:** Introduce `_VISION_MATCH_PREFILTER_SUMMARY_EVERY` (suggest **25–50** media items, tunable) mirroring embed’s `_EMBED_SUMMARY_LOG_EVERY = 250` but scaled to typical matching batch sizes.

</decision_recommendations>

<sources>
## Sources

### Primary
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-CONTEXT.md`
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-UI-SPEC.md`
- `.planning/REQUIREMENTS.md` (MATCH-02, CACHE-01, dependencies)
- `lightroom_tagger/scripts/match_instagram_dump.py` — `match_dump_media`
- `lightroom_tagger/core/matcher.py` — `score_candidates_with_vision`, `_compute_desc_scores_for_candidates`
- `lightroom_tagger/core/clip_similarity.py` — KNN helpers, `KNN_K_MAX`
- `lightroom_tagger/core/database.py` — `image_clip_embeddings` migration, `upsert_image_clip_embedding`, catalog CLIP listing
- `apps/visualizer/backend/jobs/handlers.py` — `handle_vision_match`, `_handle_batch_embed_image_inner`, stack/similarity handlers
- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_batch_embed_image`, `fingerprint_vision_match`
- `apps/visualizer/backend/library_db.py` — `JOB_TYPES_REQUIRING_CATALOG`
- `apps/visualizer/frontend/src/components/processing/MatchingTab.tsx`
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx`
- `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx`
- `apps/visualizer/frontend/src/services/api.ts` — `JobsAPI.create`
- `.cursor/rules/job-log-contract.mdc`
- `.cursor/rules/dry-callsite-sweep.mdc`

### Secondary
- `apps/visualizer/backend/tests/test_handlers_single_match.py` — `match_dump_media` / handler patterns
- `.planning/codebase/TESTING.md`
</sources>

<metadata>
## Metadata

**Research scope:** Pre-filter cascade wiring, embed job extension, cache chain orchestration, UI DRY and removal, validation/test boundaries, STRIDE notes for tunable inputs and composite jobs.

**Valid until:** 2026-05-11 (revisit if vec0 schema gains `image_type` or job dependency queue is introduced).

</metadata>

## RESEARCH COMPLETE
