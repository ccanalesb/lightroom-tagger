# E2E fixtures

This directory holds committed artifacts used by the browser-backed E2E suite.

- **`catalog.lrcat`** — a minimal real Lightroom catalog slice (read-only in tests).
- **`library_seed.db`** — a seeded SQLite file for `LIBRARY_DB` with predictable rows for stable assertions.

Maintainers regenerate or refresh these files from later plans using:

```bash
python export_fixture.py --library
python export_fixture.py --catalog-from PATH
```

(`export_fixture.py` lives alongside these artifacts; wire the exact filenames in Plan 02.)

At E2E runtime, the suite copies `library_seed.db` into a session-scoped temporary directory so writes never touch the committed seed—for example with `shutil.copy(source, dest)` before pointing the test backend at the copy.
