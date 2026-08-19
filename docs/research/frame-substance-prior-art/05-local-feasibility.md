# Local feasibility audit — what a void-frame detector can be built from today

Sub-report 5 of 5 for wayfinder ticket #276 (map #275). Read-only audit of this repo and a
read-only query of the live `library.db` / `visualizer.db` on 2026-08-19. **Re-verify the row
counts and timings before acting on them** — they move with every batch run.

DB resolved to `/Users/ccanales/projects/lightroom-tagger/library.db` via `config.yaml:2`
(`db_path`), `cli_library_db.py:19` (`resolve_library_db_path`), `managed_connections.py:14`
(`managed_library_db`). Opened `mode=ro&immutable=1`.

## Verdict

**Cheap today, no new pass needed:**

1. **Local pixels for ~97.5% of the catalog.** 41,908 JPEGs / 3.9 GB in
   `~/.cache/lightroom_tagger/vision`, 1024px longest side, quality 80. **The NAS was unmounted
   during this audit** (`/Volumes` held only `Extreme SSD` and `Macintosh HD`; `config.yaml:3`
   expects `/Volumes/ccanales`) and pixels were still readable. A full luminance pass measured
   **1.36 ms/image → ~57 s for 42,136 frames, single-threaded**.
2. **CLIP image vectors:** 41,566 rows, 512-d, L2-normalised, cosine. **The text tower is
   in-process** (`encode_text_for_clip`), so zero-shot text-prompt scoring works today with no
   new pass.
3. **Descriptions:** 41,112 rows with structured JSON (`technical.lighting`, `dominant_colors`,
   `composition.problems[]`).

**Requires a new pass, or unusable:**

4. **pHash is useless here.** 41,549 stored values, but DCT-based pHash discards absolute
   brightness by construction. Verified: two confirmed near-black frames hash to
   `f4f8f8f4f068e0a0` and `cf00ff01ff00ff40` — indistinguishable from ordinary busy frames. Only
   1 row of 41,549 is degenerate.
5. **No luminance or histogram statistic is stored anywhere.** Zero `ImageStat` / `.histogram()`
   code in the repo. This is the one genuinely new column — and it costs 57 s, not a real pass.
6. **No structured "technically failed" field** in `image_descriptions`. Prose substring matching
   yields 52 hits and is impure (false positive: *"glasses with red and black frames"*).
7. **A vision call per image is off the table:** ~1.54 s/image measured at 4 workers ⇒ ~18 h for
   42,136 frames, ~1,100× the Pillow pass.
8. **1,041 images (2.5%) have no local pixels** — 974 with no `vision_cache` row plus 67
   `__oversized__` sentinels. These need the NAS, or must be gated as `unknown`.

## 1. Pixel access — yes, without the NAS

**Cache directory:** `~/.cache/lightroom_tagger/vision` — `core/config.py:47`
(`vision_cache_dir` default), `config.py:103`, overridable via `VISION_CACHE_DIR`
(`config.py:208`), toggled by `vision_cache_enabled` (`config.py:48`).

**Format:** baseline JFIF JPEG, 3-component RGB, longest side **1024**
(`VISION_MAX_DIMENSION`, `analyzer/image_prep.py:10`), **quality 80** (`image_prep.py:11`),
written by `compress_image` (`image_prep.py:14-66`, `thumbnail(..., LANCZOS)` at `:49`).
Observed: `1024x684`, `684x1024`, `1024x835`; 53–89 KB. Cap `MAX_CACHED_IMAGE_KB = 512`
(`core/vision_cache.py:23`); oversized originals store the sentinel `__oversized__`
(`database/vision_cache.py:11`).

| Quantity | Value |
|---|---|
| `images` rows (catalog) | **42,136** |
| `.jpg` files in cache dir | **41,908** (3.9 GB) |
| `vision_cache` rows | **41,616** |
| …pointing into cache dir | **41,549** |
| …`__oversized__` sentinel | **67** |
| `images` with **no** `vision_cache` row | **974** |
| Random 500-path existence check | **0 missing on disk** |
| videos in `images` (.mov/.mp4/.avi/.m4v) | 54 |

So **41,549 keys map to a verified local JPEG**; ~359 files are orphans with no row.

