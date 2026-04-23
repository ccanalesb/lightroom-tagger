# Pitfalls Research — v3.0 Intelligent Discovery

Research targeted at **this** stack: Flask API + **app SQLite** (WAL, `busy_timeout`, jobs/checkpoints) + **read-only Lightroom catalog SQLite**; cost-sensitive **AI provider registry** (Ollama, Copilot); **multi-worker batch jobs** with resume checkpoints and per-thread DB connections. Phases are **suggested placement** for roadmapping (not yet numbered in `ROADMAP.md`).

---

## Natural Language Search

| Pitfall | Risk level | Prevention | Phase to address |
|--------|------------|------------|------------------|
| **Treating the LLM’s “SQL” as trusted input** — user NL is indirect, but model-produced predicates still reach the query layer; classic SQL injection and unintended reads (e.g. `ATTACH`, pragma tricks) if anything is string-concatenated. | **High** | **Never** execute raw model output. Use a **fixed, versioned allowlist** of tables/columns/joins, parameterized binds only, and optionally validate AST against a grammar. Log rejected generations. | Discovery / requirements; **NL search implementation** |
| **Hallucinated column or table names** that match *Lightroom* mental models but not your **app schema** (`images.key` vs Lr’s internal IDs, `image_descriptions` JSON columns, etc.). | **High** | Ship a **schema manifest** (or compact JSON) in the LLM system prompt; **retrieval** from actual `PRAGMA table_info` / introspection at build time. Execute only after mapping to allowlisted identifiers. | Schema & indexing foundation; NL search implementation |
| **Embeddings + FTS5 diverge** — text indexed for BM25 (titles, captions, AI summaries) not updated in the same transaction as the row the user sees; semantic search on vectors vs keyword search on FTS return incompatible result sets. | **Medium** | One **rebuild policy**: triggers or batch “search index sync” job after describe/score; store **index_versions** or `indexed_at` vs `described_at`. Surface “index stale” in UI when they differ. | Schema & foundation; **Jobs & concurrency** |
| **FTS5 content/external tables** on large joined views — out-of-sync when migrations add columns, or when rebuilding requires exclusive lock. | **Medium** | Prefer **FTS5 external content** with explicit sync job; test migration path on a copy of a 38K-image DB. Document rebuild time. | Schema & indexing foundation |
| **Embedding storage bloat** — float32 vectors for 10K–100K images × 512–1024 dims → hundreds of MB to GB in app DB, blowing backup size and `VACUUM` pain. | **Medium** | **Dimension budget** in requirements; table normalization (`embedding_id` + blob store or **separate file**/mmap); optional **PQ** or int8 with calibration; **per-model** storage keyed by `model_id`+`dim`. | Schema & indexing foundation; embedding & similarity |
| **Cold-start UX** — NL search works only after embeddings/FTS exist; users get empty/confusing results. | **Medium** | Degrade gracefully: **keyword-only** or metadata filters until N% indexed; banner “Semantic search: building… (3,421 / 12,000)”. Don’t show fake relevance scores. | NL search implementation; **UX & UAT** |
| **Cost surprises** — every NL query = LLM + (optional) embed query + heavy SQL. | **Medium** | Cache parsed query plans for identical NL (hash); cap tokens; route simple intent to **structured filters** without LLM. | NL search implementation |
| **Dual-DB confusion** — NL search must not assume writable Lr catalog; joining app data with Lr in one SQL string is easy to get wrong. | **High** | Explicit **data boundaries** in design: all searchable denormalized copies live in app DB, or use **app-side** two-step query (Lr read → keys → app), never `ATTACH` without threat review. | Discovery; schema foundation |

---

## Photo Stacking

