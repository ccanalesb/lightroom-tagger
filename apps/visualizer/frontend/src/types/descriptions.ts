import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type DescriptionItem =
  components['schemas']['DescriptionsListResponse.ebaf8eb.DescriptionItem']

export type DescriptionsListResponse = components['schemas']['DescriptionsListResponse.ebaf8eb']

export type DescriptionGetResponse = components['schemas']['DescriptionGetResponse.ebaf8eb']

export type DescriptionGenerateResponse =
  components['schemas']['DescriptionGenerateResponse.ebaf8eb']

export type ImageDescriptionComposition =
  components['schemas']['DescriptionGetResponse.ebaf8eb.DescriptionComposition']

export type ImageDescriptionPerspectives =
  components['schemas']['DescriptionGetResponse.ebaf8eb.DescriptionPerspectives']

export type ImageDescriptionTechnical =
  components['schemas']['DescriptionGetResponse.ebaf8eb.DescriptionTechnical']

/** Full description document as returned by ``GET /api/descriptions/:key``. */
export type ImageDescription = NonNullable<DescriptionGetResponse['description']>
