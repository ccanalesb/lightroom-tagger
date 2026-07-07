# Context: lightroom_tagger library & CLI

## Purpose

`lightroom_tagger` is an installable Python package that forms the core intelligence layer of the project. It reads Lightroom catalogs (SQLite, read-only except for keyword writes), ingests Instagram export dumps, runs vision-model matching and AI scoring, and exposes everything via a CLI. The visualizer app is a consumer of this library.

## Domain language

| Term | Meaning |
|---|---|
| **catalog** | A Lightroom `.lrcat` SQLite file. Read-only except for keyword writes via `lightroom/writer.py`. |
| **image** / **catalog image** | A photo record in the library DB indexed from the Lightroom catalog. |
| **instagram dump** | An exported ZIP/directory of Instagram media and metadata provided by the user (no API access). |
| **match** | The result of pairing a catalog image with an Instagram post, stored in `matches`. Has two states: *proposed* (created by the vision pipeline, `validated_at` is NULL) and *validated* (human-confirmed, `validated_at` is set). Only validated matches drive posting analytics and identity. |
| **validated match** | A match with `validated_at` set — human-confirmed pairing. The population used by posting analytics and identity aggregation. |
| **vision comparison** | A side-by-side AI comparison of two images to determine if they are the same photo. |
| **description** | An AI-generated textual description of a catalog image. |
| **score** | A numeric AI evaluation of an image (catalog or Instagram dump) against a named perspective (e.g. "composition", "light"). Stored in `image_scores`. `image_type` distinguishes catalog vs dump images. `is_current = 1` marks the active score for a version. |
| **perspective** | A named scoring lens (slug + prompt). Catalog images are scored per-perspective. |
| **provider** | An AI model endpoint (Ollama, NVIDIA NIM, OpenRouter, etc.) defined in `providers.json`. |
| **fallback** | The multi-provider retry chain: `FallbackDispatcher` tries providers in `fallback_order` when one fails. |
| **phash** | Perceptual hash used for fast image similarity pre-screening before vision comparison. |
| **stack** | A Lightroom virtual copy group; stack collapse logic deduplicates matched images. |
| **identity** | Aggregated style fingerprint and best-photo ranking for a photographer, computed from current catalog scores. |
| **catalog indexing** | The process of reading catalog images that haven't been analyzed yet and computing phash, EXIF, and description for each, storing results in `library.db`. Precedes matching. |
| **NL filter** | Natural-language catalog search — query the catalog using plain text instead of filters. |
| **embedding** | CLIP or text vector representation of an image or description, used for semantic search. |
| **library DB** | `library.db` — the project's own SQLite database (not the Lightroom catalog). Holds indexed images, matches, scores, descriptions, and job state for the CLI path. |
| **library_write** | Process-wide writer lock + `BEGIN IMMEDIATE` used for all writes to `library.db` to prevent `SQLITE_BUSY` under parallel workers. |
| **cancel scope** | Thread-local cooperative cancellation. A batch worker registers a `cancel_check` callback for its thread; retry sleeps and fallback dispatcher honour it. Triggered from the visualizer UI (user cancels a job) and intended to work from CLI too. |
| **scan** | Full re-read of the Lightroom catalog with idempotent upsert into `library.db`. Picks up metadata edits to already-indexed images. |
| **catalog sync** | Incremental, additions-only refresh: diffs catalog ids against `library.db`, fetches metadata only for missing images. Does not update existing rows or delete stale ones. |

## Key modules

| Module | Role |
|---|---|
| `database` | Library DB schema, migrations, image/score/description/match/stack storage, write serialization |
| `matcher` | EXIF-based candidate selection + vision comparison pipeline |
| `analyzer` | Image preparation (`image_prep`), inspection (`image_inspect`), vision comparison (`vision_compare`), description generation (`description`) |
| `vision_client` | OpenAI-compatible HTTP client (`compare_images`, `generate_description`, `complete_chat_text`) |
| `vision_client_batch` | Batch compare helpers (loaded after `vision_client` to avoid import cycles) |
| `provider_registry` | Loads `providers.json`, auto-discovers Ollama models, returns configured `openai.OpenAI` clients |
| `exceptions` | Shared error type package — `ProviderError` hierarchy + `StackMutationError` |
| `fallback` | `FallbackDispatcher` — retry + multi-provider fallback for compare/describe/score |
| `retry` | `retry_with_backoff` with `RETRYABLE_ERRORS` / `NOT_RETRYABLE_ERRORS` frozensets |
| `cancel_scope` | Thread-local cooperative cancellation — workers register a `cancel_check` callback; retry/fallback paths honour it |
| `scoring_service` | Per-perspective scoring of catalog and Instagram images via vision models |
| `identity_service` | Best-photo ranking, style fingerprint, post-next hints from current catalog scores |
| `description_service` | Describes catalog images; orchestrates `analyzer.description` + DB writes |
| `embedding_service` | Text embedding generation and storage |
| `clip_embedding_service` | CLIP image embedding generation and storage |
| `clip_similarity` | Catalog similarity search via CLIP embeddings |
| `semantic_search` | Hybrid search: FTS5 BM25 + sqlite-vec KNN + RRF fusion |
| `search_tools` | LLM function-calling tool schemas and executor for search |
| `nl_catalog_search` | Natural-language catalog search entry point |
| `catalog_sync` | Incremental additions-only catalog → library.db refresh (set-difference on ids) |
| `catalog_nl_filter` | SQL filter builder for NL search queries |
| `prompt_builder` | Builds scoring and description prompts |
| `structured_output` | Parses and retries LLM JSON score responses |
| `posting_analytics` | Instagram cadence/frequency stats from validated dump |
| `posting_analytics_captions` | Caption statistics and unposted-catalog listing |
| `vision_cache` | Cached compressed images and phash lookups for vision pipeline |
| `config` | `load_config` — merges `config.yaml` + env overrides; `get_vision_model`, `get_description_model` |
| `path_utils` | Path resolution helpers |
| `text_constants` | Shared text/string constants |
| `cli` | `argparse` CLI entry point (`lightroom-tagger` and friends); `run()` builds parser, applies global overrides, dispatches |
| `cli_commands` | Explicit command registry (`Command` dataclass + `COMMANDS` list) — each command's name, flags, and handler live in one place |
| `cli_cmds_extra` | Heavyweight CLI subcommands (`export`, `init`, `stats`, `enrich-catalog`) split out to keep `cli` under size budget |

## Architectural constraints

- **Lightroom catalog is read-only** except for keyword writes via `lightroom/writer.py`.
- **One writer at a time** on `library.db`: always use `library_write` context manager for DML; never bare `conn.commit()` in parallel worker paths.
- **Providers are OpenAI-compatible**: all vision/LLM calls go through `openai.OpenAI` client regardless of backend (Ollama, NIM, OpenRouter).
- **No Instagram API**: all Instagram data comes from user-provided export dumps via `instagram/dump_reader.py` and `instagram/deduplicator.py`. Live-crawl scraper code has been removed.
- **Tests live next to modules**: `test_*.py` files are co-located under `lightroom_tagger/core/`.
