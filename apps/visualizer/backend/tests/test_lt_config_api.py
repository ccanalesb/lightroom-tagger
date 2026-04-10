import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import api.lt_config as lt_config_mod
from app import create_app
from database import init_db


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        app = create_app()
        app.db = init_db(db_path)
        yield app.test_client()


def test_get_catalog_when_file_exists(monkeypatch, client, tmp_path):
    lrcat = tmp_path / "fake.lrcat"
    lrcat.touch()
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(f"catalog_path: {lrcat.resolve()}\n", encoding="utf-8")
    monkeypatch.setattr(lt_config_mod, "LT_CONFIG_YAML", str(yaml_path.resolve()))

    response = client.get("/api/config/catalog")
    assert response.status_code == 200
    data = response.get_json()
    assert data["exists"] is True
    assert data["catalog_path"] == str(lrcat.resolve())


def test_put_catalog_updates_yaml_and_get(monkeypatch, client, tmp_path):
    old = tmp_path / "old.lrcat"
    old.touch()
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(f"catalog_path: {old.resolve()}\n", encoding="utf-8")
    monkeypatch.setattr(lt_config_mod, "LT_CONFIG_YAML", str(yaml_path.resolve()))

    newcat = tmp_path / "newcat.lrcat"
    newcat.touch()

    put = client.put(
        "/api/config/catalog",
        json={"catalog_path": str(newcat.resolve())},
    )
    assert put.status_code == 200
    body = put.get_json()
    assert body["ok"] is True
    assert body["catalog_path"] == str(newcat.resolve())

    get = client.get("/api/config/catalog")
    assert get.status_code == 200
    assert get.get_json()["catalog_path"] == str(newcat.resolve())


def test_put_rejects_non_lrcat(monkeypatch, client, tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("catalog_path: /tmp/placeholder.lrcat\n", encoding="utf-8")
    monkeypatch.setattr(lt_config_mod, "LT_CONFIG_YAML", str(yaml_path.resolve()))

    bad = tmp_path / "not_a_catalog.txt"
    bad.touch()
    resp = client.put(
        "/api/config/catalog",
        json={"catalog_path": str(bad.resolve())},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_get_instagram_dump_keys_and_exists(monkeypatch, client, tmp_path):
    monkeypatch.delenv("INSTAGRAM_DUMP_PATH", raising=False)
    dump_dir = tmp_path / "ig_dump"
    dump_dir.mkdir()
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        f"instagram_dump_path: {dump_dir.resolve()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lt_config_mod, "LT_CONFIG_YAML", str(yaml_path.resolve()))

    response = client.get("/api/config/instagram-dump")
    assert response.status_code == 200
    data = response.get_json()
    assert set(data.keys()) == {"exists", "instagram_dump_path", "resolved_path"}
    assert data["exists"] is True
    assert data["instagram_dump_path"] == str(dump_dir.resolve())


def test_put_instagram_dump_rejects_non_directory(monkeypatch, client, tmp_path):
    monkeypatch.delenv("INSTAGRAM_DUMP_PATH", raising=False)
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("catalog_path: /tmp/placeholder.lrcat\n", encoding="utf-8")
    monkeypatch.setattr(lt_config_mod, "LT_CONFIG_YAML", str(yaml_path.resolve()))

    not_dir = tmp_path / "file_not_dir.txt"
    not_dir.write_text("x", encoding="utf-8")
    resp = client.put(
        "/api/config/instagram-dump",
        json={"instagram_dump_path": str(not_dir.resolve())},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_put_instagram_dump_persists(monkeypatch, client, tmp_path):
    monkeypatch.delenv("INSTAGRAM_DUMP_PATH", raising=False)
    dump_dir = tmp_path / "ig_dump"
    dump_dir.mkdir()
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("catalog_path: /tmp/placeholder.lrcat\n", encoding="utf-8")
    monkeypatch.setattr(lt_config_mod, "LT_CONFIG_YAML", str(yaml_path.resolve()))

    put = client.put(
        "/api/config/instagram-dump",
        json={"instagram_dump_path": str(dump_dir.resolve())},
    )
    assert put.status_code == 200
    body = put.get_json()
    assert body["ok"] is True
    assert body["instagram_dump_path"] == str(dump_dir.resolve())

    get = client.get("/api/config/instagram-dump")
    assert get.status_code == 200
    assert get.get_json()["instagram_dump_path"] == str(dump_dir.resolve())
