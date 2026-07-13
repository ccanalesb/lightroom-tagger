"""Providers API — list providers, models, manage fallback order."""

import sqlite3

from database import add_user_model, delete_user_model, get_user_models
from flask import Blueprint, current_app, jsonify, request
from spectree import Response

from api.openapi import spec
from api.schemas.jobs import ErrorBody
from api.schemas.providers import (
    DescriptionModelsResponse,
    FallbackOrderResponse,
    Provider,
    ProviderDefaults,
    ProviderDeletedResponse,
    ProviderHealthResponse,
    ProviderModel,
    ProviderListResponse,
    ProviderModelsListResponse,
    ProviderReorderSuccessResponse,
)
from lightroom_tagger.core.provider_registry import ProviderRegistry

bp = Blueprint("providers", __name__)


def _get_registry() -> ProviderRegistry:
    return ProviderRegistry()


@bp.route("/", methods=["GET"])
@spec.validate(
    resp=Response(HTTP_200=ProviderListResponse),
    tags=['providers'],
)
def list_providers():
    registry = _get_registry()
    return jsonify(registry.list_providers())


@bp.route("/fallback-order", methods=["GET", "PUT"])
@spec.validate(
    resp=Response(HTTP_200=FallbackOrderResponse, HTTP_400=ErrorBody),
    tags=['providers'],
)
def fallback_order():
    registry = _get_registry()
    if request.method == "GET":
        return jsonify({"order": registry.fallback_order})
    data = request.json
    if not data or "order" not in data:
        return jsonify({"error": "order is required"}), 400
    try:
        registry.update_fallback_order(data["order"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"order": registry.fallback_order})


