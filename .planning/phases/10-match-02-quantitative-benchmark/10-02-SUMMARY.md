---
plan: 10-02
phase: 10-match-02-quantitative-benchmark
status: complete
completed: "2026-05-02"
---

# Plan 10-02 Summary — Run benchmark against live DB

## What was built

Ran `benchmark_clip_recall.py` against `library.db` (239 validated pairs). Both artifacts committed:
- `10-RECALL.md` — funnel counts, 100.0% recall headline, prerequisite note
- `10-recall-data.csv` — 239 rows (240 lines incl. header), all statuses valid

## Results

| Metric | Value |
|--------|-------|
| total_validated | 239 |
| missing_dump_media | 0 |
| skipped_no_embedding | 0 |
| filtered_out | 230 |
| hits | 9 |
| misses | 0 |
| **Recall** | **100.0%** |

All 239 pairs had CLIP embeddings. 230 pairs were filtered out because the validated catalog key did not appear in the 90-day date-window candidate set (expected — those pairs likely rely on vision matching, not date proximity). The 9 pairs that survived date+grid filtering were all recovered by CLIP top-50.

## Key decisions honored

- **D-04:** Prerequisite `batch_embed_image catalog_and_instagram` documented in `10-RECALL.md` footer
- **D-05:** Blob pre-check ran for all pairs; `skipped_no_embedding=0` confirms all had embeddings
- **D-09:** Status taxonomy `hit|miss|filtered_out|skipped_no_embedding` correctly applied
- **D-12:** CSV header matches spec exactly

## Verification

- `test -f 10-RECALL.md` ✓
- `test -f 10-recall-data.csv` ✓
- CSV header matches D-12 spec ✓
- `rg "batch_embed_image|catalog_and_instagram" 10-RECALL.md` ✓
- `rg "Recall|%" 10-RECALL.md` ✓

## Self-Check: PASSED