| Pitfall | Risk level | Prevention | Phase to address |
|--------|------------|------------|------------------|
| **pHash-only clustering** merging different scenes (same wall, different people) or splitting true bursts. | **High** | **Two-stage** gating: time window (capture time) **then** pHash; tune on **holdout** sets from *this* catalog. Expose `max_gap_ms` / Hamming **thresholds** as job metadata + **fingerprint in checkpoint** (same pattern as `fingerprint_batch_describe`). | Stacking & clustering; UAT on real bursts |
| **Too-aggressive time clustering** — `date_taken` ties unrelated shots the same second. | **Medium** | Combine with file sequence / folder if available; require **transitivity checks** (pairwise pHash before merging clusters). | Stacking & clustering |
| **`capture_time` / `date_taken` NULL or wrong** — stacks become garbage or everything in one “unknown time” bucket. | **High** | Job skips or **singleton stacks** for NULL; metrics dashboard: “% without parseable time”. Don’t overwrite user-visible **rating/pick** from stack heuristics. | Stacking; data quality UAT |
| **Representative selection** — highest score image might be **unposted Instagram duplicate** or a motion-blurred frame. | **Medium** | Policy table: prefer `pick`/`rating` from `images` row, then score, then sharpness if you add it; **document** tie-breakers. | Stacking; UX |
| **Score propagation errors** — max/mean/last-writer; **re-running** stack job after a manual score change. | **High** | Define **idempotent** rule: e.g. “representative’s current `image_scores` rows propagate to members as **read-only suggestions** or shadow rows”, not silent overwrite of `is_current=1` unless job flag says so. Align with existing **`image_scores` versioning** (`prompt_version`, `is_current`). | Stacking; scoring integration phase |
| **Checkpoint scope explosion** — stack merge graph for 38K keys can exceed practical checkpoint size (this codebase already limits checkpoint entry counts). | **Medium** | **Chunk** by time windows; persist only frontier state; avoid storing full cluster maps per image in `jobs.metadata`. | Stacking; jobs hardening |
| **Existing `phash` on `images`** — reusing import-time hash vs recomputing after rotation/crop jobs (SEED-016) desynchronizes clusters. | **Medium** | Version **`phash_algo_version`** or invalidation on image pipeline change. | Stacking; any image-pipeline change |

---

## Visual Attribute Tags

| Pitfall | Risk level | Prevention | Phase to address |
|--------|------------|------------|------------------|
| **Prompt drift** — `mood_tags` and colors vary run-to-run; filters and search vocab become unstable. | **High** | **Enum or controlled vocab** in prompt (“choose from: …”); post-process with **fuzzy map** to canonical tags; store **`prompt_version` / schema_version** next to new fields (mirror `image_scores` pattern). | Describe / visual attributes pipeline |
| **Backward compatibility** — UI and APIs assume new keys in `image_descriptions` JSON blobs; old rows **omit** `dominant_colors` / `has_repetition`. | **High** | **Optional fields** with defaults; frontend **defensive parsing** (already a pattern for JSON columns); **migration job** “backfill attributes” optional, not blocking read path. | Describe pipeline; frontend contract phase |
| **Vocabulary explosion** — unconstrained tags → unique tag per image, useless for aggregate analytics. | **Medium** | Enforce max tags, normalize case, **merge** synonyms in a reference table; periodic **cleanup** report. | Visual attributes; analytics |
| **Double cost** — describe job already heavy; new fields **increase** tokens without caching. | **Medium** | **Structured output** schema (one JSON); optional **separate** cheap pass only when user enables “attribute extraction”. | Describe pipeline; cost review |
| **Inconsistent with similarity search** — “blue” tag from VLM doesn’t match CLIP’s notion of color. | **Low–Medium** | Document **two modalities**: text tags vs embedding space; don’t require bitwise agreement in UI. | Requirements; UAT |

---

## Visual Similarity Search

