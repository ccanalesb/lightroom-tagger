# Phase 3: Semantic Search & Results — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 03-semantic-search-and-results
**Areas discussed:** Vector storage, Embedding provider, Hybrid ranking, Result display & frontend scope

---

## Vector Storage

| Option | Description | Selected |
|--------|-------------|----------|
| `sqlite-vec` | Vectors in SQLite via loadable extension, SQL-composable with catalog queries | ✓ |
| Flat `.npy` files | Pure Python, numpy only, manual rerank step | |
| DuckDB / Chroma | Full vector DB, overkill for personal catalog scale | |

**User's choice:** `sqlite-vec`
**Notes:** Keeps vectors in the same `.db` file alongside catalog data. No second database process.

---

## Embedding Provider

| Option | Description | Selected |
|--------|-------------|----------|
| OpenAI `text-embedding-3-small` | Existing client, ~$0.02/1M tokens, no new dep | |
| Local `sentence-transformers` | Offline, no API cost, heavy dep (~500MB model) | ✓ |
| Other OpenAI-compatible (Ollama, etc.) | Local server, same API path | |

**User's choice:** Local `sentence-transformers`

### Model selection

| Option | Description | Selected |
|--------|-------------|----------|
| `all-MiniLM-L6-v2` | 384-dim, ~90MB, fast | |
| `all-mpnet-base-v2` | 768-dim, ~420MB, better semantic quality | ✓ |

**User's choice:** `all-mpnet-base-v2`
**Notes:** Better semantic quality for descriptive prose. Batch job runs infrequently so slower indexing is acceptable.

---

## Hybrid Ranking

| Option | Description | Selected |
|--------|-------------|----------|
| RRF (Reciprocal Rank Fusion) | `1/(k+rank)` summed across lists, k=60, no calibration | ✓ |
| Weighted score fusion | `α·semantic + (1-α)·fts`, requires tuning | |
| Pure semantic | Vector cosine only, no FTS | |

**User's choice:** RRF

### Degradation (images without embeddings)

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude from results | Clean, no noise, `missing_embeddings_count` in metadata | ✓ |
| FTS fallback for unembedded images | All images reachable, mixed ranking quality | |

**User's choice:** Exclude unembedded images from semantic results.

---

## Result Display & Frontend Scope

**Initial discussion:** Whether "why matched" appears as inline badge, tooltip, or on a dedicated results page.

**User clarification:** No frontend changes in Phase 3 at all. The "dedicated results page" and all display of search results (thumbnails, scores, "why matched" UI) is deferred to Phase 5 (NLS-05 chat panel).

**Resolved decisions:**
- "Why matched" string is **template-based** (assembled from ranking signals, no LLM call) and included in the API response JSON per result row
- Phase 3 delivers the **data contract** (API shape); Phase 5 renders it
- Phase 3 results page layout was NOT decided — deferred to Phase 5 entirely

### `batch_text_embed` job visibility

**User's decision:** `batch_text_embed` is a proper job type, user-triggered, queued through the existing job system, visible in `JobQueueTab` with progress like `batch_describe`.

---

## Claude's Discretion

- sqlite-vec table schema and companion DB vs inline storage
- Vector distance metric (cosine recommended for mpnet)
- Python module name for embedding service
- Exact API path for semantic search endpoint
- `missing_embeddings_count` field name in response metadata

## Deferred to Phase 5

- Dedicated search results page layout and routing
- NLS-04 UI (thumbnails, scores, "why matched" rendered in the browser)
- Search input UX (where the user types a semantic query)
