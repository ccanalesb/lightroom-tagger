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
import { createOpenApiApp, openApiDoc } from './api/openapi.js';
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

  // One route group per domain area, mirroring the Flask blueprint layout.
  app.route('/api', systemRoutes);

  // Backend-authoritative OpenAPI (ADR-0013). `scripts/export-openapi.ts` reads this.
  app.doc('/apidoc/openapi.json', openApiDoc());

  return app;
}
