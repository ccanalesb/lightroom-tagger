"""Images REST API — umbrella blueprint composes family blueprints."""

from flask import Blueprint

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.provider_registry import ProviderRegistry

bp = Blueprint("images", __name__)

from ._legacy import legacy_bp
from .catalog import catalog_bp
from .instagram import instagram_bp
from .matches import matches_bp
from .stacks import stacks_bp

bp.register_blueprint(legacy_bp)
bp.register_blueprint(instagram_bp)
bp.register_blueprint(matches_bp)
bp.register_blueprint(stacks_bp)
bp.register_blueprint(catalog_bp)

__all__ = (
    "bp",
    "catalog_bp",
    "instagram_bp",
    "matches_bp",
    "nl_catalog_search",
    "ProviderRegistry",
    "stacks_bp",
)