**NAS-independence is an explicit design contract**, not an accident —
`core/vision_cache.py:129-166`, `resolve_vision_image`. Docstring `:138-147`: *"When the original
is unreachable (e.g. an unmounted NAS), it falls back to an already-cached compressed image so
describe/score run entirely off the local vision cache — the intended contract."* Returns
`(path, silent_compression)`; `silent_compression=True` means do not recompress.

**Key → local file resolvers to reuse:**

- `apps/visualizer/backend/jobs/handlers/path_diagnostics.py:45` `try_vision_cache(lib_db, image_key)` — cached path or `None`.
- `path_diagnostics.py:58` `classify_path(lib_db, image_key)` → `(usable_path, skip_reason, skip_detail)`, **cache-first** (`:67-69`), falling back to `resolve_filepath` + `get_or_create_cached_image`. Skip buckets: `no_row`, `empty_path`, `unresolved_or_missing`, `encode_failed`. Wrapper `make_path_classify_fn` `:258`; batch preflight class `PathSkipDiagnostics` `:90`.
- `core/vision_cache.py:169` `get_cached_phash`.

**Image-serving endpoint:** `apps/visualizer/backend/api/images/catalog.py:269`
`GET /api/images/catalog/<image_key>/thumbnail` — cache-first (`:280-285`), then NAS plus
on-demand cache build (`:297-304`), `send_file(..., mimetype="image/jpeg")`. Root allow-list
`_catalog_thumbnail_roots` at `api/images/common.py:47`.

**Measured, on the live cache:**

```
known near-black 2020-12-14__DSF1513          mean L = 0.11    stddev 1.03    max 155
known near-black 2025-10-06_000191470003      mean L = 16.34   stddev 1.21    max  61
normal frame     2014-01-05T14:30:23__DSC7827 mean L = 175.12  stddev 67.73   max 254

300-image random sample: 0.41 s → 1.36 ms/img → ~57 s for 42,136 single-threaded
  (Image.open + im.draft('L',(128,128)) + convert('L') + ImageStat)
mean-L distribution over the sample: p1 ≈ 14.0, p5 ≈ 35.4, median ≈ 94.6; 1/300 below 8
```

The separation is large and the cost is negligible. **This is the answer to the most important
question: a pixel-based detector runs entirely off the local cache.**

## 2. CLIP embeddings

- **Table:** `image_clip_embeddings`, a sqlite-vec virtual table:
  `CREATE VIRTUAL TABLE image_clip_embeddings USING vec0(embedding float[512] distance_metric=cosine, image_key TEXT)`.
  Migration `database/db_init_migrations.py:128` `_migrate_image_clip_embeddings_vec0`.
- **Row count: 41,566** (41,566 distinct keys) vs **42,136** catalog images ⇒ **1,024 images lack
  an embedding; 454 embedded keys are no longer in `images`** (stale).
- **Model:** `clip-ViT-B-32`, dim `512` — `core/clip_embedding_service.py:8-9`
  (`CLIP_EMBED_MODEL_ID`, `CLIP_EMBED_DIM`).
- **Library: `sentence-transformers` 5.4.1** via `SentenceTransformer`
  (`clip_embedding_service.py:6`, lazy singleton `_get_clip_model` `:14-18`). Not `open_clip`
  (not installed), not `transformers` directly, not `ollama`.
- **Normalised: yes** — `normalize_embeddings=True` at `clip_embedding_service.py:35` (images)
  and `:52` (text). Unit-norm, cosine is meaningful.
- **Text tower available in-process: YES** — `encode_text_for_clip(texts, batch_size=24)`
  `clip_embedding_service.py:44-55`, sharing the same `_get_clip_model()` instance. Serialise
  with `numpy_to_clip_vec_blob` `:58`. **A text-prompt-vs-image zero-shot void classifier is
  buildable today with no new image pass.**
- Query seam: `core/clip_similarity.py:32` `knn_clip_catalog_keys`
  (`embedding MATCH ? AND k = ?`), `KNN_K_MAX = 500` `:21`, `NoClipEmbeddingError` `:24`. Write:
  `database/embeddings.py:17` `upsert_image_clip_embedding` (delete+insert). Extension load:
  `db_init.py:37` `_ensure_sqlite_vec_loaded`; `sqlite-vec==0.1.9` pinned (`pyproject.toml:37`).
  Batch job `batch_embed_image`, `jobs/handlers/embed.py:52`.
- Caveat: the CLI `sqlite3` binary cannot read this table (`no such module: vec0`). Go through
  Python with `sqlite_vec.load`, or read the shadow tables.

