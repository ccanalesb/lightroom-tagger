# Architecture Research

**Domain:** Photography analysis tools with Lightroom catalog integration (SQLite `.lrcat`, optional plugins, companion apps)

**Researched:** 2026-04-10

**Confidence:** MEDIUM — patterns are well established in desktop DAM tooling, SQLite reverse-engineering communities, and ML pipelines; exact Lightroom internal schema is undocumented and version-dependent.

## Standard Architecture

Tools that analyze photos and tie results back to Lightroom usually fall into one of three shapes:

1. **Lightroom Classic plugin (Lua + SDK)** — runs inside Lightroom; limited I/O; often delegates heavy work to an external helper or HTTP service.
2. **External companion app** — reads/writes the catalog SQLite file and/or sidecar XMP; may use a **separate application database** for derived state (matches, AI text, analytics) that Lightroom never sees.
3. **Hybrid** — thin plugin for menu hooks + external service for AI, matching, and reporting.

This project ([`.planning/PROJECT.md`](../PROJECT.md)) is explicitly a **web companion** with **direct `.lrcat` writes for keywords only** and a **library SQLite** for everything else — a common pattern when avoiding plugin distribution and keeping Lightroom’s UI unchanged.

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Presentation (UI / CLI / Plugin shell)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Web / SPA    │  │ Desktop UI   │  │ CLI          │  │ LR Plugin    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                 │               │
├─────────┴─────────────────┴─────────────────┴─────────────────┴─────────────┤
│                     Application / orchestration                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Job queue · REST/WebSocket · progress · auth (if multi-user)         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├───────────────────────────────────────────────────────────────────────────────┤
│                     Domain services (boundaries below)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Catalog  │ │ Match    │ │ AI /     │ │ External │ │ Analytics│          │
│  │ I/O      │ │ engine   │ │ vision   │ │ media    │ │ layer    │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
├───────┴────────────┴─────────────┴────────────┴─────────────┴─────────────────┤
│                     Data & persistence                                        │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │ App / library  │  │ Lightroom      │  │ Object / blob  │                 │
│  │ SQLite (derived│  │ .lrcat (source │  │ cache (thumbs, │                 │
│  │  state)        │  │  of truth LR)  │  │  resized, emb.)│                 │
│  └────────────────┘  └────────────────┘  └────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical implementation |
|-----------|----------------|------------------------|
| **Catalog reader** | Open `.lrcat` safely; query `AgLibrary*` tables; resolve file paths; map to stable image IDs | Dedicated module with SQLite connection policy (WAL, timeouts, optional exclusive lock for NAS); **no business logic** mixed with SQL |
| **Catalog writer** | Minimal, auditable mutations (keywords, labels, pick flags) consistent with LR rules | Small API surface; transactions; backup recommendation; schema-version checks |
| **Library / app DB** | Cache of scan results, matches, AI outputs, job state — **not** replacing Lightroom as master for edits | Separate SQLite or Postgres; migrations; JSON columns for flexible AI payloads |
| **Media access** | Resolve paths (UNC, NAS, moved volumes); read bytes for hashing and APIs | Path normalization layer; optional filesystem watcher (rare in LR tools) |
| **Matching engine** | Propose and score catalog ↔ external image pairs (social export, second catalog, duplicates) | Candidate generation (date, filename, dimensions) → cheap signals (pHash, dHash) → optional expensive signals (embeddings, vision compare) |
| **AI analysis pipeline** | Prompting, model routing, retries, cost control, result parsing | Provider abstraction (OpenAI-compatible or vendor SDKs); job-based execution; idempotent writes keyed by image + model + prompt version |
| **Ingestion adapters** | Normalize third-party dumps (Instagram export, CSV) into canonical rows | Parsers + validation; stable IDs from platform paths or hashes |
| **Multi-catalog manager** | Register many `.lrcat` paths; active catalog context; prevent cross-contamination | Catalog registry in app DB; per-catalog prefixes on imported rows or foreign keys |
| **Analytics aggregation** | Roll up engagement metrics, posting history, “best of” composites | ETL into summary tables or materialized views; time-bucketed metrics |

