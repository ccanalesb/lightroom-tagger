/**
 * System routes — health, stats, catalog cache readiness.
 * Port of the corresponding routes in `api/system.py`.
 */
import { createRoute } from '@hono/zod-openapi';
import { existsSync } from 'node:fs';
import { config } from '../config.js';
import { openLibraryDb } from '../db/connection.js';
import { getImageCount, getPostedImagesCount, hasCachedEntries } from '../db/library/statistics.js';
import { createOpenApiApp } from './openapi.js';
import { jsonBody, withValidationError } from './route-helpers.js';
import { ErrorBody } from './schemas/errors.js';
import { CatalogCacheReadyResponse, Stats, SystemStatusResponse } from './schemas/system.js';

export const systemRoutes = createOpenApiApp();

const statusRoute = createRoute({
  method: 'get',
  path: '/status',
  tags: ['system'],
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(SystemStatusResponse) },
  }),
});

systemRoutes.openapi(statusRoute, (c) => c.json({ status: 'ok' }, 200));

const statsRoute = createRoute({
  method: 'get',
  path: '/stats',
  tags: ['system'],
  responses: withValidationError({
    200: { description: 'Catalog statistics', content: jsonBody(Stats) },
    404: { description: 'Library database not found', content: jsonBody(ErrorBody) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

systemRoutes.openapi(statsRoute, (c) => {
  const dbPath = config.LIBRARY_DB;
  if (!existsSync(dbPath)) {
    return c.json({ error: 'Library database not found' }, 404);
  }
  // Read-only: these routes never mutate, which also keeps them off the write
  // lock the job processor holds during a catalog sync.
  const db = openLibraryDb(dbPath, { readonly: true });
  try {
    return c.json(
      {
        // The Flask version did `len(get_all_images(db))`, materializing every row
        // to count them. COUNT(*) is the same number without loading the catalog.
        catalog_images: getImageCount(db),
        posted_to_instagram: getPostedImagesCount(db),
        db_path: dbPath,
      },
      200,
    );
  } catch (e) {
    return c.json({ error: e instanceof Error ? e.message : String(e) }, 500);
  } finally {
    db.close();
  }
});

const catalogStatusRoute = createRoute({
  method: 'get',
  path: '/catalog/status',
  tags: ['system'],
  responses: withValidationError({
    200: { description: 'Catalog cache readiness', content: jsonBody(CatalogCacheReadyResponse) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

systemRoutes.openapi(catalogStatusRoute, (c) => {
  const dbPath = config.LIBRARY_DB;
  // A missing library DB is "not cached", not an error — matches api/system.py.
  if (!existsSync(dbPath)) return c.json({ cached: false }, 200);

  let db;
  try {
    db = openLibraryDb(dbPath, { readonly: true });
    return c.json({ cached: hasCachedEntries(db) }, 200);
  } catch (e) {
    return c.json({ error: e instanceof Error ? e.message : String(e) }, 500);
  } finally {
    db?.close();
  }
});
