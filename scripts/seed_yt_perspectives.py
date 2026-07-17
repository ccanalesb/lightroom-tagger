"""Upsert the framing / compositional-cleanliness perspectives into the DB.

These ship as tracked defaults under ``prompts/perspectives/`` and are seeded
automatically by ``seed_perspectives_from_prompts_dir`` on a *fresh* DB (only when the
``perspectives`` table is empty). This script exists for the other case: injecting or
refreshing them in an **existing** DB. It is self-contained — ``prompt_markdown`` comes
from the committed ``.md`` files (slug = filename stem); ``display_name`` / ``description``
are inlined below (originally sourced from the yt-to-photo-prompt-lab recipe).

Idempotent: inserts new slugs, updates existing ones. Run with lightroom-tagger's venv.
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
    insert_perspective,
    update_perspective,
)

PERSPECTIVES_DIR = REPO_ROOT / "prompts" / "perspectives"

# slug -> (display_name, description). Sourced from the yt-to-photo-prompt-lab recipe;
# inlined so this script has no dependency on any path outside this repo.
META = {
    "framing": (
        "Framing",
        "Evaluating the use of a natural framing device to encircle the primary subject: "
        "whether the frame creates an appealing shape, integrates into the environment, "
        "and directs focus toward the subject without distraction.",
    ),
    "compositional-cleanliness": (
        "Compositional Cleanliness",
        "Baseline craft dimension: how free the frame is from distracting or competing "
        "elements, how controlled negative space and edges are, and how clearly the "
        "primary subject reads.",
    ),
}


def main() -> int:
    db_path = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))["db_path"]
    conn = init_database(db_path)
    try:
        for slug, (display_name, description) in META.items():
            prompt_markdown = (PERSPECTIVES_DIR / f"{slug}.md").read_text(encoding="utf-8")
            if get_perspective_by_slug(conn, slug) is None:
                insert_perspective(
                    conn,
                    slug=slug,
                    display_name=display_name,
                    prompt_markdown=prompt_markdown,
                    description=description,
                    source_filename=f"{slug}.md",
                )
                print(f"[INSERT] {slug}")
            else:
                update_perspective(
                    conn,
                    slug,
                    display_name=display_name,
                    description=description,
                    prompt_markdown=prompt_markdown,
                )
                print(f"[UPDATE] {slug}")
        conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
