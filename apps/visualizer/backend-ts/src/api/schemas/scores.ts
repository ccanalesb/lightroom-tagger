/**
 * Scores API response models — single source of truth for `image_scores` shapes.
 * Port of `api/schemas/scores.py`.
 */
import { z } from '@hono/zod-openapi';

export const ImageScoreRow = z
  .object({
    id: z.int().nullish(),
    image_key: z.string(),
    image_type: z.string(),
    perspective_slug: z.string(),
    score: z.int(),
    rationale: z.string().nullish(),
    model_used: z.string().nullish(),
    prompt_version: z.string(),
    scored_at: z.string(),
    is_current: z.boolean(),
    repaired_from_malformed: z.boolean(),
    not_attempted: z.boolean().default(false),
  })
  .strict()
  .openapi('ImageScoreRow');

export const ScoresCurrentResponse = z
  .object({
    image_key: z.string(),
    image_type: z.literal('catalog'),
    current: z.array(ImageScoreRow),
  })
  .strict()
  .openapi('ScoresCurrentResponse');

export const ScoresHistoryResponse = z
  .object({
    image_key: z.string(),
    image_type: z.literal('catalog'),
    perspective_slug: z.string(),
    history: z.array(ImageScoreRow),
  })
  .strict()
  .openapi('ScoresHistoryResponse');

export type ImageScoreRow = z.infer<typeof ImageScoreRow>;
