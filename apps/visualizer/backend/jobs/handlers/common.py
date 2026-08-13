"""Cross-family helpers and constants shared by job handlers."""

from library_db import require_library_db

from lightroom_tagger.core.exceptions import AuthenticationError, InvalidRequestError

_CHECKPOINT_MAX_ENTRIES = 100_000

# SQL fragments to exclude video files from describe queries at the DB level so
# the processor never wastes a worker slot attempting to describe a .mov/.mp4/etc.
_CATALOG_NOT_VIDEO_SQL = (
    "LOWER(i.filepath) NOT LIKE '%.mov' AND "
    "LOWER(i.filepath) NOT LIKE '%.mp4' AND "
    "LOWER(i.filepath) NOT LIKE '%.avi' AND "
    "LOWER(i.filepath) NOT LIKE '%.mkv' AND "
    "LOWER(i.filepath) NOT LIKE '%.wmv' AND "
    "LOWER(i.filepath) NOT LIKE '%.m4v' AND "
    "LOWER(i.filepath) NOT LIKE '%.3gp' AND "
    "LOWER(i.filepath) NOT LIKE '%.webm' AND "
    "LOWER(i.filepath) NOT LIKE '%.mts' AND "
    "LOWER(i.filepath) NOT LIKE '%.m2ts'"
)

# Legacy date_filter labels (kept for backward compatibility with older clients
# and checkpoints). Prefer sending ``last_months`` as an int or ``year`` as a
# four-digit string instead.
_LEGACY_DATE_FILTER_MONTHS = {'3months': 3, '6months': 6, '12months': 12}


def _resolve_library_db_or_fail(runner, job_id: str) -> str | None:
    """Return the library DB path, or call ``runner.fail_job`` and return None.

    Centralizes the resolution + failure behaviour so every handler that needs
    the catalog gets a single, accurate error message when the DB is missing.
    """
    try:
        return require_library_db()
    except FileNotFoundError as e:
        runner.fail_job(job_id, str(e), severity='warning')
        return None


def _failure_severity_from_exception(exc: BaseException) -> str:
    if isinstance(exc, (AuthenticationError, InvalidRequestError)):
        return 'warning'
    if isinstance(exc, (PermissionError, OSError)):
        return 'critical'
    if isinstance(exc, RuntimeError) and str(exc) == 'Close Lightroom before writing to catalog.':
        return 'critical'
    return 'error'


def _resolve_date_window(metadata: dict) -> tuple[int | None, str | None]:
    """Normalize date-range metadata into ``(months, year)``.

    The batch describe/score/analyze handlers used to only recognize the string
    tokens ``'3months' | '6months' | '12months'`` via a hardcoded map. New
    clients send the window directly as either ``last_months: int`` or
    ``year: 'YYYY'``.

    Behaviour:
      * ``last_months`` wins when it is a positive integer.
      * ``year`` is normalized to a four-digit string (rejecting anything else).
      * ``date_filter`` is consulted last for backward compatibility with
        existing dropdowns; unknown values fall through as ``(None, None)``
        (i.e. ``'all'``).

    Returning a tuple keeps the call sites obvious: callers thread ``months``
    into existing ``date_taken >= date('now', -N months)`` clauses and ``year``
    into new ``strftime('%Y', ...) = ?`` clauses.
    """
    months: int | None = None
    year: str | None = None

    raw_last_months = metadata.get('last_months')
    if isinstance(raw_last_months, bool):
        pass  # guard against ``True`` being treated as ``1``
    elif isinstance(raw_last_months, int) and raw_last_months > 0:
        months = raw_last_months
    elif isinstance(raw_last_months, str) and raw_last_months.strip().isdigit():
        n = int(raw_last_months.strip())
        if n > 0:
            months = n

    # ``last_months`` has precedence: if both are present, the numeric
    # window wins. Otherwise ANDing two date conditions produces an
    # accidentally narrow result set (the intersection of the last N months
    # AND a specific year).
    if months is None:
        raw_year = metadata.get('year')
        if isinstance(raw_year, int) and 1900 <= raw_year <= 9999:
            year = str(raw_year)
        elif (
            isinstance(raw_year, str)
            and raw_year.strip().isdigit()
            and len(raw_year.strip()) == 4
        ):
            year = raw_year.strip()

    if months is None and year is None:
        date_filter = metadata.get('date_filter', 'all')
        months = _LEGACY_DATE_FILTER_MONTHS.get(date_filter)

    return months, year


def _select_catalog_keys(
    lib_db,
    *,
    months: int | None,
    year: str | None,
    min_rating: int | None,
    undescribed_only: bool,
) -> list[tuple[str, str]]:
    """Select ``(key, 'catalog')`` tuples matching the given window.

    Consolidates the four near-identical SQL blocks that previously lived in
    ``handle_batch_describe`` / ``handle_batch_score`` / ``handle_batch_analyze``
    so the ``year`` window only has to be added in one place.

    ``undescribed_only=True`` joins against ``image_descriptions`` to skip rows
    that already have a description — matching the semantics of
    ``get_undescribed_catalog_images``. ``undescribed_only=False`` returns every
    key in the window (equivalent to the old ``force`` arm).
    """
    params: list = []
    if undescribed_only:
        sql = (
            "SELECT i.key AS key FROM images i "
            "LEFT JOIN image_descriptions d "
            "  ON i.key = d.image_key AND d.image_type = 'catalog' "
            "WHERE d.image_key IS NULL"
        )
        date_col = "i.date_taken"
        rating_col = "i.rating"
        conditions: list[str] = [_CATALOG_NOT_VIDEO_SQL]
    else:
        sql = (
            "SELECT i.key AS key FROM images i "
            "WHERE " + _CATALOG_NOT_VIDEO_SQL
        )
        date_col = "i.date_taken"
        rating_col = "i.rating"
        conditions = []

    if months:
        conditions.append(f"{date_col} >= date('now', ?)")
        params.append(f'-{months} months')
    if year is not None:
        conditions.append(f"strftime('%Y', {date_col}) = ?")
        params.append(year)
    if min_rating is not None:
        conditions.append(f"{rating_col} >= ?")
        params.append(min_rating)

    if undescribed_only:
        if conditions:
            sql += " AND " + " AND ".join(conditions)
    else:
        if conditions:
            sql += " AND " + " AND ".join(conditions)

    sql += " ORDER BY (i.date_taken IS NULL) DESC, i.date_taken DESC, i.key DESC"

    rows = lib_db.execute(sql, tuple(params)).fetchall()
    return [(r['key'], 'catalog') for r in rows]