## Domain deep dive: major components

### Lightroom SQLite catalog (read/write)

**Boundary:** Only the **catalog I/O module** should execute raw SQL against `.lrcat`. Higher layers consume **typed records** (image ID, path, capture time, keywords).

**Read path:** Query library asset tables, join to files and folders, decode Lightroom-specific encodings. Performance usually requires **batch queries** and **indexed columns** LR already provides — avoid N+1 queries per image.

**Write path:** Keep **narrow** (e.g. keyword tags, pick status). Wider writes risk corruption or future Lightroom upgrades. Common practice: **backup catalog** before first write; document **Lightroom closed** or **read-only** expectations.

**Operational concerns:** WAL mode, file locking, network filesystems (SMB/NAS), and concurrent Lightroom access — often handled with timeouts, single-connection discipline, or documented exclusivity.

### Image matching algorithms

**Boundary:** Matching consumes **normalized descriptors** (hashes, dimensions, timestamps) from both sides; it does not open SQLite directly unless implemented as a single monolith (still preferable to isolate behind a `Matcher` interface).

**Typical stages (data flows one way):**

1. **Candidate generation** — restrict search space (same day, same aspect ratio bucket, filename similarity).
2. **Cheap similarity** — perceptual hash Hamming distance, optional difference hash.
3. **Medium cost** — text/caption similarity if both sides have text; EXIF overlap.
4. **Expensive confirmation** — vision model “same photo?” or embedding cosine similarity; capped concurrency.

**Persistence boundary:** Store proposed matches, scores, and explainability in the **app DB**, not in `.lrcat`, until the user confirms and triggers keyword write-back.

### AI analysis pipeline

**Boundary:** **Prompt + model + image bytes in** → **structured JSON or text out** → **domain service** maps results to DB columns. The pipeline does not own catalog schema knowledge.

**Major subcomponents:**

- **Provider registry** — endpoints, API keys, model list.
- **Dispatcher** — retries, fallback models/providers, rate-limit handling.
- **Job runner** — long-running describe/compare batches; progress and cancellation.
- **Cache** — hashed inputs → saved responses (filesystem or table) to save cost and stabilize UX.

**Data flow direction:** UI/API → enqueue job → worker pulls work → reads image via path resolver → calls provider → writes rows → notifies UI.

### Multi-catalog management

**Boundary:** A **catalog context** (active `catalog_id` or path) is threaded through APIs and jobs. Aggregations that span catalogs use an explicit **cross-catalog query layer** so default filters never leak rows between catalogs.

**Typical model:**

- **Registry:** `(catalog_path, fingerprint or mtime, display name, last_scan_at)`.
- **Scoped data:** All imported images and matches reference `catalog_id`.
- **Unified “photographer” views:** Optional denormalized table or views that union metrics with `catalog_id` as a dimension (not merged master files).

### Analytics aggregation

**Boundary:** Raw events live in **ingestion tables** (per post, per export file). Aggregates are **derived** and refreshed on schedule or after import.

**Common patterns:**

- **Fact table:** one row per post or per image–post link with metrics as columns.
- **Rollups:** by week, by hashtag, by AI “theme” tags if you classify posts.
- **Join to catalog:** via stable match keys so Lightroom-side rows gain `likes`, `reach`, etc., for visualization only (still stored in app DB unless written to keywords as text).

## Recommended Project Structure

For a **Python library + optional web app** (matches this repo’s direction), a clear split is:

```
lightroom_tagger/
├── lightroom/              # .lrcat read/write only
├── core/                   # matching, vision, app DB, config
├── instagram/              # dump/adapters (example external source)
└── scripts/                # one-off pipelines, CLI entry helpers

apps/visualizer/            # thin HTTP + jobs + SPA (optional)
```

### Structure Rationale

- **`lightroom/`:** Isolates undocumented Adobe schema and connection quirks from the rest of the system.
- **`core/`:** Shared algorithms and persistence used by CLI and web.
- **Source adapters (`instagram/`, future sources):** Ingestion boundaries stay swappable without touching matcher or LR writer.
- **`apps/visualizer/`:** Presentation and **job orchestration** only; avoids duplicating matching/vision logic in TypeScript.

