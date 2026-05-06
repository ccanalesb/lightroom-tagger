"""Images REST API — family blueprints registered from ``app.create_app`` (D-09)."""

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.provider_registry import ProviderRegistry

from .catalog import catalog_bp
from .instagram import instagram_bp
from .matches import matches_bp
from .search import search_bp
from .stacks import stacks_bp

__all__ = (
    "catalog_bp",
    "instagram_bp",
    "matches_bp",
    "nl_catalog_search",
    "ProviderRegistry",
    "search_bp",
    "stacks_bp",
)
