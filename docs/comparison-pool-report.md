# Comparison Pool Report

Generate a read-only offline HTML report for unmatched Instagram dump rows. The report shows the catalog candidates the matcher evaluated, plus scoring evidence, so you can diagnose whether a missed match was absent from the pool or scored poorly.

## Run

From the repo root:

```bash
/Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m lightroom_tagger.scripts.generate_comparison_pool_report \
  --db /path/to/library.db \
  --out /tmp/comparison-pool-report
```

Then open:

```bash
open /tmp/comparison-pool-report/report.html
```

The output folder contains:

- `report.html` — static file, no backend/frontend required
- `assets/` — compressed JPEG copies used by the report

## Filters

Use filters to keep the report small:

```bash
--month 202604
--job-id <visualizer-job-uuid>
--media-key <instagram-media-key>
--limit 25
```

Examples:

```bash
# Latest attempted unmatched rows, capped
/Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m lightroom_tagger.scripts.generate_comparison_pool_report \
  --db library.db \
  --out /tmp/comparison-pool-report \
  --limit 25

# Rows attempted by one visualizer vision-match job
/Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m lightroom_tagger.scripts.generate_comparison_pool_report \
  --db library.db \
  --out /tmp/comparison-pool-report-job \
  --job-id 00000000-0000-0000-0000-000000000000
```

## Backfill Evidence For Old Misses

For older rows that only show `Reconstructed — not exact run evidence`, run a diagnostic match pass. It captures a fresh exact snapshot and JPEG evidence assets without storing matches or writing Lightroom updates:

```bash
/Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m lightroom_tagger.scripts.match_instagram_dump \
  --db library.db \
  --media-key 202604/example-media-key \
  --diagnostic-only \
  --source-job-id diagnostic-2026-05-12
```

Then generate the report with `--job-id diagnostic-2026-05-12` or `--media-key`.

## What The Report Means

- Exact snapshots come from matching runs after Phase 19. These show the evaluated pool and score evidence captured at match time.
- New snapshots also store pipeline diagnostics (`date_window`, rejected-pair drops, representative-only drops, CLIP shortlist counts) and report-ready JPEG evidence assets beside the DB.
- Older rows without snapshots use best-effort reconstruction from current DB state and are labeled `Reconstructed — not exact run evidence`.
- Primary report view uses relative `assets/...` image links. Full local paths are only in hidden debug details.

## Captured Evidence Assets

When a matching run writes a comparison-pool snapshot, it now writes durable compressed JPEG evidence assets to:

```text
<library-db-filename>.comparison_pool_assets/
```

The report prefers those captured assets before trying current source paths. This makes exact snapshots survive missing catalog paths, RAW/DNG files without report-time conversion, and later path moves better than reconstructed rows.

## Help

```bash
/Users/ccanales/projects/lightroom-tagger/.venv/bin/python -m lightroom_tagger.scripts.generate_comparison_pool_report --help
```
