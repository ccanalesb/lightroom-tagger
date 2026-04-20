"""Sync perspective markdown files from ``prompts/perspectives/`` into the DB.

Reads each ``*.md`` under ``prompts/perspectives/`` and calls
``update_perspective()`` with the file's contents as ``prompt_markdown``. The
slug is derived from the filename stem (matches ``seed_perspectives_from_prompts_dir``).

Use this after editing markdowns on disk — ``seed_perspectives_from_prompts_dir``
is one-shot (only inserts when the table is empty), so existing rows need an
explicit UPDATE to pick up new content.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from lightroom_tagger.core.database import (  # noqa: E402
    get_perspective_by_slug,
    init_database,
    update_perspective,
)


def main() -> int:
    config_path = REPO_ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    db_path = config["db_path"]

    prompts_dir = REPO_ROOT / "prompts" / "perspectives"
    md_files = sorted(prompts_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {prompts_dir}")
        return 1

    conn = init_database(db_path)
    try:
        updated = 0
        missing: list[str] = []
        for md in md_files:
            slug = md.stem
            text = md.read_text(encoding="utf-8")
            if get_perspective_by_slug(conn, slug) is None:
                missing.append(slug)
                continue
            ok = update_perspective(conn, slug, prompt_markdown=text)
            status = "OK" if ok else "NO-CHANGE"
            print(f"[{status}] {slug} <- {md.name} ({len(text)} chars)")
            if ok:
                updated += 1
        conn.commit()
        print(f"\nUpdated {updated} perspective row(s).")
        if missing:
            print(
                f"Skipped (no matching slug in DB): {', '.join(missing)}",
                file=sys.stderr,
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
