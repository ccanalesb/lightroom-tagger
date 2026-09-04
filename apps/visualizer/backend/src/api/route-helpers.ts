/**
 * Route-definition helpers.
 *
 * `createRoute` does not add a 422 response implicitly; `withValidationError`
 * supplies it so the generated contract stays consistent across all routes.
 */
import type { Context } from 'hono';
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
 * Add the standard 422 to a route's response map, unless the route declares one.
 *
 * An explicit 422 wins: `POST /api/jobs/` uses `CatalogUnavailableError` when the
 * catalog is missing.
 */
export function withValidationError<R extends Record<number | string, unknown>>(
  responses: R,
): R extends { 422: unknown } ? R : R & { 422: typeof VALIDATION_ERROR_RESPONSE } {
  type Result = R extends { 422: unknown } ? R : R & { 422: typeof VALIDATION_ERROR_RESPONSE };
  if (422 in responses) return responses as Result;
  return { ...responses, 422: VALIDATION_ERROR_RESPONSE } as Result;
}

/**
 * Redirect `/prefix` to `/prefix/` with 308.
 *
 * The frontend always sends the trailing slash; without this, the bare form 404s.
 * Registered outside `openapi()` so it stays out of the generated document.
 */
export function redirectToTrailingSlash(
  app: {
    all: (path: string, handler: (c: Context) => Response) => unknown;
  },
  path: string,
): void {
  app.all(path, (c) => {
    // Build the target from the request path, not the route-local `path`: the group
    // is mounted under a prefix (`/api`), so the declared path alone would miss it.
    // Carry the query string across — dropping it would lose filters on redirect.
    const { search } = new URL(c.req.url);
    return c.redirect(`${c.req.path}/${search}`, 308);
  });
}
