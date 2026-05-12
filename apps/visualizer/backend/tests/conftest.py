import os
import sys

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Exclude tests/e2e — run with: pytest -c tests/e2e/pytest.ini tests/e2e/
collect_ignore = ["e2e"]
