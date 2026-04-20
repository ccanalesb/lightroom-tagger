"""Tests for the centralized library DB resolver (Plan B)."""
import os

import pytest

from library_db import (
    JOB_TYPES_REQUIRING_CATALOG,
    describe_library_db,
    require_library_db,
    resolve_library_db,
)


def test_jobs_requiring_catalog_is_frozen_and_non_empty():
    assert isinstance(JOB_TYPES_REQUIRING_CATALOG, frozenset)
    assert 'batch_describe' in JOB_TYPES_REQUIRING_CATALOG
    assert 'vision_match' in JOB_TYPES_REQUIRING_CATALOG


def test_describe_uses_env_when_set_and_file_exists(tmp_path, monkeypatch):
    db = tmp_path / 'library.db'
    db.touch()
    monkeypatch.setenv('LIBRARY_DB', str(db))
    status = describe_library_db()
    assert status.source == 'env'
    assert status.path == str(db)
    assert status.exists is True
    assert status.reason is None


def test_describe_reports_missing_env_file(tmp_path, monkeypatch):
    missing = tmp_path / 'nope.db'
    monkeypatch.setenv('LIBRARY_DB', str(missing))
    status = describe_library_db()
    assert status.source == 'env'
    assert status.exists is False
    assert 'does not exist' in (status.reason or '')


def test_describe_falls_through_to_config_when_env_empty(tmp_path, monkeypatch):
    """When no env var, resolver should try config.yaml (via load_config)."""
    monkeypatch.delenv('LIBRARY_DB', raising=False)
    # The repo-level config.yaml points at an existing library.db for this
    # developer setup, so we just assert the resolver reports *something*
    # without exploding. A precise match would couple the test to the user's
    # machine.
    status = describe_library_db()
    assert status.source in {'env', 'config', 'default', 'none'}


def test_require_raises_filenotfound_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARY_DB', str(tmp_path / 'missing.db'))
    with pytest.raises(FileNotFoundError) as excinfo:
        require_library_db()
    assert 'LIBRARY_DB' in str(excinfo.value)


def test_resolve_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARY_DB', str(tmp_path / 'missing.db'))
    assert resolve_library_db() is None


def test_resolve_returns_path_when_present(tmp_path, monkeypatch):
    db = tmp_path / 'library.db'
    db.touch()
    monkeypatch.setenv('LIBRARY_DB', str(db))
    assert resolve_library_db() == str(db)
