#!/usr/bin/env python3
"""Dump the Jobs OpenAPI spec to stdout (used by frontend codegen)."""

from __future__ import annotations

import json
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Avoid starting the job processor during spec export.
os.environ.setdefault('FLASK_DEBUG', 'true')

from app import create_app  # noqa: E402
from api.openapi import spec  # noqa: E402


def main() -> None:
    app = create_app()
    with app.app_context():
        json.dump(spec.spec, sys.stdout, indent=2)
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
