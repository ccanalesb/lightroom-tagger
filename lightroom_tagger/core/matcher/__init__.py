"""Instagram ↔ catalog matching: candidates, scoring, vision batch path, orchestration."""

from lightroom_tagger.core.config import get_vision_model
from lightroom_tagger.core.database import (
    _deserialize_row,
    get_vision_comparison,
    store_match,
    store_vision_comparison,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_cache import (
    InstagramCache,
    get_cached_phash,
    get_or_create_cached_image,
)
from lightroom_tagger.core.vision_client import compare_descriptions_batch

from .candidates import find_candidates_by_date, query_by_exif
from .description_batch import _compute_desc_scores_for_candidates
from .matching import match_batch, match_image
from .score_with_vision import score_candidates_with_vision
from .text_scores import score_candidates, text_similarity
from .vision_batch import BATCH_MAX_TOKENS_ESCALATION, _call_batch_chunk

__all__ = [
    "BATCH_MAX_TOKENS_ESCALATION",
    "InstagramCache",
    "ProviderRegistry",
    "compare_descriptions_batch",
    "find_candidates_by_date",
    "get_cached_phash",
    "get_or_create_cached_image",
    "get_vision_comparison",
    "get_vision_model",
    "match_batch",
    "match_image",
    "query_by_exif",
    "score_candidates",
    "score_candidates_with_vision",
    "store_match",
    "store_vision_comparison",
    "text_similarity",
]
