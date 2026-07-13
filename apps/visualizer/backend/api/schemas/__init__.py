"""Authoritative pydantic models for API response shapes (OpenAPI source of truth)."""

from api.schemas.jobs import (
    ErrorBody,
    Job,
    JobCreateRequest,
    JobLog,
    JobsHealth,
    JobsListResponse,
    JobsProcessorHealth,
    JobsRecoveredPayload,
    LibraryDbInfo,
    PaginationMeta,
    build_job_emit_payload,
    compact_job_payload,
    enrich_job_log_stats,
    validate_job_payload,
    validate_jobs_recovered_payload,
)

__all__ = [
    'ErrorBody',
    'Job',
    'JobCreateRequest',
    'JobLog',
    'JobsHealth',
    'JobsListResponse',
    'JobsProcessorHealth',
    'JobsRecoveredPayload',
    'LibraryDbInfo',
    'PaginationMeta',
    'build_job_emit_payload',
    'compact_job_payload',
    'enrich_job_log_stats',
    'validate_job_payload',
    'validate_jobs_recovered_payload',
]
