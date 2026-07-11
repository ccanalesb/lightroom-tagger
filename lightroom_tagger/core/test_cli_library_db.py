"""Tests for CLI library-DB path resolution and connection adapter."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightroom_tagger.core.cli_library_db import (
    CliError,
    resolve_library_db_path,
    with_library_db,
)
from lightroom_tagger.core.config import Config


_MISSING_DB_PATH_MSG = "No database path provided. Use --db or config.yaml"


def _args(db: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(db=db)


def _config(db_path: str = "") -> Config:
    return Config(db_path=db_path)


@pytest.mark.parametrize(
    ("args_db", "config_db", "must_exist", "expected_suffix"),
    [
        ("args.db", "config.db", True, "args.db"),
        ("args.db", "config.db", False, "args.db"),
        (None, "config.db", True, "config.db"),
        (None, "config.db", False, "config.db"),
        ("", "config.db", False, "config.db"),
    ],
)
def test_resolve_library_db_path_prefers_args_then_config(
    args_db,
    config_db,
    must_exist,
    expected_suffix,
    tmp_path,
):
    root = tmp_path / "from"
    root.mkdir()
    if args_db:
        args_db = str(root / args_db)
    config_db = str(root / config_db)
    expected_path = str(root / expected_suffix)

    if must_exist:
        Path(expected_path).write_text("")

    path = resolve_library_db_path(
        _args(args_db),
        _config(config_db),
        must_exist=must_exist,
    )
    assert path == expected_path


@pytest.mark.parametrize("must_exist", [True, False])
def test_resolve_library_db_path_missing_path_raises_cli_error(must_exist):
    with pytest.raises(CliError, match=_MISSING_DB_PATH_MSG):
        resolve_library_db_path(_args(None), _config(""), must_exist=must_exist)


def test_resolve_library_db_path_default_must_exist_is_false(tmp_path):
    db_path = str(tmp_path / "new.db")
    assert (
        resolve_library_db_path(_args(db_path), _config(""))
        == db_path
    )


def test_resolve_library_db_path_must_exist_raises_when_absent(tmp_path):
    missing = str(tmp_path / "missing.db")
    with pytest.raises(CliError, match=f"Database not found: {missing}"):
        resolve_library_db_path(_args(missing), _config(""), must_exist=True)


def test_with_library_db_maps_cli_error(capsys, tmp_path):
    db_path = str(tmp_path / "library.db")
    (tmp_path / "library.db").write_text("")

    @with_library_db(must_exist=True)
    def handler(args, config, db):
        raise CliError("bad things")

    exit_code = handler(_args(db_path), _config(""))

    assert exit_code == 1
    assert capsys.readouterr().out.endswith("Error: bad things\n")


def test_with_library_db_maps_body_exception_and_closes_connection(tmp_path, capsys):
    db_path = str(tmp_path / "library.db")
    (tmp_path / "library.db").write_text("")
    captured_conn = None

    @with_library_db(must_exist=True)
    def handler(args, config, db):
        nonlocal captured_conn
        captured_conn = db
        raise RuntimeError("boom")

    exit_code = handler(_args(db_path), _config(""))

    assert exit_code == 1
    assert "Error: boom" in capsys.readouterr().out
    with pytest.raises(sqlite3.ProgrammingError):
        captured_conn.execute("SELECT 1")


@patch("lightroom_tagger.core.cli_library_db.managed_library_db")
def test_with_library_db_require_path_false_skips_missing_guard(mock_managed):
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_managed.return_value.__enter__.return_value = mock_conn
    mock_managed.return_value.__exit__.return_value = False

    @with_library_db(require_path=False)
    def handler(args, config, db):
        assert db is mock_conn
        return 0

    assert handler(_args(None), _config("")) == 0
    mock_managed.assert_called_once_with("")