| Pitfall | Risk level | Prevention | Phase to address |
|--------|------------|------------|------------------|
| **Model lock-in** — embeddings from model A are **incomparable** with model B; re-embedding is mandatory on switch. | **High** | Table **`embedding_model_id` + `dim` + `schema_version`**; queries filter one model; migration = **re-run embed job** with new model key; never mix in one index. | Schema foundation; embedding jobs |
| **Size vs quality** — small CLIP/edge models miss nuance; large models don’t run on Ollama hardware or blow RAM. | **Medium** | **Hardware profile** in requirements (local vs future GPU); default model documented; **A/B** on sample set with photographer acceptance. | Discovery; embedding jobs |
| **10K+ images cost** — full-catalog embedding saturates I/O, GPU, and **job queue** (fairness with describe/match). | **High** | **Batch + checkpoint** (existing job patterns); **resume**; **rate limit**; optional “priority: recent N months only”; store **per-image `content_hash` or `analyzed_at` mtime** to skip unchanged. | Embedding & similarity; jobs hardening |
| **Stale vectors after re-import** — new file replaces `images.key` row or `image_hash` changes; old embedding row still keyed badly. | **High** | **`content_fingerprint`** (hash + size + mtime) on embedding row; **orphan** cleanup job; on key migration, follow **`migrate_unified_image_keys`**-style invariants. | Embedding jobs; catalog sync |
| **“More like this” on Instagram vs catalog** — two `image_type` families with different pipelines. | **Medium** | Explicit **mode** in API; separate indexes or `WHERE image_type` with consistent model. | API design; embedding |
| **ANN in SQLite** — no native FAISS in DB; **brute KNN in SQL** is O(n) or use **vector extension** (if ever introduced) / external ANN. | **Medium** | Prototype top-K at 10K; if slow, **sqlite-vec** or on-disk FAISS sidecar; **pre-filter** by date/album to shrink candidate set. | Embedding implementation; perf phase |

---

## Cross-cutting Risks

**System-level risks from adding multiple new capabilities at once**

1. **Writer contention (app DB)** — `init_database` already documents WAL **single-writer** behavior; parallel **describe/score** workers + new **FTS updates** + **embedding upserts** + **stack writes** increase “database is locked” probability despite `busy_timeout=30000`. *Mitigation:* serialize heavy writers per subsystem, **smaller transactions**, or **dedicated** “index writer” pass; **extend** `JobsHealthBanner`-style gating for “search index rebuilding”. *Phase:* **Jobs & concurrency hardening** early; re-verify under load in **UAT**.

2. **Read-only Lr catalog vs app DB consistency** — anything derived from Lr (keywords, path) for search must tolerate **Lr lock** and **stale** mirror; don't write FTS against Lr. *Mitigation:* app-side **materialized** search rows refreshed by existing prepare/enrich jobs. *Phase:* **Schema + catalog pipeline** design.

3. **Migration safety** — existing installs use **additive** `_migrate_add_column` style; new tables (embeddings, stacks, fts) need **idempotent** `CREATE IF NOT EXISTS`, **backwards-compatible** reads, and a **roll-forward** test on a user DB copy. *Mitigation:* feature flags, **dry-run** migration in CI on fixture DB. *Phase:* **Schema & indexing foundation** (before feature code lands).

4. **Checkpoint / metadata size** — new job types must respect **fingerprinting** and **size limits** (see `handlers.py` / checkpoint merge) so job resume stays reliable. *Mitigation:* externalize large graphs to tables, not `jobs.metadata`. *Phase:* each new **job handler** design review.

5. **Provider registry & cost** — LLM for NL-to-filter, VLM for attributes, local embed: **central quota** and **failover** (Ollama down → degrade to keyword). *Phase:* **Discovery**; **integration** hardening.

6. **API & React 19 data layer** — new endpoints must align with **Suspense/query keys**; partial data (stacks, vectors) can cause **stale cache** if invalidation misses (existing `invalidateAll` patterns). *Mitigation:* explicit query keys and invalidation on job completion. *Phase:* **frontend** per feature + **E2E** UAT.

7. **Security boundary** — NL search and future “agent” features must not exfiltrate **paths/EXIF** from prompts in logs. *Mitigation:* redact in logs; **allowlisted** query shapes only. *Phase:* **requirements** + code review on NL path.

---

*Generated for roadmap/requirements. Align suggested phases with `/gsd-new-milestone` v3.0 breakdown when created.*
