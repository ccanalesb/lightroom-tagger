# Feature Research

**Domain:** Photography analysis, DAM-adjacent catalog tooling, and Instagram ↔ Lightroom alignment workflows  
**Researched:** 2026-04-10  
**Confidence:** MEDIUM (product landscape + PROJECT.md alignment; no primary user interviews cited)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any serious catalog-facing or “analyze my photos” product. Missing these makes the tool feel unfinished or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Non-destructive catalog interaction** | Photographers assume the app will not corrupt originals or silently rewrite unrelated catalog state. | MEDIUM | Read-heavy paths; narrow, auditable write surface (e.g. keywords only) builds trust. |
| **Fast browse / filter / search** | Large libraries (10k–500k+ assets) are normal; sluggish grids or missing filters cause abandonment. | MEDIUM–HIGH | Pagination, lazy thumbs, indexed queries; depends on catalog schema and asset volume. |
| **Clear asset identity** | Every row must map to one real file path + stable internal id; duplicates and moves must be explainable. | MEDIUM | Foundation for matching, jobs, and audit trails. |
| **Human-in-the-loop confirmation for destructive or semantic changes** | Writes to the catalog (keywords, ratings) need review, undo story, or explicit scope. | LOW–MEDIUM | Especially for match → writeback flows. |
| **Job visibility (queued / running / failed)** | Any AI or batch work is opaque without status, errors, and partial results. | LOW–MEDIUM | Table stakes for on-demand analysis products. |
| **Provider / model configuration** | Users expect to point at an endpoint, pick a model, and see costs or limits surfaced. | LOW–MEDIUM | Multi-provider registries are increasingly expected, not “one hardcoded API.” |
| **Export or copy-paste of results** | Critique and labels need to leave the app (notes, captions, client emails). | LOW | Markdown/clipboard/CSV hooks; low cost, high perceived quality. |
| **Basic security posture for local data** | Catalogs and dumps contain personal work; “runs locally” or clear data boundaries matter. | MEDIUM | Path validation, no accidental exfiltration, documented retention. |

### Differentiators (Competitive Advantage)

Features that win positioning when table stakes are met. For this project, differentiators should reinforce **Lightroom + Instagram dump alignment**, **artistic (not technical) critique**, and **multi-catalog identity**.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Image-backed match: Instagram dump → Lightroom records** | Closes the loop between “what I published” and “where it lives in the catalog” without Instagram API dependency. | HIGH | Vision + hashing + review UI; quality of match UX is the moat. |
| **Writeback of publication state to LRCAT (e.g. keywords)** | Keeps Lightroom as source of truth for culling and filtering posted vs unpublished. | MEDIUM | Depends on safe SQLite write path and user confirmation. |
| **Multi-perspective artistic critique** | Feels like an editor’s room, not a single generic score — aligns with serious photographers and long-form reflection. | MEDIUM–HIGH | Prompt design, consistency, and perspective switching are the product. |
| **Unified photographer identity / pattern view across catalogs** | Rare in tools that treat each library as isolated; supports split workflows (wedding vs personal). | HIGH | Needs cross-catalog aggregation, privacy boundaries, and consistent feature extraction. |
| **Fusion of AI assessment with Instagram performance signals** | Connects *artistic intent* with *audience response* from dump analytics. | MEDIUM–HIGH | Depends on reliable matching and parsed dump metrics. |
| **On-demand analysis with batch-by-scope jobs** | Cost control + user agency vs “analyze everything” SaaS. | MEDIUM | Job runner, retries, idempotency; aligns with stated architecture. |
| **Visualizer / inspection UI for matches and critiques** | Speeds trust and correction — competitors often hide the reasoning chain. | MEDIUM | Side-by-side, confidence, and override flows differentiate quality. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that sound appealing but conflict with constraints, positioning, or sustainable operations for this product class.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Full-catalog mandatory AI indexing** | “Just score everything once.” | Runaway cost, weak value until matching/posting context exists, hard to iterate on prompts. | Time-boxed or selection-based jobs; progressive enrichment. |
| **Instagram real-time sync via API** | Instant reflection of live account. | API limits, ToS risk, auth fragility, duplicates project decision (export dumps). | Scheduled manual dump import; diff-aware re-import. |
| **Lightroom Classic plugin replacing web workflow** | “Stay inside LR.” | Distribution, signing, version matrix, crash support; PROJECT.md places this out of scope. | Keep narrow writeback + web for heavy UI. |
| **EXIF / gear obsession as primary analysis** | Users love camera stats. | Conflicts with artistic positioning; commoditized by many free tools. | Optional sidebar or explicit “out of core narrative” labeling if ever added. |
| **Auto-post / scheduler as core** | “End-to-end social tool.” | Different category (buffering, compliance, analytics APIs); dilutes critique + catalog story. | Deep link or export caption only. |
| **Opaque “master quality score”** | Simple UX. | Photographers distrust single numbers; hard to defend across genres. | Multi-axis rubrics per perspective + textual rationale. |
| **Silent auto-write of keywords** | Convenience. | Trust disaster; hard to audit; support burden. | Confirmed batches + dry-run + per-match toggles. |

## Feature Dependencies

