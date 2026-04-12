# Architecture Research — v2.0 Structured Scoring, Analytics & Insights

**Domain:** Integrating structured AI critique scores, aggregate analytics, and an insights dashboard into the existing Lightroom Tagger visualizer stack.

**Researched:** 2026-04-12

**Confidence:** HIGH for current-repo integration points (files and tables verified in tree); MEDIUM for specific schema choices (several valid SQLite shapes; product trade-offs decide).

**Scope:** Only how **new** capabilities attach to the existing **Flask + React + dual-SQLite** system and the **on-demand description pipeline**. Generic DAM patterns are omitted unless they map to this repo.

---

## System Overview

Existing runtime (unchanged roles):

- **Browser** → Flask REST (`apps/visualizer/backend/api/*`) + Socket.IO (`websocket/events.py`) for job progress.
- **Background job thread** (`app.py` → `JobRunner` + `jobs/handlers.py`) → opens **`LIBRARY_DB`** via `lightroom_tagger.core.database.init_database` for matching, import, batch describe, etc.
- **Visualizer DB** (`DATABASE_PATH` / `visualizer.db`) → job rows only; **not** catalog or AI outcomes.
- **Library DB** (`LIBRARY_DB` / `library.db`) → `images`, `instagram_dump_media`, `matches`, `image_descriptions`, caches.

v2.0 additions (logical boxes):

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         React SPA (Vite, Tailwind)                                │
│  Dashboard │ Images (Catalog / Matches / …) │ Processing (Jobs, Descriptions…)   │
│       └─► NEW: Insights dashboard route/section + score filters in catalog UI      │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                │ REST (+ optional Socket.IO for long aggregates)
                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    Flask blueprints (apps/visualizer/backend/api)                 │
│  images.py · descriptions.py · jobs.py · providers.py · system.py · lt_config.py │
│       └─► NEW: insights.py (or extend images.py) — aggregation + ranking APIs      │
└───────────────────────────────┬──────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌───────────────────┐                         ┌───────────────────────────────┐
│ visualizer.db     │                         │ library.db (LIBRARY_DB)        │
│ jobs, job_logs    │                         │ images, instagram_dump_media, │
│ (unchanged role)  │                         │ matches, image_descriptions,   │
└───────────────────┘                         │ NEW tables/columns for scores  │
                                              │ + optional prompt_versions     │
                                              └───────────────┬───────────────┘
                                                              │
                                                              │ read paths / captions
                                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│              lightroom_tagger/core (domain — shared CLI + visualizer)             │
│  analyzer.py (prompt + parse)  →  vision_client.generate_description               │
│  description_service.py → store_image_description                                 │
│       └─► NEW: scoring schema validation, template/version metadata, analytics   │
│           module (pure SQL + Python rollups, no new process)                       │
└──────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ProviderRegistry / FallbackDispatcher
                                │
                                ▼
              Ollama / OpenAI-compatible vision endpoints (unchanged integration)
