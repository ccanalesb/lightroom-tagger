"""Images REST API — umbrella blueprint composes family blueprints."""

from flask import Blueprint

from lightroom_tagger.core import nl_catalog_search
from lightroom_tagger.core.provider_registry import ProviderRegistry

bp = Blueprint("images", __name__)

from ._legacy import legacy_bp
from .catalog import catalog_bp

# Register legacy (static paths like /instagram/months) before catalog catch-all
# ``/<image_type>/<image_key>``.
bp.register_blueprint(legacy_bp)
bp.register_blueprint(catalog_bp)

__all__ = ("bp", "catalog_bp", "nl_catalog_search", "ProviderRegistry")
