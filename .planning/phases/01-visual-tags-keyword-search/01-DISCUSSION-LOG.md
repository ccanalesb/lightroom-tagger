# Phase 1: Visual tags & keyword search — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 01-visual-tags-keyword-search
**Areas discussed:** Search technology, FTS sync mechanism, FTS text scope, Search integration, Input handling

---

## Pre-discussion: Search technology research

Prior to discussing gray areas, user requested research into search technology options (keyword search over AI-generated description text).

Research was conducted twice — first with incorrect year (2025), then correctly with 2026.

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite FTS5 | Built-in, zero deps, 1–5ms, porter stemming, lives in same `.db` file | ✓ |
| Tantivy (tantivy-py) | Rust-based Lucene, faster at scale, separate index directory, Rust build dep | |
| DuckDB FTS | Column-oriented analytics DB, separate DB connection required, architectural mismatch | |
| Meilisearch / Typesense | Separate running service, overkill for local single-user app | |

**User's choice:** SQLite FTS5 — "I think I'm convinced"
**Notes:** User asked about alternatives before committing. Honest recommendation given: FTS5 is right for this dataset size and architecture. Tantivy would be faster at scale but adds unnecessary complexity.

---

## FTS Sync Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Python-side (in `store_image_description`) | Testable, consistent with codebase patterns, single write path | ✓ |
| Database triggers | Automatic, correct always, but harder to test in pytest | |

**User's choice:** Python-side
**Notes:** User also confirmed backfill is needed. Agreed approach: existing batch describe job with filter for rows where `dominant_colors IS NULL`, plus one-shot `rebuild` at migration time for existing summaries.

---

## What Text Gets Indexed

| Option | Description | Selected |
|--------|-------------|----------|
| `summary` only | AI description paragraph, simple | |
| `summary` + `subjects` flattened | Summary + JSON subjects array joined as text — richer matching | ✓ |
| Everything (+ Lightroom fields) | Cross-table, complex to maintain | |

**User's choice:** B — summary + subjects flattened
**Notes:** "Subjects flattened" was clarified: the `subjects` JSON array (`["man in yellow raincoat", "wet cobblestone"]`) is joined as space-separated text before indexing, making specific scene elements searchable.

---

## Search Integration in Catalog

| Option | Description | Selected |
|--------|-------------|----------|
| Unified search | One search box, searches both Lightroom fields AND descriptions | |
| Separate filter | Two distinct inputs — Lightroom keywords filter + description search | |
| Dedicated description search (replace LIKE) | FTS for descriptions only; LIKE on Lightroom fields stays as structured filter chip | ✓ |

**User's choice:** C — dedicated description search, separate from Lightroom keyword filter
**Notes:** User chose C after explanation of the distinction between Lightroom metadata (structured filter chips) and AI-generated description content (new FTS input).

---

## User Input Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Phrase mode | Wrap in quotes — strict word order required | |
| Token AND mode | Split on whitespace, AND-join — order-independent, all tokens must appear | ✓ |
| Prefix mode | Append `*` per token — partial word matching, can be noisy | |

**User's choice:** B — token AND mode
**Notes:** Most natural for searching description text. Porter stemming handles word variants. Input sanitization strips FTS special characters before splitting.

---

## Claude's Discretion

- Exact FTS table name
- Exact API parameter name for description search
- Schema migration approach
- Whether subjects are concatenated at index-time or via generated column
