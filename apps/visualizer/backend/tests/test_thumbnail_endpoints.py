"""Regression: binary thumbnail routes must not use spectree response validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from app import create_app

from lightroom_tagger.core.config import Config
from lightroom_tagger.core.database import init_database, store_image, store_instagram_dump_media

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_API_ROOT = _BACKEND_ROOT / "api"


def _minimal_jpeg_bytes() -> bytes:
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xd9"
    )


@pytest.fixture
def catalog_thumbnail_client(tmp_path, monkeypatch):
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    image_path = photos_dir / "thumb.jpg"
    image_path.write_bytes(_minimal_jpeg_bytes())

    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "thumb.jpg",
            "filepath": str(image_path),
            "rating": 3,
            "id": "101",
        },
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    cfg = Config(mount_point=str(photos_dir), vision_cache_enabled=False)
    monkeypatch.setattr("lightroom_tagger.core.config.load_config", lambda _path="config.yaml": cfg)
    return create_app().test_client(), "2024-01-10_thumb.jpg"


@pytest.fixture
def instagram_thumbnail_client(tmp_path, monkeypatch):
    dump_root = tmp_path / "instagram_dump"
    media_dir = dump_root / "media" / "posts" / "202405"
    media_dir.mkdir(parents=True)
    image_path = media_dir / "aaa.jpg"
    image_path.write_bytes(_minimal_jpeg_bytes())

    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_instagram_dump_media(
        conn,
        {
            "media_key": "202405/aaa",
            "file_path": str(image_path),
            "filename": "aaa.jpg",
            "date_folder": "202405",
            "caption": "cap-a",
            "created_at": "2024-05-01T10:00:00",
            "added_at": "2024-05-02T11:00:00",
            "post_url": "https://example/p/a",
            "image_hash": "hash-a",
            "processed": False,
        },
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    cfg = Config(instagram_dump_path=str(dump_root))
    monkeypatch.setattr("lightroom_tagger.core.config.load_config", lambda _path="config.yaml": cfg)
    return create_app().test_client(), "202405/aaa"


def test_catalog_thumbnail_returns_jpeg(catalog_thumbnail_client):
    client, image_key = catalog_thumbnail_client
    response = client.get(f"/api/images/catalog/{image_key}/thumbnail")
    assert response.status_code == 200
    assert response.content_type.startswith("image/jpeg")
    assert response.data == _minimal_jpeg_bytes()


def test_catalog_thumbnail_missing_key_returns_404(catalog_thumbnail_client):
    client, _image_key = catalog_thumbnail_client
    response = client.get("/api/images/catalog/no-such-key/thumbnail")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload is not None
    assert "error" in payload


def test_instagram_thumbnail_returns_jpeg(instagram_thumbnail_client):
    client, image_key = instagram_thumbnail_client
    response = client.get(f"/api/images/instagram/{image_key}/thumbnail")
    assert response.status_code == 200
    assert response.content_type.startswith("image/jpeg")
    assert response.data == _minimal_jpeg_bytes()


def test_instagram_thumbnail_missing_key_returns_404(instagram_thumbnail_client):
    client, _image_key = instagram_thumbnail_client
    response = client.get("/api/images/instagram/missing/key/thumbnail")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload is not None
    assert "error" in payload


def _is_spec_validate_decorator(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "validate"
        and isinstance(func.value, ast.Name)
        and func.value.id == "spec"
    )


def _function_uses_send_file(node: ast.FunctionDef) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name) and func.id == "send_file":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "send_file":
            return True
    return False


def _send_file_routes_wrapped_by_spec_validate() -> list[str]:
    violations: list[str] = []
    for py_file in sorted(_API_ROOT.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if not _function_uses_send_file(node):
                continue
            if any(_is_spec_validate_decorator(d) for d in node.decorator_list):
                rel = py_file.relative_to(_BACKEND_ROOT)
                violations.append(f"{rel}:{node.lineno}:{node.name}")
    return violations


def test_guardrail_no_send_file_route_uses_spec_validate() -> None:
    violations = _send_file_routes_wrapped_by_spec_validate()
    assert violations == [], (
        "send_file/binary routes must not use @spec.validate (reads direct_passthrough body): "
        f"{violations}"
    )


def test_guardrail_detects_send_file_with_spec_validate() -> None:
    sample = """
from spectree import Response
from flask import send_file
from api.openapi import spec
from api.schemas.jobs import ErrorBody

@spec.validate(resp=Response(HTTP_404=ErrorBody), tags=["t"])
def bad_thumbnail():
    return send_file("x.jpg", mimetype="image/jpeg")
"""
    tree = ast.parse(sample)
    fn = tree.body[-1]
    assert isinstance(fn, ast.FunctionDef)
    assert _function_uses_send_file(fn)
    assert any(_is_spec_validate_decorator(d) for d in fn.decorator_list)
