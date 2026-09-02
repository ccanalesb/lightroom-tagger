/**
 * OpenAPI configuration. Replaces `api/openapi.py` (spectree).
 *
 * ADR-0013 makes the backend authoritative for API shape: Zod schemas here are the
 * single source of truth, the OpenAPI document is generated from them, and the
 * frontend's `src/types/api.gen.ts` is generated from that document with CI failing
 * on drift. Nothing may hand-write a response interface on the frontend.
 *
 * Title and version must match the spectree spec they replace, or every generated
 * type name churns in a single diff.
 */
import { OpenAPIHono } from '@hono/zod-openapi';
import type { Env } from 'hono';

export const OPENAPI_TITLE = 'Lightroom Tagger Visualizer API';
export const OPENAPI_VERSION = '1.0.0';

/**
 * Build the OpenAPI-aware Hono app.
 *
 * Validation failures are shaped as `{ error }` so they match the `ErrorBody`
 * contract the rest of the API returns; the default hook emits a Zod error dump.
 */
export function createOpenApiApp<E extends Env = Env>(): OpenAPIHono<E> {
  return new OpenAPIHono<E>({
    defaultHook: (result, c) => {
      if (!result.success) {
        const first = result.error.issues[0];
        const where = first?.path.join('.') || 'request';
        return c.json({ error: `Invalid request parameters: ${where}` }, 400);
      }
      return undefined;
    },
  });
}

export interface OpenApiDocOptions {
  servers?: { url: string; description?: string }[];
}

/** The document descriptor handed to `app.doc()`. */
export function openApiDoc(opts: OpenApiDocOptions = {}) {
  return {
    openapi: '3.1.0',
    info: { title: OPENAPI_TITLE, version: OPENAPI_VERSION },
    ...(opts.servers ? { servers: opts.servers } : {}),
  } as const;
}
