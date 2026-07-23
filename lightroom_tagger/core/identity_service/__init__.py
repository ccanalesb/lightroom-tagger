"""Catalog identity aggregation: best-photo ranking, mirror signature, post-next hints."""

from __future__ import annotations

from .aggregates import (
    _SCORES_BASE_SQL,
    _WORD_RE,
    _RATIONALE_PREVIEW_MAX,
    _active_perspective_slugs,
    _default_min_perspectives,
    _tokenize_rationale,
    _truncate_rationale,
    compute_single_image_aggregate_scores,
)
from .mirror import build_mirror
from .percentiles import (
    compute_image_peak_percentile_scores,
    compute_within_perspective_percentile_lookup,
)
from .ranking import (
    _image_meta_map,
    _stack_fields_for_image_keys,
    _stack_non_representative_keys,
    rank_best_photos,
)
from .suggest_post import suggest_what_to_post_next

__all__ = [
    "_SCORES_BASE_SQL",
    "_WORD_RE",
    "_RATIONALE_PREVIEW_MAX",
    "_active_perspective_slugs",
    "_default_min_perspectives",
    "_image_meta_map",
    "_stack_fields_for_image_keys",
    "_stack_non_representative_keys",
    "_tokenize_rationale",
    "_truncate_rationale",
    "build_mirror",
    "compute_image_peak_percentile_scores",
    "compute_single_image_aggregate_scores",
    "compute_within_perspective_percentile_lookup",
    "rank_best_photos",
    "suggest_what_to_post_next",
]
