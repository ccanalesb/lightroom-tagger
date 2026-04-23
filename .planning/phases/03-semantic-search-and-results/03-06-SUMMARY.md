---
phase: 3
plan: "03-06"
requirements: [NLS-03, NLS-04]
key-files:
  - lightroom_tagger/core/test_semantic_rrf.py
  - apps/visualizer/backend/tests/test_handlers_batch_text_embed.py
  - apps/visualizer/backend/tests/test_images_semantic_search_api.py
  - apps/visualizer/backend/tests/test_library_db.py
  - apps/visualizer/backend/tests/test_jobs_api.py
key-decisions:
  - Hybrid matrix (c) uses three catalog keys so RRF scores are not symmetric (two-key swapped FTS/vec ranks tie).
  - Semantic-search API tests patch `api.images.embed_query_to_vec_blob` and `api.images.run_semantic_hybrid_search` so no model load and no sqlite-vec KNN in the HTTP layer.
---

# Phase 3 Plan 06: Tests Summary

**One-liner:** Added **10** new tests — **6** pure-Python RRF / `run_semantic_hybrid_search` cases (research matrix a–d), **2** `batch_text_embed` handler tests with mocked `embed_texts`, **2** `POST /semantic-search` API tests — plus **2** assertions for `batch_text_embed` in catalog job-type sets; **245** backend pytest files still green under `apps/visualizer/backend`.

## Task completion

| Task | Title | Commit |
|------|--------|--------|
| 03-06-T1 | RRF unit tests + hybrid matrix (a–d) | `762293e` |
| 03-06-T2 | Handler tests for `batch_text_embed` | `3fc1436` |
| 03-06-T3 | API tests semantic-search | `77d6842` |
| 03-06-T4 | `jobs_requiring_catalog` includes `batch_text_embed` | `2299680` |

## Test suite results

| Scope | Command | Result |
|-------|---------|--------|
| Plan slice (verification) | `PYTHONPATH=apps/visualizer/backend pytest` on listed modules + `lightroom_tagger/core/test_semantic_rrf.py` | Pass |
| RRF module | `python -m pytest lightroom_tagger/core/test_semantic_rrf.py -q` | **6 passed** |
| Full backend | `cd apps/visualizer/backend && python -m pytest -q` | **245 passed** |

## Deviations

- **Commit order:** Task **T4** was committed before **T3** (library/jobs assertions before the semantic-search API file). History: `762293e` → `3fc1436` → `2299680` → `77d6842`. Functionality and per-task atomicity are satisfied; only chronological order vs plan table differs.
- **`JOB_TYPES_REQUIRING_CATALOG`:** `batch_text_embed` was already present in `library_db.py`; T4 only locks the contract in tests.

## Self-Check: PASSED

- [x] `test_semantic_rrf.py` with RRF + hybrid matrix (a–d), no `SentenceTransformer`
- [x] `test_handlers_batch_text_embed.py` with mocked `embed_texts`
- [x] `test_images_semantic_search_api.py` with mocked embed + hybrid; metadata + row extras + short-query 400
- [x] Full backend **245** tests pass
