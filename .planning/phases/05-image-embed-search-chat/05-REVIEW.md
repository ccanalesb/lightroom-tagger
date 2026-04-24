---
status: issues_found
phase: "05-image-embed-search-chat"
depth: standard
reviewed: "2026-04-24"
---

# Phase 5 Code Review

## Medium Issues

1. **[M1] batch_embed_image progress bar stalls on skipped files**
   Skipped keys (missing filepath) don't call `update_progress` — progress stays near 5% during long skip runs. Not a correctness bug, but misleading for operators.

2. **[M2] encode_images batch failure swallows per-image errors**
   One bad file in a batch fails the entire chunk. `failed` counter is initialized but never incremented — the completed payload always reports `failed: 0` even on job abort. Makes debugging difficult.

3. **[M3] ChatSearchResponse.images missing semantic-only fields in TypeScript types**
   Semantic path returns `score`, `why_matched`, `thumbnail_url` on each image (same as semantic-search endpoint). `ChatSearchResponse.images: CatalogImage[]` and `fromCatalogListRow` don't map these. Functional but types are incomplete.

4. **[M4] Fingerprint date_filter vs resolved date window mismatch**
   `fingerprint_batch_embed_image` uses raw `date_filter` from metadata; work list uses `_resolve_date_window`. Different metadata shapes resolving to the same SQL window yield different fingerprints — unnecessary fresh starts.

## Low Issues

- Migration drops existing CLIP rows on user_version upgrade (expected for new table)
- `Image.open` in `encode_images` lacks context manager — long runs hold file handles
- SearchPage enforces non-empty but not 2-char minimum (server returns 400 for 1-char on semantic path)
- `ChatSearchResponse.search_mode` typed as `string` not `'nl_filter' | 'semantic'`

## Summary

No blocking correctness bugs. All medium issues are operability/type-completeness concerns suitable for follow-up. Phase is **merge-ready**.
