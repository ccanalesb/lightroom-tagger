"""One-shot migration: reduce the 6 active perspectives to 4.

Merges (see grilling action plan):
  - tension-human-element  -> absorbed by intensity-suggestion (renamed
    "Interpretive & Human Charge"); tension row set inactive.
  - layering               -> absorbed by environmental-context-legibility
    (renamed "Depth & Environmental Context"); layering row set inactive.
  - framing                -> rubric rewritten in place (still optional).

Survivors keep their slugs. Their new markdown carries the ``<!-- optional: true -->``
marker, so ``update_perspective`` re-derives ``optional=1`` (ADR-0012). Absorbed rows
keep their historical ``image_scores`` (excluded from aggregation via the ``active=1``
join). No re-scoring — scores self-heal on the next scoring run via ``prompt_version``.

Idempotent: safe to run repeatedly. Run with lightroom-tagger's venv.
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

PERSPECTIVES_DIR = REPO_ROOT / "prompts" / "perspectives"

# slug -> new display_name. Markdown is pulled from the committed .md file.
SURVIVORS = {
    "intensity-suggestion": "Interpretive & Human Charge",
    "environmental-context-legibility": "Depth & Environmental Context",
    "framing": "Framing",
}

# Absorbed perspectives: deactivate (history preserved, excluded from aggregation).
DEACTIVATE = ["layering", "tension-human-element"]


def main() -> int:
    db_path = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))["db_path"]
    conn = init_database(db_path)
    try:
        for slug, display_name in SURVIVORS.items():
            md = (PERSPECTIVES_DIR / f"{slug}.md").read_text(encoding="utf-8")
            ok = update_perspective(
                conn,
                slug,
                display_name=display_name,
                prompt_markdown=md,
            )
            row = get_perspective_by_slug(conn, slug)
            optional = bool(row["optional"]) if row else None
            print(f"[{'OK' if ok else 'MISSING'}] survivor {slug} "
                  f"name='{display_name}' optional={optional}")

        for slug in DEACTIVATE:
            if get_perspective_by_slug(conn, slug) is None:
                print(f"[SKIP] {slug} not present")
                continue
            update_perspective(conn, slug, active=False)
            print(f"[OK] deactivated {slug}")

        conn.commit()

        active = conn.execute(
            "SELECT slug, display_name, optional FROM perspectives "
            "WHERE active = 1 ORDER BY slug"
        ).fetchall()
        print(f"\nActive perspectives ({len(active)}):")
        for r in active:
            print(f"  - {r['slug']}  ({r['display_name']}, optional={bool(r['optional'])})")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
