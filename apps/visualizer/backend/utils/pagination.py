"""Pagination helpers shared by API routes (avoid cross-imports between sibling ``api`` modules)."""


def _clamp_pagination(limit, offset, default_limit=50):
    if limit is None:
        limit = default_limit
    else:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = default_limit
    limit = max(1, min(500, limit))
    if offset is None:
        offset = 0
    else:
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
    offset = max(0, offset)
    return limit, offset
