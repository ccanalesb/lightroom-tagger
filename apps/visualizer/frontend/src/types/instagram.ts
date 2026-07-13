import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
type InstagramImageSchema =
  components['schemas']['InstagramListResponse.2d55088.InstagramImage']

export type InstagramImage = InstagramImageSchema

/** List-row input for adapters (embedded match rows stay partial until V4). */
export type InstagramImageInput = Pick<InstagramImageSchema, 'key'> &
  Partial<Omit<InstagramImageSchema, 'key'>>

export type InstagramListResponse = components['schemas']['InstagramListResponse.2d55088']
export type InstagramMonthsResponse = components['schemas']['InstagramMonthsResponse.2d55088']
