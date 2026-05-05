"""Job handler package — job-family modules with _legacy.py as interim monolith."""
from pathlib import Path

from .. import path_setup as _path_setup  # noqa: F401 — side-effect import; keep once here only

_legacy_path = Path(__file__).resolve().parent / '_legacy.py'
_namespace = globals()
exec(
    compile(_legacy_path.read_text(encoding='utf-8'), str(_legacy_path), 'exec'),
    _namespace,
)

__all__ = ('JOB_HANDLERS',)