## 3. pHash and other cheap signals

| Signal | Table.column | How computed | Rows |
|---|---|---|---|
| pHash (64-bit) | `vision_cache.phash` | `imagehash.phash(img, hash_size=8)` — `core/hasher.py:6-22`, called `core/vision_cache.py:99` | 41,616 rows; **41,549 non-null**, 67 null; 40,557 distinct |
| pHash (dead) | `images.phash` | never populated | **0 / 42,136** |
| MD5-ish (dead) | `images.image_hash` | never populated | **0 / 42,136** |
| ahash/dhash/whash | — | `hasher.py:25-42` `compute_multiple_hashes` exists, **never persisted** | 0 |
| Dimensions / bytes / EXIF | `images.width`, `.height`, `.file_size`, `.iso`, `.aperture`, `.shutter_speed`, `.exif` | catalog read + `analyzer/image_inspect.py:15` `extract_exif` | schema `database/library_bootstrap_schema.py:5-37` |

**Would the stored hash distinguish black frames? No.** `imagehash.phash` runs a 32×32 DCT,
drops the DC term, and thresholds low-frequency coefficients against *their own median* —
absolute brightness is discarded by construction, and a uniform frame's bits are decided by
sensor noise. Verified:

```
2020-12-14__DSF1513      (mean L = 0.11)  phash = f4f8f8f4f068e0a0
2025-10-06_000191470003  (mean L = 16.34) phash = cf00ff01ff00ff40
rows with phash in ('0000000000000000','ffffffffffffffff','8000000000000000') → 1 of 41,549
```

Both look like ordinary busy-image hashes. **Do not build the detector on stored pHash.**

## 4. Descriptions

Live schema (`image_descriptions`; bootstrap `library_bootstrap_schema.py:47-64`, later columns
added at `db_init.py:177-180`):

```sql
CREATE TABLE image_descriptions (
    image_key TEXT PRIMARY KEY,
    image_type TEXT NOT NULL,
    summary TEXT DEFAULT '',
    composition TEXT DEFAULT '{}',
    perspectives TEXT DEFAULT '{}',
    technical TEXT DEFAULT '{}',
    subjects TEXT DEFAULT '[]',
    best_perspective TEXT DEFAULT '',
    model_used TEXT DEFAULT '',
    described_at TEXT,
    dominant_colors TEXT, mood_tags TEXT, has_repetition INTEGER,
    description_search_document TEXT
);
CREATE INDEX idx_desc_image_type ON image_descriptions(image_type);
```

**Row count: 41,112**, all `image_type='catalog'`, vs **42,136** images ⇒ **1,024 (2.4%)
undescribed**. FTS mirror `image_descriptions_fts` (migration `db_init_migrations.py:79`);
`description_search_document` non-null on all 41,112.

| Field | Shape | Coverage / distribution |
|---|---|---|
| `technical` | JSON, 4 keys: `dominant_colors`, `mood`, `lighting`, `time_of_day` | 17 distinct `lighting` values: `natural_side` 9,008, `overcast` 7,783, `natural_front` 6,326, `artificial` 4,712, `mixed` 3,918, **`low_light` 3,584**, `natural_back` 2,616, **`low_key` 1,231**, `golden_hour` 1,163, `blue_hour` 519, `high_key` 202, `unknown` 24, + 5 long-tail typos |
| `dominant_colors` | TEXT JSON hex array | **41,096** non-null — closest structured proxy (an all-dark palette) |
| `composition` | JSON: `layers[]`, `techniques[]`, **`problems[]`**, `depth`, `balance` | `problems[]` is free prose; **5,730** rows contain `underexpos` |
| `perspectives` | JSON `{slug: {analysis, score}}` — legacy, superseded by `image_scores` (ADR-0016) | present |
| `mood_tags` | TEXT JSON array | present |
| `has_repetition` | INTEGER 0/1 | present |

**No boolean or enum meaning "technically failed", "void", or "reject" exists.**
`low_light` / `low_key` are aesthetic labels, not failure flags — 4,815 rows carry them, far more
than the true void population.

**Prose baseline (why substring matching is insufficient):** only **52** rows match
`%black frame%` OR `%completely black%` OR `%nearly black%` OR `%entirely black%`, and the
matches are impure:

