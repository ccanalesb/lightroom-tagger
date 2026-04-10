import os
from pathlib import Path

from flask import Blueprint, jsonify, request
from lightroom_tagger.core.config import (
    load_config,
    update_config_yaml_catalog_path,
    update_config_yaml_instagram_dump_path,
)
from utils.responses import error_bad_request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
assert os.path.isfile(os.path.join(REPO_ROOT, "pyproject.toml")), "lt_config REPO_ROOT must be repository root"

LT_CONFIG_YAML = os.path.join(REPO_ROOT, "config.yaml")

bp = Blueprint("lt_config", __name__)


@bp.route('/catalog', methods=['GET'])
def get_catalog():
    cfg = load_config(LT_CONFIG_YAML)
    raw = cfg.catalog_path or ""
    resolved = str(Path(raw).expanduser()) if raw else ""
    exists = bool(resolved and os.path.isfile(resolved))
    return jsonify(
        {
            "catalog_path": raw,
            "resolved_path": resolved,
            "exists": exists,
        }
    )


@bp.route('/catalog', methods=['PUT'])
def put_catalog():
    data = request.get_json(silent=True)
    if data is None or "catalog_path" not in data:
        return error_bad_request("catalog_path is required")
    value = data["catalog_path"]
    if not isinstance(value, str):
        return error_bad_request("catalog_path must be a string")
    if not value.lower().endswith(".lrcat"):
        return error_bad_request("catalog_path must be a .lrcat file")
    expanded = str(Path(value).expanduser())
    if not os.path.isfile(expanded):
        return error_bad_request("catalog_path must be an existing file")
    update_config_yaml_catalog_path(LT_CONFIG_YAML, value)
    return jsonify({"catalog_path": value.strip(), "ok": True})


@bp.route('/instagram-dump', methods=['GET'])
def get_instagram_dump():
    cfg = load_config(LT_CONFIG_YAML)
    raw = cfg.instagram_dump_path or ""
    resolved = str(Path(raw).expanduser()) if raw else ""
    exists = bool(resolved and os.path.isdir(resolved))
    return jsonify(
        {
            "instagram_dump_path": raw,
            "resolved_path": resolved,
            "exists": exists,
        }
    )


@bp.route('/instagram-dump', methods=['PUT'])
def put_instagram_dump():
    data = request.get_json(silent=True)
    if data is None or "instagram_dump_path" not in data:
        return error_bad_request("instagram_dump_path is required")
    value = data["instagram_dump_path"]
    if not isinstance(value, str):
        return error_bad_request("instagram_dump_path must be a string")
    expanded = str(Path(value).expanduser())
    if not os.path.isdir(expanded):
        return error_bad_request("instagram_dump_path must be an existing directory")
    update_config_yaml_instagram_dump_path(LT_CONFIG_YAML, value)
    return jsonify({"instagram_dump_path": value.strip(), "ok": True})
