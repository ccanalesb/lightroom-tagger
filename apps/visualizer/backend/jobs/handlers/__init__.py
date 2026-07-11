"""Job handler package — one module per job family.

Handler callables are registered in ``jobs.registry.JOB_TYPES``; ``JOB_HANDLERS``
below is derived for backward compatibility during migration.
"""
from .. import path_setup as _path_setup  # noqa: F401

from ..registry import JOB_TYPES
from .analyze import (
    handle_batch_analyze,
    handle_batch_describe,
    handle_batch_score,
    handle_single_describe,
    handle_single_score,
)
from .catalog import handle_catalog_sync
from .embed import handle_batch_embed_image, handle_batch_text_embed
from .instagram import handle_analyze_instagram, handle_instagram_import
from .matching import handle_enrich_catalog, handle_prepare_catalog, handle_vision_match
from .stacks import (
    handle_batch_catalog_similarity,
    handle_batch_stack_detect,
    handle_catalog_cache_build,
)

# DEPRECATED: derived from JOB_TYPES, do not edit
JOB_HANDLERS = {jt.name: jt.handler for jt in JOB_TYPES}

__all__ = ('JOB_HANDLERS',)
