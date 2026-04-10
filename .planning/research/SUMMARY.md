# Project Research Summary

**Project:** Lightroom Tagger & Analyzer  
**Domain:** Photography analysis with Lightroom Classic (SQLite `.lrcat`) integration, Instagram export-dump matching, multi-perspective AI critique, and analytics dashboards — not generic CRUD.  
**Researched:** 2026-04-10  
**Confidence:** MEDIUM–HIGH (stack pins verified on PyPI/npm; features/architecture aligned with PROJECT.md; no primary user interviews for product features)

## Executive Summary

This product is a **web companion** to Lightroom Classic: it reads the catalog, ingests Instagram data exports (no API), matches published images to catalog rows, and writes back **narrow, user-confirmed** changes (e.g. keywords). Serious tools in this space use a **separate application database** for derived state (matches, jobs, AI output) and touch `.lrcat` only through a small, audited I/O layer — not as a general-purpose app DB.

The recommended technical path is **Python 3.12+** for catalog, hashing, and orchestration; **stdlib `sqlite3` + Pillow + ImageHash** for transparent `.lrcat` access and perceptual matching; **Pydantic** for structured critique contracts; **React + TypeScript + Vite** for the dashboard; and either **stay on Flask + Socket.IO** (migration cost) or adopt **FastAPI + Uvicorn** for new API work (2025–2026 default for LLM-shaped services). **On-demand jobs** with **layered matching** (cheap hashes → capped vision) keep cost and risk under control.

