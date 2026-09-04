/** Burst stack API models. */
import { z } from '@hono/zod-openapi';
import { CatalogImage } from './catalog.js';

export const StackMetadata = z
  .object({
    stack_id: z.int(),
    representative_key: z.string(),
    stack_member_count: z.int(),
    member_keys: z.array(z.string()),
  })
  .strict()
  .openapi('StackMetadata');

export const StackMembersResponse = z
  .object({ items: z.array(CatalogImage) })
  .strict()
  .openapi('StackMembersResponse');

export const StackSplitMemberRequest = z
  .object({ image_key: z.string() })
  .strict()
  .openapi('StackSplitMemberRequest');

export const StackSplitMemberResponse = z
  .object({
    split_out_key: z.string(),
    remaining_stack: StackMetadata.nullish(),
    dissolved: z.boolean(),
  })
  .strict()
  .openapi('StackSplitMemberResponse');

export const StackMergeRequest = z
  .object({ source_stack_id: z.int() })
  .strict()
  .openapi('StackMergeRequest');

export const StackMergeResponse = z
  .object({ stack: StackMetadata, merged_stack_id: z.int() })
  .strict()
  .openapi('StackMergeResponse');

export const StackRepresentativeRequest = z
  .object({ image_key: z.string() })
  .strict()
  .openapi('StackRepresentativeRequest');

export const StackRepresentativeResponse = z
  .object({ stack: StackMetadata })
  .strict()
  .openapi('StackRepresentativeResponse');

export const StackSuggestionPairRequest = z
  .object({ image_key_a: z.string(), image_key_b: z.string() })
  .strict()
  .openapi('StackSuggestionPairRequest');

export const StackSuggestion = z
  .object({
    group_id: z.int(),
    image_a: CatalogImage,
    image_b: CatalogImage,
    similarity: z.number(),
    why_matched: z.string(),
    time_gap_seconds: z.int().nullish(),
  })
  .strict()
  .openapi('StackSuggestion');

export const StackSuggestionsResponse = z
  .object({ items: z.array(StackSuggestion), total: z.int() })
  .strict()
  .openapi('StackSuggestionsResponse');

/**
 * Accept returns the stack only.
 *
 * `stackAcceptSuggestionPair` may also report `merged_stack_id` when it merged two
 * existing stacks, but this model forbids extra fields, so the route narrows the
 * result before responding.
 */
export const StackSuggestionAcceptResponse = z
  .object({ stack: StackMetadata })
  .strict()
  .openapi('StackSuggestionAcceptResponse');

export const StackSuggestionRejectResponse = z
  .object({ image_key_a: z.string(), image_key_b: z.string(), rejected: z.boolean() })
  .strict()
  .openapi('StackSuggestionRejectResponse');
