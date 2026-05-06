"""Image analysis facade — explicit barrel re-exports from ADR-0001 submodules."""
# Import order matches ``__all__`` (explicit Phase-14-style barrel contract).
# ruff: noqa: I001

from lightroom_tagger.core.config import get_description_model, get_vision_model, load_config
from lightroom_tagger.core.exceptions import ContextLengthError

from .description import (
    DESCRIPTION_PROMPT,
    _DESCRIPTION_FALLBACK,
    _describe_image_via_provider,
    build_description_prompt,
    describe_image,
    parse_description_response,
    run_external_agent,
)
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
from .vision_compare import (
    MAX_TOKENS_ESCALATION,
    _broken_provider_models,
    _compare_via_provider,
    _model_min_tokens,
    compare_with_vision,
    parse_vision_response,
    vision_score,
)

__all__ = (
    "ContextLengthError",
    "DESCRIPTION_PROMPT",
    "MAX_TOKENS_ESCALATION",
    "RAW_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "VISION_COMPRESS_QUALITY",
    "VISION_MAX_DIMENSION",
    "_DESCRIPTION_FALLBACK",
    "_broken_provider_models",
    "_compare_via_provider",
    "_describe_image_via_provider",
    "_model_min_tokens",
    "build_description_prompt",
    "compare_with_vision",
    "compress_image",
    "compute_phash",
    "convert_raw_to_jpg",
    "describe_image",
    "extract_exif",
    "get_description_model",
    "get_viewable_path",
    "get_viewable_path_managed",
    "get_vision_model",
    "load_config",
    "parse_description_response",
    "parse_vision_response",
    "run_external_agent",
    "vision_score",
)
