# Requirements — Milestone v3.0 Intelligent Discovery

**Goal:** Turn the catalog from a passive archive into a queryable, visually-aware library you can explore by meaning, mood, and similarity.

**Started:** 2026-04-23
**Status:** Roadmap defined
**Seeds incorporated:** SEED-005, SEED-006, SEED-018

---

## v3.0 Requirements

### Natural Language Search

- [x] **NLS-01**: User can type a natural language query and get catalog results mapped from structured filters — LLM returns a validated filter object (date ranges, scores, posted status, keywords), never raw SQL *(API: `POST /api/images/nl-search`, 2026-04-23; natural-language **UI** in NLS-05)*
- [ ] **NLS-02**: User can search description text with keywords and get matching catalog photos
- [x] **NLS-03**: Semantic search understands abstract queries ("moody cityscapes", "feeling of solitude") using text embeddings
- [x] **NLS-04**: Search results show thumbnails, scores, and a brief "why matched" explanation per result
- [x] **NLS-05**: Search is accessible as a chat-like panel with conversation history on one side and a results grid on the other; each message refines the active result set *(Phase 5 — 2026-04-24)*
- [ ] **NLS-06**: User can pin a catalog photo inside the chat panel to trigger visual similarity search ("find more like this")

### Photo Stacking

- [x] **STACK-01**: Job detects burst shots (photos within a configurable time window by date_taken) and groups them into stacks
- [x] **STACK-03**: Catalog and Best Photos views show the stack representative with a count badge; user can expand to see all members *(Phase 6 — 2026-04-25)*
- [ ] **STACK-04**: Stack-aware matching: Instagram matching compares against stack representatives only, then associates the match result with the full stack
- [ ] **STACK-05**: User can split or merge stacks and change which image is the representative

### Visual Attribute Tags

- [ ] **VIS-01**: Describe pipeline extracts dominant_colors, mood_tags, and has_repetition as structured fields alongside existing description output

### Visual Similarity Search

- [x] **SIM-01**: Job generates and stores image embeddings (CLIP-style) for catalog images *(Phase 5 — 2026-04-24)*
- [ ] **SIM-02**: "More like this" from any catalog photo surfaces visually similar results, accessible from the catalog view; chat-panel pin remains scoped to NLS-06 *(Phase 6 implementation — 2026-04-25; UX pivoted to job-driven similarity groups by quick `260427-f75` on 2026-04-27 — text rewrite + dead-code removal pending in Phase 9)*

### Matching Performance & Catalog Cache Pipeline *(added 2026-04-27)*

- [ ] **MATCH-02**: `vision_match` consults `image_clip_embeddings` to cosine-shortlist date-windowed catalog candidates before LLM judgment runs. Pre-filter reduces LLM comparison calls by ≥10× vs the Phase 7 baseline on a representative batch, while preserving recall on user-validated match pairs. Pipeline emits per-stage candidate counts (date-window in → embedding shortlist out → LLM judgments) in the job log.
- [x] **CACHE-01**: Catalog cache pipeline rewire — `batch_stack_detect` and `batch_catalog_similarity` are recognized as catalog-cache work (they consume `image_clip_embeddings` and produce cache artifacts). UI triggers live on the catalog cache surface, not the matching tab. The cache builds as a chain (`batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`) with per-stage progress and skip reasons visible; individual stages remain re-runnable. *(Phase 8 — backend composite job 08-04; MatchingTab cleanup 08-05; CatalogCacheTab UI 08-06 — 2026-04-27)*

---

## Future Requirements

- NLS multi-turn refinement memory across sessions (v3.1)
- Stack-aware descriptions (re-describe if representative changes) — deferred; each member keeps its own description independently
- SEED-007 full filter rollout (MatchesTab, DescriptionsTab, MatchingTab, AnalyticsPage) — deferred from v2.1
- SEED-010: Persist tab and filter state in-memory across navigation
- SEED-011: CVA for Tailwind variant composition
- SEED-012: Skeleton loading + reusable image-grid primitive
- SEED-014: Unified vision match + describe in a single batch call
- SEED-016: Rotate catalog images
- SEED-017 / SEED-020: Backend DRY/KISS refactor
- SEED-019: Per-image differentiated reasoning for "What to Post Next"

