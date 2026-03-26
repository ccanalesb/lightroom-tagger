"""Ensure project root is on sys.path for lightroom_tagger imports."""
import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
sys.path.insert(0, _PROJECT_ROOT)
