# Requirements: Lightroom Tagger & Analyzer

**Defined:** 2026-04-10
**Core Value:** Know which catalog images are posted on Instagram and get artistic critique that helps you understand your photographic voice and posting strategy.

## v1 Requirements (Complete)

All 22 requirements shipped in v1.0 (2026-04-11). See [milestones/v1.0-REQUIREMENTS.md](./milestones/v1.0-REQUIREMENTS.md) for full detail.

## v2 Requirements

Requirements for v2.0 Advanced Critique & Insights milestone.

### Structured Scoring & Prompts

- [x] **SCORE-01**: User can trigger scoring that produces numeric scores (1-10) per perspective with written rationale (Validated in Phase 6 + Phase 10 fix; see 06-VERIFICATION.md and 10-VERIFICATION.md)
- [x] **SCORE-02**: System persists scores as queryable fields (not just JSON blobs) so catalog can filter/sort by score (Validated in Phase 5; see 05-VERIFICATION.md)
- [x] **SCORE-03**: System tracks which prompt version and model generated each score (rubric versioning) (Validated in Phase 6; see 06-VERIFICATION.md)
- [x] **SCORE-04**: User can re-run scoring with an updated rubric and see both old and new results distinguished by version (Validated in Phase 6 + Phase 10 fix; see 06-VERIFICATION.md and 10-VERIFICATION.md)
- [x] **SCORE-05**: Critique prompts are grounded in photography theory from publications and critique frameworks (Validated in Phase 5; see 05-VERIFICATION.md)
- [x] **SCORE-06**: User can add new critique perspectives beyond the existing three (e.g., color theory, emotional impact, series coherence) (Validated in Phase 5; see 05-VERIFICATION.md)
- [x] **SCORE-07**: System validates structured LLM output and retries/repairs malformed JSON before persisting (Validated in Phase 5; see 05-VERIFICATION.md)

### Posting Analytics

- [x] **POST-01**: User can see posting frequency over time (timeline chart) (Validated in Phase 7; see 07-VERIFICATION.md)
- [x] **POST-02**: User can see time-of-day and day-of-week posting patterns (heatmap) (Validated in Phase 7; see 07-VERIFICATION.md)
- [x] **POST-03**: User can see caption and hashtag usage analysis across posted images (Validated in Phase 7; see 07-VERIFICATION.md)
- [x] **POST-04**: User can identify catalog images not yet posted (catalog vs posted gap view) (Validated in Phase 7; see 07-VERIFICATION.md)

### Identity & Suggestions

- [x] **IDENT-01**: User can see a "best photos" ranking based on aggregated AI perspective scores (Validated in Phase 8 + Phase 10 fix; see 08-VERIFICATION.md and 10-VERIFICATION.md)
- [x] **IDENT-02**: User can see a style fingerprint — recurring visual and thematic patterns across their work (Validated in Phase 8 + Phase 10 fix; see 08-VERIFICATION.md and 10-VERIFICATION.md)
- [x] **IDENT-03**: User can get "what to post next" suggestions based on catalog scores vs posting history gaps (Validated in Phase 8 + Phase 10 fix; see 08-VERIFICATION.md and 10-VERIFICATION.md)

### Job Resilience

- [x] **JOB-01**: Long-running jobs checkpoint progress so work is not lost on backend restart (Validated in Phase 5; see 05-VERIFICATION.md)
- [x] **JOB-02**: Orphaned jobs are auto-recovered and resumed on backend startup (Validated in Phase 5; see 05-VERIFICATION.md)

### Insights Dashboard

- [x] **DASH-01**: User can view a unified insights page with score distributions, posting patterns, and top-scored photos (Validated in Phase 9; see 09-VERIFICATION.md)

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
| SCORE-02 | v2 Phase 5 · Structured scoring foundation | Complete |
| SCORE-05 | v2 Phase 5 · Structured scoring foundation | Complete |
| SCORE-06 | v2 Phase 5 · Structured scoring foundation | Complete |
| SCORE-07 | v2 Phase 5 · Structured scoring foundation | Complete |
| JOB-01 | v2 Phase 5 · Structured scoring foundation | Complete |
| JOB-02 | v2 Phase 5 · Structured scoring foundation | Complete |
| SCORE-01 | v2 Phase 6 + Phase 10 (bug fix) | Complete |
| SCORE-03 | v2 Phase 6 | Complete |
| SCORE-04 | v2 Phase 6 + Phase 10 (bug fix) | Complete |
| POST-01 | v2 Phase 7 | Complete |
| POST-02 | v2 Phase 7 | Complete |
| POST-03 | v2 Phase 7 | Complete |
| POST-04 | v2 Phase 7 | Complete |
| IDENT-01 | v2 Phase 8 + Phase 10 (bug fix) | Complete |
| IDENT-02 | v2 Phase 8 + Phase 10 (bug fix) | Complete |
| IDENT-03 | v2 Phase 8 + Phase 10 (bug fix) | Complete |
| DASH-01 | v2 Phase 9 | Complete |

**Coverage:**
- v1 requirements: 22 (complete)
- v2 requirements: 17 total — **17 / 17** verified / complete (documentation)
- Mapped to phases: 17 / 17 (Phases 5–9 delivered; bug fixes Phase 10; verification Phase 11 — documentation updated Phase 11)

Roadmap: [.planning/ROADMAP.md](./ROADMAP.md)

---
*Requirements defined: 2026-04-10*
*v2 requirements added: 2026-04-11*
*v2 roadmap / traceability: 2026-04-12 (JOB-01, JOB-02 added for job resilience)*
*Gap closure phases 10–11 added: 2026-04-14*
