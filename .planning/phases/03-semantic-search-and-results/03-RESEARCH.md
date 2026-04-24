# Phase 3: Semantic Search & Results — Research

**Researched:** 2026-04-23  
**Status:** RESEARCH COMPLETE

## Summary

**sqlite-vec 0.1.9 is on PyPI** and loads in Python via `sqlite_vec.load(conn)` after `enable_load_extension(True)`. Use a **`vec0` table** with `float[768] distance_metric=cosine` for **all-mpnet-base-v2**, store/query vectors as **float32 blobs** (`serialize_float32` or `numpy.astype(np.float32)`). **RRF (k=60)** should be computed in Python from two **ordered rank lists**: FTS ordered by **`bm25()` ascending** (lower = more relevant), semantic ordered by **sqlite-vec `distance` ascending** (lower = closer in cosine distance). The **exact text to embed** is already centralized: reuse **`description_search_document`** from the DB or rebuild with **`build_description_search_document(summary, subjects)`** — no LLM. Batch work should mirror **`batch_describe`**: `runner.update_progress(job_id, pct, message)`, checkpoint + **`fingerprint_*`** in `checkpoint.py`, and register **`batch_text_embed`** in **`JOB_TYPES_REQUIRING_CATALOG`** and **`JOB_HANDLERS`**.

---

## 1. sqlite-vec Extension Loading & Schema

### Loading at connection time (stdlib `sqlite3`)

From upstream [Python usage docs](https://github.com/asg017/sqlite-vec/blob/main/site/using/python.md):

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect(db_path)
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)  # optional hardening after load
```

Verify with `SELECT vec_version();`.

**Platform note (macOS):** Apple-shipped Python/SQLite often **omits** `enable_load_extension`. The project already targets Homebrew/modern Python per `AGENTS.md`; document this in runbooks if users hit `AttributeError`.

**SQLite version:** **≥ 3.41 recommended** for some KNN/`LIMIT` patterns; check `sqlite3.sqlite_version`.

### `vec0` DDL for 768-dim float32 + catalog key

From [vec0 feature docs](https://github.com/asg017/sqlite-vec/blob/main/site/features/vec0.md) and [KNN docs](https://github.com/asg017/sqlite-vec/blob/main/site/features/knn.md):

- Declare the embedding column as **`float[768]`** with **cosine** distance (matches sentence-transformers / mpnet usage; see §2).

```sql
CREATE VIRTUAL TABLE image_text_embeddings USING vec0(
  embedding float[768] distance_metric=cosine,
  image_key TEXT
);
```

**Planner discretion:** Using **`image_key` as a metadata column** keeps lookups stable (no dependence on `image_descriptions.rowid`). Alternative: integer `rowid` linkage — **avoid**; rowids are not a stable public key across VACUUM-style operations the same way `image_key` is.

### KNN query pattern

```sql
SELECT image_key, distance
FROM image_text_embeddings
WHERE embedding MATCH ?
  AND k = ?
```

Bind the query vector as the same blob format used on insert (JSON string of floats, or packed float32 blob per §2).

**Metric choice:** **`distance_metric=cosine`** aligns with **all-mpnet-base-v2** (trained/evaluated with cosine). Default vec0 metric is **L2**; **do not** rely on L2 unless you skip normalization and accept a different geometry.

### INSERT / UPDATE (upsert)

`vec0` behaves like a virtual table; there is no universal `ON CONFLICT` story documented as SQLite core UPSERT. **Practical pattern:**

1. `DELETE FROM image_text_embeddings WHERE image_key = ?`
2. `INSERT INTO image_text_embeddings(rowid, embedding, image_key) VALUES (?, ?, ?)` — or let sqlite-vec assign `rowid` and insert columns as supported by the build.

Confirm exact insert column list against the installed `sqlite-vec` version in a one-line integration smoke test.

### Serialization for storage

Use **`sqlite_vec.serialize_float32(list_or_iterable)`** or **`numpy` buffer** with **`.astype(np.float32)`** — vectors must be **768 × 4 bytes**.

### PyPI version

**Confirmed:** `pip index versions sqlite-vec` lists **0.1.9** (among others). REQUIREMENTS.md implementation guidance already cites **sqlite-vec 0.1.9**.

---

## 2. sentence-transformers Embedding API

### Encoding API

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
vectors = model.encode(
    texts,  # str or list[str]
    batch_size=32,
    normalize_embeddings=True,
    show_progress_bar=False,
    convert_to_numpy=True,
)
# vectors.shape == (n, 768), dtype float32 when convert_to_numpy=True
```

