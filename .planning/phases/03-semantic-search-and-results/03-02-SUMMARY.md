---
phase: 3
plan: "03-02"
requirements: [NLS-03]
key-files.created:
  - lightroom_tagger/core/embedding_service.py
  - lightroom_tagger/core/test_embedding_service.py
key-files.modified: []
key-decisions:
  - "Embedding uses a lazy singleton SentenceTransformer(TEXT_EMBED_MODEL_ID); no ProviderRegistry or FallbackDispatcher (D-04)."
  - "encode uses normalize_embeddings=True; blobs via sqlite_vec.serialize_float32 on float32 lists for vec0 KNN binds."
---

# Phase 3 Plan 02: EmbeddingService Summary

**One-liner:** Added `embedding_service` — local all-mpnet-base-v2 wrapper that returns normalized 768-dim float32 vectors as sqlite-vec blobs, with unit tests that mock `encode` (no model download in CI).

## Task completion

| Task | Description | Commit |
|------|-------------|--------|
| 03-02-T1 | Create `embedding_service` module (lazy model, `embed_texts`, blobs) | `515855e` |
| 03-02-T2 | Unit tests: blob length + mocked `encode` / `normalize_embeddings=True` | `e70123e` |

## Deviations

- **`embed_text_to_vec_blob`** — Thin alias of `embed_query_to_vec_blob` for callers that name the input “document text” rather than “query”; same encoding path. Not listed in PLAN.md task text; added for API clarity and downstream checklist parity.

## Self-Check

**PASSED** — `pytest lightroom_tagger/core/test_embedding_service.py -q` (2 passed), `ruff check` clean on `embedding_service.py` and `test_embedding_service.py`; T1/T2 acceptance greps satisfied; no `ProviderRegistry` in `embedding_service.py`.
