import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type CatalogImage =
  components['schemas']['CatalogImage']

/** List-row / embedded input for adapters (full list rows satisfy this). */
export type CatalogImageInput = Pick<CatalogImage, 'key'> & Partial<Omit<CatalogImage, 'key'>>
export type CatalogListResponse = components['schemas']['CatalogListResponse']
export type CatalogMonthsResponse = components['schemas']['CatalogMonthsResponse']
export type CatalogSimilarityGroup =
  components['schemas']['CatalogSimilarityGroup']
export type CatalogSimilarityGroupsResponse =
  components['schemas']['CatalogSimilarityGroupsResponse']

type ImageViewSchema = components['schemas']['ImageView']

/** Detail modal superset — required identity plus optional fields filled per source. */
export type ImageView = Pick<ImageViewSchema, 'image_type' | 'key'> &
  Partial<Omit<ImageViewSchema, 'image_type' | 'key'>>

export type ImageDetailResponse = ImageViewSchema
export type InstagramPostedResponse =
  components['schemas']['InstagramPostedResponse']
export type IdentityPerPerspectiveScore =
  components['schemas']['IdentityPerPerspectiveScore']