## Architectural Patterns

### Pattern 1: Separate application database from Lightroom catalog

**What:** Treat `.lrcat` as Lightroom’s domain; store all analysis, matches, and analytics in an **app-owned** SQLite (or other) database.

**When to use:** Almost always for companion apps and heavy AI pipelines.

**Trade-offs:** Must run **scan/import** steps to stay in sync when the catalog changes; on the plus side, no risk of bloating or corrupting LR’s internal tables with experimental columns.

### Pattern 2: Job queue for AI and heavy matching

**What:** All long-running work runs in **workers** (threads, processes, or task queue) with durable job state.

**When to use:** Web UI, multi-image vision compares, or batch matching.

**Trade-offs:** More moving parts vs. synchronous CLI; essential for progress, retry, and not blocking HTTP requests.

### Pattern 3: Layered matching (cheap → expensive)

**What:** Progressively filter candidates before calling cloud vision.

**When to use:** Large catalogs and cost-sensitive AI.

**Trade-offs:** More code and tuning; large savings in API spend and latency.

### Pattern 4: Provider abstraction behind a small interface

**What:** `compare_images`, `generate_description`, or `embed` with shared error types and retries.

**When to use:** Multiple vendors (Ollama, OpenRouter, OpenAI) or model churn.

**Trade-offs:** Slight indirection; avoids scattering HTTP details across matchers and UI.

## Data Flow

### Request flow (companion web app)

```
User action (UI)
    ↓
REST / WebSocket API
    ↓
Orchestration (validate catalog context, enqueue job)
    ↓
Worker: read app DB + resolve file paths
    ↓
Domain: matcher and/or vision_client
    ↓
Write results → app DB (and optionally .lrcat via writer)
    ↓
Push progress → UI
```

### End-to-end: catalog → analysis → external source → write-back

```
.lrcat ──read──► Catalog reader ──► App DB (images, keywords mirror)
                                        │
Instagram dump ──ingest──► Adapter ───────┤
                                        ▼
                                  Matcher ◄──► Vision (optional)
                                        │
                                        ▼
                                  matches / descriptions
                                        │
                    user confirm ───────┴──► .lrcat writer (keywords)
```

### Key data flows

1. **Scan / sync:** `.lrcat` → normalized rows → **app DB** (one direction until explicit write-back).
2. **Match:** External media + catalog rows → candidate set → scores → **app DB**; optional **LR writer** after approval.
3. **Analyze:** Image path → resize/cache → provider API → parsed result → **app DB**; UI reads from app DB only.
4. **Multi-catalog:** User selects catalog → all queries filtered by `catalog_id` → aggregations optionally **union** with catalog dimension.
5. **Analytics:** Raw dump metrics → ingestion tables → scheduled rollups → dashboards join on **match keys** to catalog images.

## Suggested build order (dependencies between components)

Build from **lowest dependency** to **highest**. Each step should be usable on its own (CLI or tests) before the next.

| Order | Component | Depends on | Delivers |
|-------|-----------|------------|----------|
| 1 | **Config + paths** | — | Catalog paths, DB path, env |
| 2 | **App DB schema + migrations** | Config | Stable tables for images, jobs |
| 3 | **Catalog reader → app DB (scan)** | 1–2 | Usable inventory of images |
| 4 | **Media path resolver + file reads** | 3 | Bytes for hashing |
| 5 | **Hasher (pHash / metadata)** | 4 | Descriptors for matching |
| 6 | **Ingestion adapter(s)** | 2, 5 | External rows comparable to catalog |
| 7 | **Matcher (cheap stages first)** | 5–6 | Proposed matches without AI |
| 8 | **Catalog writer (minimal)** | 3 | Proven safe keyword updates |
| 9 | **Vision / AI client + cache** | 4–5 | Descriptions and compare scores |
| 10 | **Vision-augmented matcher** | 7, 9 | Higher-quality matches |
| 11 | **Job runner + progress** | 2 | Web-scale execution of 6–10 |
| 12 | **Multi-catalog registry** | 2, 3 | Scoped scans and UI switching |
| 13 | **Analytics aggregation** | 6, 7/10 | Dashboards and “best of” |

