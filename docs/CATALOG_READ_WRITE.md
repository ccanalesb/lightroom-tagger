# Lightroom catalog (.lrcat) read vs write

## Read paths (do not write)

By default, `sqlite3` URI parameter `mode=ro` is used when opening the catalog for reads.

- Catalog reads and scans use `lightroom_tagger/lightroom/reader.py` (`connect_catalog`).
- `lightroom_tagger/catalog_reader.py` re-exports the same `connect_catalog` (delegate to the reader).
- `lightroom_tagger/schema_explorer.py` opens the catalog only through the reader.
- `lightroom_tagger/lightroom/schema.py` opens the catalog only through the reader.
- `lightroom_tagger/cli.py` imports `connect_catalog` from the reader for scan workflows.
- `lightroom_tagger/core/cli.py` imports `connect_catalog` from the reader for scan workflows.

Keyword writeback and repair scripts use a **separate** SQLite connection from the read-only reader.

## Write paths

- `lightroom_tagger/lightroom/writer.py` — keyword writeback to the catalog.
- `lightroom_tagger/lr_writer.py` — alternate writer surface for catalog updates.
- `lightroom_tagger/lightroom/cleanup_wrong_links.py` — one-time repair script that mutates the catalog.
