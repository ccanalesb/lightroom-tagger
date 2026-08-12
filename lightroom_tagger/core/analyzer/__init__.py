"""Image analysis facade — explicit barrel re-exports from ADR-0001 submodules."""
# Import order matches ``__all__`` (explicit Phase-14-style barrel contract).
# ruff: noqa: I001

from lightroom_tagger.core.config import get_description_model, get_vision_model, load_config
from lightroom_tagger.core.exceptions import ContextLengthError

from .description import (
    DESCRIPTION_PROMPT,
    _DESCRIPTION_FALLBACK,
    build_description_op_spec,
    build_description_prompt,
    parse_description_response,
    run_description_vision_op,
    run_external_agent,
)
from .scoring import build_score_op_spec, parse_score_vision_response
from .image_inspect import compute_phash, extract_exif
from .image_prep import (
    RAW_EXTENSIONS,
    VIDEO_EXTENSIONS,
    VISION_COMPRESS_QUALITY,
    VISION_MAX_DIMENSION,
    compress_image,
    convert_raw_to_jpg,
    get_viewable_path,
    get_viewable_path_managed,
)
from lightroom_tagger.core.error_policy import (
    ContextLengthEscalationPolicy,
    MAX_TOKENS_ESCALATION,
)

__all__ = (
    "ContextLengthError",
    "ContextLengthEscalationPolicy",
    "DESCRIPTION_PROMPT",
    "MAX_TOKENS_ESCALATION",
    "RAW_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "VISION_COMPRESS_QUALITY",
    "VISION_MAX_DIMENSION",
    "_DESCRIPTION_FALLBACK",
    "build_description_op_spec",
    "build_description_prompt",
    "build_score_op_spec",
    "compress_image",
    "compute_phash",
    "convert_raw_to_jpg",
    "extract_exif",
    "get_description_model",
    "get_viewable_path",
    "get_viewable_path_managed",
    "get_vision_model",
    "load_config",
    "parse_description_response",
    "parse_score_vision_response",
    "run_description_vision_op",
    "run_external_agent",
)
