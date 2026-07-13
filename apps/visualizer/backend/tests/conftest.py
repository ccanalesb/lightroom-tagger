import os
import sys

import pytest

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Exclude tests/e2e — run with: pytest -c tests/e2e/pytest.ini tests/e2e/
collect_ignore = ["e2e"]


@pytest.fixture(autouse=True)
def _temp_library_db_for_catalog_jobs(tmp_path, monkeypatch):
    """Catalog-requiring job types need a resolvable library.db in tests."""
    db = tmp_path / 'library.db'
    db.touch()
    monkeypatch.setenv('LIBRARY_DB', str(db))
