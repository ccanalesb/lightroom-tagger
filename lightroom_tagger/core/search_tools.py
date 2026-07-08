"""Tool schemas and executor for LLM function-calling search."""
from __future__ import annotations

import sqlite3
from typing import Any

from lightroom_tagger.core.database import (
    catalog_schema_facets,
    get_all_current_perspective_slugs,
    query_catalog_images,
)

from lightroom_tagger.core.search_tools_definitions import ALL_TOOLS



def execute_tool(
    name: str,
    args: dict[str, Any],
    db: sqlite3.Connection,
    *,
    restrict_to_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Execute a tool call and return a result dict suitable for a tool message."""
    if name == "get_scoring_perspectives":
        return _exec_get_scoring_perspectives(db)
    if name == "search_catalog":
        return _exec_search_catalog(args, db, restrict_to_keys=restrict_to_keys)
    if name == "filter_by_date":
        return _exec_filter_by_date(args, db, restrict_to_keys=restrict_to_keys)
    if name == "get_catalog_schema":
        return _exec_get_catalog_schema(db)
    return {"error": f"Unknown tool: {name}"}


def _exec_get_catalog_schema(db: sqlite3.Connection) -> dict[str, Any]:
    """Return available filter fields with live counts so the model can pick
    the right combination of filters without blind trial-and-error."""
    facets = catalog_schema_facets(db)
    return {
        "total_catalog_images": facets.total,
        "analyzed_images": facets.analyzed,
        "date_range": {
            "earliest": facets.date_range["earliest"],
            "latest": facets.date_range["latest"],
            "note": "Use date_from/date_to (YYYY-MM-DD) or month (YYYYMM) to filter by date.",
        },
        "filters": {
            "description_search": {
                "description": "FTS over AI-generated descriptions. Use visual nouns, NOT genre labels.",
                "indexed_images": facets.analyzed,
            },
            "mood_tags": {
                "description": "AI mood/atmosphere tags. Pass array of tags; image matches if it has ANY.",
                "images_with_mood_tags": facets.with_mood,
                "top_40_tags": facets.top_moods,
            },
            "dominant_colors": {
                "description": "Hex color codes only (e.g. '#c62828'). Image matches if ANY code present.",
                "images_with_colors": facets.with_colors,
            },
            "has_repetition": {
                "description": "Visual repetition/patterns/symmetry flag.",
                "images_with_true": facets.has_rep,
            },
            "color_label": {
                "description": "Lightroom color flag.",
                "available_values_and_counts": facets.color_labels,
            },
            "score_perspective": {
                "description": "Quality score perspective. Use with sort_by_score='desc'.",
                "available_slugs": facets.perspectives,
            },
            "min_rating": {
                "description": "Lightroom star rating 1–5.",
                "images_with_any_rating": facets.rated,
            },
            "posted": {
                "description": "Instagram posted: true=posted, false=not yet posted.",
                "images_posted": facets.posted,
            },
        },
    }


def _exec_get_scoring_perspectives(db: sqlite3.Connection) -> dict[str, Any]:
    return {"perspectives": get_all_current_perspective_slugs(db)}


def _exec_search_catalog(
    args: dict[str, Any],
    db: sqlite3.Connection,
    *,
    restrict_to_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    try:
        limit = min(int(args.get("limit") or 10), 100)

        kwargs: dict[str, Any] = {}
        if args.get("description_search"):
            kwargs["description_search"] = str(args["description_search"])
        sp = (args.get("score_perspective") or "").strip() or None
        if sp:
            kwargs["score_perspective"] = sp
        if args.get("sort_by_score"):
            kwargs["sort_by_score"] = str(args["sort_by_score"])
        if args.get("sort_by_date"):
            kwargs["sort_by_date"] = str(args["sort_by_date"])
        if args.get("min_score") is not None:
            kwargs["min_score"] = int(args["min_score"])
        if args.get("min_rating") is not None:
            kwargs["min_rating"] = int(args["min_rating"])
        if args.get("has_repetition") is not None:
            kwargs["has_repetition"] = bool(args["has_repetition"])
        if args.get("posted") is not None:
            kwargs["posted"] = bool(args["posted"])
        if args.get("date_from"):
            kwargs["date_from"] = str(args["date_from"])
        if args.get("date_to"):
            kwargs["date_to"] = str(args["date_to"])
        if args.get("month"):
            kwargs["month"] = str(args["month"])
        if args.get("color_label"):
            kwargs["color_label"] = str(args["color_label"])
        if args.get("mood_tags"):
            kwargs["mood_tags"] = [str(t) for t in args["mood_tags"]]
        if args.get("dominant_colors"):
            kwargs["dominant_colors"] = [str(c) for c in args["dominant_colors"]]

        rows, total = query_catalog_images(
            db, limit=limit, offset=0, restrict_to_keys=restrict_to_keys, **kwargs
        )
        images = _rows_to_tool_result(rows, score_perspective_slug=sp)
        return {"total_matched": total, "returned": len(images), "images": images}
    except ValueError as exc:
        return {"error": str(exc)}


def _exec_filter_by_date(
    args: dict[str, Any],
    db: sqlite3.Connection,
    *,
    restrict_to_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    try:
        limit = min(int(args.get("limit") or 10), 100)
        kwargs: dict[str, Any] = {}
        if args.get("date_from"):
            kwargs["date_from"] = str(args["date_from"])
        if args.get("date_to"):
            kwargs["date_to"] = str(args["date_to"])
        if args.get("sort_direction"):
            kwargs["sort_by_date"] = str(args["sort_direction"])

        rows, total = query_catalog_images(
            db, limit=limit, offset=0, restrict_to_keys=restrict_to_keys, **kwargs
        )
        images = _rows_to_tool_result(rows, score_perspective_slug=None)
        return {"total_matched": total, "returned": len(images), "images": images}
    except ValueError as exc:
        return {"error": str(exc)}


def _rows_to_tool_result(
    rows: list[dict[str, Any]],
    *,
    score_perspective_slug: str | None,
) -> list[dict[str, Any]]:
    """Convert DB rows to rich tool result dicts."""
    result: list[dict[str, Any]] = []
    for row in rows:
        key = row.get("key")
        if key is None and row.get("id") is not None:
            key = row.get("id")
        item: dict[str, Any] = {
            "key": key,
            "filename": row.get("filename"),
            "date_taken": row.get("date_taken"),
        }
        score_val = row.get("catalog_perspective_score")
        if score_val is None and row.get("score") is not None:
            score_val = row["score"]
        if score_val is not None:
            item["score"] = score_val
        if score_perspective_slug:
            item["score_perspective"] = score_perspective_slug
        elif row.get("score_perspective"):
            item["score_perspective"] = row["score_perspective"]
        rationale = row.get("score_rationale") or row.get("rationale")
        if rationale:
            item["score_rationale"] = rationale
        desc = (
            row.get("description")
            or row.get("summary")
            or row.get("description_summary")
        )
        if desc:
            item["description"] = desc
        if row.get("mood_tags") is not None:
            item["mood_tags"] = row["mood_tags"]
        if row.get("dominant_colors") is not None:
            item["dominant_colors"] = row["dominant_colors"]
        result.append(item)
    return result
