# Pitfalls Research

**Domain:** Photography analysis tools, Lightroom Classic SQLite catalogs, Instagram export matching, vision/LLM critique  
**Researched:** 2026-04-10  
**Confidence:** HIGH (Adobe SQLite behavior, export matching, and vision pipelines are well-documented in practitioner lore; exact LR schema details vary by version — treat schema as version-sensitive)

## Critical Pitfalls

### Pitfall 1: Treating the Lightroom catalog as a generic SQLite file

**What goes wrong:** Corrupted catalogs, Lightroom crashes, or silent inconsistency after writes. Worst case: unusable catalog requiring restore from backup.

**Why it happens:** Developers assume SQLite best practices from web apps transfer directly. Lightroom uses a specific schema, often runs with WAL mode, and holds long-lived locks while open. Undocumented columns, triggers, or Adobe’s expectations around referential integrity are easy to violate.

**How to avoid:** Open catalogs read-only by default; use explicit transactions and minimal writes (e.g., keyword tables only). Document supported Lightroom major versions and test schema against real `.lrcat` samples. Never write while Lightroom has the catalog open unless you have a deliberate, tested strategy (usually: don’t). Always backup `.lrcat` plus `-wal` / `-shm` when present before any write. Prefer additive operations aligned with Adobe’s model (e.g., keyword links) over ad-hoc row surgery.

**Warning signs:** `database is locked` in logs; Lightroom “catalog corrupted” dialogs after a tool run; new rows that appear in raw SQL but never show in UI; foreign-key errors only in some LR versions.

**Phase to address:** **Catalog & SQLite foundation** (read paths, write policy, version matrix, backup contract).

---

### Pitfall 2: Writing to the catalog without a reversible, auditable trail

**What goes wrong:** Keywords applied to wrong images; impossible to undo at scale; user loses trust in automation.

**Why it happens:** Matching is probabilistic; a single “apply” button that writes straight to `.lrcat` skips human confirmation and job history.

**How to avoid:** Persist proposed matches and keyword ops in your app DB first; require explicit confirm (or batch confirm with diff UI). Store: source image id, target catalog id, confidence, model/prompt version, and timestamp. Offer “dry run” and export of planned changes. Keep pre-write catalog backup as part of the write job.

**Warning signs:** Users report wrong “posted” tags; no way to list “what this tool changed last Tuesday”; retries double-apply keywords.

**Phase to address:** **Instagram dump matching + write-back workflow** (confirmation UX, idempotent writes, audit log).

---

### Pitfall 3: Matching Instagram exports to Lightroom using filenames, dates, or pixel-identical hashes alone

**What goes wrong:** Systematic false negatives (no match) or dangerous false positives (wrong match → wrong keyword).

**Why it happens:** Instagram re-encodes, crops, strips or alters metadata, and renames files in exports. Pixel hashes and naive file names fail often; capture-time alone collides on bursts and synced duplicates.

**How to avoid:** Use a tiered strategy: cheap signals (dimensions, rough capture time window, optional perceptual hash) to narrow candidates, then vision or perceptual similarity for disambiguation. Always surface confidence and allow override. Test on carousels, Stories exports (if present), and screenshots reposted to IG.

**Warning signs:** High “unmatched” rate on real dumps; matches that look wrong when side-by-side; same IG post matching multiple catalog candidates with similar scores.

**Phase to address:** **Instagram dump ingest & matching** (eval set from real exports, metrics for precision/recall, manual review queue).

---

### Pitfall 4: Assuming one Instagram export layout forever

**What goes wrong:** Importer breaks after Meta changes ZIP structure, folder names, or JSON schema; silent partial imports.

**Why it happens:** Export formats evolve; locale and account type (personal vs professional) can shift paths. Code hard-codes a single directory tree.

**How to avoid:** Isolate parsing behind a versioned adapter; detect format with probes (presence of key folders/files) not a single path. Log parse warnings with file paths. Add fixture ZIPs or extracted subtrees in tests for each supported format revision.

**Warning signs:** “0 posts imported” with no error; images found but analytics missing; works on one machine’s export, fails on another’s.

**Phase to address:** **Instagram dump ingest & matching** (parser tests, format detection, user-visible validation report).

---

### Pitfall 5: AI critique that is non-reproducible, ungrounded, or unbounded in cost

**What goes wrong:** Same image gets wildly different scores across runs; users cannot compare “before/after” edits; monthly API cost spikes from accidental full-catalog jobs.

**Why it happens:** Temperature > 0, changing models, vague prompts, and no stored prompt hash/version. On-demand jobs without caps or queue limits allow runaway concurrency.

