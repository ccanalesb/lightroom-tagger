/**
 * Descriptions API response models.
 *
 * Note the differing strictness, which is deliberate and mirrors pydantic:
 *   - list/envelope models forbid extra properties (`extra='forbid'`)
 *   - the nested description sub-objects IGNORE extras (`extra='ignore'`)
 *   - `ImageDescription` ALLOWS extras (`extra='allow'`) — description rows carry
 *     columns beyond the documented ones and they are passed through
 */
import { z } from '@hono/zod-openapi';
import { PaginationMeta } from './pagination.js';
import { PerspectiveScore } from './perspectives.js';

export const DescriptionItem = z
  .object({
    image_key: z.string(),
    image_type: z.literal('catalog'),
    filename: z.string().nullish(),
    date_ref: z.string().nullish(),
    summary: z.string().nullish(),
    best_perspective: z.string().nullish(),
    desc_model: z.string().nullish(),
    described_at: z.string().nullish(),
    has_description: z.int(),
  })
  .strict()
  .openapi('DescriptionItem');

export const DescriptionsListResponse = z
  .object({
    total: z.int(),
    items: z.array(DescriptionItem),
    pagination: PaginationMeta,
  })
  .strict()
  .openapi('DescriptionsListResponse');

export const DescriptionComposition = z
  .object({
    layers: z.array(z.string()).nullish(),
    techniques: z.array(z.string()).nullish(),
    problems: z.array(z.string()).nullish(),
    depth: z.string().nullish(),
    balance: z.string().nullish(),
  })
  .openapi('DescriptionComposition');

export const DescriptionPerspectives = z
  .object({
    street: PerspectiveScore.nullish(),
    documentary: PerspectiveScore.nullish(),
    publisher: PerspectiveScore.nullish(),
  })
  .openapi('DescriptionPerspectives');

export const DescriptionTechnical = z
  .object({
    dominant_colors: z.array(z.string()).nullish(),
    mood: z.string().nullish(),
    lighting: z.string().nullish(),
    time_of_day: z.string().nullish(),
  })
  .openapi('DescriptionTechnical');

/**
 * `extra='allow'` in pydantic — `.passthrough()` here. Description rows include
 * columns the model does not name (`dominant_colors`, `mood_tags`, …) and the
 * route returns the row as-is, so narrowing this would silently drop data.
 */
export const ImageDescription = z
  .object({
    image_key: z.string(),
    image_type: z.string(),
    summary: z.string(),
    composition: z.union([DescriptionComposition, z.record(z.string(), z.unknown())]).default({}),
    perspectives: z
      .union([DescriptionPerspectives, z.record(z.string(), z.unknown())])
      .default({}),
    technical: z.union([DescriptionTechnical, z.record(z.string(), z.unknown())]).default({}),
    subjects: z.array(z.string()).default([]),
    best_perspective: z.string(),
    model_used: z.string(),
    described_at: z.string().nullish(),
  })
  .passthrough()
  .openapi('ImageDescription');

export const DescriptionGetResponse = z
  .object({ description: ImageDescription.nullable() })
  .strict()
  .openapi('DescriptionGetResponse');

/**
 * Not `.strict()`: the pydantic model has no `extra='forbid'`, so an unknown key
 * in the body is ignored rather than rejected. Tightening it would 422 requests
 * Flask accepts.
 *
 * `image_type` is validated in the handler, not here — Flask answers 400 with
 * `Invalid image_type: …` for a bad value, and a Zod enum would make it a 422.
 */
export const DescriptionGenerateRequest = z
  .object({
    force: z.boolean().default(false),
    image_type: z.string().default('catalog'),
    model: z.string().nullish().default(null),
    provider_id: z.string().nullish().default(null),
    /**
     * The model name passed *through* to the provider, distinct from `model`:
     * `model` sets `DESCRIPTION_VISION_MODEL` for the call and is only honoured
     * when no `provider_id` is given, while `provider_model` names the model
     * within an explicitly chosen provider.
     */
    provider_model: z.string().nullish().default(null),
  })
  .openapi('DescriptionGenerateRequest');

export const DescriptionGenerateResponse = z
  .object({
    generated: z.boolean(),
    description: ImageDescription.nullable(),
  })
  .strict()
  .openapi('DescriptionGenerateResponse');

export const DescriptionProviderError = z
  .object({
    error: z.string(),
    message: z.string(),
    provider: z.string().nullish(),
  })
  .openapi('DescriptionProviderError');

export type DescriptionItem = z.infer<typeof DescriptionItem>;
