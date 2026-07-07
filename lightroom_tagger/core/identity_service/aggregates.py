"""Per-image aggregate scores over active critique perspectives."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from lightroom_tagger.core.text_constants import EN_STOPWORDS as _EN_STOPWORDS

# Current catalog scores only — identity aggregation excludes non-catalog rows (D-40 / phase 10).
_SCORES_BASE_SQL = """
    SELECT
        s.image_key,
        s.image_type,
        s.perspective_slug,
        s.score,
        s.rationale,
        s.model_used,
        s.prompt_version,
        s.scored_at,
        p.display_name AS perspective_display_name
    FROM image_scores s
    INNER JOIN perspectives p
        ON p.slug = s.perspective_slug AND p.active = 1
    WHERE s.is_current = 1
        AND s.image_type = 'catalog'
        AND s.not_attempted = 0
"""

_WORD_RE = re.compile(r"[\w']+", flags=re.UNICODE)

_RATIONALE_PREVIEW_MAX = 240


def _active_perspective_slugs(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug ASC"
    ).fetchall()
    return [str(r["slug"]) for r in rows]


def _default_min_perspectives(active_count: int) -> int:
    """Minimum 1 perspective required for eligibility."""
    return 1


def _tokenize_rationale(text: str | None) -> list[str]:
    """D-43: lowercase word tokens, length >= 3, minimal English stopwords dropped."""
    if not text:
        return []
    out: list[str] = []
    for m in _WORD_RE.finditer(text.lower()):
        w = m.group(0).strip("'")
        if len(w) < 3 or w in _EN_STOPWORDS:
            continue
        out.append(w)
    return out


def _truncate_rationale(text: str | None, max_chars: int = _RATIONALE_PREVIEW_MAX) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def compute_image_aggregate_scores(
    conn: sqlite3.Connection,
    *,
    min_perspectives: int | None = None,
    include_ineligible: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build per-image aggregates over active perspectives (equal weights, D-40).

    Returns ``(items, meta)``. Each item includes ``per_perspective`` entries with
    ``rationale_preview`` (truncated). When ``include_ineligible`` is False, only
    eligible rows are returned (used internally for tighter payloads).
    """
    active_slugs = _active_perspective_slugs(conn)
    active_count = len(active_slugs)
    slug_set = set(active_slugs)
    min_used = (
        int(min_perspectives)
        if min_perspectives is not None
        else _default_min_perspectives(active_count)
    )

    total_catalog = int(
        conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
    )

    rows = conn.execute(_SCORES_BASE_SQL).fetchall()

    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        by_key.setdefault(str(r["image_key"]), []).append(
            {
                "perspective_slug": slug,
                "display_name": r["perspective_display_name"] or slug,
                "score": int(r["score"]),
                "rationale": r.get("rationale") or "",
                "model_used": r.get("model_used") or "",
                "prompt_version": r.get("prompt_version") or "",
                "scored_at": r.get("scored_at") or "",
            }
        )

    items: list[dict[str, Any]] = []
    eligible_count = 0
    for image_key, perspectives in by_key.items():
        n = len(perspectives)
        agg = sum(p["score"] for p in perspectives) / n if n else 0.0
        eligible = n >= min_used
        if eligible:
            eligible_count += 1

        per_out: list[dict[str, Any]] = []
        for p in sorted(perspectives, key=lambda x: x["perspective_slug"]):
            per_out.append(
                {
                    "perspective_slug": p["perspective_slug"],
                    "display_name": p["display_name"],
                    "score": p["score"],
                    "prompt_version": p["prompt_version"],
                    "model_used": p["model_used"],
                    "scored_at": p["scored_at"],
                    "rationale_preview": _truncate_rationale(p.get("rationale")),
                }
            )

        row = {
            "image_key": image_key,
            "aggregate_score": round(agg, 4),
            "perspectives_covered": n,
            "eligible": eligible,
            "per_perspective": per_out,
        }
        if include_ineligible or eligible:
            items.append(row)

    scored_any_count = len(by_key)
    coverage_rule = "eligible when perspectives_covered >= min_perspectives (default 1)"
    meta: dict[str, Any] = {
        "active_perspectives": active_slugs,
        "weighting": "equal",
        "min_perspectives_used": min_used,
        "coverage_rule": coverage_rule,
        "total_catalog_images": total_catalog,
        "eligible_count": eligible_count,
        "scored_any_count": scored_any_count,
    }
    if eligible_count == 0 and active_count > 0:
        meta["coverage_note"] = (
            "No images meet the minimum perspective coverage for ranking; "
            "score at least one perspective per image."
        )
    return items, meta


def compute_single_image_aggregate_scores(
    conn: sqlite3.Connection,
    image_key: str,
) -> dict[str, Any] | None:
    """Aggregate identity scores for a single catalog image.

    Reuses :data:`_SCORES_BASE_SQL` (``is_current = 1`` AND
    ``image_type = 'catalog'``) and the active-perspectives / equal-weight
    rules from :func:`compute_image_aggregate_scores`. Returns a per-image
    record (``image_key``, ``aggregate_score``, ``perspectives_covered``,
    ``eligible``, ``per_perspective``) or ``None`` when no current catalog
    scores exist for ``image_key`` on active perspectives.
    """
    active_slugs = _active_perspective_slugs(conn)
    if not active_slugs:
        return None
    slug_set = set(active_slugs)
    min_used = _default_min_perspectives(len(active_slugs))

    rows = conn.execute(
        _SCORES_BASE_SQL + "\n        AND s.image_key = ?",
        (image_key,),
    ).fetchall()

    perspectives: list[dict[str, Any]] = []
    for r in rows:
        slug = str(r["perspective_slug"])
        if slug not in slug_set:
            continue
        perspectives.append(
            {
                "perspective_slug": slug,
                "display_name": r["perspective_display_name"] or slug,
                "score": int(r["score"]),
                "rationale": r.get("rationale") or "",
                "model_used": r.get("model_used") or "",
                "prompt_version": r.get("prompt_version") or "",
                "scored_at": r.get("scored_at") or "",
            }
        )

    if not perspectives:
        return None

    n = len(perspectives)
    agg = sum(p["score"] for p in perspectives) / n
    per_out: list[dict[str, Any]] = []
    for p in sorted(perspectives, key=lambda x: x["perspective_slug"]):
        per_out.append(
            {
                "perspective_slug": p["perspective_slug"],
                "display_name": p["display_name"],
                "score": p["score"],
                "prompt_version": p["prompt_version"],
                "model_used": p["model_used"],
                "scored_at": p["scored_at"],
                "rationale_preview": _truncate_rationale(p.get("rationale")),
            }
        )

    return {
        "image_key": str(image_key),
        "aggregate_score": round(agg, 4),
        "perspectives_covered": n,
        "eligible": n >= min_used,
        "per_perspective": per_out,
    }