**Implication for roadmap phasing:** Ship **scan + app DB** before any AI; ship **cheap matcher** before **vision**; ship **single-catalog** before **cross-catalog analytics** unless registry is trivial.

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|---------------------------|
| Single user, one catalog | Monolith + SQLite is sufficient; synchronous CLI OK for small batches |
| Single user, large catalog | Indexed app DB, worker pool for hashing/matching, strict candidate limits before vision |
| Multi-catalog, still single user | Catalog-scoped indices; avoid loading all catalogs in one process without need |
| Multi-user hosted service | Move job queue to Redis/RQ or cloud tasks; **do not** share writable `.lrcat` paths; per-tenant storage |

### Scaling Priorities

1. **First bottleneck:** Full-catalog pairwise compare — fix with **candidate generation** and **descriptor indexes** (hash buckets).
2. **Second bottleneck:** Vision API rate limits and cost — fix with **caching**, **concurrency caps**, and **tiered matching**.

## Anti-Patterns

### Anti-Pattern 1: Treating the Lightroom catalog as the app’s primary database

**What people do:** Add many custom tables or bulk columns inside `.lrcat` via raw SQL.

**Why it's wrong:** Undocumented schema, upgrade fragility, corruption risk, and merge/sync pain.

**Do this instead:** Keep **derived state** in the **app DB**; use `.lrcat` for **minimal, Lightroom-native** fields (e.g. keywords) the user expects in LR.

### Anti-Pattern 2: Unbounded vision calls during matching

**What people do:** Call a VLM for every catalog image × every external image.

**Why it's wrong:** Cost and latency explode; rate limits break the UX.

**Do this instead:** **Layered matching** with hard caps; vision only on top-K pairs.

### Anti-Pattern 3: Implicit multi-catalog queries

**What people do:** One global `images` table without `catalog_id`, or forget filters in new endpoints.

**Why it's wrong:** Cross-catalog data leaks and wrong write-back targets.

**Do this instead:** **Mandatory catalog context** in APIs and job payloads; integration tests for isolation.

## Integration Points

### External Services

| Service | Integration pattern | Notes |
|---------|-------------------|--------|
| **Lightroom Classic** | SQLite file I/O + user workflow (close LR / backup) | Not a supported public SQL API — defensive coding and backups |
| **Vision / LLM APIs** | HTTPS, OpenAI-compatible or vendor SDK | Token limits, image size caps, structured output parsing |
| **Instagram (export)** | File-based dump ingestion | No API in this project’s scope; parsers are versioned with export format |
| **Object storage (optional)** | S3-compatible for caches | Useful if moving off local disk for thumbnails |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|--------|
| **Presentation ↔ Orchestration** | REST, WebSocket, CLI argv | No direct `.lrcat` access from frontend |
| **Orchestration ↔ Domain** | Python function calls, job handlers | Handlers stay thin |
| **Domain ↔ Lightroom file** | `lightroom.reader` / `lightroom.writer` only | Single ownership of PRAGMAs and SQL dialect assumptions |
| **Domain ↔ App DB** | Repository-style module (`core.database`) | JSON serialization centralized |
| **Matcher ↔ Vision** | Optional dependency injected or stage interface | Matcher usable without API keys |
| **Ingestion ↔ Matcher** | Shared schema for “external image” rows | Adapters map to same descriptor pipeline as catalog |

## Sources

- Adobe Lightroom Classic catalog as **SQLite** (community schema notes; version-specific) — treat as **unofficial**.
- General **perceptual hashing** and **image retrieval** literature (pHash/dHash pipelines).
- **OpenAI-compatible** multimodal APIs — common abstraction layer for local (Ollama) and cloud providers.
- Internal alignment: [`.planning/codebase/ARCHITECTURE.md`](../codebase/ARCHITECTURE.md) (this repository’s implemented layering).

---
*Architecture research for: photography analysis tools with Lightroom integration*

*Researched: 2026-04-10*
