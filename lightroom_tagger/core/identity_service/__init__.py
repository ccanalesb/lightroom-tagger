"""Catalog identity aggregation: best-photo ranking, style fingerprint, post-next hints.

Design decisions D-40–D-47 are documented in
``.planning/phases/08-identity-suggestions/08-CONTEXT.md``.
"""

from __future__ import annotations

from ._legacy import (
    _SCORES_BASE_SQL,
    _WORD_RE,
    _RATIONALE_PREVIEW_MAX,
    _active_perspective_slugs,
    _aggregate_histogram,
    _default_min_perspectives,
    _image_meta_map,
    _posted_catalog_keys_sql,
    _stack_fields_for_image_keys,
    _stack_non_representative_keys,
    _tokenize_rationale,
    _truncate_rationale,
    build_style_fingerprint,
    compute_image_aggregate_scores,
    compute_single_image_aggregate_scores,
    rank_best_photos,
    suggest_what_to_post_next,
)

__all__ = [
    "_SCORES_BASE_SQL",
    "_WORD_RE",
    "_RATIONALE_PREVIEW_MAX",
    "_active_perspective_slugs",
    "_aggregate_histogram",
    "_default_min_perspectives",
    "_image_meta_map",
    "_posted_catalog_keys_sql",
    "_stack_fields_for_image_keys",
    "_stack_non_representative_keys",
    "_tokenize_rationale",
    "_truncate_rationale",
    "build_style_fingerprint",
    "compute_image_aggregate_scores",
    "compute_single_image_aggregate_scores",
    "rank_best_photos",
    "suggest_what_to_post_next",
]
