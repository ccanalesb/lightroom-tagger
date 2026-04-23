# Research Summary — v3.0 Intelligent Discovery

## Stack Additions

- **sqlite-vec 0.1.9** — Dense text + image vectors in SQLite, KNN via `vec0` (local-first, one file; pin and test extension load in CI; pre-1.0).
- **sentence-transformers 5.4.1** — Local MTEB-competitive text embeddings; batch in jobs, not per request.
- **torch 2.11.0** — Backend for ST and CLIP; pin per platform/CUDA.
- **open-clip-torch 3.3.0** — CLIP-style image vectors for “more like this.”
- **numpy 2.4.4** / **scipy 1.17.1** / **scikit-learn 1.8.0** — Vector math, distances, pHash/DBSCAN clustering (optional **hdbscan** later if DBSCAN is noisy).
- **openai 2.32.0** — LLM for NL→structured plan and optional cloud embeddings; same `ProviderRegistry` pattern as vision.

*FTS5: no extra package (stdlib `sqlite3`).*

## NL Search: Recommended Approach

Ship **LLM-to-structured-filters** first, not executable SQL. The model returns a **JSON object** (date ranges, `mood_tags`, `min_score`, `fts_query`, etc.) that you validate (e.g. Pydantic) and map to **whitelisted** `query_catalog_images` / hybrid parameters—**never** pass raw model-generated SQL to SQLite. Reuse `ProviderRegistry` for chat; include a **schema manifest** (or introspected allowlist) so the model cannot invent Lightroom-shaped column names. This matches injection safety and the existing query helper.

**Phase 1:** metadata + **FTS5** on denormalized `search_text` (or trigger-maintained FTS) for lexical “street,” names, and caption keywords—fast and explainable. **Phase 2:** **text embeddings** (`sentence-transformers` or OpenAI) over description/keyword text, stored for hybrid ranking (e.g. RRF or weighted fusion with FTS). **Phase 3:** full **semantic** NL once index coverage is acceptable; until then degrade to keyword + filters and show “index building” progress. Simple intents can **skip** the LLM and map straight to filters to control cost.

## Photo Stacking: Recommended Approach

**Order:** (1) **Burst detection**—sort by `date_taken`, group within a configurable `delta_ms` (use `date_taken` / EXIF; no `capture_time` today). (2) **pHash** within time windows (Hamming + tuning)—avoid pHash-only global clustering, which merges different scenes. (3) **Stack-aware scoring** after stacks exist: propagate to members with a documented rule (e.g. primary only + API inheritance) and align with `image_scores` versioning.

**Schema:** `image_stacks` (`id`, `stack_type`, `primary_image_key`, metadata JSON for thresholds) and `image_stack_members` (`stack_id`, `image_key`, `role`, `sort_order`); **composite PK `(stack_id, image_key)`**; **recommended `UNIQUE(image_key)`** so each image is in at most one stack for v1. Soft FK to `images.key`. New jobs: e.g. `batch_stack_burst`, `batch_stack_phash` (or one `batch_stack` with `mode`), with **chunked checkpoints** to avoid huge job metadata.

## Visual Attribute Tags: Recommended Approach

**Storage:** add nullable columns on **`image_descriptions`**: `dominant_colors` (JSON array), `mood_tags` (JSON array), `has_repetition` (0/1). **Why:** no breaking change for existing JSON consumers; old rows = NULL; serializers default empty. Update **`store_image_description`** and `ON CONFLICT` columns; extend **`DESCRIPTION_PROMPT`** and **`parse_description_response()`** in `analyzer.py` to emit/ normalize these (promote from nested `technical.mood` where present). **Do not** block core description: keep attributes in the same structured pass or a clearly async phase with per-image status.

**Facets:** controlled **vocab** in the prompt (or post-map to canonical tags) to avoid tag sprawl; wire into `query_catalog_images` and FilterBar. Optional **backfill** job; failures/retries must not break core describe.

## Visual Similarity: Recommended Approach

**Model:** **open-clip** (or API embeddings if product chooses)—image embedding per `images` row, **separate** from text embeddings (different product jobs: NL vs “looks like”). **Storage:** `image_embeddings` (BLOB `float32`, `model_id`, `dim`, `derived_from` for invalidation); use **sqlite-vec** for KNN at scale; architecture doc allows **numpy cosine in batches** at smaller corpus first.

**Jobs:** new type **`batch_embed_image`** (same checkpoint/resume/fairness patterns as `batch_describe`); **content fingerprint** / mtime to skip unchanged and avoid stale rows after re-import. **API:** e.g. `GET /api/images/<key>/similar` loading the seed vector then KNN, with optional pre-filter (date, folder). **Cold start:** show progress or “best effort” with lower threshold; don’t mix **model A** and **model B** vectors—key rows by `model_id` + `dim` and re-embed on model change.

## Build Order (Critical Path)

1. **Schema + migrations** — `image_descriptions` facet columns, `image_stacks` / `image_stack_members`, `image_text_embeddings`, `image_embeddings` (+ optional `embedding_meta`); idempotent, additive migrations.
2. **Describe pipeline (visual attributes)** — prompt, parse, `store`, API; unblocks facets without stacks/embeddings.
3. **FTS5 + `search_text`** — one column updated in `store_image_description` + backfill; before NL that assumes keyword search over descriptions.
4. **Text embedding job** — `batch_text_embed` (or equivalent); depends on stable text fields.
5. **NL search** — LLM → validated filter object + hybrid query using FTS + text vectors; `POST /api/search` (or similar) reusing list shapes.
6. **Image embed job + similar API** — can parallel (5) after (1) if staffed; needs `image_embeddings` + optional sqlite-vec path.
7. **Stack jobs + stack-aware scoring** — can parallel (5)–(6) after (1); scoring policy lands after stacks are populated.

**Tight “full Intelligent Discovery” UI path:** **1 → 2 → 3 → 4 → 5**; **6** and **7** in parallel after **1** (7’s scoring pass depends on stacks + existing score pipeline).

## Watch Out For (Top 5)

1. **Executing LLM “SQL”** — Treat as **untrusted**; use structured filters, parameterized queries, and allowlists only. Log rejections. Prevents injection and `ATTACH`/pragma abuse.
2. **Schema hallucination & catalog boundaries** — Model invents Lr-isms or conflates read-only Lr DB with app DB. Denormalize searchable fields in the **app** DB; never merge writable and Lr in one ad hoc SQL string without a reviewed design.
3. **pHash- or time-only stacking mistakes** — Use **time window then pHash**; handle **NULL / bad `date_taken`** (skip or singletons); version or invalidate pHash if the image pipeline changes—otherwise clusters drift.
4. **Embedding model lock-in and staleness** — Store **`model_id` + `dim`**; one model per query; re-embed on change; use **fingerprints** so imports/replacements do not leave orphan vectors.
5. **Writer contention and index drift** — Single-writer pressure grows with describe + FTS + embed + stack writes; keep transactions small, one rebuild policy for FTS vs vectors vs `described_at`, and surface **“index stale”** in UI when jobs lag.
