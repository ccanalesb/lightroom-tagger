# Phase 12: Operational baseline & embed reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 12-operational-baseline-embed-reliability
**Areas discussed:** Embed job discoverability, Path-failure preflight, "Why skipped" summary, Compression log noise

---

## Embed job discoverability

| Option | Description | Selected |
|--------|-------------|----------|
| Navigation link is sufficient | Keep guidance text + link to Processing tab; apply consistently wherever the error surfaces | ✓ |
| Inline trigger button | Add a button that enqueues `batch_embed_image` directly from the error state, no navigation needed | |
| Processing tab only (status quo) | Keep it in the Processing tab; improve discoverability within the tab | |

**User's choice:** Navigation link is sufficient
**Notes:** The Search page already implements this pattern correctly (`no_clip_embedding` warning with links to Catalog cache + job queue). Other surfaces should follow the same pattern. No inline job-trigger button needed.

---

## Path-failure preflight — sample size

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed small sample | ~20–50 paths, fast, good signal for a network share being down | ✓ |
| Percentage of catalog | 5–10% of total images, scales with catalog size | |
| Claude's discretion | Claude picks a sensible default | |

**User's choice:** Fixed small sample

---

## Path-failure preflight — abort threshold

| Option | Description | Selected |
|--------|-------------|----------|
| >50% unreachable | Majority-failure rule | ✓ |
| >80% unreachable | Only abort on near-total failure | |
| Claude's discretion | | |

**User's choice:** >50% unreachable

---

## Path-failure preflight — user-facing behavior on abort

| Option | Description | Selected |
|--------|-------------|----------|
| Hard stop with single actionable message | Job fails immediately with count/sample ratio + likely cause + retry instruction | ✓ |
| Warning + confirm | Job pauses, shows diagnosis, asks user to confirm before aborting | |
| Claude's discretion | | |

**User's choice:** Hard stop with single actionable message — no confirm prompt

---

## "Why skipped" summary — display location

| Option | Description | Selected |
|--------|-------------|----------|
| Job detail modal only | Breakdown in existing embed diagnostics section; zero-skip categories hidden | ✓ |
| Job detail modal + Processing tab | Also show compact summary in CatalogCacheTab after job completes | |
| Claude's discretion | | |

**User's choice:** Job detail modal only
**Notes:** Zero-skip categories (count = 0) are hidden. Three categories: missing file, empty path, no DB row.

---

## Compression log noise on restart

| Option | Description | Selected |
|--------|-------------|----------|
| Skip silently | No log output at all for already-compressed images | |
| Single summary log | Skip silently per-image; one end-of-resume log: "N images already compressed, skipped" | ✓ |
| Claude's discretion | | |

**User's choice:** Single summary log (only emitted if N > 0)

---

## Claude's Discretion

- Exact preflight sample count within 20–50 range
- Exact wording of the preflight abort message (must include count/sample ratio and likely cause)
- Whether the preflight sampler shuffles or takes a head/tail slice

## Deferred Ideas

None
