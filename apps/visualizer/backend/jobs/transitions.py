"""Pure job status transitions — no Flask/HTTP dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from database import (
    add_job_log,
    get_job,
    update_job_field,
    update_job_status,
)

CANCELLABLE_STATUSES = frozenset({'running', 'pending'})
TERMINAL_CANCEL_STATUSES = frozenset({'cancelled', 'completed', 'failed'})
RETRYABLE_STATUSES = frozenset({'failed', 'cancelled'})

_CANCEL_LOG_MESSAGE = 'Cancel requested via API'
_RETRY_LOG_MESSAGE = 'Job queued for retry'


@dataclass(frozen=True)
class Outcome:
    """Result of a job state transition."""

    edge: str  # cancelled | noop | invalid | retried
    job: dict | None
    reason: str | None = None
    should_signal_cancel: bool = False


def can_cancel(job: dict) -> bool:
    return job['status'] in CANCELLABLE_STATUSES


def can_retry(job: dict) -> bool:
    return job['status'] in RETRYABLE_STATUSES


# The DB helpers are accepted as keyword args (defaulting to the ``database``
# module functions) so the API route can forward its own module-level names.
# That keeps existing route tests working — they monkeypatch
# ``api.jobs.update_job_status`` to simulate a locked DB.
def transition_cancel(
    db,
    job_id: str,
    *,
    get_job_fn: Callable = get_job,
    update_status: Callable = update_job_status,
    add_log: Callable = add_job_log,
) -> Outcome:
    job = get_job_fn(db, job_id)
    if not job:
        return Outcome(edge='invalid', job=None, reason='Job not found')

    status = job['status']

    if status in CANCELLABLE_STATUSES:
        update_status(db, job_id, 'cancelled')
        add_log(db, job_id, 'info', _CANCEL_LOG_MESSAGE)
        updated = get_job_fn(db, job_id)
        return Outcome(
            edge='cancelled',
            job=updated,
            should_signal_cancel=(status == 'running'),
        )

    if status in TERMINAL_CANCEL_STATUSES:
        return Outcome(
            edge='noop',
            job=job,
            reason=f'Job is already {status}',
            should_signal_cancel=(status == 'cancelled'),
        )

    # Defensive fallback: unreachable for the known status set (cancellable +
    # terminal cover all statuses), kept to mirror the original route and guard
    # against an unexpected status ever reaching here.
    return Outcome(
        edge='invalid',
        job=job,
        reason=f"Cannot cancel job in status {status!r}",
    )


def transition_retry(
    db,
    job_id: str,
    *,
    get_job_fn: Callable = get_job,
    update_status: Callable = update_job_status,
    update_field: Callable = update_job_field,
    add_log: Callable = add_job_log,
) -> Outcome:
    job = get_job_fn(db, job_id)
    if not job:
        return Outcome(edge='invalid', job=None, reason='Job not found')

    if job['status'] not in RETRYABLE_STATUSES:
        return Outcome(
            edge='invalid',
            job=job,
            reason='Can only retry failed or cancelled jobs',
        )

    update_status(db, job_id, 'pending', progress=0, current_step=None)
    update_field(db, job_id, 'error', None)
    db.execute(
        'UPDATE jobs SET error_severity = NULL WHERE id = ?',
        (job_id,),
    )
    db.commit()
    update_field(db, job_id, 'result', None)
    add_log(db, job_id, 'info', _RETRY_LOG_MESSAGE)

    return Outcome(edge='retried', job=get_job_fn(db, job_id))
