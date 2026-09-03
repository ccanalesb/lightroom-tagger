/**
 * Byte-for-byte parity against the Flask backend on the real catalog.
 *
 * This is the test that matters most for the catalog port. The unit tests use a
 * hand-built fixture with a handful of rows; this one replays 33 captured requests
 * against the live 43,451-image `library.db` and requires the TypeScript response
 * to equal Flask's exactly — every field of every row, in the same order, with the
 * same JSON types. A transposed SQL binding, a wrong `ORDER BY` tiebreaker, or a
 * `0` that became `false` all show up here and nowhere else.
 *
 * Gated on `LT_CATALOG_PARITY=1` plus `LIBRARY_DB`, because it needs the user's real
 * database. Regenerate the baseline with `scripts/capture-flask-parity.py`.
 *
 * The baseline was captured against a *copy* of the database, and every request
 * here is a GET, so running this cannot modify the catalog.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createApp } from '../src/app.js';

interface Baseline {
  keys: Record<string, string | number>;
  responses: Record<string, { status: number; json: unknown }>;
}

const fixturePath = join(import.meta.dirname, 'fixtures', 'flask-catalog-parity.json');
const enabled =
  process.env.LT_CATALOG_PARITY === '1' &&
  Boolean(process.env.LIBRARY_DB) &&
  existsSync(process.env.LIBRARY_DB ?? '') &&
  existsSync(fixturePath);

const baseline: Baseline = enabled
  ? (JSON.parse(readFileSync(fixturePath, 'utf8')) as Baseline)
  : { keys: {}, responses: {} };

const paths = Object.keys(baseline.responses).sort();

describe.skipIf(!enabled)('catalog parity with the Flask backend', () => {
  const app = createApp();

  beforeAll(() => {
    // The captured `total` counts depend on the whole catalog, so a truncated or
    // different database would produce confusing per-field diffs rather than one
    // clear failure.
    expect(paths.length).toBeGreaterThan(0);
  });

  // The Mirror scans every score in the catalog and tokenizes 147,000 rationales;
  // a few seconds is expected here, and the default 5s timeout is not enough.
  it.each(paths)('%s', { timeout: 60_000 }, async (path) => {
    const expected = baseline.responses[path]!;
    const res = await app.request(path);
    expect(res.status, `${path}: status`).toBe(expected.status);
    expect(await res.json(), `${path}: body`).toEqual(expected.json);
  });

  it('reports what was compared', () => {
    const rows = paths.reduce((sum, p) => {
      const body = baseline.responses[p]!.json as Record<string, unknown>;
      const list = (body.images ?? body.items ?? body.months ?? body.data) as unknown[] | undefined;
      return sum + (Array.isArray(list) ? list.length : 1);
    }, 0);
    console.log(
      `catalog parity: ${paths.length} requests, ${rows} rows compared field-by-field ` +
        `against Flask on the real catalog`,
    );
  });
});
