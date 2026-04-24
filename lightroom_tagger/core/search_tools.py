"""Tool schemas and executor for LLM function-calling search."""
from __future__ import annotations

import sqlite3
from typing import Any

from lightroom_tagger.core.database import query_catalog_images

# --- Tool schemas (OpenAI function-calling format) ---

SEARCH_CATALOG_TOOL = {
    "type": "function",
    "function": {
        "name": "search_catalog",
        "description": (
            "Search the photo catalog with optional filters. "
            "Returns images sorted by relevance or score. "
            "Use limit=1 for 'the best', limit=10 for browsing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description_search": {
                    "type": "string",
                    "description": (
                        "What is visually in the photo — people, scenes, colours, mood, objects. "
                        "Free-text search over AI-generated descriptions."
                    ),
                },
                "score_perspective": {
                    "type": "string",
                    "description": (
                        "Perspective slug for quality scoring. "
                        "Call get_scoring_perspectives first to see valid slugs."
                    ),
                },
                "sort_by_score": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort by score. Requires score_perspective.",
                },
                "sort_by_date": {
                    "type": "string",
                    "enum": ["newest", "oldest"],
                },
                "min_score": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Minimum score (1–10). Requires score_perspective.",
                },
                "min_rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Minimum Lightroom star rating.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Number of results to return. Default 10. Use 1 for 'the best'.",
                },
            },
            "additionalProperties": False,
        },
    },
}

GET_SCORING_PERSPECTIVES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_scoring_perspectives",
        "description": (
            "Returns available scoring perspective slugs and descriptions. "
            "Call this before using score_perspective in search_catalog."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}

FILTER_BY_DATE_TOOL = {
    "type": "function",
    "function": {
        "name": "filter_by_date",
        "description": "Filter images by date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                "sort_direction": {"type": "string", "enum": ["newest", "oldest"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
    },
}

ALL_TOOLS = [SEARCH_CATALOG_TOOL, GET_SCORING_PERSPECTIVES_TOOL, FILTER_BY_DATE_TOOL]


def execute_tool(name: str, args: dict[str, Any], db: sqlite3.Connection) -> dict[str, Any]:
    """Execute a tool call and return a result dict suitable for a tool message."""
    if name == "get_scoring_perspectives":
        return _exec_get_scoring_perspectives(db)
    if name == "search_catalog":
        return _exec_search_catalog(args, db)
    if name == "filter_by_date":
        return _exec_filter_by_date(args, db)
    return {"error": f"Unknown tool: {name}"}


def _exec_get_scoring_perspectives(db: sqlite3.Connection) -> dict[str, Any]:
    rows = db.execute(
        "SELECT DISTINCT perspective_slug FROM image_scores "
        "WHERE is_current = 1 ORDER BY perspective_slug"
    ).fetchall()
    slugs = [r["perspective_slug"] for r in rows]
    return {"perspectives": slugs}


def _exec_search_catalog(args: dict[str, Any], db: sqlite3.Connection) -> dict[str, Any]:
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

        rows, total = query_catalog_images(db, limit=limit, offset=0, **kwargs)
        images = _rows_to_tool_result(rows, score_perspective_slug=sp)
        return {"total_matched": total, "returned": len(images), "images": images}
    except ValueError as exc:
        return {"error": str(exc)}


def _exec_filter_by_date(args: dict[str, Any], db: sqlite3.Connection) -> dict[str, Any]:
    try:
        limit = min(int(args.get("limit") or 10), 100)
        kwargs: dict[str, Any] = {}
        if args.get("date_from"):
            kwargs["date_from"] = str(args["date_from"])
        if args.get("date_to"):
            kwargs["date_to"] = str(args["date_to"])
        if args.get("sort_direction"):
            kwargs["sort_by_date"] = str(args["sort_direction"])

        rows, total = query_catalog_images(db, limit=limit, offset=0, **kwargs)
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
