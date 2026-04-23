---
status: issues_found
phase: 3
reviewed: 2026-04-23
---

# Phase 3 Code Review

## Summary

Phase 3 delivers hybrid FTS + sqlite-vec search with RRF fusion, batch text embedding, and the `POST /api/images/semantic-search` endpoint. **RRF math matches the stated contract** (1-based ranks, `k = 60`, contribution `1/(60+rank)`, final ordering descending by fused score with deterministic key tie-break). **User search text is not concatenated into SQL**: FTS match strings are built via `build_description_fts_query` (tokenized, quoted literals) and passed as bound parameters; vector side uses a blob parameter.

The main gaps are **correctness under stale/orphan keys** (API can raise), **operational fragility if sqlite-vec cannot load**, and **scalability hotspots** (full scan of embedding keys per request; per-row SELECTs in the embed job). D-08 (“no pure semantic”: empty FTS while the vec index is non-empty → no rows, `fts_no_match`) is **intentional per plan 03-04** and covered by tests — not treated as a defect here.

## Issues Found

### Critical (blocking)

1. **`semantic-search` can 500 when semantic keys lack catalog rows** (`apps/visualizer/backend/api/images.py`). Results from `run_semantic_hybrid_search` are merged with `query_catalog_images_by_keys` by **positional index** (`for i, sem_row in enumerate(rows): images[i][...]`). If any `image_key` appears in hybrid results but not in `images` (deleted catalog row, manual DB edits, or orphaned `image_text_embeddings`), `catalog_rows` is shorter than `rows` and indexing raises **`IndexError`**. **Fix:** merge by `image_key` (dict lookup / filter `rows` to keys present in the catalog response) instead of assuming equal lengths.

### Medium (should fix)

1. **Full-table read on every hybrid search** (`lightroom_tagger/core/semantic_search.py`, post-filter D-09). `SELECT image_key FROM image_text_embeddings` materializes **all** embedded keys per request. For large libraries this is unnecessary memory and a sequential scan. Prefer reusing the KNN result set plus explicit membership checks, or a single bounded query aligned with the candidate universe.

2. **sqlite-vec load is all-or-nothing** (`lightroom_tagger/core/database.py` `_ensure_sqlite_vec_loaded`). `sqlite_vec.load(conn)` is not guarded; failure prevents `init_database` from completing, so the visualizer and library tooling cannot start without a working extension. Consider a documented failure mode or lazy/degraded path for read-only features if that matches product goals.

3. **N+1 reads in `batch_text_embed`** (`apps/visualizer/backend/jobs/handlers.py` `_handle_batch_text_embed_inner`). One `SELECT ... FROM image_descriptions` per image before batching encodes. For tens of thousands of keys this dominates wall time. Batching or joining the selection query with description text would cut round trips.

4. **Shared `SentenceTransformer` singleton** (`lightroom_tagger/core/embedding_service.py`). `_get_model()` uses an unguarded global. Concurrent use from the Flask request thread and job workers may stress the underlying library (implementation-dependent). Worth verifying thread-safety or serializing embed calls if crashes or nondeterministic outputs appear under load.

5. **`fingerprint_batch_text_embed` omits `last_months` / `year`** (`apps/visualizer/backend/jobs/checkpoint.py`). Fingerprint keys off `date_filter` (legacy) and the sorted pair list. Two runs with different **`last_months` / `year`** metadata could theoretically yield the **same** key list and **collide** on fingerprint (resume semantics ambiguous). Low probability but worth aligning with `fingerprint_batch_describe`-style normalization if checkpoints must be bulletproof.

### Low (optional)

1. **`failed` counter never incremented** in `handle_batch_text_embed` — always reported as `0`; flush/embed paths don’t distinguish hard failures from cancel.

2. **`user_query` parameter** in `run_semantic_hybrid_search` is unused (`_ = user_query`) — dead API surface; harmless but noisy for readers.

3. **Type/runtime**: `embedding_service` imports `sqlite_vec` at module import time; environments missing the package fail at import before any application-level error handling.

## Verdict

**issues_found** — 1 critical (API robustness), 5 medium, 3 low.
