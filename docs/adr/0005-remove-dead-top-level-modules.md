# ADR-0005: Remove dead top-level module island

**Status:** Accepted  
**Date:** 2026-07-03

## Context

The `lightroom_tagger` package accumulated a top-level island of dead modules that shadowed live implementations and misled maintainers:

- `catalog_reader.py` — orphan reader duplicate; live path is `lightroom/reader.py`
- `lr_writer.py` — diverged keyword writer (keyword-UUID bug, no backup/lock guards); live path is `lightroom/writer.py`
- `lightroom/tagger.py` — redundant CLI entry wrapper; live entry is `__main__.py` and the `lightroom-tagger` console script (`core/cli.py`)

`CONTEXT.md` incorrectly named `lr_writer.py` as the keyword-write path. The dead top-level CLI (`cli.py`) and Instagram live-crawl scraper had already been removed earlier; their canonical replacements are `core/cli.py` and dump-based ingestion (`instagram/dump_reader.py`, `instagram/deduplicator.py`).

The only capability worth preserving from the dead CLI was `enrich-catalog`, especially `--cache-only` for bulk vision-cache pre-warming.

## Decision

1. **Delete** the dead modules: `catalog_reader.py`, `lr_writer.py`, `lightroom/tagger.py` (plus previously removed `cli.py` and `instagram/scraper.py`).
2. **Preserve `enrich-catalog` on the live CLI** (`core/cli.py` → `cli_cmds_extra.cmd_enrich_catalog`):
   - Full enrichment delegates to `lightroom/enricher.enrich_catalog_images` (single live enrich implementation).
   - `--cache-only` delegates to new `core/vision_cache.warm_vision_cache`.
3. **Correct docs** so read/write paths and keyword writes point at live modules (`lightroom/reader.py`, `lightroom/writer.py`, `core/cli.py`).

## Canonical module map

| Concern | Canonical module |
|---|---|
| Catalog reads | `lightroom/reader.py` |
| Keyword writes | `lightroom/writer.py` |
| CLI | `core/cli.py` (+ `cli_cmds_extra.py` for heavyweight subcommands) |
| Catalog enrichment | `lightroom/enricher.py` |
| Vision cache warming | `core/vision_cache.py` (`warm_vision_cache`) |
| Instagram data | `instagram/dump_reader.py`, `instagram/deduplicator.py` |

## Consequences

- ~1,500 lines of dead/duplicated/unsafe code removed; docs match reality.
- `enrich-catalog [--cache-only] [--limit] [--db]` remains available via `lightroom-tagger`.
- No second enrich implementation; CLI and visualizer both route through the live enricher (CLI) or inline job handler (visualizer job — unchanged in this ADR).
