"""Tests for POST /api/images/nl-search (LLM filter mocked)."""

import pytest
from app import create_app

from lightroom_tagger.core.database import init_database, store_image


@pytest.fixture
def nl_search_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "low.jpg",
            "rating": 3,
            "id": "100",
            "instagram_posted": True,
        },
    )
    store_image(
        conn,
        {
            "date_taken": "2024-06-15",
            "filename": "high.jpg",
            "rating": 5,
            "id": "200",
        },
    )
    conn.close()

    monkeypatch.setattr("utils.db.LIBRARY_DB", db_path)
    app = create_app()
    return app.test_client()


def test_nl_search_empty_query_400(nl_search_client):
    for body in ({"query": ""}, {"query": "   "}):
        r = nl_search_client.post("/api/images/nl-search", json=body)
        assert r.status_code == 400
        assert r.get_json() == {"error": "query must be non-empty"}


def test_nl_search_mock_llm_success(nl_search_client, monkeypatch):
    monkeypatch.setattr(
        "lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm",
        lambda *a, **k: '{"posted": false}',
    )
    r = nl_search_client.post("/api/images/nl-search", json={"query": "unposted only"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["filters"]["posted"] is False
    assert "total" in data
    assert "images" in data
    assert isinstance(data["images"], list)


def test_nl_search_not_json_400_includes_nl_filter(nl_search_client, monkeypatch):
    monkeypatch.setattr(
        "lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm",
        lambda *a, **k: "not-json",
    )
    r = nl_search_client.post("/api/images/nl-search", json={"query": "x"})
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert "NL filter" in err


def test_nl_search_extra_key_from_llm_400(nl_search_client, monkeypatch):
    monkeypatch.setattr(
        "lightroom_tagger.core.nl_catalog_search.run_nl_catalog_filter_llm",
        lambda *a, **k: '{"posted": true, "bogus": 1}',
    )
    r = nl_search_client.post("/api/images/nl-search", json={"query": "posted"})
    assert r.status_code == 400
    data = r.get_json()
    assert "error" in data
    assert "NL filter" in data["error"]