- true positive `2025-10-06_000191470003` — *"Nearly black frame with minimal visible detail; appears to be an underexposed or failed capture…"*
- true positive `2020-12-14__DSF1513` — *"A nearly completely black frame with a tiny, distant reddish-orange crescent…"*
- **false positive** `2020-06-07_DSCF9528` — *"…wearing glasses with red and **black frames**…"*
- **false positive** `2020-03-01__CC14735` — *"A photograph of a **framed** winter landscape painting…"*

Low recall *and* impure. Prose matching is a labelling aid, not a detector.

**Model/provider:** `ollama:kimi-k2.6:cloud` **41,095**, `ollama:gemma4:e2b` **16**,
`github_copilot:gemini-2.5-pro` **1**. Default at `providers.json`
`defaults.description = {provider: ollama, model: kimi-k2.6:cloud}`. Write helper
`database/descriptions.py:91` `store_image_description`; read `:157` `get_image_description`; gap
query `:182` `get_undescribed_catalog_images`.

**Related:** `image_scores` = 279,558 rows, 278,051 `is_current=1`, across **41,112 distinct
images** and 5 active perspectives (`perspectives`: 10 rows, 5 `active=1`, 4 `optional=1`).

## 5. The pipeline seam

**The eligibility function is `score_image_for_perspective` — `core/scoring_service.py:165`.**
Its precondition ladder at `:181-215` already contains the exact structural analogue of the gate
we want:

```python
# scoring_service.py:191-195
if os.path.splitext(filepath)[1].lower() in VIDEO_EXTENSIONS:
    return VisionOpOutcome(
        status="skipped",
        reason=f"Video file not scorable: {os.path.basename(filepath)}",
    )
```

**Insertion point: `lightroom_tagger/core/scoring_service.py:196`** — immediately after the video
check, before `get_perspective_by_slug` at `:197`. Returning
`VisionOpOutcome(status="skipped", reason=...)` is the sanctioned contract: ADR-0014 §2
(`docs/adr/0014-...md:28-35`) states pre-model non-attemptable conditions are `skipped`, are
recorded in batch checkpoints, and are **not** re-selected on resume — exactly the semantics a
void gate needs.

Other precondition sites: `:181` (`image_type`), `:184-186` (missing row/filepath), `:205-209`
(already-current score), `:213-215` (`resolve_vision_image` returned `None`).

**In-engine alternative:** `run_vision_op_persist(spec, pre_check=..., ...)` —
`core/vision_op.py:104`, `pre_check` param at `:107`, invoked `:112-115`. Scoring currently calls
it **without** `pre_check` (`scoring_service.py:152-156`), so the hook is free.
`description_service.py:130-145` shows the equivalent inline ladder for the describe pass.

| Layer | Location |
|---|---|
| Job type registration | `apps/visualizer/backend/jobs/registry.py:58` `JOB_TYPES`, `batch_score` `:87-95`; `JobType` dataclass `:46`; dispatch `get_job_handler` `:153` |
| Job handler (cancel scope) | `jobs/handlers/analyze.py:1302` `handle_batch_score` |
| Handler body | `analyze.py:1314` `_handle_batch_score_inner` |
| **Candidate selection** | `analyze.py:1340` → `jobs/handlers/common.py:107` `_select_catalog_keys(..., undescribed_only=False)` |
| Shared score pipeline | `analyze.py:877` `_run_score_pass` (triple expansion `:933-935`, already-current prefilter `:978-1000`) |
| Per-image call site | `analyze.py:112` `_score_single_image` → `:127` `score_image_for_perspective` |
| Combined describe→score | `analyze.py:1364` `handle_batch_analyze` → `:1378` inner; describe `_run_describe_pass` `:386`, score `:877` — **the between-passes seam lives inside `_handle_batch_analyze_inner`** |

**Cheapest batch-level gate:** exclude void keys in selection, mirroring how videos are excluded
— `common.py:11-22` `_CATALOG_NOT_VIDEO_SQL`, used at `common.py:136`/`:140` inside
`_select_catalog_keys` (`:107`). A `NOT EXISTS (SELECT 1 FROM <signal table> …)` clause there
means gated frames never occupy a worker slot. **Do both:** SQL exclusion for throughput, plus
the `scoring_service.py:196` precondition for correctness on single-image and CLI paths.

## 6. Write path for a new signal

`lightroom_tagger/core/database/` — 20 modules, 4,167 lines:

