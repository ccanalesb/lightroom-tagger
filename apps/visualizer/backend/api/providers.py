"""Providers API — list providers, models, manage fallback order."""

from flask import Blueprint, jsonify

from lightroom_tagger.core.provider_registry import ProviderRegistry

bp = Blueprint("providers", __name__)


def _get_registry() -> ProviderRegistry:
    return ProviderRegistry()


@bp.route("/", methods=["GET"])
def list_providers():
    registry = _get_registry()
    return jsonify(registry.list_providers())


@bp.route("/<provider_id>/models", methods=["GET"])
def list_models(provider_id: str):
    registry = _get_registry()
    try:
        models = registry.list_models(provider_id)
    except KeyError:
        return jsonify({"error": f"Unknown provider: {provider_id}"}), 404
    return jsonify(models)


@bp.route("/fallback-order", methods=["GET"])
def get_fallback_order():
    registry = _get_registry()
    return jsonify({"order": registry.fallback_order})


@bp.route("/defaults", methods=["GET"])
def get_defaults():
    registry = _get_registry()
    return jsonify(registry.defaults)