**How to avoid:** Store `model`, `provider`, `prompt_version` (or hash), and decoding settings with every result. Use low temperature for scoring rubrics; separate “creative commentary” from “structured scores” if needed. Enforce job limits, batch sizes, and cancellation. Align with PROJECT.md: on-demand only, no upfront full-catalog analysis.

**Warning signs:** User complaints that critique “makes no sense” for obvious images; DB rows with NULL model/prompt metadata; cost graphs correlate with single UI actions that fan out to thousands of calls.

**Phase to address:** **AI analysis & providers** (result schema, versioning, rate limits, job model).

---

### Pitfall 6: Multi-perspective critique without a stable evaluation contract

**What goes wrong:** “Street vs editor vs publisher” blur together; outputs are fluffy or contradictory with no way to fix prompts systematically.

**Why it happens:** Single mega-prompt asking for everything; no JSON schema or scoring dimensions per persona.

**How to avoid:** Define per-perspective output shape (required fields, scales, forbidden claims). Ground prompts in explicit photography theory snippets you control. Add golden-image regression tests: fixed inputs → snapshot structured outputs (allow wording drift only where acceptable).

**Warning signs:** Unparseable model output in production; UI shows empty sections; personas duplicate the same paragraph.

**Phase to address:** **AI analysis & providers** (prompt library, response schema, regression fixtures).

---

### Pitfall 7: Large catalogs handled with naive full scans and unbounded memory

**What goes wrong:** Timeouts, OOM, or UI that freezes; SQLite and disk thrash on every page load.

**Why it happens:** Listing all images on each request; loading full binaries for thumbnails; N+1 queries per row; no indexes on hot columns in app DB.

**How to avoid:** Pagination and cursor-based APIs; lazy thumbnail generation; cache stable hashes and paths in `library.db` (or equivalent) with indexes; background indexing jobs with progress. Stream or memory-map large files only when needed; never return base64 originals in list endpoints.

**Warning signs:** API latency grows linearly with catalog size; memory proportional to image count; single “open catalog” action triggers full rescan every time.

**Phase to address:** **Scale, indexing & jobs** (catalog scan pipeline, API pagination, DB indexes).

---

### Pitfall 8: Multi-catalog “unified identity” without explicit scope and deduplication rules

**What goes wrong:** Double-counting the same shoot across catalogs; misleading aggregates; privacy bleed (client wedding catalog mixed into personal “voice” stats).

**Why it happens:** Treating all catalogs as one flat corpus without `catalog_id` scoping, or assuming paths are globally unique.

**How to avoid:** Every row keyed by `(catalog_id, …)`; UI and APIs default to active catalog with clear switcher. For cross-catalog analytics, define rules: exclude paths, tag filters, or explicit opt-in. Deduplicate by content hash only when same file is provably shared, not when filenames match.

**Warning signs:** Stats change when user switches catalog in unintuitive ways; same physical image appears as two unrelated records without explanation.

**Phase to address:** **Visualizer & multi-catalog UX** (data model, scoping, copy for what “unified” means).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Direct `.lrcat` writes without backup job | Faster MVP | Irrecoverable corruption or user anger | Never for production writes; dev-only with disposable catalogs |
| Single hard-coded Instagram export path | Quick demo on one machine | Breaks for other users/locales | Early spike only; replace with detection + tests |
| Storing full critique text without model/prompt version | Smaller schema now | Cannot debug regressions or compare runs | Never for user-visible scores; OK for ephemeral experiments you discard |
| Full catalog hash on every app start | Simple code | Unusable at 100k+ images | Only with explicit “reindex” button and persisted index state |
| Relying on one vision model for match + critique | Fewer integration points | Vendor lock-in, cost spikes, single point of failure | Short internal testing if you abstract provider behind registry |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Lightroom Classic `.lrcat` | Editing while LR is open; copying only `.lrcat` without WAL/SHM for backup | Close LR or read-only; backup trio; test on copy |
| Instagram data export | Parsing only `media/` and ignoring JSON activity feeds | Map media IDs to analytics from export JSON; handle missing fields |
| Instagram export | Assuming original filename equals catalog filename | Normalize; match on content/time/vision |
| Vision API (Ollama/OpenRouter/etc.) | Sending full-resolution images always | Resize/limit longest edge for compare/describe; preserve aspect ratio |
| App SQLite (`library.db`) | Duplicating Lightroom as source of truth for keywords | LR remains canonical for keywords you write; app DB for workflow state |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|------------------|
| Unindexed match queries | Slow matching as rows grow | Indexes on hash, catalog_id, capture_time windows | ~10k+ images with naive joins |
| Synchronous vision in HTTP request | Gateway timeouts, stuck UI | Job queue + polling/WebSocket progress | > few seconds per request path |
| Reloading entire image binary per comparison | High RAM and disk IO | Thumbnails / downscaled buffers; cache per job | Hundreds of comparisons in one session |
| Listing all images for picker | Slow first paint | Virtualized lists + server pagination | 50k+ assets |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Serving catalog paths that escape intended roots | Local file read (LFI-style) if backend reads arbitrary paths | Canonicalize paths; enforce root allowlist per catalog |
| Exposing Instagram dump or `.lrcat` via static file server | Personal photos + DMs metadata leaked | Keep data dirs outside web root; auth on API |
| Logging full prompts with image base64 | Credential leakage in logs; huge logs | Log hashes/ids only; redact secrets |
| Multi-user deployment (if ever) mixing catalogs | Cross-tenant data leak | Tenant id + catalog ACLs from day one if not single-user |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Auto-write keywords on “good enough” match | Wrong public/posted state in LR | Confirm step; show side-by-side |
| Opaque “matching score” | No trust | Explain top factors (time, crop, model version) |
| Critique reads like generic AI blog | Feels useless | Persona-specific, structured, optional “why” tied to visible elements |
| No progress for long jobs | App feels frozen | Determinate progress + cancel |
| Multi-catalog switcher without context | Writes go to wrong catalog | Persistent banner: active catalog name + path |