```
__init__.py                        296   barrel; re-exports everything (ADR-0008 §2)
db_init.py                         209   init_database() — schema + ordered migrations
db_init_migrations.py              353   _migrate_* functions
db_init_instagram_drop.py          177   one-off drop migration
db_init_drop_instagram_index.py     21   one-off drop migration
library_bootstrap_schema.py        102   BASE_LIBRARY_SCHEMA_SQL (7 CREATE TABLE)
catalog.py                         397   images read/write, generate_key, library_write
catalog_query.py                   364   filtered catalog listing
catalog_query_filters.py           159
catalog_query_best_score.py         68
catalog_statistics.py              165
catalog_write.py                   139
scores.py                          396   image_scores
descriptions.py                    291   image_descriptions + FTS
embeddings.py                       93   image_clip_embeddings (vec0)
similarity.py                      111   catalog_similarity_*
stacks.py                          351   image_stacks / image_stack_members
stack_suggestions.py               256   detect/pending/accept/reject  ← TEMPLATE
vision_cache.py                     97   vision_cache
insights_summary.py                122
```

**Migration mechanism.** No numbered migration files, no version table. `db_init.py:152`
`init_database(db_path)` runs, in fixed order: connection setup + `sqlite_vec` load
(`:155-157`), WAL / `busy_timeout=30000` / `synchronous=NORMAL` (`:158-170`);
`conn.executescript(BASE_LIBRARY_SCHEMA_SQL)` (`:172-174`, all `CREATE TABLE IF NOT EXISTS`);
column additions via `_migrate_add_column(conn, table, column, type)` (`:177-182`, helper
`db_init_migrations.py:23`, guarded by `_column_exists` `:18`); `_migrate_images_schema`
(`:186`); indexes (`:190-195`); the ordered idempotent table migrations (`:197-207`);
`seed_perspectives_from_prompts_dir` (`:207`); `commit()` (`:208`).
`_migrate_unified_image_keys` (`db_init_migrations.py:231`) is the only one gated on
`PRAGMA user_version` — a data remap, not a DDL add.

**To add a table:** write `_migrate_<name>(conn)` in `db_init_migrations.py` using
`conn.executescript` with `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`,
re-export from `database/__init__.py`, and add one call to `db_init.py`'s ordered list. **Copy
`_migrate_catalog_similarity_rejections` — `db_init_migrations.py:179-194`** (composite PK,
`CHECK`, `*_at TEXT NOT NULL DEFAULT (datetime('now'))`, one index), or
`_migrate_catalog_similarity` `:197-229` for a parent/child two-table shape.

**To add a column:** one line,
`_migrate_add_column(conn, 'image_descriptions', 'void_score', 'REAL')` alongside
`db_init.py:177-182`.

**Conventions:**

- snake_case, subject-prefixed: `image_*` (per-image) or `catalog_*` (derived/job-scoped).
- `image_key TEXT` referencing `images.key`; pairs stored lexicographically normalised with
  `CHECK (key_a < key_b)` (`db_init_migrations.py:189`) and a `normalize_image_pair` helper
  (`stack_suggestions.py:90`).
- Timestamps `TEXT` ISO-8601, `DEFAULT (datetime('now'))` or explicit
  `datetime.now(timezone.utc).isoformat()`. Booleans `INTEGER NOT NULL DEFAULT 0`. JSON `TEXT`
  via `_serialize_json` (`db_init.py:63`).
- Indexes `idx_<table>_<cols>`, `DESC` on recency columns.
- Read helpers return **detached** `dict(row)` / scalars / lists — never live `sqlite3.Row`
  (ADR-0008 §3). Enforced by `test_library_db_read_guardrail.py` (table regex `:26-37`).
- Writers document `"""… Call inside :func:`library_write`."""` (`stack_suggestions.py:135`,
  `:163`, `:211`; `embeddings.py:20`).
- Lifecycle via `managed_library_db` only (ADR-0011), enforced by
  `test_db_lifecycle_guardrail.py`.
- **Line budget: core `.py` ≤ 400 lines** — `test_architecture.py:31`, `:121`.

**Best module to copy: `lightroom_tagger/core/database/stack_suggestions.py`** (256 lines) —
precisely the detect/pending/accept/reject shape to mirror:

