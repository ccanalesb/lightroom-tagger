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
 * Request-validation failures return **422** with a pydantic-shaped error array,
 * matching the `ValidationError` schema spectree attached to every route. Verified
 * against the running Flask app: `PUT /api/config/catalog {}` answers 422 with
 * `[{"loc": ["catalog_path"], "msg": "Field required", "type": "missing", ...}]`.
 *
 * One deliberate divergence, and it is a bug fix rather than a port. On routes
 * wrapped by the `with_db` decorator, spectree's 422 was raised as a Werkzeug
 * `HTTPException` *inside* `with_db`'s `except Exception` handler, which swallowed
 * it and returned `500 {"error": "??? Unknown Error: None"}`. So the documented 422
 * was unreachable for every images/stacks/scores route — `POST
 * /api/images/stacks/999999/split-member {}` really does answer 500 with that
 * string. This returns the documented 422 instead. Anything relying on the 500
 * was relying on a decorator-ordering accident.
 */
export function createOpenApiApp<E extends Env = Env>(): OpenAPIHono<E> {
  return new OpenAPIHono<E>({
    defaultHook: (result, c) => {
      if (!result.success) {
        // `input` and `url` appear in pydantic's real output but are absent from the
        // declared schema; they are not fabricated here.
        const issues = result.error.issues.map((issue) => ({
          loc: issue.path.map(String),
          msg: issue.message,
          type: issue.code,
        }));
        return c.json(issues, 422);
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
