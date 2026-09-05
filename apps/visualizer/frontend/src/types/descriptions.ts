import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
export type DescriptionItem =
  components['schemas']['DescriptionItem']

export type DescriptionsListResponse = components['schemas']['DescriptionsListResponse']

export type DescriptionGetResponse = components['schemas']['DescriptionGetResponse']

export type DescriptionGenerateResponse =
  components['schemas']['DescriptionGenerateResponse']

export type ImageDescriptionComposition =
  components['schemas']['DescriptionComposition']

export type ImageDescriptionPerspectives =
  components['schemas']['DescriptionPerspectives']

export type ImageDescriptionTechnical =
  components['schemas']['DescriptionTechnical']

/** Full description document as returned by ``GET /api/descriptions/:key``. */
export type ImageDescription = NonNullable<DescriptionGetResponse['description']>
