"""Shared perspective slug validation (avoid sibling imports between api blueprints)."""

import re

PERSPECTIVE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
