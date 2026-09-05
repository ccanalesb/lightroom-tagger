/**
 * Perspectives API response models.
 *
 * `optional` is read-only over HTTP — it is derived from the markdown marker on
 * write (ADR-0012), never accepted from a request body.
 */
import { z } from '@hono/zod-openapi';

export const PerspectiveSummary = z
  .object({
    id: z.int(),
    slug: z.string(),
    display_name: z.string(),
    description: z.string(),
    active: z.boolean(),
    optional: z.boolean(),
    source_filename: z.string().nullish(),
    updated_at: z.string().nullish(),
  })
  .strict()
  .openapi('PerspectiveSummary');

export const PerspectiveDetail = PerspectiveSummary.extend({
  prompt_markdown: z.string(),
  created_at: z.string().nullish(),
})
  .strict()
  .openapi('PerspectiveDetail');

/** Nested perspective line item in image descriptions. */
export const PerspectiveScore = z
  .object({
    analysis: z.string(),
    score: z.int(),
  })
  .strict()
  .openapi('PerspectiveScore');

/** `GET /api/perspectives/` response body — a bare array. */
export const PerspectiveListResponse = z
  .array(PerspectiveSummary)
  .openapi('PerspectiveListResponse');

export type PerspectiveSummary = z.infer<typeof PerspectiveSummary>;
export type PerspectiveDetail = z.infer<typeof PerspectiveDetail>;
