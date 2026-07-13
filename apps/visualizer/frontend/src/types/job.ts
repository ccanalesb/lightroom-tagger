import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type Job = components['schemas']['Job.45d9b59']
export type JobLog = components['schemas']['Job.45d9b59.JobLog']
export type JobStatus = Job['status']
export type JobsListResponse = components['schemas']['JobsListResponse.45d9b59']
export type JobsHealth = components['schemas']['JobsHealth.45d9b59']

/** Client query param for ``GET /api/jobs/:id`` (not part of response schema). */
export type JobsGetOptions = {
  logs_limit?: number
}
