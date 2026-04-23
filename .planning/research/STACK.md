# Stack Research — v3.0 Intelligent Discovery

**Audience:** Requirements and roadmap (v3.0 natural language search, stacking, visual facets, similarity).  
**Verified:** Library versions checked against PyPI via `pip index versions` on **2026-04-23** (authoritative for “current” in this doc).

---

## New Dependencies Required

| library | version | purpose | why not alternatives |
|--------|---------|---------|----------------------|
| **sqlite-vec** | **0.1.9** (latest stable on PyPI; pre-releases e.g. 0.1.10a* exist) | Store **dense vectors** (text + image embeddings) in SQLite with KNN search (`vec0` virtual tables + distance functions) | **sqlite-vss**: same author ecosystem but **maintenance effort moved to sqlite-vec**; VSS wraps Faiss → heavier deploy story. **External vector DB** (Pinecone, Qdrant server): ops and sync cost for a single-user / local-first catalog. **pgvector**: forces Postgres alongside existing SQLite — big migration. |
| **sentence-transformers** | **5.4.1** | **Local text embeddings** for semantic search over descriptions/keywords; batch encoding in jobs | **OpenAI-only embeddings**: fine for cloud but adds cost/latency and ties offline use to API; keep as optional path via existing `openai` stack. **Bare `transformers`**: more plumbing; ST is the standard ergonomic layer. |
| **torch** | **2.11.0** (pin per platform/CUDA separately) | Backend for ST and CLIP-style image models | **ONNX-only** path: possible later for smaller deploys, but two parallel inference stacks early = overkill. |
| **open-clip-torch** | **3.3.0** | **Image embeddings** (CLIP-style) for “more like this”; well-supported checkpoints | **Original OpenAI CLIP repo only**: fewer maintained packaging options. **timms** / **timm** + custom heads: more assembly. **sentence-transformers `[image]`**: viable for some multimodal models; open_clip is the common default for “CLIP vec + proven checkpoints”. |
| **numpy** | **2.4.4** | Vector math, batch stack features, bridge to sqlite-vec blobs | Avoid duplicating with ad-hoc lists; already a transitive dep of ML stack. |
| **scipy** | **1.17.1** | Distances, linkage, optional graph-free helpers for clustering / validation | Full **RAPIDS** / **cuML**: GPU cluster only, huge dep for burst grouping. |
| **scikit-learn** | **1.8.0** | **pHash / feature clustering** (e.g. DBSCAN on Hamming or embedded space), optional hierarchy for stacks | **hdbscan** **0.8.42**: only if density-based clustering proves better than time-window + DBSCAN; add when metrics justify, not day one. |
| **openai** | **2.32.0** | **LLM-to-SQL** and **cloud embeddings** using the same pattern as today’s vision/LLM calls | Already implied by `provider_registry` + vision; pin for structured-output / tool use in query layer. |

**Transitive (do not pin unless resolution forces it):** `transformers`, `huggingface-hub`, `tqdm`, `Pillow` (already in backend requirements for images).

**Optional / phase later**

| library | version | when | why not now |
|--------|---------|------|-------------|
| **hdbscan** | 0.8.42 | If pHash clusters are noisy and DBSCAN tuning fails | Extra C++ dependency chain on some platforms. |
| **sqlparse** | (latest) | If you want **SQL lint/allowlist enforcement** after LLM generation | Can start with strict AST allowlists without it. |

---

## SQLite Extensions

### FTS5 (full-text search)

- **Setup:** **No third-party extension.** FTS5 ships with SQLite and is available in Python’s `sqlite3` when linked against a standard build (typical on macOS/Linux/Windows CPython).
- **Usage:** `CREATE VIRTUAL TABLE ... USING fts5(...)` — index `image_descriptions` text fields (and/or denormalized combined doc), optionally **external content** or **contentless** with manual `INSERT INTO fts(fts, ...)` on row changes.
- **Why:** Lexical retrieval for keywords and named entities; pairs with semantic search (hybrid ranking: RRF or weighted sum) for “moody cityscapes”-style queries where FTS catches tokens and embeddings catch vibe.
- **Not needed:** SQLite **FTS3/4** for new work; spellfix1 unless product wants typo tolerance.

### Vector storage (sqlite-vec vs others)

| Option | Notes |
|--------|--------|
| **sqlite-vec** | **Recommended** for v3: one file with catalog + library data, matches current **WAL + single-file** deployment, KNN in-process, `pip install sqlite-vec` loads extension. |
| **sqlite-vss** | **Avoid for new work:** maintenance focus shifted to sqlite-vec; Faiss payload = larger binary story. |
| **In-app numpy brute force** | OK for tiny dev sets; **does not scale** past low tens of thousands of images for interactive search. |
| **Dedicated vector SaaS** | **Defer** until multi-user or multi-machine sync is a requirement. |

**Caveat:** sqlite-vec is **pre-1.0**; pin versions in requirements and test extension load on target OSes in CI.

---

## Embedding Strategy

### Text embeddings (semantic natural language search)