```
[Catalog registration & path resolution]
    └──requires──> [Stable asset identity & thumbnails]
                       └──requires──> [Safe read-only LRCAT access]

[Instagram dump ingest & normalize]
    └──requires──> [Parser for dump format + media layout]
                       └──requires──> [Storage for IG copies / hashes]

[Image match (dump ↔ catalog)]
    └──requires──> [Catalog asset identity]
    └──requires──> [Dump ingest]
    └──requires──> [Vision or perceptual hash pipeline]
                       └──requires──> [Job runner + status UI]

[Match review & confirmation]
    └──requires──> [Image match]
    └──enhances──> [Keyword writeback to LRCAT]

[Keyword writeback to LRCAT]
    └──requires──> [Match review & confirmation]
    └──requires──> [Transactional SQLite write strategy]

[Single-image / batch on-demand critique]
    └──requires──> [Job runner + provider config]
    └──requires──> [Catalog asset identity]

[Multi-perspective prompts]
    └──enhances──> [Single-image / batch critique]

[Instagram analytics fusion]
    └──requires──> [Dump ingest]
    └──requires──> [Image match]
    └──enhances──> [“Best photos” / ranking views]

[Unified photographer identity across catalogs]
    └──requires──> [Multi-catalog switching & registry]
    └──requires──> [Critique / feature summaries per asset]
    └──conflicts──> [Single-catalog siloed UX without shared user profile layer]
```

### Dependency Notes

- **Image match requires catalog identity + dump ingest:** Matching is meaningless without both sides normalized to comparable assets and metadata.
- **Keyword writeback requires confirmed matches:** Prevents corrupting LRCAT keywords with low-confidence associations.
- **Multi-perspective critique enhances generic critique:** Same infrastructure; differentiator is prompt/persona layer and UI surfacing, not a separate backend.
- **Analytics fusion requires successful matching:** Performance metrics must attach to the correct catalog row.
- **Unified identity conflicts with per-catalog silos:** Without a cross-catalog notion of “this photographer” and shared derived features, the narrative view fragments.

## MVP Definition

### Launch With (v1)

Minimum viable product — enough to validate “I can see what’s posted, trust matches, and get useful critique.”

- [ ] **Register one or more catalogs + browse assets** — Proves integration path and performance baseline.
- [ ] **Ingest Instagram dump (defined format) + list IG posts** — Establishes the non-API workflow.
- [ ] **Match pipeline with confidence + manual confirm** — Core risk reducer; without it, writeback and analytics fusion are unsafe.
- [ ] **Keyword writeback for “posted” (or equivalent) after confirmation** — Delivers the Lightroom-side payoff from PROJECT.md.
- [ ] **On-demand critique for a single image (one perspective minimum, multi ready)** — Validates AI value without batch cost explosion.
- [ ] **Job status and error surfacing** — Table stakes for async AI and matching.

### Add After Validation (v1.x)

Features to add once matching and single-image critique are trusted.

- [ ] **Multi-perspective critique presets** — Trigger: users ask for “editor vs street” comparisons repeatedly.
- [ ] **Timeframe / selection-based batch critique jobs** — Trigger: cost model is understood and jobs stable.
- [ ] **Instagram analytics panels tied to matched rows** — Trigger: dump parsing proven stable across exports.
- [ ] **“Best photos” composite ranking** — Trigger: both critique signals and performance data exist with acceptable noise.

### Future Consideration (v2+)

Defer until core workflows are sticky and data quality is high.

- [ ] **Cross-catalog identity dashboard (deep synthesis)** — Needs enough labeled data and UX for privacy boundaries.
- [ ] **Re-import diff / history of dumps** — Trigger: users re-export IG monthly and need merge semantics.
- [ ] **Additional external sources (e.g. second platform)** — Trigger: explicit demand; avoid premature normalization.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Confirmed match + keyword writeback | HIGH | HIGH | P1 |
| Dump ingest + IG post listing | HIGH | MEDIUM | P1 |
| Catalog browse + multi-catalog switch | HIGH | MEDIUM | P1 |
| Job runner + status / errors | MEDIUM | MEDIUM | P1 |
| Single-image on-demand critique | HIGH | MEDIUM | P1 |
| Multi-perspective critique | MEDIUM | MEDIUM | P2 |
| Analytics fusion views | MEDIUM | HIGH | P2 |
| Unified photographer identity narrative | HIGH | HIGH | P2 |
| Batch critique by timeframe | MEDIUM | MEDIUM | P2 |
| Re-import / dump diff | MEDIUM | HIGH | P3 |
| Export integrations (Notion, etc.) | LOW–MEDIUM | LOW–MEDIUM | P3 |

**Priority key:**

- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Lightroom Classic (native) | DAM / AI search (e.g. Excire-style) | Consumer cloud (Google/Apple Photos) | Our Approach |
|---------|----------------------------|-------------------------------------|--------------------------------------|--------------|
| Catalog of record | Native | Companion or separate index | Cloud library | **Read LRCAT; augment, don’t replace** |
| AI labeling / search | Limited / manual keywords | Strong search, weak “critique” | Auto albums, faces | **Artistic critique + optional keywords** |
| Instagram alignment | None | None | Weak / different goals | **Dump-based match + writeback** |
| Multi-library identity | Per-catalog | Usually per-catalog | Single user cloud | **Explicit cross-catalog analyst view** |
| Cost model | Subscription to Adobe | Product purchase / sub | Bundled | **On-demand jobs, user-chosen models** |

## Sources

- **Internal:** `.planning/PROJECT.md` (requirements, constraints, out-of-scope decisions).
- **Product landscape (general):** Adobe Lightroom / Bridge patterns; DAM and AI-search tools (Excire, Imagen, etc.) for expectations around large libraries and AI assist; consumer photo clouds for baseline “AI understands my library” assumptions.
- **Gap:** Primary user interviews and quantitative survey not cited — confidence MEDIUM.

---
*Feature research for: Photography analysis & catalog management (Lightroom + Instagram dump workflows)*  
*Researched: 2026-04-10*