| Element | Line |
|---|---|
| Threshold constant with an issue-referencing rationale comment | `:18-19` `BLANK_FRAME_SCORE_FLOOR = 4.5` |
| Module-level parameterised SQL constant | `:21` `_PENDING_PAIRS_SQL` |
| Key normaliser | `:90` `normalize_image_pair` |
| Predicate | `:98` `is_blank_frame_catalog_key`, `:104` `is_catalog_similarity_pair_rejected` |
| Reject write | `:119` `reject_catalog_similarity_pair` (`INSERT OR IGNORE`) |
| Accept mutation | `:206` `stack_accept_suggestion_pair` |
| Pending count / page | `:233` `count_pending_stack_suggestions`, `:242` `list_pending_stack_suggestions` |
| Test template | `core/test_database_stack_suggestions.py` |

## 7. Existing image-analysis utilities

**Declared** (`pyproject.toml:26-43`): `pillow>=10.0.0`, `ImageHash>=4.3.0`, `rawpy>=0.26.1`,
`sentence-transformers>=3.0.0`, `sqlite-vec==0.1.9`, `ollama>=0.1.0`, `openai>=1.0.0`,
`pydantic`, `pyyaml`, `requests`, `tqdm`, flask stack. **NumPy is not declared** (transitive via
torch / sentence-transformers). No OpenCV, scikit-image, or pyvips. Dev extras `:46-52`: pytest,
pytest-cov, black, ruff, mypy.

**Actually importable in `.venv`** (Python 3.12.13):

| Package | Version |
|---|---|
| pillow | **12.2.0** |
| numpy | **2.4.4** |
| ImageHash | **4.3.2** |
| rawpy | **0.26.1** |
| torch | 2.11.0 |
| sentence-transformers | 5.4.1 |
| transformers | 5.6.2 |
| scipy | 1.17.1 |
| PyWavelets | 1.9.0 |
| sqlite-vec | 0.1.9 |
| ollama | 0.6.1 |
| opencv-python / -headless | **MISSING** |
| scikit-image | **MISSING** |
| pyvips | **MISSING** |
| open_clip_torch | **MISSING** |

**Binaries:** `ffmpeg 8.1` and `ffprobe` at `/opt/homebrew/bin` — present, undeclared, unused by
the codebase. `vips` and `exiftool` absent.

**Existing pixel-opening code to reuse:**

| Function | Location | What it does |
|---|---|---|
| `compress_image` | `analyzer/image_prep.py:14-66` | `Image.open` `:42`, RGB convert `:45`, `thumbnail(LANCZOS)` `:49`, save q80 `:54` |
| `convert_raw_to_jpg` | `image_prep.py:69-113` | `rawpy.imread` + `postprocess(use_camera_wb=True, half_size=True)` `:88-89`, 3 retries on `LibRawIOError` for NAS flakiness `:100-105` |
| `get_viewable_path` / `_managed` | `image_prep.py:116` / `:132` | RAW → `.JPG` sidecar → temp JPEG; `_managed` returns `(path, is_temp)` ownership |
| `compute_phash` | `hasher.py:6-22` | `Image.open` + `imagehash.phash` |
| `compute_multiple_hashes` | `hasher.py:25-42` | phash/ahash/dhash/whash — unused, unpersisted |
| `batch_compute_hashes` | `hasher.py:45-65` | serial loop over paths |
| `extract_exif` | `analyzer/image_inspect.py:15-32` | Pillow `_getexif`, whitelisted tags |
| `encode_images` | `clip_embedding_service.py:21-41` | `Image.open(p).convert("RGB")` `:29`, batched CLIP encode |
| `RAW_EXTENSIONS` / `VIDEO_EXTENSIONS` | `image_prep.py:6-7` | 12 RAW, 11 video extensions |

**Nothing computes luminance, histograms, or exposure statistics.** A grep across
`lightroom_tagger`, `apps` and `scripts` for `ImageStat|\.histogram\(|convert\('L'\)` returns
zero hits outside `imagehash`'s internals.

## 8. Vision ops (ADR-0014)

**Registration mechanism: there is no registry** — a spec-builder convention plus a static
guardrail.

- `VisionOpSpec` dataclass — `core/vision_op.py:28-45` (`resolve_kind`, `operation`,
  `provider_id`, `model`, `fn_factory`, `parse_response`, `log_callback`, `registry`,
  `error_policy`, `abort_tracker`, `_cleanup`).
- Engine `run_vision_op(spec)` — `vision_op.py:67-101`: `resolve_model` `:70-74` →
  `FallbackDispatcher.call_with_fallback` `:86-93` → parse `:94-97` → `_cleanup` in `finally`
  `:99-101`. Parser arity sniffed by `_parser_wants_provider_model` `:48`.
