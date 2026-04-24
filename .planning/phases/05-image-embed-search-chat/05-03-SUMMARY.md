# Plan 05-03 Summary: `batch_embed_image` job handler and registration

**Completed:** 2026-04-24  
**Requirement:** SIM-01 (checkpointed, catalog-only image CLIP embeddings with model/dim in fingerprint)

## Delivered

1. **`fingerprint_batch_embed_image`** (`apps/visualizer/backend/jobs/checkpoint.py`)  
   - Canonical SHA-256 over `date_filter`, `min_rating`, `force`, `image_type`, sorted **key list**, plus `CLIP_EMBED_DIM` / `CLIP_EMBED_MODEL_ID` so model or dim changes invalidate checkpoints.  
   - Module docstring documents `batch_embed_image` checkpoint shape (`job_type`, `fingerprint`, `processed_pairs` as catalog `image_key` strings, `total_at_start`, `checkpoint_version: 1`).

2. **`handle_batch_embed_image` / `_handle_batch_embed_image_inner`** (`apps/visualizer/backend/jobs/handlers.py`)  
   - Mirrors `batch_text_embed`: catalog-only, `init_database`, date window + `min_rating`, force vs incremental lists (`list_catalog_keys_for_clip_embed_force` / `list_catalog_keys_needing_clip_embedding`), fingerprint + checkpoint v1 resume, 5–95% progress on embedded count, `persist_checkpoint` with cap, skip with warning when row/path missing or file absent, batch buffer size 8 (`_BATCH_EMBED_IMAGE_SIZE`), `encode_images` → `numpy_to_clip_vec_blob` → `upsert_image_clip_embedding` under `library_write`.  
   - Registered in `JOB_HANDLERS['batch_embed_image']`.

3. **`JOB_TYPES_REQUIRING_CATALOG`** (`apps/visualizer/backend/library_db.py`)  
   - Added `'batch_embed_image'` next to `'batch_text_embed'`.

## Commits

| Commit     | Message |
|------------|---------|
| `b29bb66`  | `feat(05-03): add fingerprint_batch_embed_image to checkpoint module` |
| `7788e62`  | `feat(05-03): add handle_batch_embed_image job handler` |
| `4bccc5a`  | `feat(05-03): register batch_embed_image in JOB_TYPES_REQUIRING_CATALOG` |
| (latest)   | `docs(05-03): complete batch_embed_image job handler plan` (this artifact) |

## Verification

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/backend
PYTHONPATH=. python -c "from jobs.handlers import JOB_HANDLERS; assert 'batch_embed_image' in JOB_HANDLERS; print('OK')"
PYTHONPATH=. python -c "from jobs.checkpoint import fingerprint_batch_embed_image; assert len(fingerprint_batch_embed_image({'image_type': 'catalog', 'force': False}, ['b', 'a'])) == 64; print('OK')"
```

Both commands exit 0.

## Notes

- Result payload on completion: `embedded`, `skipped`, `failed` (0 unless extended), `total` (initial work-list size at fingerprint time).
