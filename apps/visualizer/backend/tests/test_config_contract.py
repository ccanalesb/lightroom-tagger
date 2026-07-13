"""Contract tests for Config pydantic models."""

from __future__ import annotations

import os

import pytest
from app import create_app

from api.schemas.config import (
    ConfigCatalogGetResponse,
    ConfigCatalogPutResponse,
    ConfigInstagramDumpGetResponse,
    ConfigStackDetectionGetResponse,
    ConfigStackDetectionPutResponse,
)


@pytest.fixture
def config_contract_client(tmp_path, monkeypatch):
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text("catalog_path: ''\ninstagram_dump_path: ''\nstack_burst_delta_ms: 500\n")
    monkeypatch.setattr("api.lt_config.LT_CONFIG_YAML", str(cfg_yaml))
    return create_app().test_client(), tmp_path


def test_config_catalog_get_round_trip(config_contract_client):
    client, _tmp = config_contract_client
    payload = client.get("/api/config/catalog").get_json()
    validated = ConfigCatalogGetResponse.model_validate(payload)
    assert isinstance(validated.exists, bool)


def test_config_instagram_dump_get_round_trip(config_contract_client):
    client, _tmp = config_contract_client
    payload = client.get("/api/config/instagram-dump").get_json()
    validated = ConfigInstagramDumpGetResponse.model_validate(payload)
    assert isinstance(validated.exists, bool)


def test_config_stack_detection_get_round_trip(config_contract_client):
    client, _tmp = config_contract_client
    payload = client.get("/api/config/stack-detection").get_json()
    validated = ConfigStackDetectionGetResponse.model_validate(payload)
    assert validated.stack_burst_delta_ms == 500


def test_config_stack_detection_put_round_trip(config_contract_client):
    client, _tmp = config_contract_client
    payload = client.put(
        "/api/config/stack-detection",
        json={"stack_burst_delta_ms": 750},
    ).get_json()
    validated = ConfigStackDetectionPutResponse.model_validate(payload)
    assert validated.ok is True
    assert validated.stack_burst_delta_ms == 750


def test_config_catalog_put_round_trip(config_contract_client):
    client, tmp = config_contract_client
    lrcat = tmp / "test.lrcat"
    lrcat.write_text("fake")
    payload = client.put(
        "/api/config/catalog",
        json={"catalog_path": str(lrcat)},
    ).get_json()
    validated = ConfigCatalogPutResponse.model_validate(payload)
    assert validated.ok is True
    assert os.path.basename(validated.catalog_path) == "test.lrcat"
