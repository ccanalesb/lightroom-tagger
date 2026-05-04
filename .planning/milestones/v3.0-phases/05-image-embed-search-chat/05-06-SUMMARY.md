# Plan 05-06: Tests sweep and integration assertions — SUMMARY

**Status:** complete (2026-04-24)

## Objectives (SIM-01, NLS-05)

- CLIP + sqlite-vec: existing `test_clip_embedding_service.py` and `test_database.py` already satisfied the plan; verified only (no new commits).
- `batch_embed_image` handler: new `test_handlers_batch_embed_image.py` with zero-work, CLIP row write, incremental vs force, checkpoint resume, fingerprint mismatch.
- `POST /api/images/chat-search`: new `test_images_chat_search_api.py` (NL path, semantic fallback, empty message 400, multi-turn, invalid LLM JSON 400).
- `JOB_TYPES_REQUIRING_CATALOG`: `batch_embed_image` asserted in `test_library_db.py`.
- `SearchPage`: new `SearchPage.test.tsx` (mock `ImagesAPI.chatSearch`, form submit, results copy + filename).

## Commits (tasks 3–6; tasks 1–2 no code changes)

| Task | Commit   | Message |
|------|----------|---------|
| 1–2  | —        | N/A: acceptance runs only (CLIP + DB tests already in place) |
| 3    | `d7e6efe` | `test(05-06): add batch_embed_image handler tests` |
| 4    | `e7ce483` | `test(05-06): add chat-search API endpoint tests` |
| 5    | `d7253e5` | `test(05-06): assert batch_embed_image in JOB_TYPES_REQUIRING_CATALOG` |
| 6    | `7ffb425` | `test(05-06): add SearchPage vitest unit test` |
| doc  | — | `docs(05-06): complete tests sweep plan` |

## Handler tests — implementation note

`encode_images` is imported into `jobs.handlers` via `from lightroom_tagger.core.clip_embedding_service import encode_images`. Patching with `@patch("jobs.handlers.encode_images")` led to `MagicMock.call_args` recording `[]` for the first positional argument while the real call used a non-empty path list (inconsistent mock bookkeeping in this setup). Production-safe alternative used: `monkeypatch.setattr(jobs.handlers, "encode_images", ...)` and/or explicit `calls` list capture for assertions (still patches the `jobs.handlers` binding as required).

## Verification (machine)

```bash
cd /Users/ccanales/projects/lightroom-tagger
python -m pytest lightroom_tagger/core/test_clip_embedding_service.py \
  lightroom_tagger/core/test_database.py \
  apps/visualizer/backend/tests/test_handlers_batch_embed_image.py \
  apps/visualizer/backend/tests/test_images_chat_search_api.py \
  apps/visualizer/backend/tests/test_library_db.py -q
cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run src/pages/SearchPage.test.tsx
```

**Last run:** `72 passed` (pytest, ~3.1s); `npx tsc --noEmit` clean; `vitest run src/pages/SearchPage.test.tsx` — 1 passed.

## Files touched

- `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` (new)
- `apps/visualizer/backend/tests/test_images_chat_search_api.py` (new)
- `apps/visualizer/backend/tests/test_library_db.py` (+1 assertion)
- `apps/visualizer/frontend/src/pages/SearchPage.test.tsx` (new)

## No changes

- `lightroom_tagger/core/test_clip_embedding_service.py` — already covered normalize/shape/2048-byte blob
- `lightroom_tagger/core/test_database.py` — `user_version == 5`, `image_clip_embeddings` vec0 + round-trip already present
