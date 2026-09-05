/**
 * Config route tests.
 *
 * These routes WRITE `config.yaml`, so every test points `LT_CONFIG_YAML` at a temp
 * file. Without that override the suite would rewrite the user's real config.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parse as parseYaml } from 'yaml';
import { createApp } from '../src/app.js';

let dir: string;
let cfgPath: string;
const app = createApp();
const json = async <T>(res: Response): Promise<T> => (await res.json()) as T;

const put = (path: string, body: unknown) =>
  app.request(path, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });

const readCfg = (): Record<string, unknown> =>
  parseYaml(readFileSync(cfgPath, 'utf8')) as Record<string, unknown>;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'lt-cfg-'));
  cfgPath = join(dir, 'config.yaml');
  process.env.LT_CONFIG_YAML = cfgPath;
});

afterEach(() => {
  delete process.env.LT_CONFIG_YAML;
  rmSync(dir, { recursive: true, force: true });
});

describe('GET /api/config/catalog', () => {
  it('reports the raw path, the expanded path, and whether it exists', async () => {
    const lrcat = join(dir, 'My Catalog.lrcat');
    writeFileSync(lrcat, 'x');
    writeFileSync(cfgPath, `catalog_path: ${JSON.stringify(lrcat)}\nworkers: 4\n`);

    const res = await app.request('/api/config/catalog');
    expect(res.status).toBe(200);
    expect(await json(res)).toEqual({
      catalog_path: lrcat,
      resolved_path: lrcat,
      exists: true,
    });
  });

  it('reports exists: false for a configured but missing file', async () => {
    writeFileSync(cfgPath, 'catalog_path: /nope/missing.lrcat\n');
    const body = await json<{ exists: boolean; catalog_path: string }>(
      await app.request('/api/config/catalog'),
    );
    expect(body.exists).toBe(false);
    expect(body.catalog_path).toBe('/nope/missing.lrcat');
  });

  it('returns empty strings when nothing is configured', async () => {
    writeFileSync(cfgPath, 'workers: 4\n');
    expect(await json(await app.request('/api/config/catalog'))).toEqual({
      catalog_path: '',
      resolved_path: '',
      exists: false,
    });
  });

  it('echoes the raw value, keeping ~ unexpanded, and resolves it separately', async () => {
    // The UI edits what the user typed; resolved_path is shown alongside.
    writeFileSync(cfgPath, 'catalog_path: ~/Pictures/Cat.lrcat\n');
    const body = await json<{ catalog_path: string; resolved_path: string }>(
      await app.request('/api/config/catalog'),
    );
    expect(body.catalog_path).toBe('~/Pictures/Cat.lrcat');
    expect(body.resolved_path).not.toContain('~');
    expect(body.resolved_path.endsWith('/Pictures/Cat.lrcat')).toBe(true);
  });
});

describe('PUT /api/config/catalog', () => {
  it('writes the value and preserves unrelated keys and their order', async () => {
    writeFileSync(cfgPath, 'workers: 7\nvision_model: gemma\ncatalog_path: /old.lrcat\n');
    const lrcat = join(dir, 'new.lrcat');
    writeFileSync(lrcat, 'x');

    const res = await put('/api/config/catalog', { catalog_path: lrcat });
    expect(res.status).toBe(200);
    expect(await json(res)).toEqual({ catalog_path: lrcat, ok: true });

    const cfg = readCfg();
    expect(cfg.catalog_path).toBe(lrcat);
    // A rewrite must not drop keys the backend does not understand.
    expect(cfg.workers).toBe(7);
    expect(cfg.vision_model).toBe('gemma');
    expect(Object.keys(cfg)).toEqual(['workers', 'vision_model', 'catalog_path']);
  });

  it('rejects a padded path, because validation runs before the trim', async () => {
    // Validation runs on the raw path before trim, so padded paths fail the extension check.
    const lrcat = join(dir, 'spaced.lrcat');
    writeFileSync(lrcat, 'x');

    const trailing = await put('/api/config/catalog', { catalog_path: `${lrcat}  ` });
    expect(trailing.status).toBe(400);
    expect(await json(trailing)).toEqual({ error: 'catalog_path must be a .lrcat file' });

    const leading = await put('/api/config/catalog', { catalog_path: `  ${lrcat}` });
    expect(leading.status).toBe(400);
    expect(await json(leading)).toEqual({ error: 'catalog_path must be an existing file' });
  });

  it.each([
    [{ catalog_path: '/tmp/notacatalog.txt' }, 'catalog_path must be a .lrcat file'],
    [{ catalog_path: '/nope/missing.lrcat' }, 'catalog_path must be an existing file'],
  ])('rejects %j with a 400', async (body, message) => {
    const res = await put('/api/config/catalog', body);
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: message });
  });

  it.each([
    [{}, 'a missing field'],
    [{ catalog_path: 5 }, 'a non-string'],
    [{ catalog_path: '/nope/missing.lrcat', extra: 1 }, 'an unexpected field'],
  ])('answers 422 for %o (%s)', async (body, _why) => {
    // Schema violations return 422, not 400.
    const res = await put('/api/config/catalog', body);
    expect(res.status).toBe(422);
  });

  it('accepts a .LRCAT extension case-insensitively', async () => {
    const lrcat = join(dir, 'Shouty.LRCAT');
    writeFileSync(lrcat, 'x');
    expect((await put('/api/config/catalog', { catalog_path: lrcat })).status).toBe(200);
  });

  it('does not write the file when validation fails', async () => {
    writeFileSync(cfgPath, 'catalog_path: /original.lrcat\n');
    await put('/api/config/catalog', { catalog_path: '/nope/missing.lrcat' });
    expect(readCfg().catalog_path).toBe('/original.lrcat');
  });
});

describe('GET /api/config/stack-detection', () => {
  it('returns the configured value', async () => {
    writeFileSync(cfgPath, 'stack_burst_delta_ms: 1500\n');
    expect(await json(await app.request('/api/config/stack-detection'))).toEqual({
      stack_burst_delta_ms: 1500,
    });
  });

  it('falls back to the 2000ms default', async () => {
    writeFileSync(cfgPath, 'workers: 4\n');
    expect(await json(await app.request('/api/config/stack-detection'))).toEqual({
      stack_burst_delta_ms: 2000,
    });
  });
});

describe('PUT /api/config/stack-detection', () => {
  it('writes the value and preserves other keys', async () => {
    writeFileSync(cfgPath, 'workers: 4\n');
    const res = await put('/api/config/stack-detection', { stack_burst_delta_ms: 750 });
    expect(res.status).toBe(200);
    expect(await json(res)).toEqual({ stack_burst_delta_ms: 750, ok: true });
    expect(readCfg()).toEqual({ workers: 4, stack_burst_delta_ms: 750 });
  });

  it.each([
    [{ stack_burst_delta_ms: 0 }, 'stack_burst_delta_ms must be at least 1'],
    [{ stack_burst_delta_ms: -5 }, 'stack_burst_delta_ms must be at least 1'],
  ])('rejects %j with a 400', async (body, message) => {
    const res = await put('/api/config/stack-detection', body);
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: message });
  });

  it.each([
    [{}, 'a missing field'],
    [{ stack_burst_delta_ms: 12.5 }, 'a fractional number'],
    [{ stack_burst_delta_ms: '900' }, 'a numeric string'],
    [{ stack_burst_delta_ms: true }, 'a boolean'],
  ])('answers 422 for %o (%s)', async (body, _why) => {
    // Numeric strings and booleans are rejected at schema validation (422); Zod does not
    // coerce them to integers the way the old backend did before its handler-level 400s.
    const res = await put('/api/config/stack-detection', body);
    expect(res.status).toBe(422);
    // Nothing reached the writer: the file is not even created.
    expect(existsSync(cfgPath)).toBe(false);
  });

  it('accepts the minimum of 1', async () => {
    writeFileSync(cfgPath, '');
    const res = await put('/api/config/stack-detection', { stack_burst_delta_ms: 1 });
    expect(res.status).toBe(200);
    expect(readCfg().stack_burst_delta_ms).toBe(1);
  });

  it('creates config.yaml when it does not exist yet', async () => {
    const res = await put('/api/config/stack-detection', { stack_burst_delta_ms: 1234 });
    expect(res.status).toBe(200);
    expect(readCfg().stack_burst_delta_ms).toBe(1234);
  });
});
