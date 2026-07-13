import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type CatalogImage =
  components['schemas']['CatalogListResponse.573ec44.CatalogImage']

/** List-row / embedded input for adapters (full list rows satisfy this). */
export type CatalogImageInput = Pick<CatalogImage, 'key'> & Partial<Omit<CatalogImage, 'key'>>
export type CatalogListResponse = components['schemas']['CatalogListResponse.573ec44']
export type CatalogMonthsResponse = components['schemas']['CatalogMonthsResponse.573ec44']
export type CatalogSimilarityGroup =
  components['schemas']['CatalogSimilarityGroupsResponse.573ec44.CatalogSimilarityGroup']
export type CatalogSimilarityGroupsResponse =
  components['schemas']['CatalogSimilarityGroupsResponse.573ec44']

type ImageViewSchema = components['schemas']['ImageView.573ec44']

/** Detail modal superset — required identity plus optional fields filled per source. */
export type ImageView = Pick<ImageViewSchema, 'image_type' | 'key'> &
  Partial<Omit<ImageViewSchema, 'image_type' | 'key'>>

export type ImageDetailResponse = ImageViewSchema
export type IdentityPerPerspectiveScore =
  components['schemas']['ImageView.573ec44.IdentityPerPerspectiveScore']