## "Looks Done But Isn't" Checklist

- [ ] **Catalog read:** Works on `.lrcat` from two different Lightroom major versions — verify schema-sensitive queries
- [ ] **Catalog write:** After keyword write, Lightroom shows keywords without repair — verify on clean copy
- [ ] **Matching:** Carousel and single-image posts both resolve — verify with export fixtures
- [ ] **Instagram import:** Analytics join to media when JSON uses indirect IDs — verify counts match Instagram app for a sample week
- [ ] **AI jobs:** Failed job leaves no partial `.lrcat` writes — verify transactional boundaries
- [ ] **Scale:** Cold start with 50k+ images completes index in acceptable time — verify with synthetic or real large catalog
- [ ] **Multi-catalog:** Unified dashboard does not mix client catalogs unless user opts in — verify scoping in API responses

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Corrupted `.lrcat` after write | HIGH | Restore from pre-write backup; avoid further writes until cause fixed |
| Mass wrong keywords | MEDIUM | LR metadata backup if available; or SQL/script to remove bad keyword links on a copy; re-test in LR |
| Bad matches committed | LOW–MEDIUM | Re-run matching with tightened thresholds; manual CSV of corrections |
| Export parser broken after Meta update | LOW | Pin to known-good export; ship parser v2 alongside v1 |
| Runaway API cost | MEDIUM | Revoke keys, cap provider-side limits, add server-side concurrency caps |

## Pitfall-to-Phase Mapping

Use this table when `ROADMAP.md` exists: replace the **Prevention track** name with the concrete phase id (e.g. `12`, `12.1`).

| Pitfall | Prevention track | Verification |
|---------|------------------|----------------|
| Generic SQLite treatment of `.lrcat` | Catalog & SQLite foundation | Version matrix doc; write tests on disposable catalogs; lock behavior checklist |
| Unaudited write-back | Instagram dump matching + write-back workflow | Audit log UI or export; dry-run integration test |
| Weak matching signals | Instagram dump ingest & matching | Labeled eval set; precision/recall thresholds documented |
| Fragile export parsing | Instagram dump ingest & matching | Multiple fixture exports; parse report with errors |
| Non-reproducible / costly AI | AI analysis & providers | Stored prompt hash; load test job caps |
| Unstable multi-perspective output | AI analysis & providers | JSON schema validation; golden snapshots |
| Naive large-catalog access | Scale, indexing & jobs | Pagination tests; profiling on large DB |
| Ambiguous multi-catalog scope | Visualizer & multi-catalog UX | API always scoped; UX review of switcher + stats |

## Sources

- Adobe Lightroom Classic catalog SQLite behavior (WAL, backup practice) — vendor-adjacent community and forensic write-ups; validate against your LR versions
- Meta “Download your information” / Instagram export structure changes — empirical testing per export date
- Vision API cost/latency patterns — provider docs + internal job metrics
- Project constraints and intent — `.planning/PROJECT.md` (2026-04-10)
- Codebase integration notes — `.planning/codebase/INTEGRATIONS.md`

---
*Pitfalls research for: Lightroom Tagger & Analyzer — photography analysis, catalog integration, Instagram exports*  
*Researched: 2026-04-10*
