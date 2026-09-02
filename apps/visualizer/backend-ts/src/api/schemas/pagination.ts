/**
 * Shared pagination envelope. Port of `PaginationMeta` in `api/schemas/jobs.py`.
 *
 * Lives in its own module rather than under `jobs`: several groups import it, and
 * the module-boundary policy forbids one `api` area importing a sibling.
 * `PaginationMeta` does not forbid extra properties, matching the Python model.
 */
import { z } from '@hono/zod-openapi';

export const PaginationMeta = z
  .object({
    offset: z.int(),
    limit: z.int(),
    current_page: z.int(),
    total_pages: z.int(),
    has_more: z.boolean(),
  })
  .openapi('PaginationMeta');

export type PaginationMeta = z.infer<typeof PaginationMeta>;