The main risks are **treating `.lrcat` like any SQLite app** (corruption, locks), **unaudited write-back** after probabilistic matching, and **runaway vision cost** or **fragile dump parsers**. Mitigate with read-only defaults, backup-before-write, human-in-the-loop confirmation, versioned export adapters, and stored model/prompt metadata on every AI result. Details: [STACK.md](./STACK.md), [FEATURES.md](./FEATURES.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [PITFALLS.md](./PITFALLS.md).

## Key Findings

### Recommended Stack

Single language (Python) for SQLite, image prep, and LLM clients keeps ops simple. Prefer **stdlib `sqlite3`** for `.lrcat` — maximum control and no ORM mapped to undocumented Adobe tables. **Pillow** and **ImageHash** are the default for decode/resize and dump ↔ catalog matching; add embeddings or vision only on shortlists when hashes plateau. **OpenAI SDK** (and optional **LiteLLM** when 3+ providers matter) plus **Ollama** for cheap experiments match PROJECT.md. Frontend: **React 19**, **Vite 8**, **TypeScript**, **Recharts** for analytics, **Zustand** for light state; **python-socketio** / **socket.io-client** if live job progress stays on Socket.IO. Quality gates: **pytest**, **ruff**, **mypy**. **Catalog backup discipline** is part of the operational stack, not optional.

**Core technologies:**

- **Python 3.12+** — catalog tooling, matching, AI orchestration, API — performance, typing, one runtime for the whole pipeline.
- **stdlib `sqlite3` + thin SQL modules** — `.lrcat` and app DB — avoids ORM fragility on Adobe schema; explicit transactions for writes.
- **Pillow + ImageHash** — normalization and perceptual/difference hashes — standard, low-GPU path for “same photo, different export.”
- **Pydantic 2.x** — critique JSON, jobs, provider config — structured outputs and API validation.
- **FastAPI + Uvicorn** (greenfield API) *or* **Flask + Flask-SocketIO** (current repo) — HTTP + async-friendly or lowest migration cost, respectively.
- **React + Vite + TypeScript + Recharts** — data-dense UI and analytics — aligns with existing visualizer direction.

### Expected Features

**Must have (P1 / table stakes + MVP launch):**

- **Non-destructive, auditable catalog interaction** — trust; narrow write surface (keywords), clear scope.
- **Fast browse / filter / search** — large libraries; pagination, lazy thumbs, indexed app DB queries.
- **Stable asset identity** — path + internal id; foundation for matching and jobs.
- **Human-in-the-loop for writes** — confirm matches before keyword writeback; undo/dry-run story.
- **Job visibility** — queued / running / failed; errors and partial results for AI and matching.
- **Provider / model configuration** — endpoints, models, limits surfaced.
- **Register catalogs + browse assets** — proves integration and performance.
- **Instagram dump ingest + list posts** — non-API workflow.
- **Match pipeline with confidence + manual confirm** — core risk reducer.
- **Keyword writeback after confirmation** — Lightroom-side payoff.
- **On-demand single-image critique** (one perspective minimum; multi ready) — validates AI without batch cost explosion.

**Should have (P2 / differentiators and post-validation):**

- **Multi-perspective critique presets** — editor / street / publisher; structured rubrics, not one “master score.”
- **Timeframe / selection batch critique** — once jobs and costs are stable.
- **Instagram analytics tied to matched rows** — fusion of artistic signals and performance.
- **“Best photos” composite ranking** — needs both critique and match quality.
- **Unified photographer identity across catalogs** — rare moat; needs explicit privacy/scoping rules.

**Defer (P3 / v2+):**

- **Deep cross-catalog identity dashboard** — after core workflows stick.
- **Re-import diff / dump history** — merge semantics when users re-export monthly.
- **Second platform / heavy export integrations** — explicit demand only.

Full landscape and dependency graph: [FEATURES.md](./FEATURES.md).

### Architecture Approach

Treat **`.lrcat` as Lightroom’s domain** and an **app-owned SQLite (or DB)** for matches, AI output, jobs, and analytics. Only a **catalog I/O module** runs raw SQL against `.lrcat`; higher layers use typed records. **Matching** produces candidates → cheap signals → optional capped vision; **persist proposals in the app DB** until the user confirms, then write keywords. **Jobs** carry all long-running work with durable state and progress to the UI. **Catalog context (`catalog_id`)** must thread through APIs and jobs to prevent cross-catalog leaks and wrong write-back targets. Package layout: `lightroom/` for catalog I/O, `core/` for matcher/vision/DB, source adapters (e.g. Instagram) separate, `apps/visualizer/` thin over orchestration.

**Major components:**

1. **Catalog reader / writer** — safe open, batch queries, minimal transactional writes (keywords); backup and LR-closed policy.
2. **App / library DB** — scan cache, matches, AI results, job state; migrations; JSON for flexible payloads.
3. **Matching engine** — layered pipeline behind a `Matcher` interface; optional vision injection.
4. **AI pipeline** — provider registry, retries/cache, idempotent keys (image + model + prompt version).
5. **Ingestion adapters** — versioned Instagram dump parsing → canonical rows.
6. **Job queue + progress** — workers; REST/WebSocket (or SSE) for status.
7. **Multi-catalog registry** — active catalog; scoped queries; optional cross-catalog aggregates with explicit rules.

### Critical Pitfalls

1. **Treating `.lrcat` as generic SQLite** — corruption, locks, version-sensitive schema — **avoid:** read-only default, minimal writes, backup `.lrcat` + WAL/SHM, do not write while Lightroom holds the file without a tested strategy (usually: don’t).
2. **Write-back without audit or confirmation** — wrong keywords at scale — **avoid:** app DB staging, explicit confirm/dry-run, idempotent writes, audit fields (confidence, catalog id, timestamp).
3. **Matching on filenames, dates, or pixel hashes alone** — false negatives/positives on IG re-encode/crop — **avoid:** tiered signals, perceptual hash + optional vision on top-K, confidence + override UI.
4. **Assuming one Instagram export layout forever** — silent broken imports — **avoid:** versioned adapters, format probes, fixtures per revision, user-visible parse reports.
5. **Non-reproducible or unbounded AI** — cost spikes, inconsistent scores — **avoid:** store model/provider/prompt version and decoding settings, job caps and cancellation, low temperature for rubrics, on-demand scope (no mandatory full-catalog indexing).

Additional traps: unstable multi-perspective contracts without JSON schema and golden tests; naive full scans and N+1 queries at scale; multi-catalog queries without mandatory scoping. Full list: [PITFALLS.md](./PITFALLS.md).

## Implications for Roadmap

Suggested phase structure follows **low-level dependencies first**: app DB + scan before AI; cheap matcher before vision-heavy matcher; confirmed writeback only after match review; analytics after ingest + match keys.

### Phase 1: Catalog & application data foundation

**Rationale:** Everything else needs stable inventory, safe read paths, and an app DB — not raw `.lrcat` as the only store.  
**Delivers:** Config/paths, app DB schema + migrations, catalog reader → scan into app DB, path resolution basics, read policy and backup documentation.  
**Addresses:** Table stakes (identity, browse performance baseline), FEATURES dependency chain root.  
**Avoids:** Pitfall 1 (generic SQLite treatment), Pitfall 7 (naive full scans) — start with pagination/indexing plan.

### Phase 2: Instagram dump ingest & tiered matching

**Rationale:** Matching is the critical path for writeback and analytics; ingest must be versioned and testable.  
**Delivers:** Versioned dump adapter, normalized external rows, hasher pipeline, matcher stages (candidates → pHash/dHash → optional vision cap), match review data in app DB.  
**Addresses:** P1 match + ingest; differentiator “image-backed match.”  
**Avoids:** Pitfalls 3–4 (weak signals, fragile export layout).

### Phase 3: Confirmed keyword writeback & job UX

**Rationale:** Lightroom payoff must not ship without human confirmation and operational safety.  
**Delivers:** Confirmation/dry-run flows, minimal catalog writer, transactional write strategy, job status/errors (extend if not done in Phase 1–2).  
**Addresses:** P1 keyword writeback; table stakes job visibility.  
**Avoids:** Pitfall 2 (unaudited writes).

### Phase 4: AI analysis & providers

**Rationale:** Critique builds on job infrastructure and stable image access; provider abstraction avoids lock-in.  
**Delivers:** Provider registry, vision/describe clients, cache, structured Pydantic outputs, single-image on-demand jobs; prompt/version metadata on stored results.  
**Addresses:** P1 on-demand critique; foundation for P2 multi-perspective.  
**Avoids:** Pitfalls 5–6 (cost/reproducibility, unstable multi-perspective output).

### Phase 5: Analytics fusion, scale, & multi-catalog depth

**Rationale:** Dashboards and cross-catalog narrative need reliable match keys and scoped aggregation.  
**Delivers:** Analytics rollups joined on matches, Recharts (or equivalent) surfaces, multi-catalog registry hardening, optional batch critique by timeframe, “best of” when signals exist.  
**Addresses:** P2 analytics, unified identity (where explicitly scoped).  
**Avoids:** Pitfall 8 (ambiguous multi-catalog scope), scale traps (indexes, async jobs).

### Phase Ordering Rationale

- **FEATURES** dependency graph: dump ingest and catalog identity precede match; match review precedes writeback; matching precedes analytics fusion.  
- **ARCHITECTURE** build order: scan + app DB → hasher + ingest → matcher → writer → vision-augmented matcher → jobs → multi-catalog → analytics.  
- **PITFALLS** mapping: foundation phases own catalog SQLite discipline and scale; ingest/matching own export fragility and signal quality; writeback owns audit; AI owns versioning and caps.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1 (catalog foundation):** Adobe schema varies by Lightroom major version — maintain a small version matrix and test on real catalog **copies**.  
- **Phase 2 (ingest & matching):** Meta export format drift — keep fixture exports and detection probes; consider labeled eval set for precision/recall targets.  
- **Phase 4 (AI):** Provider-specific limits, structured output quirks, and cost models — spike per chosen vendor; LiteLLM only if multi-provider is real.

Phases with standard patterns (lighter research):

- **Phase 4 (job + progress patterns):** Established job-queue + polling/WebSocket patterns; repo already has Socket.IO direction.  
- **Phase 1 (app DB):** SQLite + migrations are well-trodden; risk is mostly catalog-specific, not greenfield ORM design.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM–HIGH | Versions checked PyPI/npm 2026-04-10; FastAPI vs Flask trade-off is situational for this repo. |
| Features | MEDIUM | Grounded in PROJECT.md and product landscape; no cited user interviews. |
| Architecture | MEDIUM | Common companion-app pattern; exact LR internals undocumented and version-dependent. |
| Pitfalls | HIGH | Practitioner consensus on SQLite, exports, and vision cost; schema details need per-version validation. |

**Overall confidence:** MEDIUM–HIGH for engineering direction; MEDIUM for product prioritization until validated in use.

### Gaps to Address

- **User validation:** Confirm MVP scope (e.g. minimum perspectives, batch job expectations) with real workflows — use early shipping or interviews.  
- **Lightroom versions:** Lock supported major versions and add regression queries on sample catalogs.  
- **Instagram export samples:** Collect anonymized fixtures across locales/account types for parser coverage.  
- **Matching quality metrics:** Define acceptable precision/recall or “good enough” UX thresholds for launch.

## Sources

### Primary (HIGH confidence)

- **PyPI / npm registry** — package versions cited in [STACK.md](./STACK.md) (verified 2026-04-10).  
- **[`.planning/PROJECT.md`](../PROJECT.md)** — scope, constraints, out-of-scope (no Instagram API, on-demand analysis, web not plugin).

### Secondary (MEDIUM confidence)

- [STACK.md](./STACK.md), [FEATURES.md](./FEATURES.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [PITFALLS.md](./PITFALLS.md) — synthesized research set (2026-04-10).  
- Community Lightroom catalog notes (e.g. lrcat structure docs) — unofficial; validate against your catalogs.

### Tertiary (LOW confidence — validate in implementation)

- Exact `AgLibrary*` column behavior across all Lightroom releases — treat as version-sensitive until probed.

---
*Research completed: 2026-04-10*  
*Ready for roadmap: yes*