@bp.route("/defaults", methods=["GET", "PUT"])
@spec.validate(
    resp=Response(HTTP_200=ProviderDefaults, HTTP_400=ErrorBody),
    tags=['providers'],
)
def defaults():
    registry = _get_registry()
    if request.method == "GET":
        return jsonify(registry.defaults)
    data = request.json
    if not data:
        return jsonify({"error": "body is required"}), 400
    try:
        registry.update_defaults(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(registry.defaults)


@bp.route("/models/description", methods=["GET"])
@spec.validate(
    resp=Response(HTTP_200=DescriptionModelsResponse),
    tags=['providers'],
)
def all_description_models():
    """Flat list of all models across all providers, for the NL/description task selector.

    Each model entry includes ``tool_calling`` from the provider's ``providers.json``
    config (function-calling / tools support).

    For providers with no statically configured models (e.g. oMLX), attempts a live
    /v1/models discovery with a short timeout so the selector still includes them when
    they are running.
    """
    registry = _get_registry()
    result = []
    for provider in registry.list_providers():
        pid = provider["id"]
        models_list = registry.list_models(pid)

        if not models_list:
            try:
                client = registry.get_client(pid)
                discovered = list(client.models.list(timeout=2.0))
                models_list = [
                    {"id": m.id, "name": m.id, "source": "discovered"}
                    for m in discovered
                ]
            except Exception:
                pass

        seen = set()
        for m in models_list:
            key = (pid, m["id"])
            if key in seen:
                continue
            seen.add(key)
            result.append({
                "provider_id": pid,
                "provider_name": provider["name"],
                "model_id": m["id"],
                "model_name": m.get("name", m["id"]),
                "tool_calling": bool(provider.get("tool_calling", False)),
            })

    defaults = registry.defaults.get("description", {}) or {}
    return jsonify({
        "models": result,
        "default_provider": defaults.get("provider"),
        "default_model": defaults.get("model"),
    })


@bp.route("/<provider_id>/health", methods=["GET"])
@spec.validate(
    resp=Response(HTTP_200=ProviderHealthResponse, HTTP_404=ErrorBody),
    tags=['providers'],
)
def provider_health(provider_id: str):
    registry = _get_registry()
    try:
        ok, detail = registry.probe_connection(provider_id)
    except KeyError:
        return jsonify({"error": "Unknown provider"}), 404
    if ok:
        return jsonify({"reachable": True})
    return jsonify({"reachable": False, "error": detail})


@bp.route("/<provider_id>/models/<path:model_id>", methods=["DELETE"])
@spec.validate(
    resp=Response(HTTP_200=ProviderDeletedResponse, HTTP_404=ErrorBody),
    tags=['providers'],
)
def delete_model(provider_id: str, model_id: str):
    deleted = delete_user_model(current_app.db, provider_id, model_id)
    if deleted:
        return jsonify({"deleted": True})
    registry = _get_registry()
    try:
        removed = registry.remove_model(provider_id, model_id)
    except KeyError:
        return jsonify({"error": f"Unknown provider: {provider_id}"}), 404
    if removed:
        return jsonify({"deleted": True})
    return jsonify({"error": "Model not found"}), 404


@bp.route("/<provider_id>/models/order", methods=["PUT"])
@spec.validate(
    resp=Response(HTTP_200=ProviderReorderSuccessResponse, HTTP_400=ErrorBody, HTTP_404=ErrorBody),
    tags=['providers'],
)
def reorder_models_endpoint(provider_id: str):
    """Reorder models for a provider."""
    registry = _get_registry()
    data = request.json
    if not data or "order" not in data:
        return jsonify({"error": "order is required"}), 400
    try:
        registry.reorder_models(provider_id, data["order"])
        return jsonify({"success": True})
    except KeyError:
        return jsonify({"error": f"Unknown provider: {provider_id}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/<provider_id>/models", methods=["GET", "POST"])
@spec.validate(
    resp=Response(
        HTTP_200=ProviderModelsListResponse,
        HTTP_201=ProviderModel,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
        HTTP_409=ErrorBody,
    ),
    tags=['providers'],
)
def models(provider_id: str):
    registry = _get_registry()
    if provider_id not in [provider["id"] for provider in registry.list_providers()]:
        return jsonify({"error": f"Unknown provider: {provider_id}"}), 404

    if request.method == "GET":
        models_list = registry.list_models(provider_id)
        existing_model_ids = {model_entry["id"] for model_entry in models_list}
        user_models = get_user_models(current_app.db, provider_id)
        for user_model in user_models:
            user_model_id = user_model["model_id"]
            if user_model_id in existing_model_ids:
                continue
            existing_model_ids.add(user_model_id)
            models_list.append({
                "id": user_model_id,
                "name": user_model["model_name"],
                "vision": bool(user_model["vision"]),
                "source": "user",
            })
        
        # Apply custom order if it exists
        provider_config = registry._providers.get(provider_id, {})
        model_order = provider_config.get("model_order", [])
        if model_order:
            models_by_id = {m["id"]: m for m in models_list}
            ordered = []
            for model_id in model_order:
                if model_id in models_by_id:
                    ordered.append(models_by_id[model_id])
            # Add any models not in the order (new discoveries)
            for model in models_list:
                if model["id"] not in model_order:
                    ordered.append(model)
            models_list = ordered
        
        return jsonify(models_list)

    data = request.json
    if not data:
        return jsonify({"error": "id and name are required"}), 400

    model_id = data.get("id")
    model_name = data.get("name")
    if not isinstance(model_id, str) or not model_id.strip():
        return jsonify({"error": "id must be a non-empty string"}), 400
    if not isinstance(model_name, str) or not model_name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400

    vision = data.get("vision", True)
    if "vision" in data and not isinstance(vision, bool):
        return jsonify({"error": "vision must be a boolean"}), 400

    try:
        add_user_model(
            current_app.db,
            provider_id,
            model_id,
            model_name,
            vision,
        )
    except sqlite3.IntegrityError:
        return jsonify(
            {"error": f"Model {model_id} already exists for {provider_id}"}
        ), 409
    return (
        jsonify({
            "id": model_id,
            "name": model_name,
            "vision": vision,
            "source": "user",
        }),
        201,
    )
