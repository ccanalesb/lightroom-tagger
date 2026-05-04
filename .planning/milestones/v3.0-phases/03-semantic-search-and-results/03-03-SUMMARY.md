---
phase: 3
plan: "03-03"
requirements: [NLS-03]
key-files:
  - apps/visualizer/backend/jobs/checkpoint.py
  - apps/visualizer/backend/tests/test_job_checkpoint.py
  - lightroom_tagger/core/database.py
  - apps/visualizer/backend/library_db.py
  - apps/visualizer/backend/jobs/handlers.py
key-decisions:
  - "Checkpoint fingerprint includes TEXT_EMBED_MODEL_ID / TEXT_EMBED_DIM; pairs are sorted so selection order does not change the fingerprint."
  - "Selection uses embeddable text (description_search_document or non-empty summary), with force mode omitting the NOT EXISTS vec filter."
  - "Vec upsert is DELETE + INSERT into image_text_embeddings inside library_write; batch encode size 16 with embed_texts(..., batch_size=16)."
---

# Phase 3 Plan 03: batch_text_embed Job Handler Summary

**One-liner:** Registered `batch_text_embed` as a catalog job with checkpointed resume, 5–100% progress, batched local embeddings, and sqlite-vec upserts keyed by catalog `image_key`.

## Task completion

| Task | Description | Commit |
|------|-------------|--------|
| 03-03-T1 | `fingerprint_batch_text_embed` + checkpoint docstring | `8251767` |
| 03-03-T2 | Unit test stability, permutation, force sensitivity | `af2f0de` |
| 03-03-T3 | DB selection/count helpers + `upsert_image_text_embedding` | `1e3a63a` |
| 03-03-T4 | `JOB_HANDLERS`, `JOB_TYPES_REQUIRING_CATALOG`, `handle_batch_text_embed` | `947b981` |

## Deviations

- Naming follows the plan: `list_catalog_keys_needing_text_embedding` / `list_catalog_keys_for_text_embed_force` / `upsert_image_text_embedding` (not alternate names sometimes used in informal checklists).
- `complete_job` result includes `failed`; it stays `0` on the success path (no per-row embed failure loop; a thrown exception fails the whole job like other batch handlers).

## Self-Check: PASSED

- Fingerprint + tests: `pytest apps/visualizer/backend/tests/test_job_checkpoint.py -q` (4 passed).
- Full backend suite: `pytest apps/visualizer/backend/tests/ -q` (241 passed).
- Grep/plan acceptance criteria for T1–T4 verified after implementation.
