# Roadmap: Lightroom Tagger & Analyzer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-04-11) · [archive](./milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Advanced Critique & Insights** — Phases 5–11 (shipped 2026-04-15) · [archive](./milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Consolidate** — 9 phases (shipped 2026-04-23) · [archive](./milestones/v2.1-ROADMAP.md)
- 🚧 **v3.0 Intelligent Discovery** — 7 phases (in progress) — [roadmap below](#v3-0-intelligent-discovery)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-04-11</summary>

- [x] Phase 1: Catalog management (CAT-01..05) — completed 2026-04-10
- [x] Phase 2: Jobs & system reliability (SYS-01..05) — completed 2026-04-10
- [x] Phase 3: Instagram sync (IG-01..06) — completed 2026-04-10
- [x] Phase 4: AI analysis (AI-01..06) — completed 2026-04-11

</details>

<details>
<summary>✅ v2.0 Advanced Critique & Insights (Phases 5–11) — SHIPPED 2026-04-15</summary>

- [x] Phase 5: Structured scoring foundation (6 plans) — SCORE-02, SCORE-05, SCORE-06, SCORE-07, JOB-01, JOB-02
- [x] Phase 6: Scoring pipeline & catalog score UX (4 plans) — SCORE-01, SCORE-03, SCORE-04
- [x] Phase 7: Posting analytics (4 plans) — POST-01, POST-02, POST-03, POST-04
- [x] Phase 8: Identity & suggestions (3 plans) — IDENT-01, IDENT-02, IDENT-03
- [x] Phase 9: Insights dashboard (3 plans) — DASH-01
- [x] Phase 10: Batch scoring fix & integration bugs (2 plans) — gap closure
- [x] Phase 11: Verification & documentation update (2 plans) — gap closure

</details>

<details>
<summary>✅ v2.1 Polish & Consolidate (9 phases) — SHIPPED 2026-04-23</summary>

- [x] Phase 1: Matching & review polish — POLISH-01, POLISH-02 — completed 2026-04-17
- [x] Phase 2: Job queue & processing UX — JOB-03, JOB-04, JOB-05 — completed 2026-04-17
- [x] Phase 3: Unified Analyze job — JOB-06 — completed 2026-04-17
- [x] Phase 4: Reusable filter framework — FILTER-01, FILTER-02 — completed 2026-04-17
- [x] Phase 4.1 (INSERTED 2026-04-17): InstagramTab filter migration — FILTER-02 — completed 2026-04-17
- [x] Phase 5: Identity & Insights clarity — IDENT-04, IDENT-05, DASH-02, DASH-03 — completed 2026-04-21
- [x] Phase 6: Images page visual consistency — UI-01, UI-02, UI-03 — completed 2026-04-22
- [x] Phase 7: React Suspense data layer — DATA-01 — completed 2026-04-23
- [x] Phase 8: Two-stage cascade matching — MATCH-01..04 — completed 2026-04-21

</details>

### 🚧 v3.0 Intelligent Discovery

<a id="v3-0-intelligent-discovery"></a>

**Goal:** Turn the catalog from a passive archive into a queryable, visually-aware library you can explore by meaning, mood, and similarity.

**Build order (research-aligned):** schema + visual attributes on descriptions → keyword/FTS → LLM-to-filters + facets → text embeddings + semantic “why matched” → stack detection jobs → image embeddings + chat search UI → visual similarity + stack surfaces → stack-aware match/edit + pin-to-similar in chat.

| Phase | Name | Focus |
|-------|------|--------|
| 1 | [Visual tags & keyword search](#phase-1--visual-tags--keyword-search) | VIS-01, NLS-02 |
| 2 | [NL filters](#phase-2--nl-filters) | NLS-01 |
| 3 | [Semantic search & results](#phase-3--semantic-search--results) | NLS-03, NLS-04 |
| 4 | [Stack detection](#phase-4--stack-detection) | STACK-01, STACK-02 |
| 5 | [Image embed & search chat](#phase-5--image-embed--search-chat) | SIM-01, NLS-05 |
| 6 | [Similarity & stack UI](#phase-6--similarity--stack-ui) | SIM-02, STACK-03 |
| 7 | [Stacks in matching & pin similarity](#phase-7--stacks-in-matching--pin-similarity) | STACK-04, STACK-05, NLS-06 |

#### Phase 1 — Visual tags & keyword search

**Requirements:** VIS-01, NLS-02

- Additive schema and storage for `dominant_colors`, `mood_tags`, and `has_repetition` on `image_descriptions` with describe-time extraction and backfill path for new describes.
- Denormalized `search_text` (or equivalent) maintained on describe/store; **FTS5** index for lexical search over description and keyword text.
- API and catalog list path support keyword/phrase search over description text (filter or dedicated search parameter) with tests proving no raw SQL from user input.
- Re-describe and storage flows preserve existing description consumers; null-safe serialization for pre-migration rows.

#### Phase 2 — NL filters

**Plan progress:** 02-01 + 02-02 **complete** (2026-04-23) — Pydantic filter + DB arrays; `POST /api/images/nl-search` with `ProviderRegistry` + `FallbackDispatcher` + `complete_chat_text`, API tests. Phase 2 NL filters: **done** (next: Phase 3).

**Requirements:** NLS-01

- Natural-language input is translated to a **validated** Pydantic filter object (allowlisted fields only, including `dominant_colors` and `mood_tags` from VIS-01); invalid shapes rejected with clear errors.
- End-to-end path from NL box → filters → result list without executing model-generated SQL.
- LLM is always called — no bypass logic; provider/registry alignment via existing `FallbackDispatcher` + `complete_chat_text` pattern.

#### Phase 3 — Semantic search & results

**Plan progress:** **6/6 complete** (2026-04-23) — 03-01 sqlite-vec + `image_text_embeddings`; 03-02 embedding service; 03-03 `batch_text_embed` job; 03-04 `run_semantic_hybrid_search` + RRF (k=60); 03-05 `POST /api/images/semantic-search`; 03-06 tests (RRF matrix, handler, API, catalog job types). Artifact: `03-06-SUMMARY.md`.

**Requirements:** NLS-03, NLS-04

- `batch_text_embed` (or equivalent) job stores text vectors keyed for hybrid use with FTS; coverage/progress visible when index is building.
- Semantic queries return ranked catalog results; hybrid ranking (e.g. RRF or weighted fusion) documented and test-covered for deterministic inputs.
- Result rows show thumbnails, scores, and a short “why matched” string per item (source: FTS, embedding, filter facet, or combination).
- Degradation path when embeddings missing (keyword + filters only) is explicit in UI or response metadata.

#### Phase 4 — Stack detection

**Requirements:** STACK-01, STACK-02

- Schema: `image_stacks` + `image_stack_members` with `UNIQUE(image_key)`; migrations idempotent.
- Job groups burst sequences by `date_taken` within configurable `delta_ms` with checkpointed progress.
- Second pass clusters time-separated near-duplicates via pHash (Hamming threshold configurable); bad/null `date_taken` handled without corrupting groups. *(STACK-02 pHash clustering: descoped from Phase 4 — dropped per user decision 2026-04-24)*
- Observable job lifecycle for stack jobs consistent with existing job UX.

#### Phase 5 — Image embed & search chat

**Requirements:** SIM-01, NLS-05

- `batch_embed_image` (or equivalent) stores float vectors with `model_id` + `dim` (and invalidation/fingerprint rules per research); sqlite-vec or approved fallback for storage/KNN prep.
- Image embedding job uses checkpointing, cancellation, and progress reporting consistent with existing batch job patterns; skips unchanged images when fingerprints match.
- Chat-like layout: conversation thread on one side, results grid on the other; each turn refines the active result set using the Phase 1–3 search stack.
- Empty, loading, and error states for the panel; no dependency on visual similarity for basic chat search (pin comes in Phase 7).

#### Phase 6 — Similarity & stack UI

**Requirements:** SIM-02, STACK-03

- `GET` (or equivalent) **similar** API: seed image → KNN/ANN results with optional pre-filters; never mixes vectors from different `model_id`/dims.
- Catalog and Best Photos show stack **representative** with member count; expand/collapse to browse members without breaking existing list performance budgets.
- “More like this” entry point from catalog (and wiring for chat pin in Phase 7) is reachable in the UI with consistent card/grid patterns.

#### Phase 7 — Stacks in matching & pin similarity

**Requirements:** STACK-04, STACK-05, NLS-06

- Instagram matching compares dump media to **stack representatives** only; match association applies to the full stack per contract.
- User can split, merge, and change representative with persistence and safe defaults for edge cases.
- NLS-05 chat panel supports **pin** active catalog image → triggers visual similarity (uses SIM-01/SIM-02); result set updates in the grid.
- End-to-end tests or integration checks for representative-only matching vs member expansion.

#### Progress (v3.0)

| Phase | Goal | Requirements | Success criteria count | Status |
|-------|------|--------------|------------------------|--------|
| 1 | Visual tags & keyword search | VIS-01, NLS-02 | 4 | ✅ Complete (2026-04-23) |
| 2 | NL filters | NLS-01 | 3 | ✅ Complete (2026-04-23) |
| 3 | Semantic search & results | NLS-03, NLS-04 | 4 | ✅ Complete (2026-04-23; 6/6 plans) |
| 4 | Stack detection | STACK-01, STACK-02 | 4 | ✅ Complete (2026-04-24; 4/4 plans) |
| 5 | Image embed & search chat | SIM-01, NLS-05 | 4 | ✅ Complete (2026-04-24; 6/6 plans) |
| 6 | Similarity & stack UI | SIM-02, STACK-03 | 3 | Pending |
| 7 | Stacks in matching & pin similarity | STACK-04, STACK-05, NLS-06 | 4 | Pending |

---

*Roadmap created: 2026-04-10 · v1.0 shipped: 2026-04-11 · v2.0 shipped: 2026-04-15 · v2.1 shipped: 2026-04-23 · v3.0 roadmap: 2026-04-23*