- Persist wrapper `run_vision_op_persist(spec, pre_check, accept_result, persist)` —
  `vision_op.py:104-121`; returns `VisionOpOutcome` (`:18`, `wrote` property `:23`).
- ADR-0014 §3: *"Op definitions live in `analyzer`."* Guardrail `core/test_vision_op_guardrail.py`
  rejects an inline `resolve_model → FallbackDispatcher → call_with_fallback` outside
  `vision_op.py`.

**Currently registered vision ops — exactly two:**

| `operation` | Builder | file:line |
|---|---|---|
| `"describe"` | `build_description_op_spec` | `analyzer/description.py:148` (`operation="describe"` `:150`) |
| `"score"` | `build_score_op_spec` | `analyzer/scoring.py:104` (`operation="score"` `:106`) |

Both exported via the `analyzer/__init__.py` barrel (`:15`, `:19`). The
`build_compare_op_spec` / `build_compare_batch_op_spec` ops named in ADR-0014 §3 were **deleted**
in `f18c2ba` — the ADR text is now stale on that point.

**To add an op:** (1) new submodule under `core/analyzer/` with
`build_<op>_op_spec(path, *, …) -> VisionOpSpec` (copy `analyzer/scoring.py:47-116`); (2) export
from `analyzer/__init__.py`; (3) a service assembling the spec and calling
`run_vision_op_persist` with `pre_check` / `accept_result` / `persist` (copy
`scoring_service.py:81-162`); (4) optionally a `JobType` in `registry.py:58`. **ADR-0014 §6 notes
embedding generation is explicitly outside the engine — a pixel-statistic detector likewise does
not belong in it.**

**Ollama invocation:** OpenAI-compatible client from `ProviderRegistry`. `providers.json`
`ollama`: `base_url_env: OLLAMA_HOST`, `base_url_default: http://localhost:11434/v1`,
`api_key: "ollama"`, `auto_discover: true`, `request_timeout_seconds: 300`,
`retry.max_retries: 2`,
`model_order: [kimi-k2.6:cloud, kimi-k3:cloud, gemma4:31b-cloud, gemma4:e2b, gemma4:26b, kimi-k2.5:cloud]`.
`fallback_order: [ollama, github_copilot, omlx, nvidia_nim, opencode_go]`. Calls route
`fn_factory` → `vision_client.generate_description` (`analyzer/scoring.py:76-86`). A native
`/api/chat` path exists for image payloads: `core/vision_client_ollama.py:110` `native_chat`,
`:33` `is_ollama_client`, `:42` `native_chat_url`, `:50` `content_to_native`, error mapping
`:95-107`, `:141-154`.

**Per-image vision cost — not on the table.** There is **no per-image timing instrumentation**
in the codebase (`perf_counter` / `elapsed` / `duration_ms` appear nowhere in
`lightroom_tagger` or the backend outside `app.py` heartbeats at `:291-347`). Wall-clock derived
from `apps/visualizer/visualizer.db` (`jobs.started_at` / `completed_at` + `result` JSON; the
column is `type`, not `job_type`), 4 workers (`config.yaml:4`):

| Run | Wall clock | Units | Per unit |
|---|---|---|---|
| `batch_describe` 2026-08-03T19:04 | 2,908 s | 1,887 described (987 skipped, 42,082 total) | **≈1.54 s/image** |
| `batch_score` 2026-07-17T16:40 | 4,251 s | 5,218 scored | **≈0.81 s/call** |
| `batch_analyze` (n=11) | avg 1,386 s | — | — |
| `single_describe` (n=8) | avg 118.6 s | 1 image | 40–403 s observed, `github_copilot:gpt-5-mini` |
| `single_score` (n=2) | avg 225.9 s | 1–3 perspectives | 151 s, 301 s |
| `batch_embed_image` (n=2) | avg 3,350 s | CLIP pass | — |

Note the default description model `ollama:kimi-k2.6:cloud` is a **cloud** model behind the
Ollama endpoint, not local weights — these figures are network-bound, and a genuinely local
model (`gemma4:e2b`, 16 rows) is untimed at scale.

