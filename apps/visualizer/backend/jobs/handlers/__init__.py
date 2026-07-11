"""Job handler package — one module per job family.

Handler callables are registered in ``jobs.registry.JOB_TYPES``; ``JOB_HANDLERS``
below is derived for backward compatibility during migration.
"""
from .. import path_setup as _path_setup  # noqa: F401

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

_JOB_HANDLERS: dict | None = None


def __getattr__(name: str):
    if name == 'JOB_HANDLERS':
        global _JOB_HANDLERS
        if _JOB_HANDLERS is None:
            from ..registry import JOB_TYPES

            # DEPRECATED: derived from JOB_TYPES, do not edit
            _JOB_HANDLERS = {jt.name: jt.handler for jt in JOB_TYPES}
        return _JOB_HANDLERS
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


__all__ = (
    'JOB_HANDLERS',
    'handle_analyze_instagram',
    'handle_instagram_import',
    'handle_vision_match',
    'handle_enrich_catalog',
    'handle_prepare_catalog',
    'handle_batch_describe',
    'handle_single_describe',
    'handle_single_score',
    'handle_batch_score',
    'handle_batch_analyze',
    'handle_batch_stack_detect',
    'handle_batch_catalog_similarity',
    'handle_batch_text_embed',
    'handle_batch_embed_image',
    'handle_catalog_sync',
    'handle_catalog_cache_build',
)
