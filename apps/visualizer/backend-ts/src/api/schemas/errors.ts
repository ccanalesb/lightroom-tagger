/**
 * Shared error bodies. Ported from the `ErrorBody` family in `api/schemas/jobs.py`.
 *
 * `ErrorBody` deliberately does NOT forbid extra properties — subclasses such as
 * `CatalogUnavailableError` extend it with `code` and `library_db`.
 */
import { z } from '@hono/zod-openapi';

export const ErrorBody = z
  .object({
    error: z.string(),
    code: z.string().nullish(),
  })
  .openapi('ErrorBody');

export type ErrorBody = z.infer<typeof ErrorBody>;

/**
 * Request-validation failure element.
 *
 * spectree attached a 422 to every decorated route automatically, under a
 * content-hashed schema name (`ValidationError.6a07bef`). We emit the same
 * structure under a stable name: the hash was an artefact of spectree internals,
 * nothing on the frontend consumes the type, and a name that changes with an
 * upstream implementation detail is a poor thing to gate CI on.
 */
export const ValidationErrorElement = z
  .object({
    loc: z.array(z.string()).describe('Missing field name'),
    msg: z.string().describe('Error message'),
    type: z.string().describe('Error type'),
    ctx: z.record(z.string(), z.unknown()).nullish().describe('Error context'),
  })
  .openapi('ValidationErrorElement');

export const ValidationError = z
  .array(ValidationErrorElement)
  .describe('Model of a validation error response.')
  .openapi('ValidationError');

export type ValidationError = z.infer<typeof ValidationError>;
