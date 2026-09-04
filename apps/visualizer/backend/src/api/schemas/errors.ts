/**
 * Shared error bodies.
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
 * Stable schema name for CI; a content-hashed name would churn with upstream internals.
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
