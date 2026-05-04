# Plan 05-04 summary: `POST /api/images/chat-search` and multi-turn NL cascade

**Completed:** 2026-04-24

## Commits

| Task | Message | Hash |
|------|---------|------|
| 1 | `feat(05-04): add complete_chat_messages for multi-turn LLM chat` | `6421e1d` |
| 2 | `feat(05-04): add run_nl_catalog_filter_llm_multi_turn with history support` | `070c69c` |
| 3 | `feat(05-04): add POST /api/images/chat-search NL-first cascade endpoint` | `8700226` |
| Docs | `docs(05-04): complete chat-search endpoint plan` | (this file) |

## What shipped

1. **`complete_chat_messages`** (`lightroom_tagger/core/vision_client.py`) — Multi-turn text chat mirroring `complete_chat_text` (Claude `extra_body`, `_map_openai_error`), with system + user/assistant turns; skips empty content.
2. **`_normalize_nl_messages` + `run_nl_catalog_filter_llm_multi_turn`** (`lightroom_tagger/core/nl_catalog_search.py`) — Same provider resolution and `FallbackDispatcher` `nl_filter` path as `run_nl_catalog_filter_llm`, but calls `complete_chat_messages` with normalized history.
3. **`POST /api/images/chat-search`** (`apps/visualizer/backend/api/images.py`) — Request: required `message`, optional `messages` (list), `limit`/`offset`, `provider_id`/`model`, optional `score_perspective` (semantic branch). Builds `turns_for_llm`, parses NL JSON, then:
   - **`_effective_catalog_nl_kwargs`** — Drops empty strings/lists so `{}` means no structured filters.
   - **Empty `kwargs_eff`** — Semantic path only (no `query_catalog_images` with pagination alone): same pipeline as `semantic_search_images`; response `search_mode: "semantic"`, `filters: null`, `metadata` populated.
   - **Non-empty `kwargs_eff`** — `query_catalog_images` with filters; response `search_mode: "nl_filter"`, `filters` from model, `metadata: null`.

## Verification

```bash
cd /Users/ccanales/projects/lightroom-tagger/apps/visualizer/backend && PYTHONPATH=. python -c "from api.images import bp; print('chat-search route registered')"
grep -n "chat-search" /Users/ccanales/projects/lightroom-tagger/apps/visualizer/backend/api/images.py
grep -n "run_nl_catalog_filter_llm_multi_turn" /Users/ccanales/projects/lightroom-tagger/lightroom_tagger/core/nl_catalog_search.py
```

NLS-05 backend: single endpoint orchestrates NL → structured SQL **or** semantic hybrid with `search_mode` discriminant; prior `messages` are passed into the LLM (D-08).
