import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type Job = components['schemas']['Job']
export type JobLog = components['schemas']['JobLog']
export type JobStatus = Job['status']
export type JobsListResponse = components['schemas']['JobsListResponse']
export type JobsHealth = components['schemas']['JobsHealth']

/** Client query param for ``GET /api/jobs/:id`` (not part of response schema). */
export type JobsGetOptions = {
  logs_limit?: number
}
