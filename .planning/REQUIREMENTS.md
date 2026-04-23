# Requirements — Milestone v3.0 Intelligent Discovery

**Goal:** Turn the catalog from a passive archive into a queryable, visually-aware library you can explore by meaning, mood, and similarity.

**Started:** 2026-04-23
**Status:** Defining requirements
**Seeds incorporated:** SEED-005, SEED-006, SEED-018

---

## v3.0 Requirements

### Natural Language Search

- [ ] **NLS-01**: User can type a natural language query and get catalog results mapped from structured filters — LLM returns a validated filter object (date ranges, scores, posted status, keywords), never raw SQL
- [ ] **NLS-02**: User can search description text with keywords and get matching catalog photos
- [ ] **NLS-03**: Semantic search understands abstract queries ("moody cityscapes", "feeling of solitude") using text embeddings
- [ ] **NLS-04**: Search results show thumbnails, scores, and a brief "why matched" explanation per result
- [ ] **NLS-05**: Search is accessible as a chat-like panel with conversation history on one side and a results grid on the other; each message refines the active result set
- [ ] **NLS-06**: User can pin a catalog photo inside the chat panel to trigger visual similarity search ("find more like this")

### Photo Stacking

- [ ] **STACK-01**: Job detects burst shots (photos within a configurable time window by date_taken) and groups them into stacks
- [ ] **STACK-02**: Job clusters visually similar but time-separated photos into stacks using pHash similarity
- [ ] **STACK-03**: Catalog and Best Photos views show the stack representative with a count badge; user can expand to see all members
- [ ] **STACK-04**: Stack-aware matching: Instagram matching compares against stack representatives only, then associates the match result with the full stack
- [ ] **STACK-05**: User can split or merge stacks and change which image is the representative

### Visual Attribute Tags

- [ ] **VIS-01**: Describe pipeline extracts dominant_colors, mood_tags, and has_repetition as structured fields alongside existing description output
- [ ] **VIS-02**: Catalog filter bar surfaces color and mood facets for filtering

### Visual Similarity Search

- [ ] **SIM-01**: Job generates and stores image embeddings (CLIP-style) for catalog images
- [ ] **SIM-02**: "More like this" from any catalog photo surfaces visually similar results, accessible from the catalog view and from within the NLS-05 chat panel (NLS-06)

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

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| NLS-01 | TBD | Pending |
| NLS-02 | TBD | Pending |
| NLS-03 | TBD | Pending |
| NLS-04 | TBD | Pending |
| NLS-05 | TBD | Pending |
| NLS-06 | TBD | Pending |
| STACK-01 | TBD | Pending |
| STACK-02 | TBD | Pending |
| STACK-03 | TBD | Pending |
| STACK-04 | TBD | Pending |
| STACK-05 | TBD | Pending |
| VIS-01 | TBD | Pending |
| VIS-02 | TBD | Pending |
| SIM-01 | TBD | Pending |
| SIM-02 | TBD | Pending |

**Total:** 15 requirements across 4 categories.

---

## Dependencies

- **NLS-03** depends on text embeddings from a `batch_text_embed` job (needs NLS-01 and NLS-02 first to establish search layer)
- **NLS-06** depends on **SIM-01** (image embeddings must exist to power the pinned-photo similarity trigger in the chat panel)
- **STACK-04** depends on **STACK-01** and **STACK-02** (stacks must exist before matching can use representatives)
- **STACK-03** depends on **STACK-01** (at minimum burst stacks needed for Best Photos view)
- **SIM-02** depends on **SIM-01** (embeddings must be generated before similarity queries work)
- **VIS-02** depends on **VIS-01** (attributes must be extracted before filter facets can be wired)

## Implementation Guidance (non-requirement)

- LLM-to-SQL: The LLM must return a **validated filter object** (Pydantic), not executable SQL. Allowlisted query parameters only. Reuse existing `ProviderRegistry` pattern.
- Stacking: Use `date_taken` for burst detection (no `capture_time` column today). Build `image_stacks` + `image_stack_members` tables with `UNIQUE(image_key)` so each image belongs to at most one stack in v1.
- Visual attributes: Store `dominant_colors` (JSON), `mood_tags` (JSON), `has_repetition` (int) as nullable columns on `image_descriptions`. Old rows default NULL. No breaking change.
- Image embeddings: Use `open-clip-torch` 3.3.0. Store in `image_embeddings` table keyed by `model_id` + `dim` so re-embedding on model change is safe. Use `sqlite-vec` 0.1.9 for KNN queries at scale.

---

*Requirements defined: 2026-04-23*
