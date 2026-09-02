/**
 * Read and write the repo-level `config.yaml`. Port of `api/lt_config.py`.
 *
 * These routes do not touch `library.db` — they edit the user's own config file,
 * so no library-DB middleware here.
 */
import { createRoute } from '@hono/zod-openapi';
import { statSync } from 'node:fs';
import {
  config,
  expandUserPath,
  loadLibraryConfig,
  updateConfigYamlCatalogPath,
  updateConfigYamlStackBurstDeltaMs,
} from '../config.js';
import { createOpenApiApp } from './openapi.js';
import { jsonBody, withValidationError } from './route-helpers.js';
import {
  ConfigCatalogGetResponse,
  ConfigCatalogPutResponse,
  ConfigStackDetectionGetResponse,
  ConfigStackDetectionPutResponse,
} from './schemas/config.js';
import { ErrorBody } from './schemas/errors.js';

export const ltConfigRoutes = createOpenApiApp();

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

async function readJsonBody(c: { req: { json: () => Promise<unknown> } }): Promise<unknown> {
  try {
    return await c.req.json();
  } catch {
    // Matches `request.get_json(silent=True)` returning None on unparseable input.
    return null;
  }
}

// --- catalog ----------------------------------------------------------------

const getCatalogRoute = createRoute({
  method: 'get',
  path: '/config/catalog',
  tags: ['config'],
  responses: withValidationError({
    200: { description: 'Catalog path config', content: jsonBody(ConfigCatalogGetResponse) },
  }),
});

ltConfigRoutes.openapi(getCatalogRoute, (c) => {
  const cfg = loadLibraryConfig(config.LT_CONFIG_YAML);
  // The RAW value is echoed back, not the resolved one: the UI edits what the user
  // typed (which may contain `~`), and `resolved_path` is shown alongside it.
  const raw = cfg.catalogPathRaw || '';
  const resolved = raw ? expandUserPath(raw) : '';
  return c.json(
    { catalog_path: raw, resolved_path: resolved, exists: Boolean(resolved && isFile(resolved)) },
    200,
  );
});

const putCatalogRoute = createRoute({
  method: 'put',
  path: '/config/catalog',
  tags: ['config'],
  responses: withValidationError({
    200: { description: 'Saved', content: jsonBody(ConfigCatalogPutResponse) },
    400: { description: 'Invalid request', content: jsonBody(ErrorBody) },
  }),
});

ltConfigRoutes.openapi(putCatalogRoute, async (c) => {
  const data = await readJsonBody(c);
  if (data === null || typeof data !== 'object' || !('catalog_path' in data)) {
    return c.json({ error: 'catalog_path is required' }, 400);
  }
  const value = (data as { catalog_path: unknown }).catalog_path;
  if (typeof value !== 'string') {
    return c.json({ error: 'catalog_path must be a string' }, 400);
  }
  if (!value.toLowerCase().endsWith('.lrcat')) {
    return c.json({ error: 'catalog_path must be a .lrcat file' }, 400);
  }
  if (!isFile(expandUserPath(value))) {
    return c.json({ error: 'catalog_path must be an existing file' }, 400);
  }

  updateConfigYamlCatalogPath(config.LT_CONFIG_YAML, value);
  // Python writes the stripped value and echoes the stripped value.
  return c.json({ catalog_path: value.trim(), ok: true }, 200);
});

// --- stack detection --------------------------------------------------------

const getStackDetectionRoute = createRoute({
  method: 'get',
  path: '/config/stack-detection',
  tags: ['config'],
  responses: withValidationError({
    200: {
      description: 'Stack detection config',
      content: jsonBody(ConfigStackDetectionGetResponse),
    },
  }),
});

ltConfigRoutes.openapi(getStackDetectionRoute, (c) => {
  const cfg = loadLibraryConfig(config.LT_CONFIG_YAML);
  return c.json({ stack_burst_delta_ms: Math.trunc(cfg.stackBurstDeltaMs) }, 200);
});

const putStackDetectionRoute = createRoute({
  method: 'put',
  path: '/config/stack-detection',
  tags: ['config'],
  responses: withValidationError({
    200: { description: 'Saved', content: jsonBody(ConfigStackDetectionPutResponse) },
    400: { description: 'Invalid request', content: jsonBody(ErrorBody) },
  }),
});

ltConfigRoutes.openapi(putStackDetectionRoute, async (c) => {
  const data = await readJsonBody(c);
  if (data === null || typeof data !== 'object' || !('stack_burst_delta_ms' in data)) {
    return c.json({ error: 'stack_burst_delta_ms is required' }, 400);
  }
  const value = (data as { stack_burst_delta_ms: unknown }).stack_burst_delta_ms;

  // Python used `type(value) is not int`, which rejects bools (a bool IS an int
  // subclass, and `type()` is exact) and rejects floats like 2000.0. JSON gives us
  // numbers, so require an integer-valued number and reject booleans explicitly.
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    return c.json({ error: 'stack_burst_delta_ms must be an integer' }, 400);
  }
  if (value < 1) {
    return c.json({ error: 'stack_burst_delta_ms must be at least 1' }, 400);
  }

  updateConfigYamlStackBurstDeltaMs(config.LT_CONFIG_YAML, value);
  return c.json({ stack_burst_delta_ms: value, ok: true }, 200);
});