- **Role:** Embed user query + embed existing **description/keyword/caption** fields (from `image_descriptions` and related text) into the **same model space** for similarity.
- **Recommended default — local:** `sentence-transformers` + a **small MTEB-competitive** model (e.g. bge-small / e5-family — **pick one** and lock for the release so dimensions stay stable in DB). Store dimension in schema metadata.
- **Optional — cloud:** **OpenAI** `text-embedding-3-small` / `large` via existing `openai` client and provider config for users who prefer API-only.
- **Why separate from image:** Text–text similarity answers “moody cityscapes” from **language**; image vectors answer **visual** “more like this.” Mixing without clear UX confuses ranking.

### Image embeddings (visual similarity)

- **Role:** **open_clip** (or ST multimodal where applicable) → fixed-dim vector per image; stored in sqlite-vec; query = vector of selected image.
- **Alignment with pHash:** **pHash** stays for **near-duplicate / burst** proximity; **CLIP** handles **semantic** similarity (subject, style) that Hamming distance misses. Use both in product: different entry points (stacking vs “similar looks”).

### LLM-to-SQL (structured query)

- **Not an “embedding library”:** Use **chat completion** via `ProviderRegistry` (Ollama / GitHub Copilot / OpenAI-compatible) with **JSON schema or tool** output, then **validate** SQL against an allowlist (tables/columns/joins).
- **Why:** Converts natural language to **filters** (`date_taken`, `rating`, `keywords`, new facet columns) combined with FTS + vector subqueries.

---

## What NOT to Add

| Avoid | Reason |
|-------|--------|
| **Postgres + pgvector** | Valid at scale; v3.0 doubles storage/ops for this app’s validated SQLite-centric design. |
| **Elasticsearch / OpenSearch** | Powerful FTS + analytics; redundant if FTS5 + embeddings cover search **TAM** for a local catalog. |
| **sqlite-vss** for greenfield | Superseded by sqlite-vec for new projects per maintainer direction. |
| **Pinecone / Weaviate / Chroma server** | Another process to ship, secure, and sync; use sqlite-vec until corpus or multi-user sync forces external search. |
| **faiss-cpu** directly | Unless you abandon sqlite-vec for custom ANN; sqlite-vec already covers in-file KNN. |
| **Heavy “unified multimodal embedding”** for text+image in one model | Harder to tune; split models match feature ownership (NL search vs visual match). |
| **AutoGraph / full ORM query builder for LLM SQL** | Risky; narrow, audited SQL templates + allowlists are safer than generic SQLAlchemy-from-LLM. |

---

## Integration Points

### `ProviderRegistry` (`lightroom_tagger/core/provider_registry.py`)

- **LLM-to-SQL:** Add a **query planner** service that obtains a `openai.OpenAI`-compatible client the same way vision does, with a **dedicated model id** (or reuse `defaults` with a new key e.g. `text_query_model`).
- **Embeddings API path:** If using OpenAI embeddings, same client, different endpoint; optional second provider entry for “embedding-only” base URL.
- **Local ST / open_clip:** Run **inside batch jobs** (same process as other long-running work), not per HTTP request, to avoid loading models on every API call.

### Job system (batch_describe / batch_score / batch_analyze / vision_match)

- **New or extended jobs:**  
  - **Index job:** compute text embeddings + image embeddings + FTS row updates when descriptions change.  
  - **Stack job:** burst detection (time + pHash) + write `image_stacks`; propagate scores to members.  
- **Checkpointing:** Reuse existing checkpoint patterns so partial library states remain valid after restarts.

### `database.py` / schema migrations

- **FTS5:** New virtual table + triggers or application-level sync from `image_descriptions` / catalog.  
- **sqlite-vec:** `vec0` table(s) keyed by stable `image_id` / `catalog_images` key; store **model id + dim** in a small `embedding_meta` table or schema version.  
- **New columns** (facets): `dominant_colors` (JSON), `mood_tags` (JSON or normalized child table), `has_repetition` (INTEGER/BOOLEAN) — **no new ML lib** if values come from structured LLM output at describe time.  
- **`load_extension`:** Ensure connection init enables extension loading where required for sqlite-vec (platform policy may need `trusted` path — document in ops).

### Flask API

- **New endpoints:** e.g. `POST /api/search/nl`, `GET /api/images/:id/similar`, facet filter query params; implementation composes SQL + FTS + vec KNN; never pass raw LLM SQL to SQLite without validation.

### Frontend (React 19 + Vite + TypeScript)

- **Natural language search:** Search field + optional “interpreted query” preview (chips) + result list; reuse existing filter/page patterns (`react-router-dom`, `zustand`).
- **Facets:** Multi-select for `mood_tags` / color buckets from API enums; align with `04-reusable-filter-framework` if present.
- **“More like this”:** Image detail or grid action → call similarity API → gallery strip or navigated list.
- **No mandatory new UI framework:** Radix/Headless is optional polish; **no** requirement for Next.js for these features.
- **Client-side embeddings:** **Not recommended** (bundle size + model IP); keep embedding on backend/job.

---

## Version verification note

PyPI “latest” moves continuously. Re-pin before release with:

`pip index versions <package>`

or lockfile export from the chosen environment, and re-run on the release train.
