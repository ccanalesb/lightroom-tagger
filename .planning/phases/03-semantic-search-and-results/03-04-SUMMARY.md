---
phase: 3
plan: "03-04"
requirements: [NLS-03]
key_files:
  - lightroom_tagger/core/semantic_search.py
  - lightroom_tagger/core/database.py
key_decisions:
  - D-07 pure-Python RRF (RRF_K=60, rank 1-based)
  - D-08 FTS participates; empty FTS + non-empty vec → no rows, fts_no_match
  - D-09 post-filter to embedded keys when vec index non-empty
  - D-10 template why_matched from ranks + cosine distance
---

# Phase 3 Plan 04: Semantic Hybrid Search Summary

**One-liner:** Implemented FTS5 BM25–ordered keys plus sqlite-vec cosine KNN, fused with reciprocal rank fusion in Python, template `why_matched` strings, D-09 embedding post-filter, FTS-only degradation when the vec table is empty, and `query_catalog_images_by_keys` for stable key-order hydration.

## Task completion

| Task | Title | Commit |
|------|--------|--------|
| 03-04-T1 | Pure RRF fuse helper | `4362191` |
| 03-04-T2 | SQL helpers: FTS ranked keys + KNN keys | `e1488c0` |
| 03-04-T3 | why_matched templates + hybrid orchestrator | `092426a` |
| 03-04-T4 | query_catalog_images_by_keys preserve order | `525627e` |

## Deviations

None. sqlite-vec KNN uses a single float32 blob bind for `embedding MATCH ?` and a separate `k = ?` bind per 03-RESEARCH.md / plan.

## Verification

- `python -c "from lightroom_tagger.core.semantic_search import run_semantic_hybrid_search; …"` — OK
- Plan greps for `run_semantic_hybrid_search`, `fts_no_match`, `query_catalog_images_by_keys`, `FTS match · embedding:` — OK

## Self-Check: PASSED
