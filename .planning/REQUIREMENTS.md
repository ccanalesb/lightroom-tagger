# Requirements: Lightroom Tagger & Analyzer

**Defined:** 2026-04-10
**Core Value:** Know which catalog images are posted on Instagram and get artistic critique that helps you understand your photographic voice and posting strategy.

## v1 Requirements (Complete)

All 22 requirements shipped in v1.0 (2026-04-11). See [milestones/v1.0-REQUIREMENTS.md](./milestones/v1.0-REQUIREMENTS.md) for full detail.

## v2 Requirements

Requirements for v2.0 Advanced Critique & Insights milestone.

### Structured Scoring & Prompts

- [ ] **SCORE-01**: User can trigger scoring that produces numeric scores (1-10) per perspective with written rationale
- [ ] **SCORE-02**: System persists scores as queryable fields (not just JSON blobs) so catalog can filter/sort by score
- [ ] **SCORE-03**: System tracks which prompt version and model generated each score (rubric versioning)
- [ ] **SCORE-04**: User can re-run scoring with an updated rubric and see both old and new results distinguished by version
- [ ] **SCORE-05**: Critique prompts are grounded in photography theory from publications and critique frameworks
- [ ] **SCORE-06**: User can add new critique perspectives beyond the existing three (e.g., color theory, emotional impact, series coherence)
- [ ] **SCORE-07**: System validates structured LLM output and retries/repairs malformed JSON before persisting

### Posting Analytics

- [ ] **POST-01**: User can see posting frequency over time (timeline chart)
- [ ] **POST-02**: User can see time-of-day and day-of-week posting patterns (heatmap)
- [ ] **POST-03**: User can see caption and hashtag usage analysis across posted images
- [ ] **POST-04**: User can identify catalog images not yet posted (catalog vs posted gap view)

### Identity & Suggestions

- [ ] **IDENT-01**: User can see a "best photos" ranking based on aggregated AI perspective scores
- [ ] **IDENT-02**: User can see a style fingerprint — recurring visual and thematic patterns across their work
- [ ] **IDENT-03**: User can get "what to post next" suggestions based on catalog scores vs posting history gaps

### Job Resilience

- [ ] **JOB-01**: Long-running jobs checkpoint progress so work is not lost on backend restart
- [ ] **JOB-02**: Orphaned jobs are auto-recovered and resumed on backend startup

### Insights Dashboard

- [ ] **DASH-01**: User can view a unified insights page with score distributions, posting patterns, and top-scored photos

## Future Requirements

Deferred beyond v2.0.

### Multi-Catalog

- **MCAT-01**: User can switch between multiple registered catalogs
- **MCAT-02**: System maintains unified photographer identity view across catalogs
- **MCAT-03**: User can analyze catalog-specific work independently

### Engagement Overlay

- **ENG-01**: User can manually enter or import engagement data (likes, saves) for posted images
- **ENG-02**: "Best photos" ranking incorporates engagement data alongside AI scores

### Dashboard Drill-Down

- **DRILL-01**: User can click chart data points to navigate to specific photos

## Out of Scope

| Feature | Reason |
|---------|--------|
| Instagram API integration | Too restrictive and fragile; export-based workflow is reliable |
| Lightroom plugin | Keep Lightroom unchanged; web app is more flexible |
| Technical EXIF analysis | Focus is artistic critique, not camera settings |
| Real-time Instagram syncing | Manual dump workflow sufficient for use case |
| Batch analysis of entire catalog upfront | On-demand keeps costs controlled |
| Per-post engagement metrics from dumps | Instagram exports don't include likes/saves/comments counts |
| Embedding-based style fingerprint | Overkill — use score pattern analysis first |
| Full NLP on captions | Simple frequency/hashtag analysis sufficient for v2 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAT-01..05 | v1 Phase 1 · Catalog management | Complete |
| SYS-01..05 | v1 Phase 2 · Jobs & system reliability | Complete |
| IG-01..06 | v1 Phase 3 · Instagram sync | Complete |
| AI-01..06 | v1 Phase 4 · AI analysis | Complete |
| SCORE-02 | v2 Phase 5 · Structured scoring foundation | Pending |
| SCORE-05 | v2 Phase 5 · Structured scoring foundation | Pending |
| SCORE-06 | v2 Phase 5 · Structured scoring foundation | Pending |
| SCORE-07 | v2 Phase 5 · Structured scoring foundation | Pending |
| JOB-01 | v2 Phase 5 · Structured scoring foundation | Pending |
| JOB-02 | v2 Phase 5 · Structured scoring foundation | Pending |
| SCORE-01 | v2 Phase 6 · Scoring pipeline & catalog score UX | Pending |
| SCORE-03 | v2 Phase 6 · Scoring pipeline & catalog score UX | Pending |
| SCORE-04 | v2 Phase 6 · Scoring pipeline & catalog score UX | Pending |
| POST-01 | v2 Phase 7 · Posting analytics | Pending |
| POST-02 | v2 Phase 7 · Posting analytics | Pending |
| POST-03 | v2 Phase 7 · Posting analytics | Pending |
| POST-04 | v2 Phase 7 · Posting analytics | Pending |
| IDENT-01 | v2 Phase 8 · Identity & "what to post next" | Pending |
| IDENT-02 | v2 Phase 8 · Identity & "what to post next" | Pending |
| IDENT-03 | v2 Phase 8 · Identity & "what to post next" | Pending |
| DASH-01 | v2 Phase 9 · Insights dashboard | Pending |

**Coverage:**
- v1 requirements: 22 (complete)
- v2 requirements: 17 total
- Mapped to phases: 17 / 17 (Phases 5-9; see [ROADMAP.md](./ROADMAP.md))

Roadmap: [.planning/ROADMAP.md](./ROADMAP.md)

---
*Requirements defined: 2026-04-10*
*v2 requirements added: 2026-04-11*
*v2 roadmap / traceability: 2026-04-12 (JOB-01, JOB-02 added for job resilience)*
