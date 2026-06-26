"""Job handler package — one module per job family."""
from .. import path_setup as _path_setup  # noqa: F401

from .analyze import (
    handle_batch_analyze,
    handle_batch_describe,
    handle_batch_score,
    handle_single_describe,
    handle_single_score,
)
from .embed import handle_batch_embed_image, handle_batch_text_embed
from .instagram import handle_analyze_instagram, handle_instagram_import
from .matching import handle_enrich_catalog, handle_prepare_catalog, handle_vision_match
from .catalog import handle_catalog_sync
from .stacks import (
    handle_batch_catalog_similarity,
    handle_batch_stack_detect,
    handle_catalog_cache_build,
)

JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'instagram_import': handle_instagram_import,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
    'prepare_catalog': handle_prepare_catalog,
    'batch_describe': handle_batch_describe,
    'single_describe': handle_single_describe,
    'single_score': handle_single_score,
    'batch_score': handle_batch_score,
    'batch_analyze': handle_batch_analyze,
    'batch_stack_detect': handle_batch_stack_detect,
    'batch_catalog_similarity': handle_batch_catalog_similarity,
    'batch_text_embed': handle_batch_text_embed,
    'batch_embed_image': handle_batch_embed_image,
    'catalog_sync': handle_catalog_sync,
    'catalog_cache_build': handle_catalog_cache_build,
}

__all__ = ('JOB_HANDLERS',)
