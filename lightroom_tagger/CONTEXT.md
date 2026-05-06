# Context: lightroom_tagger library & CLI

## Purpose

`lightroom_tagger` is an installable Python package that forms the core intelligence layer of the project. It reads Lightroom catalogs (SQLite, read-only except for keyword writes), ingests Instagram export dumps, runs vision-model matching and AI scoring, and exposes everything via a CLI. The visualizer app is a consumer of this library.

## Domain language

| Term | Meaning |
|---|---|
| **catalog** | A Lightroom `.lrcat` SQLite file. Read-only except for keyword writes via `lr_writer.py`. |
| **image** / **catalog image** | A photo record in the library DB indexed from the Lightroom catalog. |
| **instagram dump** | An exported ZIP/directory of Instagram media and metadata provided by the user (no API access). |
| **match** | The result of pairing a catalog image with an Instagram post, stored in `library.db`. |
| **vision comparison** | A side-by-side AI comparison of two images to determine if they are the same photo. |
| **description** | An AI-generated textual description of a catalog image. |
| **score** | A numeric AI evaluation of a catalog image against a named perspective (e.g. "composition", "light"). Stored in `image_scores`. `is_current = 1` marks the active score for a version. |
| **perspective** | A named scoring lens (slug + prompt). Catalog images are scored per-perspective. |
| **provider** | An AI model endpoint (Ollama, NVIDIA NIM, OpenRouter, etc.) defined in `providers.json`. |
| **fallback** | The multi-provider retry chain: `FallbackDispatcher` tries providers in `fallback_order` when one fails. |
| **phash** | Perceptual hash used for fast image similarity pre-screening before vision comparison. |
| **stack** | A Lightroom virtual copy group; stack collapse logic deduplicates matched images. |
| **identity** | Aggregated style fingerprint and best-photo ranking for a photographer, computed from current catalog scores. |
| **posting analytics** | Statistics derived from the validated Instagram dump (cadence, frequency, top-performing posts). |
| **NL filter** | Natural-language catalog search via `catalog_nl_filter.py` / `nl_catalog_search.py`. |
| **embedding** | CLIP or text embedding used for semantic search (`clip_embedding_service.py`, `embedding_service.py`). |
| **library DB** | `library.db` — the project's own SQLite database (not the Lightroom catalog). Holds indexed images, matches, scores, descriptions, and job state for the CLI path. |
| **library_write** | Process-wide writer lock + `BEGIN IMMEDIATE` used for all writes to `library.db` to prevent `SQLITE_BUSY` under parallel workers. |

## Key modules

| Module | Role |
|---|---|
| `lightroom_tagger/core/database.py` | Schema, WAL, `library_write` serializer, row helpers, `resolve_filepath` for NAS paths |
| `lightroom_tagger/core/matcher.py` | EXIF-based candidate query + vision comparison pipeline |
| `lightroom_tagger/core/vision_client.py` | OpenAI-compatible HTTP client (`compare_images`, `generate_description`, `complete_chat_text`) |
| `lightroom_tagger/core/provider_registry.py` | Loads `providers.json`, auto-discovers Ollama models, returns configured `openai.OpenAI` clients |
| `lightroom_tagger/core/provider_errors.py` | Typed exception hierarchy (`ProviderError`, `RateLimitError`, `TimeoutError`, etc.) |
| `lightroom_tagger/core/fallback.py` | `FallbackDispatcher` — retry + multi-provider fallback for compare/describe/score |
| `lightroom_tagger/core/retry.py` | `retry_with_backoff` with `RETRYABLE_ERRORS` / `NOT_RETRYABLE_ERRORS` frozensets |
| `lightroom_tagger/core/scoring_service.py` | Per-perspective scoring of catalog and Instagram images via vision models |
| `lightroom_tagger/core/identity_service.py` | Best-photo ranking, style fingerprint, post-next hints from current catalog scores |
| `lightroom_tagger/core/analyzer.py` | Image description generation; `compress_image`, `get_viewable_path` |
| `lightroom_tagger/core/prompt_builder.py` | Builds scoring and description prompts |
| `lightroom_tagger/core/structured_output.py` | Parses and retries LLM JSON score responses |
| `lightroom_tagger/core/config.py` | `load_config` — merges `config.yaml` + env overrides |
| `lightroom_tagger/core/posting_analytics.py` | Instagram cadence/frequency stats from validated dump |
| `lightroom_tagger/catalog_reader.py` | Reads the Lightroom catalog SQLite |
| `lightroom_tagger/lr_writer.py` | Writes keywords back to the Lightroom catalog |
| `lightroom_tagger/core/pipelines.py` | Top-level pipeline fns (`run_match_pipeline`, etc.) — high-level operations over the library; handlers are thin adapters over these (ADR-0003) |
| `lightroom_tagger/core/exceptions/` | Shared error type package — `ProviderError` hierarchy + `StackMutationError`; import from here, not sub-modules (ADR-0004) |
| `lightroom_tagger/core/cli.py` | `argparse` CLI entry point (`lightroom-tagger` and friends) |

## Architectural constraints

- **Lightroom catalog is read-only** except for keyword writes via `lr_writer.py`.
- **One writer at a time** on `library.db`: always use `library_write` context manager for DML; never bare `conn.commit()` in parallel worker paths.
- **Providers are OpenAI-compatible**: all vision/LLM calls go through `openai.OpenAI` client regardless of backend (Ollama, NIM, OpenRouter).
- **No Instagram API**: all Instagram data comes from user-provided export dumps.
- **Tests live next to modules**: `test_*.py` files are co-located under `lightroom_tagger/core/`.
