# Requirements: Lightroom Tagger & Analyzer

**Defined:** 2026-04-10
**Core Value:** Know which catalog images are posted on Instagram and get artistic critique that helps you understand your photographic voice and posting strategy.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Catalog Management

- [ ] **CAT-01**: User can register a Lightroom catalog (.lrcat file)
- [ ] **CAT-02**: User can browse photos from the catalog with pagination
- [ ] **CAT-03**: User can search/filter photos by basic criteria
- [ ] **CAT-04**: System maintains stable photo identity across sessions
- [ ] **CAT-05**: System reads catalog safely without corruption risk

### Instagram Sync

- [ ] **IG-01**: User can upload Instagram export dump
- [ ] **IG-02**: System parses images and metadata from dump
- [ ] **IG-03**: System matches dump images to catalog photos with confidence scores
- [ ] **IG-04**: User can confirm or reject proposed matches
- [ ] **IG-05**: System writes "posted" keyword to confirmed matches in Lightroom catalog
- [ ] **IG-06**: User can see which catalog photos are marked as posted

### AI Analysis

- [x] **AI-01**: User can configure AI provider (Ollama, OpenAI, etc.)
- [ ] **AI-02**: User can trigger on-demand description for a single photo
- [x] **AI-03**: User can trigger batch description for selected photos or timeframe
- [x] **AI-04**: System stores AI descriptions with source photo
- [ ] **AI-05**: User can view AI descriptions alongside photos
- [x] **AI-06**: System tracks which photos have been analyzed

### Jobs & System

- [ ] **SYS-01**: User can see job status (queued, running, complete, failed)
- [ ] **SYS-02**: User can cancel running jobs
- [ ] **SYS-03**: System backs up catalog before any write operation
- [ ] **SYS-04**: User receives clear error messages when operations fail
- [ ] **SYS-05**: System prevents writes when Lightroom has catalog open

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced AI Analysis

- **AI-07**: Multi-perspective critique (street photographer, editor, publisher views)
- **AI-08**: Structured artistic feedback (composition, narrative, rhythm)
- **AI-09**: Score photos from different perspectives
- **AI-10**: Improve critique prompts with photography theory knowledge

### Analytics & Insights

- **ANLZ-01**: Extract and display Instagram analytics (likes, saves, engagement)
- **ANLZ-02**: Identify "best photos" combining AI scores and Instagram performance
- **ANLZ-03**: Show photographer identity analysis across all work
- **ANLZ-04**: Identify patterns in what performs well on Instagram
- **ANLZ-05**: Suggest what to post next based on catalog analysis

### Multi-Catalog

- **MCAT-01**: User can switch between multiple registered catalogs
- **MCAT-02**: System maintains unified photographer identity view across catalogs
- **MCAT-03**: User can analyze catalog-specific work (e.g., wedding catalog) independently

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Instagram API integration | Too restrictive and fragile; export-based workflow is reliable |
| Lightroom plugin | Keep Lightroom unchanged; web app is more flexible |
| Technical EXIF analysis | Focus is artistic critique, not camera settings |
| Real-time Instagram syncing | Manual dump workflow sufficient for use case |
| Batch analysis of entire catalog upfront | On-demand keeps costs controlled |
| Support for multiple social platforms | Focus on Instagram first; add others only with clear demand |
| Automated posting suggestions | Defer until patterns are proven valuable |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAT-01 | 1 · Catalog management | Pending |
| CAT-02 | 1 · Catalog management | Pending |
| CAT-03 | 1 · Catalog management | Pending |
| CAT-04 | 1 · Catalog management | Pending |
| CAT-05 | 1 · Catalog management | Pending |
| SYS-01 | 2 · Jobs & system reliability | Pending |
| SYS-02 | 2 · Jobs & system reliability | Pending |
| SYS-03 | 2 · Jobs & system reliability | Pending |
| SYS-04 | 2 · Jobs & system reliability | Pending |
| SYS-05 | 2 · Jobs & system reliability | Pending |
| IG-01 | 3 · Instagram sync | Pending |
| IG-02 | 3 · Instagram sync | Pending |
| IG-03 | 3 · Instagram sync | Pending |
| IG-04 | 3 · Instagram sync | Pending |
| IG-05 | 3 · Instagram sync | Pending |
| IG-06 | 3 · Instagram sync | Pending |
| AI-01 | 4 · AI analysis | Complete |
| AI-02 | 4 · AI analysis | Pending |
| AI-03 | 4 · AI analysis | Complete |
| AI-04 | 4 · AI analysis | Complete |
| AI-05 | 4 · AI analysis | Pending |
| AI-06 | 4 · AI analysis | Complete |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

Roadmap: [.planning/ROADMAP.md](./ROADMAP.md)

---
*Requirements defined: 2026-04-10*
*Last updated: 2026-04-10 after roadmap creation*
