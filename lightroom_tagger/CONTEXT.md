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
| **match score** | The single 0–1 confidence the matcher assigns to a catalog↔Instagram candidate pairing: a weighted blend of the phash-similarity, description-text-similarity, and vision-verdict signals (`total_score` in matcher results). Distinct from **score** below, which evaluates one image against a perspective. |
| **vision comparison** | A side-by-side AI comparison of two images to determine if they are the same photo. |
| **description** | An AI-generated textual description of a catalog image. |
| **score** | A numeric AI evaluation of an image (catalog or Instagram dump) against a named perspective (e.g. "composition", "light"). Stored in `image_scores`. `image_type` distinguishes catalog vs dump images. `is_current = 1` marks the active score for a version. Not to be confused with the matcher's **match score**. |
| **perspective** | A named scoring lens (slug + prompt). Catalog images are scored per-perspective. |
| **optional perspective** | A perspective whose technique a strong photograph could legitimately skip (`perspectives.optional = 1`). Only optional perspectives may be excused; seeded as optional when the source markdown carries `<!-- optional: true -->` (the export contract from yt-to-photo-prompt-lab). |
| **excused score** | An `image_scores` row with `not_attempted = 1`: the model judged the perspective's technique genuinely absent (only allowed for optional perspectives). It still carries a numeric score/rationale but is excluded from identity aggregation. Mirrors yt-to-photo-prompt-lab's "not scorable" outcome. |
| **provider** | An AI model endpoint (Ollama, NVIDIA NIM, OpenRouter, etc.) defined in `providers.json`. |
| **resolved model** | A `(provider_id, model)` pair chosen by `provider_resolution.resolve_model()` via the single precedence ladder (explicit arg → env → `providers.json` defaults → `config.yaml` → `fallback_order`). See ADR-0007. |
| **provider call seam** | All provider/LLM HTTP calls go through `FallbackDispatcher.call_with_fallback` with a `fn_factory` that invokes `vision_client` / `vision_client_batch` helpers — never raw `client.chat.completions.create` at orchestration sites. Escalation (token bump, batch split, abort) is a pluggable `ErrorPolicy`. See ADR-0009. |
| **vision op** | One provider vision call routed through the vision-op engine (`resolve_model` → `FallbackDispatcher` → parse), optionally persisted via `run_vision_op_persist`. Description, scoring, and compare build `VisionOpSpec` via `analyzer` op-spec helpers. See ADR-0014. |
| **fallback** | The multi-provider retry chain: `FallbackDispatcher` tries providers in `fallback_order` when one fails. |
| **phash** | Perceptual hash used for fast image similarity pre-screening before vision comparison. |
| **stack** | A Lightroom virtual copy group; stack collapse logic deduplicates matched images. |
| **identity** | Aggregated style fingerprint and best-photo ranking for a photographer, computed from current catalog scores. |
| **catalog indexing** | The process of reading catalog images that haven't been analyzed yet and computing phash, EXIF, and description for each, storing results in `library.db`. Precedes matching. |
| **scan** | Full re-read of the catalog → idempotent upsert (by `key`) of *every* image into `library.db` (CLI `lightroom-tagger scan`). Heals everything but re-reads all rows. *Catalog sync* is the incremental counterpart. |
| **catalog sync** | Incremental refresh of `library.db` from the catalog: set-difference of catalog `id_local` against ids already in `library.db`, fetching+upserting only the missing rows. **Additions-only** — metadata edits to already-synced images are not detected (use a full *scan*), and images removed from the catalog are *logged as stale, never deleted*. Assumes a single configured catalog (`config.yaml` `catalog_path`); cross-catalog `id_local` collisions are unhandled. Runs as a standalone `catalog_sync` job and as the non-fatal stage 0 of `catalog_cache_build`. |
| **NL filter** | Natural-language catalog search — query the catalog using plain text instead of filters. |
| **embedding** | CLIP or text vector representation of an image or description, used for semantic search. |
| **library DB** | `library.db` — the project's own SQLite database (not the Lightroom catalog). Holds indexed images, matches, scores, descriptions, and job state for the CLI path. |
| **library_write** | Process-wide writer lock + `BEGIN IMMEDIATE` used for all writes to `library.db` to prevent `SQLITE_BUSY` under parallel workers. |
| **library-DB read seam** | Typed read helpers in `lightroom_tagger.core.database` — the only supported way for blueprints, tools, and handlers to query `library.db` tables. Returns detached `dict`/scalar/list/set values, never live `sqlite3.Row`. See ADR-0008. |
| **library-DB lifecycle seam** | Open/close `library.db` through `managed_library_db(path)` (or CLI `with_library_db` / handler `make_managed_library_db`) — never hand-roll `init_database(...)` + manual `close()` at orchestration sites. See ADR-0011. |
| **catalog lifecycle seam** | Open/close a `.lrcat` read connection through `managed_catalog(path)` — never hand-roll `connect_catalog(...)` + manual `close()` at orchestration sites. See ADR-0011. |
| **cancel scope** | Thread-local cooperative cancellation. A batch worker registers a `cancel_check` callback for its thread; retry sleeps and fallback dispatcher honour it. Triggered from the visualizer UI (user cancels a job) and intended to work from CLI too. |

