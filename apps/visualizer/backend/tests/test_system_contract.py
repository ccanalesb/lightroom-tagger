"""Contract tests for System pydantic models."""

from __future__ import annotations

import pytest
from app import create_app

from api.schemas.system import (
    CachePipelineStatus,
    CacheStatus,
    CatalogCacheReadyResponse,
    Stats,
    SystemStatusResponse,
    VisionModelsResponse,
)
from lightroom_tagger.core.database import (
    init_database,
    store_image,
    store_instagram_dump_media,
    store_match,
    update_instagram_status,
)


def _client_for_library(tmp_path, monkeypatch):
    import config
    import utils.db as db_utils

    db_path = tmp_path / "library.db"
    lib = init_database(str(db_path))
    k1 = store_image(lib, {"date_taken": "2024-01-01", "filename": "a.jpg"})
    store_image(lib, {"date_taken": "2024-02-01", "filename": "b.jpg"})
    update_instagram_status(lib, k1, posted=True)
    store_instagram_dump_media(
        lib,
        {
            "media_key": "202401/111",
            "file_path": "/tmp/111.jpg",
            "date_folder": "202401",
        },
    )
    store_match(
        lib,
        {"catalog_key": k1, "insta_key": "202401/111", "total_score": 0.8},
    )
    lib.close()

    monkeypatch.setattr(config, "LIBRARY_DB", str(db_path))
    monkeypatch.setattr(db_utils, "LIBRARY_DB", str(db_path))

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client(), str(db_path)


@pytest.fixture
def system_contract_client(tmp_path, monkeypatch):
    client, _db_path = _client_for_library(tmp_path, monkeypatch)
    return client


def test_status_round_trip(system_contract_client):
    payload = system_contract_client.get("/api/status").get_json()
    validated = SystemStatusResponse.model_validate(payload)
    assert validated.status == "ok"


def test_stats_round_trip(system_contract_client, tmp_path, monkeypatch):
    client, db_path = _client_for_library(tmp_path, monkeypatch)
    payload = client.get("/api/stats").get_json()
    validated = Stats.model_validate(payload)
    assert validated.catalog_images == 2
    assert validated.db_path == db_path


def test_vision_models_round_trip(system_contract_client):
    payload = system_contract_client.get("/api/vision-models").get_json()
    validated = VisionModelsResponse.model_validate(payload)
    assert len(validated.models) >= 1


def test_catalog_cache_status_round_trip(system_contract_client):
    payload = system_contract_client.get("/api/catalog/status").get_json()
    validated = CatalogCacheReadyResponse.model_validate(payload)
    assert isinstance(validated.cached, bool)


def test_cache_status_round_trip(system_contract_client):
    payload = system_contract_client.get("/api/cache/status").get_json()
    validated = CacheStatus.model_validate(payload)
    assert validated.total_images >= 0


def test_cache_pipeline_status_round_trip(system_contract_client):
    payload = system_contract_client.get("/api/cache/pipeline-status").get_json()
    validated = CachePipelineStatus.model_validate(payload)
    assert validated.catalog_sync is None or validated.catalog_sync.job_id


def test_stats_rejects_wrong_shape():
    with pytest.raises(Exception):
        Stats.model_validate({"catalog_images": "x"})