**Extrapolation: 42,136 × 1.54 s ≈ 18 hours** for one vision call per image, versus **57 s** for
the Pillow luminance pass — a ~1,100× ratio. A per-image vision call is viable only for
adjudicating a small shortlist (≈500 borderline frames ≈ 13 min).

## 9. Test fixtures

**Library tests — co-located** with modules under `lightroom_tagger/core/` as `test_*.py`
(`lightroom_tagger/CONTEXT.md:91`). Relevant: `test_scoring_service.py`,
`test_database_stack_suggestions.py`, `test_database_vision_cache.py`,
`test_database_descriptions.py`, `test_database_scores.py`, `test_database_embeddings.py`,
`test_vision_op.py`, `test_architecture.py`. There is **no `conftest.py`** under
`lightroom_tagger/`.

**Backend tests** — `apps/visualizer/backend/tests/test_*.py` (58 files). `tests/conftest.py:14-19`
has one autouse fixture creating `tmp_path/'library.db'` and setting `LIBRARY_DB`;
`collect_ignore = ["e2e"]` at `:11`.

**No pytest fixture factories, no factory_boy.** The convention is plain module-level `_helper()`
functions writing into a **real** DB built by `init_database(str(tmp_path / "library.db"))`:

| Factory | Location |
|---|---|
| `store_image(db, {date_taken, filename, filepath, …}) -> key` | `database/catalog.py:91` |
| `insert_image_score(db, {image_key, image_type, perspective_slug, score, …})` | `database/scores.py:155` |
| `store_image_description(db, record)` | `database/descriptions.py:91` |
| `store_vision_cached_image(db, key, compressed_path, phash, mtime)` | `database/vision_cache.py:27` |
| `upsert_image_clip_embedding(db, key, blob)` | `database/embeddings.py:17` |
| local `_score(conn, image_key, score)` | `test_database_stack_suggestions.py:27-42` |
| local `_unit_axis(dim)` → 512-d vec0 blob | `test_database_stack_suggestions.py:22-25` |
| local `_seed_described_image(db, key='cat_001', …)` | `backend/tests/test_descriptions_api.py:21` |

`test_database_stack_suggestions.py:45-60` is the shape to copy for a detector test.

**Gap: no fixture anywhere synthesises real image pixels.** A pixel detector's tests must either
(a) write small JPEGs with Pillow into `tmp_path` — no precedent in the repo, you'd be
establishing it — and seed matching `vision_cache` rows via `store_vision_cached_image`, or
(b) inject the statistic and test only the thresholding and gating logic. Recommend (a) for the
reader and (b) for the gate.

## Cheapest viable detector given what exists

Read the already-cached JPEG, compute mean luminance plus a high-percentile brightness,
threshold, persist one row per image. No new pass over the NAS, no vision call, no new
dependency. `classify_path` (`path_diagnostics.py:58`) hands you a local path cache-first for
41,549 of 42,136 keys with the NAS offline; `Image.open(p)` + `im.draft('L', (128,128))` +
`ImageStat.Stat` costs **1.36 ms/image ⇒ ~57 s for the whole catalog single-threaded**, and
separates cleanly on real data (confirmed voids at mean L 0.11 and 16.34 versus 175 for a normal
frame; sample p1 ≈ 14).

Persist to a new table (`image_key` PK, the statistics, a verdict, a timestamp, a reviewed flag)
added as a `_migrate_*` on the `_migrate_catalog_similarity_rejections:179` template, with helpers
in a new `database/` module copied from `stack_suggestions.py`'s detect/pending/accept/reject
shape. Gate in two places: exclude flagged keys in `_select_catalog_keys` (`common.py:107`,
alongside `_CATALOG_NOT_VIDEO_SQL` at `:11`) so they never take a worker slot, and add the
precondition at `scoring_service.py:196` returning
`VisionOpOutcome(status="skipped", reason="void frame")` so single-image and CLI paths are
covered too.

Use the two free ancillary signals for validation and threshold tuning only, never as the primary
discriminator: the 52 prose hits and 5,730 `underexpos` mentions in `composition.problems[]` give
a roughly-labelled set to calibrate against, and `encode_text_for_clip`
(`clip_embedding_service.py:44`) scores all 41,566 stored vectors against text prompts in
seconds. Reserve a vision call for adjudicating a few hundred borderline frames (~13 min), and
mark the 1,041 images without local pixels as `unknown` rather than guessing.

---

*Created using Anthropic Claude. This line should stay on internal versions until a human has
reviewed and verified the content.*