## Key modules

| Module | Role |
|---|---|
| `database` | Library DB schema, migrations, image/score/description/match/stack storage, write serialization, and **read seam** (typed query helpers — all library-DB reads go through this module per ADR-0008) |
| `matcher` | EXIF-based candidate selection + vision comparison pipeline |
| `analyzer` | Image preparation (`image_prep`), inspection (`image_inspect`), vision comparison (`vision_compare`), description generation (`description`) |
| `vision_client` | OpenAI-compatible HTTP wrappers (`compare_images`, `generate_description`, `complete_chat_text`, `complete_chat_with_tools`) — the only place raw SDK completions live |
| `vision_client_batch` | Batch compare helpers (loaded after `vision_client` to avoid import cycles) |
| `provider_registry` | Loads `providers.json`, auto-discovers Ollama models, returns configured `openai.OpenAI` clients |
| `provider_resolution` | `resolve_model()` — single precedence ladder for provider/model selection; returns `ResolvedModel` with a reusable registry |
| `exceptions` | Shared error type package — `ProviderError` hierarchy + `StackMutationError` |
| `fallback` | `FallbackDispatcher` — single entry point for all provider/LLM calls (retry + multi-provider fallback) |
| `vision_op` | Vision-op engine — `run_vision_op`, `run_vision_op_persist`, `VisionOpSpec`, `VisionOpOutcome`; single orchestration primitive for description, scoring, and compare (ADR-0014) |
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
| `cli_library_db` | CLI adapter — `resolve_library_db_path`, `with_library_db`, and `CliError` mapping to exit code 1 |
| `managed_connections` | `managed_library_db` and `managed_catalog` lifecycle context managers (ADR-0011) |

## Error-handling layers

Four distinct error surfaces — do not conflate them:

1. **CLI** → `print("Error: …")` + `return 1` (`cli_library_db.map_cli_errors`, `CliError`).
2. **HTTP/API** (visualizer) → `utils/responses.py` helpers (`error_not_found`, `error_bad_request`, …).
3. **Provider/LLM dispatch** → `ErrorPolicy` retry/escalation ladder on `FallbackDispatcher` (issue #81, parent #54; ADR-0009).
4. **Domain error types** → `lightroom_tagger.core.exceptions` (`ProviderError` hierarchy, `StackMutationError`, …; ADR-0004).

## Architectural constraints

- **Lightroom catalog is read-only** except for keyword writes via `lightroom/writer.py`.
- **One writer at a time** on `library.db`: always use `library_write` context manager for DML; never bare `conn.commit()` in parallel worker paths.
- **Library-DB reads through core.database only**: blueprints, job handlers, CLI tools, and `search_tools` must not issue raw SQL against library tables — use typed helpers from `lightroom_tagger.core.database` (ADR-0008). Helpers return detached rows (`dict`), never live `sqlite3.Row`.
- **Library-DB and catalog lifecycle through managed context managers only** (ADR-0011): use `managed_library_db` / `managed_catalog` (or CLI `with_library_db` / handler `make_managed_library_db`); no hand-rolled `init_database(...)` or `connect_catalog(...)` + manual `close()` at orchestration sites (enforced by `test_db_lifecycle_guardrail.py`).
- **Provider/model resolution through `resolve_model` only** (ADR-0007): no ad-hoc precedence ladders at call sites.
- **Provider/LLM calls through the dispatcher seam only** (ADR-0009): orchestration code uses `FallbackDispatcher.call_with_fallback` with `vision_client` / `vision_client_batch` helpers inside `fn_factory`; no raw `client.chat.completions.create` outside the seam (enforced by `test_provider_call_guardrail.py`).
- **Vision-op orchestration through the engine only** (ADR-0014): no inline `resolve_model → FallbackDispatcher → parse` outside `vision_op.py`; callers build `VisionOpSpec` via `analyzer` op-spec helpers and invoke `run_vision_op` / `run_vision_op_persist` (enforced by `test_vision_op_guardrail.py`). `nl_catalog_search` is explicitly excluded (text NL filter + tool loop).
- **Providers are OpenAI-compatible**: all vision/LLM calls go through `openai.OpenAI` client regardless of backend (Ollama, NIM, OpenRouter).
- **No Instagram API**: all Instagram data comes from user-provided export dumps via `instagram/dump_reader.py` and `instagram/deduplicator.py`. Live-crawl scraper code has been removed.
- **Tests live next to modules**: `test_*.py` files are co-located under `lightroom_tagger/core/`.
