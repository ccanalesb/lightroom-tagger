# Roadmap: Lightroom Tagger & Analyzer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-04-11) · [archive](./milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Advanced Critique & Insights** — Phases 5–11 (shipped 2026-04-15) · [archive](./milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Polish & Consolidate** — 9 phases (shipped 2026-04-23) · [archive](./milestones/v2.1-ROADMAP.md)
- 🚧 **v3.0 Intelligent Discovery** — 8 phases (in progress) — [roadmap below](#v3-0-intelligent-discovery)

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
| 7.1 | [Phase 7 remediation fixes](#phase-71--phase-7-remediation-fixes-inserted-2026-04-26) | Remediation |
| 8 | [Embedding pre-filter & catalog cache pipeline](#phase-8--embedding-pre-filter--catalog-cache-pipeline) | MATCH-02, MATCH-03, CACHE-01 |

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

#### Phase 5.1 — Search UI polish *(inserted 2026-04-24)*

**Goal:** Fix four concrete UX issues in the Search page: missing clear button, excessive spacing, broken mobile layout, cut-off provider/model dropdowns.

- Clear button wipes conversation thread and result grid when at least one message exists.
- Layout density tightened — reduced gaps, better column balance at desktop widths.
- Mobile layout: single-column stacking, selector row wraps gracefully, input doesn't overflow.
- Provider/model dropdowns handle long names without clipping or layout overflow.

#### Phase 5.2 — Tool-calling search *(inserted 2026-04-24)*

**Goal:** Replace the single-shot JSON filter approach with a multi-tool LLM architecture where the model reasons about intent and calls typed tools — enabling superlatives ("the best"), quantity control, and smarter composition.

**Design decisions (agreed 2026-04-24):**
- Multiple focused tools (not one monolithic filter object)
- Capability detection at model-selector time — models that don't support function calling are not shown for chat search
- Tool results include rich metadata (description, score, rationale, mood_tags, date_taken) bounded by the `limit` the model requests
- User controls context size by requesting "next 10" etc.; no artificial server-side capping
- Multi-turn history stores tool calls + results so model retains search context across turns

**Tools to implement:**
- `search_catalog(description_search?, score_perspective?, sort_by_score?, sort_by_date?, min_score?, min_rating?, limit?)` — main workhorse
- `get_scoring_perspectives()` — runtime discovery of valid perspective slugs
- `filter_by_date(date_from?, date_to?, sort_direction?, limit?)` — temporal queries

**Requirements:**
- Backend executes tool calls from LLM response and feeds results back as tool messages
- Models without function calling support are filtered from the chat search model selector
- Tool results return rich image metadata (description, score, rationale, mood_tags, date_taken) up to the model-requested limit
- Conversation history preserves tool call / tool result turns for multi-turn continuity
- Fallback path for non-capable models still works via existing JSON approach (for other features)

#### Phase 6 — Similarity & stack UI

**Requirements:** SIM-02, STACK-03

**Plan progress:** **4/4 complete** (2026-04-25) — 06-01 stack collapse + metadata; 06-02 CLIP-only similarity core; 06-03 similar + stack members API; 06-04 stack expand UI + “More like this” modal. Verification: 9/9 passed.

**Plans:** 4 plans

Plans:

- [x] 06-01-PLAN.md — DB stack collapse + `rank_best_photos` primary-row filter + `stack_id` / `stack_member_count` / `is_stack_representative` on list rows
- [x] 06-02-PLAN.md — `lightroom_tagger/core/clip_similarity.py` CLIP-only KNN + order-preserving catalog filter; unit tests
- [x] 06-03-PLAN.md — Flask: `GET /api/images/catalog/<key>/similar`, `GET /api/images/stacks/<id>/members`, stack fields on catalog/best-photos JSON; `test_images_clip_similar_api.py`
- [x] 06-04-PLAN.md — Frontend: `ImagesAPI.getCatalogSimilar` + strings, Catalog/Best Photos stack expand, `ImageDetailModal` “More like this” + “Visually similar”

- `GET` (or equivalent) **similar** API: seed image → KNN/ANN results with optional pre-filters; never mixes vectors from different `model_id`/dims.
- Catalog and Best Photos show stack **representative** with member count; expand/collapse to browse members without breaking existing list performance budgets.
- “More like this” entry point from catalog (and wiring for chat pin in Phase 7) is reachable in the UI with consistent card/grid patterns.

#### Phase 7 — Stacks in matching & pin similarity

**Requirements:** STACK-04, STACK-05, NLS-06

- Instagram matching compares dump media to **stack representatives** only; match association applies to the full stack per contract.
- User can split, merge, and change representative with persistence and safe defaults for edge cases.
- NLS-05 chat panel supports **pin** active catalog image → triggers visual similarity (uses SIM-01/SIM-02); result set updates in the grid.
- End-to-end tests or integration checks for representative-only matching vs member expansion.

#### Phase 7.1 — Phase 7 remediation fixes *(INSERTED 2026-04-26)*

**Goal:** Correct regressions and implementation defects from Phase 7 so STACK-04, STACK-05, and NLS-06 behavior is production-safe and test-verified.

**Requirements:** Remediation

- Fix priority defects introduced in Phase 7 implementation before advancing to embedding pre-filter work.
- Keep scope constrained to correction/hardening of shipped Phase 7 surfaces (matching, stack edits, and pin similarity).
- Add verification coverage for each fixed defect and re-run relevant Phase 7 acceptance checks.

#### Phase 8 — Embedding pre-filter & catalog cache pipeline *(scope expanded 2026-04-27)*

**Goal:** (1) Make `image_clip_embeddings` actually useful in matching by wiring a CLIP-cosine pre-filter into `vision_match` so LLM judgment runs only on a recall-first shortlist, and (2) re-home stack-detect and catalog-similarity as catalog-cache pipeline stages — they consume cache artifacts (CLIP embeddings) and produce cache artifacts (stacks, similarity groups), so their triggers belong on the catalog cache surface, not under matching. Phases 5 and 6 built the embedding/similarity infrastructure; Phase 7 wired stacks into matching. Phase 8 is the wiring that turns those investments into matching-performance wins.

**Why now:** Today `vision_match` calls the LLM on every non-rep date-windowed catalog row even though CLIP vectors for those exact rows already sit in `image_clip_embeddings`. Matching is paying full LLM cost for work the cache could pre-shortlist. Separately, `batch_stack_detect` and `batch_catalog_similarity` triggers currently live under MatchingTab even though they are catalog-cache jobs (operate on catalog images, depend on `batch_embed_image`, produce cache artifacts).

**Design decisions (locked from 2026-04-24, retained):**
- Date window (90 days) remains the first filter — cuts effective catalog size before any embedding work
- Recall-first top-k (generous default, e.g. top-100/200) — missing a true match is worse than extra LLM calls
- LLM cascade runs only on the shortlist, not the full catalog
- Opt-in fallback: when shortlist is empty, user can explicitly trigger a wider search (extended or removed date window); fallback is never automatic
- Pipeline is observable — every stage logs candidate counts in/out

**Design decisions (added 2026-04-27 with expanded scope):**
- Stack detection and catalog similarity are catalog-cache pipeline stages, not matching jobs — UI triggers live on the catalog cache surface
- Cache builds as a chain (embed → stack-detect → catalog-similarity); user can run the chain as one composite "Build cache" job, and chain steps are individually re-runnable for surgical refresh
- Embedding model question (DINOv2 vs CLIP vs SigLIP) is deferred — Phase 8 wires the existing CLIP embeddings; benchmark-embedding-recall is its own follow-up todo and may promote a different model in a later phase
- FAISS vs sqlite-vec is a discuss-phase decision — sqlite-vec is already loaded and powers similarity today; FAISS is real engineering only justified if sqlite-vec KNN can't meet the recall/latency target on this catalog size

**Requirements (covered: MATCH-02, MATCH-03, CACHE-01):**
- `vision_match` consults `image_clip_embeddings` to cosine-shortlist candidates inside the date window before LLM judgment runs; ≥10× LLM-call reduction vs current Phase 7 baseline on a representative batch, with recall preserved on user-validated match pairs
- Stack detection and catalog similarity job triggers live on the catalog cache surface (not the matching tab); cache pipeline runs as a chain (`batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`) with per-stage progress, candidate counts, and skip reasons visible in the job log
- When the pre-filter shortlist is empty for a media item, the UI surfaces an explicit "wider search" opt-in (extended or removed date window); fallback never auto-runs
- Pipeline observability: each cascade stage emits throttled summary logs showing in→out candidate counts, so operators can verify the pre-filter is doing its job
- Benchmark of CLIP recall on user-validated match pairs is captured in the existing `benchmark-embedding-recall.md` todo (separate work, not a Phase 8 gate; sets the top-k floor for tuning)

#### Progress (v3.0)

| Phase | Goal | Requirements | Success criteria count | Status |
|-------|------|--------------|------------------------|--------|
| 1 | Visual tags & keyword search | VIS-01, NLS-02 | 4 | ✅ Complete (2026-04-23) |
| 2 | NL filters | NLS-01 | 3 | ✅ Complete (2026-04-23) |
| 3 | Semantic search & results | NLS-03, NLS-04 | 4 | ✅ Complete (2026-04-23; 6/6 plans) |
| 4 | Stack detection | STACK-01, STACK-02 | 4 | ✅ Complete (2026-04-24; 4/4 plans) |
| 5 | Image embed & search chat | SIM-01, NLS-05 | 4 | ✅ Complete (2026-04-24; 6/6 plans) |
| 5.1 | Search UI polish | — | 4 | ✅ Complete (2026-04-24) |
| 5.2 | Tool-calling search | — | 5 | ✅ Complete (2026-04-24) |
| 6 | Similarity & stack UI | SIM-02, STACK-03 | 3 | ✅ Complete (2026-04-25; 4/4 plans) |
| 7 | Stacks in matching & pin similarity | STACK-04, STACK-05, NLS-06 | 4 | Pending |
| 7.1 | Phase 7 remediation fixes | Remediation | 3 | ✅ Complete (2026-04-26; 3/3 plans) |
| 8 | Embedding pre-filter & catalog cache pipeline | MATCH-02, MATCH-03, CACHE-01 | TBD | Planned (2026-04-27 — scope expanded) |

---

*Roadmap created: 2026-04-10 · v1.0 shipped: 2026-04-11 · v2.0 shipped: 2026-04-15 · v2.1 shipped: 2026-04-23 · v3.0 roadmap: 2026-04-23*
