"""Tests for managed_library_db and managed_catalog lifecycle context managers."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.database import managed_catalog, managed_library_db


def test_managed_library_db_yields_live_connection(tmp_path):
    db_path = str(tmp_path / "library.db")
    with managed_library_db(db_path) as conn:
        assert isinstance(conn, sqlite3.Connection)
        row = conn.execute("SELECT 1 AS n").fetchone()
        assert row["n"] == 1


def test_managed_library_db_closes_after_block(tmp_path):
    db_path = str(tmp_path / "library.db")
    with managed_library_db(db_path) as conn:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_managed_library_db_closes_on_exception(tmp_path):
    db_path = str(tmp_path / "library.db")
    conn = None
    with pytest.raises(RuntimeError):
        with managed_library_db(db_path) as conn:
            raise RuntimeError("boom")
    assert conn is not None
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_managed_library_db_passes_path_through(tmp_path):
    db_path = str(tmp_path / "nested" / "custom.db")
    with patch(
        "lightroom_tagger.core.managed_connections.init_database",
    ) as mock_init:
        mock_init.return_value = MagicMock(spec=sqlite3.Connection)
        with managed_library_db(db_path):
            pass
        mock_init.assert_called_once_with(db_path)


@patch("lightroom_tagger.core.managed_connections.connect_catalog")
def test_managed_catalog_yields_live_connection(mock_connect_catalog):
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_connect_catalog.return_value = mock_conn

    with managed_catalog("/given/catalog.lrcat") as conn:
        assert conn is mock_conn

    mock_connect_catalog.assert_called_once_with("/given/catalog.lrcat")


@patch("lightroom_tagger.core.managed_connections.connect_catalog")
def test_managed_catalog_closes_after_block(mock_connect_catalog):
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_connect_catalog.return_value = mock_conn

    with managed_catalog("/given/catalog.lrcat"):
        pass

    mock_conn.close.assert_called_once()


@patch("lightroom_tagger.core.managed_connections.connect_catalog")
def test_managed_catalog_closes_on_exception(mock_connect_catalog):
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_connect_catalog.return_value = mock_conn

    with pytest.raises(RuntimeError):
        with managed_catalog("/given/catalog.lrcat"):
            raise RuntimeError("boom")

    mock_conn.close.assert_called_once()


@patch("lightroom_tagger.core.managed_connections.connect_catalog")
def test_managed_catalog_passes_path_through(mock_connect_catalog):
    mock_connect_catalog.return_value = MagicMock(spec=sqlite3.Connection)

    with managed_catalog("/exact/path/catalog.lrcat"):
        pass

    mock_connect_catalog.assert_called_once_with("/exact/path/catalog.lrcat")
