"""Regenerate committed E2E fixtures (library SQLite seed, catalog copy)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from lightroom_tagger.core.database.db_init import init_database

_KEYS = [f"e2e_cat_{i:03d}" for i in range(1, 6)]


def _regenerate_library_seed(dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    conn = init_database(str(dest))
    try:
        for key in _KEYS:
            filename = f"e2e-{key}.dng"
            filepath = f"/tmp/lightroom-tagger-e2e/{key}.dng"
            conn.execute(
                """
                INSERT INTO images (key, filename, filepath, title, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, filename, filepath, "Lightroom Tagger", "e2e seed"),
            )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    bak = dest.with_name(dest.name + ".pre-key-migration.bak")
    if bak.is_file():
        bak.unlink()


def main() -> None:
    parent = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        action="store_true",
        help="Recreate library_seed.db next to this script",
    )
    parser.add_argument(
        "--catalog-from",
        metavar="SRC",
        help="Copy SRC to catalog.lrcat next to this script",
    )
    args = parser.parse_args()
    if not args.library and not args.catalog_from:
        parser.error("specify --library and/or --catalog-from SRC")
    if args.library:
        _regenerate_library_seed(parent / "library_seed.db")
    if args.catalog_from:
        shutil.copy2(args.catalog_from, parent / "catalog.lrcat")


if __name__ == "__main__":
    main()