## Out of Scope (v3.0)

- Score propagation from stack representative to members — each image scores independently; stacking is about catalog clarity and matching efficiency, not scoring cost
- Multi-catalog / cross-catalog search — single catalog search first
- Instagram engagement data (likes/saves) — no API access
- Real-time / streaming search results
- Voice input for NL search
- Embedding generation at import time (lazy generation via job is sufficient)
- **STACK-02** *(descoped 2026-04-24)*: pHash clustering for time-separated near-duplicates was dropped from Phase 4 scope; burst-only stacks (**STACK-01**) are sufficient for v3.0.

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| NLS-01 | 2 | Complete (2026-04-23) — API + validation |
| NLS-02 | 1 | Pending |
| NLS-03 | 3 | ✅ Complete (2026-04-23) |
| NLS-04 | 3 | ✅ Complete (2026-04-23) |
| NLS-05 | 5 | ✅ Complete (2026-04-24) |
| NLS-06 | 7 | Pending |
| STACK-01 | 4 | ✅ Complete (2026-04-24) |
| STACK-02 | 4 | Pending |
| STACK-03 | 6 | ✅ Complete (2026-04-25) |
| STACK-04 | 7 | Pending |
| STACK-05 | 7 | Pending |
| VIS-01 | 1 | Pending |
| SIM-01 | 5 | ✅ Complete (2026-04-24) |
| SIM-02 | 6, 9 | Partial — Phase 9 (gap closure: pivot doc sync + orphaned-code removal) |
| MATCH-02 | 8, 10 | Partial — Phase 10 (gap closure: quantitative ≥10× benchmark on user-validated match pairs) |
| CACHE-01 | 8 | ✅ Complete (2026-04-27) |

**Total:** 16 requirements across 5 categories. Gap closure phases 9, 10, 11 added 2026-04-29 from `v3.0-MILESTONE-AUDIT.md` (status: `tech_debt`).

---

## Dependencies

- **NLS-03** depends on text embeddings from a `batch_text_embed` job (needs NLS-01 and NLS-02 first to establish search layer)
- **NLS-06** depends on **SIM-01** (image embeddings must exist to power the pinned-photo similarity trigger in the chat panel)
- **STACK-04** depends on **STACK-01** (burst stacks and representatives required for representative-only matching; **STACK-02** pHash clustering is descoped for v3.0 — see Out of Scope).
- **STACK-03** depends on **STACK-01** (at minimum burst stacks needed for Best Photos view)
- **SIM-02** depends on **SIM-01** (embeddings must be generated before similarity queries work)
- **MATCH-02** depends on **SIM-01** (CLIP embeddings must populate `image_clip_embeddings` before the matching pre-filter can shortlist) and on **STACK-04** (representative-only candidate filter from Phase 7 must already cut non-rep rows before the embedding shortlist runs)
- **CACHE-01** depends on **SIM-01**, **STACK-01**, and **SIM-02** (the cache stages being chained — embed, stack-detect, catalog-similarity — must each already exist as standalone jobs)

## Implementation Guidance (non-requirement)

- LLM-to-SQL: The LLM must return a **validated filter object** (Pydantic), not executable SQL. Allowlisted query parameters only. Reuse existing `ProviderRegistry` pattern.
- Stacking: Use `date_taken` for burst detection (no `capture_time` column today). Build `image_stacks` + `image_stack_members` tables with `UNIQUE(image_key)` so each image belongs to at most one stack in v1.
- Visual attributes: Store `dominant_colors` (JSON), `mood_tags` (JSON), `has_repetition` (int) as nullable columns on `image_descriptions`. Old rows default NULL. No breaking change.
- Image embeddings: Use `open-clip-torch` 3.3.0. Store in `image_embeddings` table keyed by `model_id` + `dim` so re-embedding on model change is safe. Use `sqlite-vec` 0.1.9 for KNN queries at scale.

---

*Requirements defined: 2026-04-23*
