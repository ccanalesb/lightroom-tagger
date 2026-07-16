"""Jobs API and socket payload models — single source of truth for Job shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

JobStatus = Literal['pending', 'running', 'completed', 'failed', 'cancelled']
JobLogLevel = Literal['debug', 'info', 'warning', 'error']
ErrorSeverity = Literal['warning', 'error', 'critical']
LibraryDbSource = Literal['env', 'config', 'default', 'none']

_CHECKPOINT_LIST_KEYS = (
    'processed_pairs',
    'processed_media_keys',
    'processed_image_keys',
    'processed_triplets',
)


class JobLog(BaseModel):
    timestamp: str
    level: JobLogLevel
    message: str


class Job(BaseModel):
    """Shared by REST job endpoints and ``job_updated`` / ``job_created`` socket emits."""

    model_config = ConfigDict(extra='forbid')

    id: str
    type: str
    status: JobStatus
    progress: int
    current_step: str | None = None
    logs: list[JobLog] = Field(default_factory=list)
    logs_total: int = 0
    warning_count: int = 0
    error_count: int = 0
    last_log_at: str | None = None
    result: Any | None = None
    error: str | None = None
    error_severity: ErrorSeverity | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    cancel_noop: bool | None = None
    cancel_noop_reason: str | None = None


class JobCreateRequest(BaseModel):
    type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaginationMeta(BaseModel):
    offset: int
    limit: int
    current_page: int
    total_pages: int
    has_more: bool


class JobsListResponse(BaseModel):
    total: int
    data: list[Job]
    pagination: PaginationMeta


class JobListResponse(RootModel[list[Job]]):
    """``GET /api/jobs/active`` response body."""


class LibraryDbInfo(BaseModel):
    path: str | None
    source: LibraryDbSource
    exists: bool
    reason: str | None = None


class JobsHealth(BaseModel):
    library_db: LibraryDbInfo
    jobs_requiring_catalog: list[str]
    catalog_available: bool


class JobsProcessorHealth(BaseModel):
    running: bool
    started_at: float | None = None
    last_iteration_at: float | None = None
    last_iteration_age_seconds: float | None = None
    iterations_total: int = 0
    current_job_id: str | None = None
    current_job_started_at: float | None = None
    pending_count: int = 0
    running_count: int = 0
    stale: bool = False
    stale_threshold_seconds: float
    last_error: str | None = None


class JobsRecoveredPayload(BaseModel):
    job_ids: list[str]


class ErrorBody(BaseModel):
    error: str
    code: str | None = None


class CatalogUnavailableError(ErrorBody):
    code: Literal['catalog_unavailable']
    library_db: LibraryDbInfo


class DbBusyError(ErrorBody):
    code: Literal['db_busy']


def compact_checkpoint_lists(checkpoint: dict) -> dict:
    compact = dict(checkpoint)
    for key in _CHECKPOINT_LIST_KEYS:
        value = compact.get(key)
        if isinstance(value, list):
            compact[f'{key}_count'] = len(value)
            del compact[key]
    return compact


def compact_job_payload(job: dict) -> dict:
    """Replace bulky checkpoint lists with ``*_count`` tallies for wire payloads."""
    payload = dict(job)
    metadata = payload.get('metadata')
    if isinstance(metadata, dict):
        checkpoint = metadata.get('checkpoint')
        if isinstance(checkpoint, dict):
            payload['metadata'] = {
                **metadata,
                'checkpoint': compact_checkpoint_lists(checkpoint),
            }
    return payload


def enrich_job_log_stats(db, job: dict) -> dict:
    """Attach log summary fields from ``job_logs`` (same as list/active endpoints)."""
    from database import get_job_log_stats_bulk

    enriched = dict(job)
    stats = get_job_log_stats_bulk(db, [enriched['id']]).get(enriched['id'], {})
    enriched['logs_total'] = int(stats.get('logs_total', enriched.get('logs_total', 0) or 0))
    enriched['warning_count'] = int(stats.get('warning_count', enriched.get('warning_count', 0) or 0))
    enriched['error_count'] = int(stats.get('error_count', enriched.get('error_count', 0) or 0))
    enriched['last_log_at'] = stats.get('last_log_at', enriched.get('last_log_at'))
    return enriched


def validate_job_payload(job: dict) -> dict:
    """Validate a compacted job dict against :class:`Job`; raises on shape drift."""
    data = Job.model_validate(compact_job_payload(job)).model_dump(mode='json')
    if data.get('cancel_noop') is None:
        data.pop('cancel_noop', None)
        data.pop('cancel_noop_reason', None)
    return data


def build_job_emit_payload(db, job: dict, **extra) -> dict:
    """Prepare and validate a job dict for socket emit or JSON response."""
    payload = enrich_job_log_stats(db, job)
    payload.update(extra)
    return validate_job_payload(payload)


def validate_jobs_recovered_payload(payload: dict) -> dict:
    """Validate ``jobs_recovered`` socket payload."""
    return JobsRecoveredPayload.model_validate(payload).model_dump(mode='json')
