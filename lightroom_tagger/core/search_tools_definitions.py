"""OpenAI-style tool payloads for NL search tooling."""
from __future__ import annotations

# --- Tool schemas (OpenAI function-calling format) ---

SEARCH_CATALOG_TOOL = {
    "type": "function",
    "function": {
        "name": "search_catalog",
        "description": (
            "Search the photo catalog with optional filters. "
            "All filters are AND-combined. "
            "Use limit=1 for 'the best', limit=10 for browsing. "
            "Call get_catalog_schema first if unsure which filters have data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description_search": {
                    "type": "string",
                    "description": (
                        "FTS over AI-generated image descriptions — visual content only "
                        "(objects, scenes, people, mood). "
                        "Use visual nouns (crowd, sidewalk, market, mountains). "
                        "NEVER use genre labels like 'street photography' — they return 0. "
                        "Do NOT combine with has_repetition or mood_tags for the same concept."
                    ),
                },
                "mood_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "AI-generated mood/atmosphere tags. An image matches if it has ANY of the tags. "
                        "Examples: ['melancholic'], ['dramatic', 'moody'], ['joyful', 'festive']. "
                        "Call get_catalog_schema to see a sample of available tags (11000+ images have them). "
                        "Use for mood, atmosphere, or feeling queries instead of description_search."
                    ),
                },
                "dominant_colors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Filter by dominant color hex codes (e.g. ['#c62828', '#1565c0']). "
                        "ONLY use hex codes — color names like 'red' will return 0 results. "
                        "An image matches if ANY of the listed hex codes appears in its dominant colors."
                    ),
                },
                "score_perspective": {
                    "type": "string",
                    "description": (
                        "Perspective slug for quality scoring. "
                        "Call get_scoring_perspectives or get_catalog_schema to see valid slugs."
                    ),
                },
                "sort_by_score": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort by score (desc=best first). Requires score_perspective.",
                },
                "sort_by_date": {
                    "type": "string",
                    "enum": ["newest", "oldest"],
                    "description": "Sort by date taken. Can combine with sort_by_score (score wins).",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date inclusive, format YYYY-MM-DD.",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date inclusive, format YYYY-MM-DD.",
                },
                "month": {
                    "type": "string",
                    "description": (
                        "Filter to a specific month, format YYYYMM (e.g. '202312' for December 2023). "
                        "Use this for 'photos from [month]' queries."
                    ),
                },
                "color_label": {
                    "type": "string",
                    "enum": ["red", "yellow", "green", "blue", "purple"],
                    "description": "Lightroom color label/flag assigned to the image.",
                },
                "min_score": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Minimum quality score (1–10). Requires score_perspective.",
                },
                "min_rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Minimum Lightroom star rating (1–5).",
                },
                "has_repetition": {
                    "type": "boolean",
                    "description": (
                        "Pre-computed flag: true = image has visual repetition/patterns/symmetry (~8000 images). "
                        "Use as PRIMARY filter for repetition/pattern queries. "
                        "Do NOT also add 'pattern' or 'repetition' to description_search."
                    ),
                },
                "posted": {
                    "type": "boolean",
                    "description": "Instagram posted: true=already posted (95 images), false=not yet posted.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Results to return. Default 10. Use 1 for 'the best'.",
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

GET_CATALOG_SCHEMA_TOOL = {
    "type": "function",
    "function": {
        "name": "get_catalog_schema",
        "description": (
            "Returns counts for every available filter in search_catalog. "
            "Call this first when you are unsure whether a filter has data or "
            "want to pick the right combination of filters before searching."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}

ALL_TOOLS = [
    SEARCH_CATALOG_TOOL,
    GET_SCORING_PERSPECTIVES_TOOL,
    GET_CATALOG_SCHEMA_TOOL,
]
