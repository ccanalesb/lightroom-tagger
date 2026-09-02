/**
 * Route-definition helpers.
 *
 * spectree added a 422 response to every `@spec.validate`-decorated route without
 * the route author writing one. `createRoute` has no such implicit behaviour, so
 * `withValidationError` supplies it — keeping the generated contract (and therefore
 * `api.gen.ts`) consistent across all 63 routes instead of depending on each route
 * author remembering.
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
 * Add the standard 422 to a route's response map.
 *
 * Use on every route so no group silently omits it and drifts the contract.
 */
export function withValidationError<R extends Record<number | string, unknown>>(responses: R) {
  return { ...responses, 422: VALIDATION_ERROR_RESPONSE } as R & {
    422: typeof VALIDATION_ERROR_RESPONSE;
  };
}

/**
 * Redirect `/prefix` to `/prefix/`, the way Werkzeug's `strict_slashes` did.
 *
 * Flask blueprints registered with a `url_prefix` and a `"/"` route serve the
 * trailing-slash form as canonical and answer the bare form with a 308 (verified
 * against Werkzeug directly). Hono simply 404s it. The frontend always sends the
 * slash, so this is not load-bearing today — but a 404 where the old backend
 * redirected is a silent behaviour change, and 308 preserves the method and body
 * so non-GET callers keep working.
 *
 * Registered as a plain handler, not via `openapi()`, so it stays out of the
 * generated document — Flask did not document the redirect either.
 */
export function redirectToTrailingSlash(
  app: {
    all: (path: string, handler: (c: Context) => Response) => unknown;
  },
  path: string,
): void {
  app.all(path, (c) => {
    // Build the target from the REQUEST path, not the route-local `path`: the group
    // is mounted under a prefix (`/api`), so the declared path alone would produce
    // `/perspectives/` and send the client somewhere that does not exist.
    //
    // Carry the query string across, as Werkzeug's redirect does — dropping it
    // would turn `?active_only=true` into a full list on the second request.
    const { search } = new URL(c.req.url);
    return c.redirect(`${c.req.path}/${search}`, 308);
  });
}
