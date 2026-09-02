/**
 * Route-definition helpers.
 *
 * spectree added a 422 response to every `@spec.validate`-decorated route without
 * the route author writing one. `createRoute` has no such implicit behaviour, so
 * `withValidationError` supplies it — keeping the generated contract (and therefore
 * `api.gen.ts`) consistent across all 63 routes instead of depending on each route
 * author remembering.
 */
import type { ZodType } from 'zod';
import { ValidationError } from './schemas/errors.js';

/** Wrap a schema as an `application/json` response body. */
export function jsonBody<T extends ZodType>(schema: T) {
  return { 'application/json': { schema } } as const;
}

export const VALIDATION_ERROR_RESPONSE = {
  description: 'Unprocessable Content',
  content: jsonBody(ValidationError),
} as const;

/**
 * Add the standard 422 to a route's response map.
 *
 * Use on every route so no group silently omits it and drifts the contract.
 */
export function withValidationError<R extends Record<number | string, unknown>>(responses: R) {
  return { ...responses, 422: VALIDATION_ERROR_RESPONSE } as R & {
    422: typeof VALIDATION_ERROR_RESPONSE;
  };
}
