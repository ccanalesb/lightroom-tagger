# Phase 19: Generate Read-Only HTML Comparison-Pool Report - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `19-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-12  
**Phase:** 19-generate-read-only-html-comparison-pool-report  
**Areas discussed:** Candidate Pool Fidelity, Invocation Model, Report Contents, Scope Controls, Output Safety

---

## Candidate Pool Fidelity

| Option | Description | Selected |
|--------|-------------|----------|
| Persist exact pool snapshots going forward | Faithful for future runs; older runs may be unavailable. | |
| Reconstruct from current DB/code | Faster and useful now, but not guaranteed exact. | |
| Hybrid | Use persisted snapshots when present; reconstruct old misses with a visible warning. | ✓ |

**User's choice:** Hybrid.  
**Notes:** User asked what a pool means and why strictness matters. Clarification: a pool is the catalog candidates the matcher actually considered for one Instagram image. The reason strictness matters is current code does not save exact candidate lists for failed matches. Decision: save exact pools going forward, allow reconstructed reports for old misses with a visible warning.

---

## Invocation Model

| Option | Description | Selected |
|--------|-------------|----------|
| CLI/offline command | Run a local command that writes HTML files; no app UI. | ✓ |
| Backend debug endpoint | Generate/download from an API route. | |
| Both | CLI first, endpoint optional later. | |

**User's choice:** CLI/offline command.  
**Notes:** Aligns with the todo constraint: investigation artifact only, no product screen.

---

## Report Contents

| Option | Description | Selected |
|--------|-------------|----------|
| Visual only | Instagram image, candidate thumbnails, stable IDs. | |
| Visual + scoring evidence | Thumbnails, IDs, rank, total score, pHash/description/vision scores, vision verdict/model. | |
| Full debug evidence | Visual/scoring evidence plus stored prompt response, reasoning, and log excerpts when available. | ✓ |

**User's choice:** Full debug evidence.  
**Notes:** User wants debug evidence included, but hidden from plain sight behind a modal or collapsible view.

---

## Scope Controls

| Option | Description | Selected |
|--------|-------------|----------|
| All unmatched attempted Instagram images | Broad report, can get large. | |
| Filtered by month/job/media key | User must narrow each run. | |
| Default all unmatched, optional filters | Easy first run; supports narrowing with filters. | ✓ |

**User's choice:** Default all unmatched, optional filters.  
**Notes:** Locked filters: `--month`, `--job-id`, `--media-key`, and `--limit`.

---

## Output Safety

| Option | Description | Selected |
|--------|-------------|----------|
| Reference original local paths | Simplest, but breaks if files move and exposes filesystem paths. | |
| Copy thumbnails/assets into a report folder | Portable-ish, safer, bigger output. | ✓ |
| Embed thumbnails as base64 in one HTML file | Easy to open/share, but file can get huge. | |

**User's choice:** Copy thumbnails/assets into a report folder.  
**Notes:** User added that images should always be compressed. Full local paths may be included only in hidden debug details.

---

## Claude's Discretion

- Exact CLI module name and non-essential argument spelling.
- Exact HTML style, layout, thumbnail dimensions, and compression quality.

## Deferred Ideas

- Product UI for this report — out of scope.
- Labeling or writing judgments back from the report — out of scope.
