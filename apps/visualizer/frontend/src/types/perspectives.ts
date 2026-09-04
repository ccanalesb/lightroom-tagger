import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type PerspectiveSummary =
  components['schemas']['PerspectiveSummary']
export type PerspectiveDetail = components['schemas']['PerspectiveDetail']

/** Matches backend ``PerspectiveScore`` pydantic model (nested in descriptions, not a REST route). */
export type PerspectiveScore = {
  analysis: string
  score: number
}
