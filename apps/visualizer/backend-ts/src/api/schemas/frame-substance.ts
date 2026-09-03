/** Frame substance per-image API models. Port of `api/schemas/frame_substance.py`. */
import { z } from '@hono/zod-openapi';

/**
 * Why a frame is being called condemned.
 *
 * `pixel_detector` is the authoritative signal and carries a tier (A for `void`, B
 * for `illegible`). `excusal_channel` is a separate, weaker observation — every
 * active optional perspective declined to score — and is always advisory, so the UI
 * can show it without implying the detector agreed.
 */
export const FrameSubstanceInstrument = z
  .object({
    kind: z.enum(['pixel_detector', 'excusal_channel']),
    verdict: z.enum(['void', 'illegible']).nullish(),
    tier: z.enum(['A', 'B']).nullish(),
    advisory: z.boolean().default(false),
  })
  .strict()
  .openapi('FrameSubstanceInstrument');

export const FrameSubstanceResponse = z
  .object({
    image_key: z.string(),
    has_detection_run: z.boolean(),
    verdict: z.enum(['void', 'illegible', 'ok', 'unknown']).nullish(),
    unknown_reason: z.string().nullish(),
    detector_version: z.string().nullish(),
    judged_at: z.string().nullish(),
    is_stale: z.boolean().default(false),
    has_override: z.boolean().default(false),
    flagged: z.boolean().default(false),
    /** `null` — not `false` — when the Lightroom catalog cannot be read. */
    has_cull_keyword: z.boolean().nullish(),
    instrument: FrameSubstanceInstrument.nullish(),
    restore_tier: z.enum(['A', 'B']).nullish(),
    catalog_write_available: z.boolean(),
    catalog_write_unavailable_reason: z.string().nullish(),
  })
  .strict()
  .openapi('FrameSubstanceResponse');

export const FrameSubstanceOverrideResponse = z
  .object({ image_key: z.string(), has_override: z.boolean() })
  .strict()
  .openapi('FrameSubstanceOverrideResponse');

export const CullKeywordMutationResponse = z
  .object({
    image_key: z.string(),
    // The writer's three-way outcome, never collapsed into a boolean: "already
    // present" and "image not found" are different things for the user to see.
    result: z
      .enum(['added', 'already_present', 'image_not_found', 'removed', 'not_present'])
      .describe('Three-way writer outcome; never collapsed into a boolean.'),
  })
  .strict()
  .openapi('CullKeywordMutationResponse');
