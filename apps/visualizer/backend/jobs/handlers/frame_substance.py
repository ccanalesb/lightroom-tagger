"""Frame substance batch job handler (#295)."""

from __future__ import annotations

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.frame_substance_batch import run_frame_substance_detection

from .common import _failure_severity_from_exception, _resolve_library_db_or_fail
from .db_lifecycle import make_managed_library_db

managed_library_db = make_managed_library_db(lambda p: init_database(p))


def handle_batch_frame_substance(runner, job_id: str, metadata: dict) -> None:
    """Scan local vision-cache previews and persist frame substance verdicts."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_frame_substance_inner(runner, job_id, metadata)


def _handle_batch_frame_substance_inner(runner, job_id: str, metadata: dict) -> None:
    db_path = _resolve_library_db_or_fail(runner, job_id)
    if db_path is None:
        return

    runner.update_progress(job_id, 5, "Scanning catalog for frame substance...")

    try:
        with managed_library_db(db_path) as lib_db:
            result = run_frame_substance_detection(
                lib_db,
                progress=lambda pct, msg: runner.update_progress(job_id, pct, msg),
            )
    except RuntimeError as exc:
        if str(exc) == "cancelled":
            runner.finalize_cancelled(job_id)
            return
        runner.fail_job(job_id, str(exc))
        return
    except Exception as exc:
        runner.fail_job(job_id, str(exc), severity=_failure_severity_from_exception(exc))
        return

    runner.complete_job(job_id, result)