```

---

## Component Responsibilities

### Existing components (touch points for v2.0)

| Area | Path / module | Role today | v2.0 relevance |
|------|----------------|------------|----------------|
| Description prompt & parse | `lightroom_tagger/core/analyzer.py` | `DESCRIPTION_PROMPT`, `parse_description_response`, per-perspective `score` inside `perspectives` JSON | Extend prompt for new dimensions/perspectives; tighten JSON schema; optionally attach **prompt_version** / **rubric_id** to outputs |
| Vision I/O | `lightroom_tagger/core/vision_client.py` | `generate_description` uses `build_description_prompt` + `parse_vision_response` | Same call path; may add structured-output constraints or repair pass if model drifts |
| Persist descriptions | `lightroom_tagger/core/description_service.py` | `describe_matched_image` / `describe_instagram_image` → `store_image_description` | After parse, populate new score columns or child table; keep **single write path** for batch + HTTP generate |
| Library schema & CRUD | `lightroom_tagger/core/database.py` | `image_descriptions` + `store_image_description` | Migrations for queryable scores; indexes for sort/filter; optional normalization table |
| Catalog API | `apps/visualizer/backend/api/images.py` | Catalog list with LEFT JOIN `image_descriptions`, `analyzed` filter | Expose numeric scores for filters, sort, badges; “best photos” precomputed or sort keys |
| Descriptions API | `apps/visualizer/backend/api/descriptions.py` | List/get/generate descriptions | Return extended schema; optional `force` regenerate with new prompt version |
| Jobs | `apps/visualizer/backend/jobs/handlers.py` | Batch describe, cancellation via `JobRunner` / `threading.Event` | Re-run jobs to backfill scores after schema/prompt change |
| UI shell | `apps/visualizer/frontend/src/App.tsx`, `Layout.tsx` | Routes: `/`, `/images`, `/processing` | Add `/insights` or embed insights in `DashboardPage` |
| Dashboard (minimal) | `pages/DashboardPage.tsx` | Counts from `ImagesAPI`, `JobsAPI` | Replace/extend with chart cards fed by new insights endpoints |

### New components (recommended placement)

| Component | Suggested location | Responsibility |
|-----------|-------------------|----------------|
| **Prompt template registry** | `lightroom_tagger/core/prompt_templates.py` (or versioned JSON under `lightroom_tagger/core/`) + optional DB table for operator overrides | Map `prompt_version` → full system prompt; allow A/B and audit trail without code deploy |
| **Score schema validator** | `lightroom_tagger/core/scoring_schema.py` | Validate / coerce model JSON; define allowed dimensions per perspective; default missing scores to NULL |
| **Analytics / insights service** | `lightroom_tagger/core/insights.py` (library-side) **or** `apps/visualizer/backend/services/insights.py` (API-only) | Posting histograms (from `instagram_dump_media.created_at`), caption/hashtag stats, score distributions, gaps (posted vs high-scoring catalog) |
| **Insights API blueprint** | `apps/visualizer/backend/api/insights.py` | `GET` endpoints returning JSON aggregates (no heavy logic in route handlers — call service) |
| **Insights UI** | `apps/visualizer/frontend/src/pages/InsightsPage.tsx` + `components/insights/*` | Charts, tables, filters; consumes insights API |
| **Optional materialized snapshot** | New table e.g. `insights_cache` in **library.db** | Store precomputed rollups if aggregate queries become slow on large DBs |

---

## Architectural Patterns

1. **Single write funnel for AI results**  
   All describe paths (HTTP `generate`, batch job handlers, future CLI) should continue to land in **`store_image_description`** (or one new helper it calls) so scores stay consistent.

2. **JSON blob + extracted columns (hybrid)**  
   Keep rich narrative in existing `perspectives` / `composition` / `technical` JSON for forward compatibility; add **queryable** REAL/INTEGER columns or a **child table** for filters (`WHERE score_composition >= 7`, index-friendly). Parsing JSON in every catalog list query does not scale.

3. **Prompt versioning**  
   Persist `prompt_version` (and optionally `schema_version`) on `image_descriptions` so aggregations can filter “same rubric only” and re-run jobs can target outdated rows.

4. **Read-only analytics on library.db**  
   Aggregations are SELECT-only against `images`, `matches`, `instagram_dump_media`, `image_descriptions`. No Lightroom catalog writes required for insights.

5. **On-demand + job backfill**  
   New fields appear first for **new** describes; optional job type **backfill_scores** recomputes from stored images when prompts change (same pattern as batch describe).

6. **Dual-DB awareness**  
   Insights and scores live in **library.db**. Job **orchestration** stays in **visualizer.db**; long-running aggregate jobs remain normal `jobs` rows if needed.

---

## Data Flow

### 1) Structured scoring (happy path)

```
UI or job → describe_image path (analyzer + vision_client)
         → parse JSON → scoring_schema.validate/coerce
         → merge into structured dict
         → store_image_description (JSON + extracted numeric fields / child rows)
         → catalog API includes scores in list/detail payloads
```

### 2) Catalog UI filter “min composition score ≥ N”

```
Browser GET /api/images/catalog?min_score_composition=7
       → SQL WHERE on indexed column(s) or JOIN to score table
       → paginated rows with embedded description summary + scores
```

### 3) Posting pattern analytics

```
GET /api/insights/posting-times
       → SQL on instagram_dump_media.created_at (hour-of-day, DOW buckets)
       → optional JOIN matches → catalog keys for “posted vs catalog rating” views
```

### 4) Caption / hashtag style

```
Read caption text from instagram_dump_media.caption
       → Python tokenization / hashtag extraction in insights service
       → aggregate counts; optional second-phase **AI caption critique** job writes to new columns or related table
```

### 5) “What to post next” / gap analysis

```
SQL: high-scoring catalog images (from scores) LEFT ANTI JOIN posted set
       (via images.instagram_posted / matches / keywords — use one canonical signal)
       → ranked list returned as JSON suggestion list
```

---

## Integration Points

### External services

| Service | Pattern | v2.0 note |
|---------|---------|-----------|
| Vision / LLM (Ollama, OpenAI-compatible) | Existing `ProviderRegistry` + `vision_client.generate_description` | Prompt grows; monitor **context length** and **payload size** (same compression path as today) |
| Instagram | Export files → `instagram_dump_media` | Timestamps and captions drive **posting analytics**; no API |

### Internal boundaries

| Boundary | Today | v2.0 change |
|----------|--------|-------------|
| **analyzer ↔ vision_client** | Prompt string + parse | Add versioned template lookup; shared schema constants |
| **description_service ↔ database** | `_store_structured` | Persist scores + version fields |
| **API ↔ library.db** | `@with_db` per request | New insights routes; extend catalog query builder with score predicates |
| **Handlers ↔ domain** | Handlers call `describe_matched_image` loops | Pass `prompt_version` / force flags in job metadata |
| **React ↔ API** | `services/api.ts` | New client methods for `/api/insights/*`; catalog query params for scores |

### Schema direction (library.db)

**Today:** `image_descriptions` holds `perspectives` JSON (includes per-perspective `score` in practice) with `PRIMARY KEY (image_key)` — see `lightroom_tagger/core/database.py`.  
**Caution:** Application code also uses `image_type`; composite uniqueness for `(image_key, image_type)` is not enforced at the DB level (see `.planning/codebase/CONCERNS.md`). v2.0 should avoid widening that mismatch when adding columns or child tables.

**Likely additions (pick one strategy):**

- **A — Flat columns** on `image_descriptions`: e.g. `score_composition`, `score_narrative`, `score_rhythm`, `prompt_version TEXT`, plus generated indexes. Simple queries; rigid schema.
- **B — Normalized `image_critique_scores`**: `(image_key, image_type, perspective, dimension, score, prompt_version)` with composite index for filters. Flexible perspectives; more JOINs.
- **C — Hybrid**: keep full JSON + **generated** rollups in A or B for hot query paths.

**Posting / caption analytics** can remain query-time only until performance requires a small `insights_snapshot` table refreshed by a job.

---

## Suggested build order (dependencies)

1. **Prompt + JSON schema** in `analyzer.py` / `scoring_schema.py` + tests (no UI) — defines contract for models.
2. **Library DB migration** — columns or score table + `prompt_version`; extend `store_image_description` and deserialization helpers.
3. **Wire description pipeline** — `description_service` + job handlers + `POST .../generate` paths populate new fields.
4. **Catalog API** — extend `query_catalog_images` / `images.py` for sort/filter on new fields; frontend catalog filters.
5. **Insights service + `/api/insights`** — posting patterns and score histograms from existing tables.
6. **Insights UI** — new page or dashboard section; add a small chart dependency if needed (no chart library in `package.json` today).
7. **Higher-level features** — “best photos” ranking, identity clustering, caption AI — build on stable scores + aggregates.

This order respects the dependency chain: **no dashboard without queryable scores; no reliable scores without schema + prompt version**.

---

## Sources

- [`.planning/PROJECT.md`](../PROJECT.md) — v2.0 milestone requirements (structured scores, posting analytics, insights dashboard).
- [`.planning/codebase/ARCHITECTURE.md`](../codebase/ARCHITECTURE.md) — implemented layers, dual-DB split, job thread model.
- [`.planning/codebase/CONCERNS.md`](../codebase/CONCERNS.md) — `image_descriptions` key/`image_type` caveat, SQLite concurrency notes.
- `lightroom_tagger/core/database.py` — `image_descriptions` table definition, `store_image_description`, related queries.
- `lightroom_tagger/core/analyzer.py` — current structured JSON prompt and perspective scores embedded in JSON.
- `lightroom_tagger/core/description_service.py` — single persistence path for catalog vs Instagram describes.
- `apps/visualizer/backend/app.py` — blueprint registration and job processor wiring.
- `apps/visualizer/frontend/package.json` — current frontend dependencies (no visualization chart library yet).

---
*Architecture research for: v2.0 Advanced Critique & Insights integration*

*Researched: 2026-04-12*