### Normalization

**`normalize_embeddings=True`** yields **unit L2** vectors → **cosine similarity = dot product**, and **cosine distance** from sqlite-vec stays in a well-behaved range (see `vec_distance_cosine` in [api-reference](https://github.com/asg017/sqlite-vec/blob/main/site/api-reference.md)).

### Batch size (CPU)

Start **`batch_size=16`–`32`** on CPU; tune with wall-clock and RSS. sentence-transformers batches sentences internally; very small batches waste overhead, very large batches can spike memory.

### Model download / cache

First run downloads weights to the **Hugging Face / sentence-transformers cache** (typically under **`~/.cache/`** — often `hub` / `torch` subtrees depending on install). Offline environments must pre-cache.

### Serialization for sqlite-vec

Per-row: `blob = sqlite_vec.serialize_float32(vec.tolist())` or pass **`vec.astype(np.float32)`** where the driver accepts buffer protocol.

---

## 3. FTS5 + Vector Hybrid Search (RRF)

### FTS5 ranked list with BM25

SQLite FTS5 **`bm25(table)`**: **lower scores = more relevant** (sort **`ORDER BY bm25(image_descriptions_fts) ASC`**). This matches common SQLite FTS5 examples.

**Important:** Project catalog queries today use FTS as a **boolean filter** (`MATCH` inside `EXISTS` / `IN`), **not** a ranked list. Phase 3 needs a **dedicated FTS SELECT** that returns **`image_key`** (via join `image_descriptions_fts.rowid = image_descriptions.rowid`) **ordered by bm25**.

### Building rank positions for RRF

For each list independently:

1. Sort by relevance (FTS: bm25 asc; vec: distance asc).
2. Assign **rank 1** to the best row, **rank 2** to the next, etc.

**Do not** feed raw bm25 or cosine distance into `1/(k+rank)` — RRF uses **integer ranks**, not scores.

### RRF fusion in Python (k=60)

```python
K = 60

def rrf_score(ranks_by_source: dict[str, int]) -> float:
    return sum(1.0 / (K + r) for r in ranks_by_source.values())

# For each candidate image_key, collect ranks from each list it appears in.
# Keys appearing in only one list still contribute one term (D-07 / standard RRF).
```

Sort final keys by **RRF score descending**; tie-break deterministically (e.g. `image_key`).

### Semantic list scope

Per **D-09**, KNN only includes **embedded** catalog images. FTS list may include **any** catalog row with matching FTS row. RRF naturally handles **FTS-only** hits (semantic rank missing → only FTS term).

### When there are no embeddings at all

Semantic branch returns **no candidates** → RRF scores collapse to FTS-only contributions. Response **metadata** should still expose **`missing_embeddings_count`** (and optionally a boolean like **`semantic_index_empty`**) so Phase 5 can show degradation copy without inferring it from scores.

---

## 4. Existing Batch Job Pattern

### `create_new_job` (`apps/visualizer/backend/api/jobs.py`)

- Validates body has **`type`**, optional **`metadata`**.
- If `type in JOB_TYPES_REQUIRING_CATALOG`, calls **`describe_library_db()`** and returns **422** when catalog DB missing.
- **`create_job` → `get_job`**, returns **201** with job dict.

**Phase 3:** add **`batch_text_embed`** to **`JOB_TYPES_REQUIRING_CATALOG`** (`library_db.py`) and **`JOB_HANDLERS`** (`handlers.py`).

### Progress reporting (`JobRunner.update_progress`)

```73:82:apps/visualizer/backend/jobs/runner.py
    def update_progress(self, job_id: str, progress: int, current_step: str):
        """Update job progress. No-op if the job has been cancelled or already completed."""
        if self.is_cancelled(job_id):
            return
        row = get_job(self.db, job_id)
        if row and row.get('status') in ('completed', 'cancelled'):
            return
        update_job_status(self.db, job_id, 'running', progress=progress, current_step=current_step)
        add_job_log(self.db, job_id, 'info', current_step)
        self.emit_progress(job_id, progress, current_step)
```

Handlers pass **`progress` 0–100** and a short human **`current_step`** string (also duplicated into job logs). No separate “callback object” — call **`runner.update_progress`** directly from the embedding loop.

### Checkpoint / cancel pattern

**`batch_describe`** (`_run_describe_pass` in `handlers.py`):

- **`fingerprint_batch_describe(metadata, selection)`** for stale checkpoint detection.
- **`processed_pairs`** stored under `metadata["checkpoint"]` with **`checkpoint_version: 1`**.
- **`cancel_scope.install(lambda: runner.is_cancelled(job_id))`** on sequential path; **per-worker** install for thread pool path.
- **`runner.persist_checkpoint` / `runner.clear_checkpoint` / `runner.complete_job`**.

**Phase 3:** add **`fingerprint_batch_text_embed`** (new in `checkpoint.py`) including knobs like **`force`**, selection fingerprint, and **embedding model id / dim** so model changes invalidate checkpoints.

---

## 5. Semantic Search API Shape

### Endpoint

Recommend **`POST /api/images/semantic-search`** (parallel to **`POST /api/images/nl-search`**, `images` blueprint).

### Request body

Minimal:

```json
{
  "query": "moody cityscapes at night",
  "limit": 50,
  "offset": 0
}
```

Optional later (not required by D-12 / Phase 3 scope lock): structured **`filters`** mirroring `query_catalog_images` — only if product wants semantic + facet filters in one hop. Context decisions already separate NL filters (`nl-search`) from semantic hybrid.

### Response shape (vs `nl-search`)

Phase 2 contract:

```616:620:apps/visualizer/backend/api/images.py
        return jsonify({
            'filters': filters.model_dump(exclude_none=True),
            'total': total,
            'images': images,
        })
```

**Semantic search** should **omit `filters`** and add **`metadata`**:

```json
{
  "total": 123,
  "images": [ /* catalog-shaped rows + extras */ ],
  "metadata": {
    "missing_embeddings_count": 42,
    "k": 60
  }
}
```

Field name **`missing_embeddings_count`** matches **03-CONTEXT D-09/D-11** naming intent.

### Per-row fields (NLS-04 data contract)

Base transform: reuse **`_rows_to_catalog_api_images`** pattern from `images.py`, then extend each row with:

- **`score`**: final **RRF** score (float) — document that it is **not** a probability.
- **`why_matched`**: template string from **D-10** (FTS rank / semantic distance / both; no LLM).

**Thumbnails:** catalog list rows today expose `key`, `filepath`, etc.; thumbnail delivery is via **`GET /api/images/catalog/<image_key>/thumbnail`**. For NLS-04, add a computed **`thumbnail_url`** (relative URL string) for Phase 5 convenience, e.g. **`/api/images/catalog/{key}/thumbnail`**.

---

## 6. Text Alignment (FTS5 ↔ Embeddings)

### Canonical text

**`build_description_search_document`** implements Phase 1 **D-06** (summary + space-joined subjects):

```230:247:lightroom_tagger/core/database.py
def build_description_search_document(summary: str, subjects_json_or_obj: object) -> str:
    """Build normalized full-text for summary + subjects (D-06)."""
    part = re.sub(r"\s+", " ", (summary or "").strip())
    ...
    joined = " ".join(s for s in subj if isinstance(s, str))
    ...
    return f"{part} {joined}"
```

### Persisted copy

**`store_image_description`** writes **`description_search_document`** for `image_type == "catalog"` using the same helper — this is what FTS indexes.

### Embed-time source of truth (no LLM)

For each catalog image in **`batch_text_embed`**:

1. **Preferred:** `SELECT description_search_document, summary, subjects FROM image_descriptions WHERE image_key = ? AND image_type = 'catalog'`
2. If `description_search_document` is **NULL** but summary exists, fall back to **`build_description_search_document(summary, subjects)`** in Python.
3. **Skip / log** rows with no usable text (empty document) — they cannot be embedded meaningfully.

This guarantees **embedding text ≡ FTS document** whenever the denormalized column is populated.

---

## 7. Test Patterns

### Deterministic hybrid / RRF tests

**Never** call the real `SentenceTransformer` in unit/integration tests for ranking assertions. Instead:

- **Stub `encode`** to return **fixed** `numpy` vectors (e.g. three images: orthogonal or controlled cosine distances).
- Insert matching **vec0** rows + FTS rows using **`init_database`** + **`store_image_description`** (maintains FTS).
- Call a **pure Python** function **`rrf_fuse(fts_ranks, vec_ranks, k=60)`** tested in isolation with hand-built rank dicts.
- **Golden tests:** small fixed queries where FTS ranks are driven by **`bm25`** ordering on seeded `description_search_document` text.

### Minimum scenario matrix

| Case | Assert |
|------|--------|
| (a) Pure embedding | Query vector closest to one row; others far; FTS returns empty or low rank — winner still surfaces via semantic rank |
| (b) Pure FTS | Rare token only in one `description_search_document`; stub encoder returns **identical** vectors → ties broken by FTS rank contribution |
| (c) Both contribute | Two candidates: A wins FTS, B wins semantic; RRF ordering matches hand-computed `1/(60+r)` sum |
| (d) Degradation | Zero rows in vec0 table; metadata **`missing_embeddings_count`** equals catalog-described minus embedded; ordering equals FTS-only ranking path |

### File patterns to mirror

- **`apps/visualizer/backend/tests/test_images_nl_search_api.py`** — Flask `test_client`, `monkeypatch` `LIBRARY_DB`, mock heavy deps.
- **`apps/visualizer/backend/tests/test_images_catalog_api.py`** — `init_database` + `store_image` + `store_image_description` fixtures.

Add **`test_images_semantic_search_api.py`** with mocked embedding backend.

---

## 8. Same-DB `vec0` Confirmation

- **Same file:** sqlite-vec is a **loadable extension**; **`vec0` virtual tables** live in the **same SQLite database** as normal tables. This matches **D-01** (single `.db`).
- **WAL:** WAL is a **database-wide journal mode**. Mixing normal tables and `vec0` does not imply a separate WAL. Standard caveats: **one writer**; long-running embedding jobs should use the same **`library_write` / connection discipline** as other catalog mutators.
- **Backup:** copying the `.db` file should include vectors; verify with **`VACUUM`** / backup procedures in CI if you rely on file snapshots.

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **macOS / stock Python lacks `enable_load_extension`** | Document supported Python builds; optional CI matrix entry |
| **sqlite-vec pre-1.0 API drift** | Pin **`sqlite-vec==0.1.9`**; smoke test `CREATE VIRTUAL TABLE` + `MATCH` in pytest |
| **FTS rank query shape drift** | Isolate FTS rank SQL in one helper; test bm25 ordering on toy corpus |
| **RRF confusion with raw scores** | Code review: ranks are integers; separate “display similarity” from RRF |
| **Embedding memory on large catalogs** | Batch commits; tune `batch_size`; consider periodic `commit` in job loop |
| **D-09 “excluded from semantic”** | KNN candidate set is embedded-only; document that FTS can still retrieve unembedded images unless you add an explicit post-filter |

---

## Planning Recommendations

Suggested **wave structure** for the planner:

1. **Schema + init + migration** — `init_database`: load sqlite-vec, create `vec0` table + index hygiene; idempotent migration gated on `user_version` (mirror `_migrate_image_descriptions_fts`).
2. **Embedding module** — thin wrapper around `SentenceTransformer` (not `ProviderRegistry`, per **D-04**); pure functions for “text → float32 blob”.
3. **`batch_text_embed` job** — selection SQL (catalog + described + optional force), checkpoint + fingerprint, `update_progress` cadence, vec0 upsert/delete.
4. **Search service** — FTS ranked query helper, KNN query helper, RRF fusion + `why_matched` templates + `missing_embeddings_count` computation.
5. **`POST /api/images/semantic-search`** — validation (`query` non-empty), wire search service, response mapping with **`score` / `why_matched` / `thumbnail_url`**.
6. **Tests** — RRF unit tests, mocked encoder API tests, one integration test with real sqlite-vec extension if CI allows loading extensions.

---

## RESEARCH COMPLETE
