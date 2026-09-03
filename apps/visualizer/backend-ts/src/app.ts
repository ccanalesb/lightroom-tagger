/**
 * Application factory. Port of `create_app()` in `app.py`.
 *
 * Deliberately side-effect free: constructing the app must not start the job
 * processor or write to stdout. The Python `create_app()` printed the auto-detected
 * NAS prefix to stdout, which corrupted `export_openapi.py`'s JSON output and broke
 * `npm run verify:contract`. Diagnostics here go to stderr.
 */
import { cors } from 'hono/cors';
import { config } from './config.js';
import { HttpError } from './utils/responses.js';
import { createOpenApiApp, openApiDoc } from './api/openapi.js';
import { descriptionsRoutes } from './api/descriptions.js';
import { catalogRoutes } from './api/images/catalog.js';
import { stacksRoutes } from './api/images/stacks.js';
import { ltConfigRoutes } from './api/lt-config.js';
import { perspectivesRoutes } from './api/perspectives.js';
import { scoresRoutes } from './api/scores.js';
import { systemRoutes } from './api/system.js';

export function createApp() {
  const app = createOpenApiApp();

  app.use(
    '/api/*',
    cors({
      origin: config.FRONTEND_ORIGINS,
      credentials: true,
    }),
  );

  // One route group per domain area, mirroring the Flask blueprint layout and its
  // url_prefix values exactly — the frontend and the OpenAPI contract depend on them.
  //
  // Order matters within the images tree: `/images/catalog/months` and
  // `/images/catalog-similarity-groups` must be registered before the
  // `/images/catalog/{image_key}` catch-all, or they are matched as image keys.
  // `catalogRoutes` declares them in that order internally.
  app.route('/api', catalogRoutes);
  app.route('/api', stacksRoutes);
  app.route('/api', systemRoutes);
  app.route('/api', descriptionsRoutes);
  app.route('/api', ltConfigRoutes);
  app.route('/api', perspectivesRoutes);
  app.route('/api/scores', scoresRoutes);

  /**
   * `/api/images/<bad_type>/<key>` for a family that is not mounted.
   *
   * Registered after the images groups so real paths resolve to them first. It also
   * catches a non-numeric stack id: Flask's `<int:stack_id>` simply did not match
   * `/api/images/stacks/abc/members`, so the request fell through to here and got
   * this 400 rather than a 404. Verified against the running Flask app.
   *
   * The message embeds a Python tuple repr because that is what the frontend has
   * been receiving — `_DETAIL_IMAGE_TYPES` was interpolated directly.
   */
  app.all('/api/images/:bad_type/*', (c) => {
    if (c.req.method !== 'GET') return c.notFound();
    return c.json(
      { error: "invalid image_type; expected one of ('catalog', 'instagram')" },
      400,
    );
  });

  /**
   * Uncaught errors become a 500 carrying the message.
   *
   * Every Flask route wrapped its body in `try/except Exception` and returned
   * `error_server_error(str(e))`, and `with_db` did the same again one layer out.
   * Centralizing it here keeps the same response without declaring an undocumented
   * 500 on each route — spectree only listed 500 for `/api/stats` and
   * `/api/catalog/status`, so declaring it everywhere would drift the contract.
   */
  app.onError((err, c) => {
    if (err instanceof HttpError) return c.json({ error: err.message }, err.status);
    return c.json({ error: err instanceof Error ? err.message : String(err) }, 500);
  });

  // Backend-authoritative OpenAPI (ADR-0013). `scripts/export-openapi.ts` reads this.
  app.doc('/apidoc/openapi.json', openApiDoc());

  return app;
}
