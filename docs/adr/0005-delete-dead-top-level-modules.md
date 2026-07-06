# ADR-0005: Delete dead top-level module island

**Status:** Accepted  
**Date:** 2026-07-06

## Context

The `lightroom_tagger` package accumulated a parallel “module island” at the package root and under `lightroom/` — duplicate or orphan surfaces that diverged from the live code paths (PRD #38). After `enrich-catalog` was preserved on the live CLI (`core/cli.py`, #41), these modules had zero production importers and posed maintenance risk.

Three of the six were already removed by earlier cleanup (commit `0fb6ba7`, "Remove deprecated live-crawl Instagram code and stale CLI stack"):

- **`lightroom_tagger/cli.py`** — superseded by `lightroom_tagger/core/cli.py`, the sole CLI registered in `pyproject.toml` (`lightroom-tagger` console script).
- **`lightroom_tagger/tagger.py`** — top-level entry-point wrapper that delegated to the dead `cli.py`; redundant with `__main__.py` and the console script.
- **`lightroom_tagger/instagram_scraper.py`** — deprecated live-crawl scraper; Instagram data now comes only from user export dumps via `instagram/dump_reader.py`.

The remaining three still-present modules are deleted in this change:

- **`lightroom_tagger/catalog_reader.py`** — re-exported `connect_catalog` from the live reader but duplicated otherwise-unused catalog query logic; zero importers.
- **`lightroom_tagger/lr_writer.py`** — diverged copy of the catalog writer (keyword-UUID bug, missing backup/lock guards). The safe writer is `lightroom_tagger/lightroom/writer.py`.
- **`lightroom_tagger/lightroom/tagger.py`** — redundant entry-point wrapper delegating to `core.cli:main`; superseded by `__main__.py` and the `lightroom-tagger` console script.

`CONTEXT.md` incorrectly named `lr_writer.py` as the keyword-write path; keyword writes always belonged on `lightroom/writer.py`.

`get_catalog_images_missing_cache` in `core/database/catalog.py` remains exported. With the dead top-level `cli.py` gone, its only non-test caller is `warm_vision_cache` in `core/vision_cache.py` — the export is intentionally retained.

## Decision

Delete the three still-present dead modules (`catalog_reader.py`, `lr_writer.py`, `lightroom/tagger.py`), completing removal of the six-module island. Correct documentation to point at canonical locations only:

| Concern | Canonical module |
|---|---|
| CLI entry point | `lightroom_tagger/core/cli.py` (+ `__main__.py`, `lightroom-tagger` script) |
| Catalog reads | `lightroom_tagger/lightroom/reader.py` |
| Catalog keyword writes | `lightroom_tagger/lightroom/writer.py` |
| Instagram ingest | `lightroom_tagger/instagram/dump_reader.py`, `deduplicator.py` |
| Catalog enrichment | `lightroom_tagger/lightroom/enricher.py` (invoked via `enrich-catalog` on live CLI) |

Update `CONTEXT.md`, `docs/CATALOG_READ_WRITE.md`, and `README.md` accordingly.

## Consequences

- One clear read/write/CLI surface; architecture reviews should not resurrect the deleted duplicates.
- The `pytest` pass set is unchanged by the deletions, confirming the removed modules were unreferenced.
- Docs no longer vouch for `catalog_reader.py`, top-level `cli.py`, or `lr_writer.py`.
