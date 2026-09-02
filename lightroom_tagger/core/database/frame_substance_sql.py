"""The one SQL phrasing of "this frame is condemned" (#301).

A leaf module on purpose: the ranking, stack suggestions and the catalog
listing all need this fragment, and they sit on both sides of
``frame_substance``'s own imports, so anything with dependencies here
would close an import cycle.
"""

from __future__ import annotations

FLAGGED_VERDICTS = frozenset({"void", "illegible"})


def flagged_exists_sql(*image_key_columns: str) -> str:
    """SQL for "this frame is condemned and the user has not overridden it".

    Four read paths express this rule — the ranking's ``_SCORES_BASE_SQL``,
    pending stack suggestions (which matches either end of a pair), and the
    catalog listing's flagged filter in both directions. They must not be
    able to disagree, so they all render it from here.
    ``is_frame_substance_flagged`` is the same rule for callers holding a
    single image key.
    """
    if len(image_key_columns) == 1:
        match = f"fs.image_key = {image_key_columns[0]}"
    else:
        match = f"fs.image_key IN ({', '.join(image_key_columns)})"
    return f"""
        EXISTS (
            SELECT 1
            FROM image_frame_substance fs
            WHERE {match}
              AND fs.verdict IN ('void', 'illegible')
              AND NOT EXISTS (
                  SELECT 1
                  FROM frame_substance_overrides o
                  WHERE o.image_key = fs.image_key
              )
        )
    """
