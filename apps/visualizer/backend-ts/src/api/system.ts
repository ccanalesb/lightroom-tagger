/**
 * System routes — health, stats, catalog cache readiness.
 * Port of the corresponding routes in `api/system.py`.
 */
import { createRoute } from '@hono/zod-openapi';
import { existsSync } from 'node:fs';
import { config, loadLibraryConfig } from '../config.js';
import { ERROR_DB_NOT_FOUND } from '../constants/errors.js';
import { openDb, openLibraryDb } from '../db/connection.js';
import { getCachePipelineStatus } from '../db/jobs/pipeline-status.js';
import { getInsightsSummary } from '../db/library/insights.js';
import {
  getCacheStats,
  getImageCount,
  getPostedImagesCount,
  hasCachedEntries,
} from '../db/library/statistics.js';
import { createOpenApiApp } from './openapi.js';
import { jsonBody, withValidationError } from './route-helpers.js';
import { ErrorBody } from './schemas/errors.js';
import {
  CachePipelineStatus,
  CacheStatus,
  CatalogCacheReadyResponse,
  InsightsSummary,
  Stats,
  SystemStatusResponse,
} from './schemas/system.js';

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
    return c.json({ error: ERROR_DB_NOT_FOUND }, 404);
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

/**
 * These three do not use the `libraryDb` middleware.
 *
 * `/stats` and `/catalog/status` above already open their own connection, because
 * the system group is mounted at `/api` alongside every other group and a
 * `use('/*', …)` here would open a connection for requests it does not own.
 * `/cache/pipeline-status` reads a different database entirely.
 */

const insightsSummaryRoute = createRoute({
  method: 'get',
  path: '/insights-summary',
  tags: ['system'],
  responses: withValidationError({
    200: { description: 'Insights tile counts', content: jsonBody(InsightsSummary) },
    404: { description: 'Library database not found', content: jsonBody(ErrorBody) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

systemRoutes.openapi(insightsSummaryRoute, (c) => {
  const dbPath = config.LIBRARY_DB;
  if (!existsSync(dbPath)) return c.json({ error: ERROR_DB_NOT_FOUND }, 404);

  const db = openLibraryDb(dbPath, { readonly: true });
  try {
    return c.json(getInsightsSummary(db), 200);
  } catch (e) {
    return c.json({ error: e instanceof Error ? e.message : String(e) }, 500);
  } finally {
    db.close();
  }
});

const cacheStatusRoute = createRoute({
  method: 'get',
  path: '/cache/status',
  tags: ['system'],
  responses: withValidationError({
    200: { description: 'Vision cache status', content: jsonBody(CacheStatus) },
    404: { description: 'Library database not found', content: jsonBody(ErrorBody) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

systemRoutes.openapi(cacheStatusRoute, (c) => {
  const dbPath = config.LIBRARY_DB;
  if (!existsSync(dbPath)) return c.json({ error: ERROR_DB_NOT_FOUND }, 404);

  const db = openLibraryDb(dbPath, { readonly: true });
  try {
    const cacheDir = loadLibraryConfig(config.LT_CONFIG_YAML).visionCacheDir;
    const stats = getCacheStats(db, cacheDir);
    return c.json(
      {
        ...stats,
        // Rounded to two places for display, as Flask did. The raw byte sum stays
        // in `getCacheStats` so a caller that wants precision can have it.
        cache_size_mb: Math.round(stats.cache_size_mb * 100) / 100,
      },
      200,
    );
  } catch (e) {
    return c.json({ error: e instanceof Error ? e.message : String(e) }, 500);
  } finally {
    db.close();
  }
});

const cachePipelineStatusRoute = createRoute({
  method: 'get',
  path: '/cache/pipeline-status',
  tags: ['system'],
  responses: withValidationError({
    200: { description: 'Latest run per pipeline trigger', content: jsonBody(CachePipelineStatus) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

systemRoutes.openapi(cachePipelineStatusRoute, (c) => {
  // The jobs table lives in `visualizer.db`. Flask reached it through
  // `current_app.db`, a connection opened once at startup and shared across
  // threads; opened per request here instead, which is what makes the route safe
  // to serve while the job processor is writing.
  const dbPath = config.VISUALIZER_DB;
  if (!existsSync(dbPath)) {
    // Flask would have raised on a missing app DB and answered 500; the message is
    // the one the caller can act on.
    return c.json({ error: `Jobs database not found: ${dbPath}` }, 500);
  }
  const db = openDb(dbPath, { readonly: true, vec: false });
  try {
    return c.json(getCachePipelineStatus(db), 200);
  } catch (e) {
    return c.json({ error: e instanceof Error ? e.message : String(e) }, 500);
  } finally {
    db.close();
  }
});
