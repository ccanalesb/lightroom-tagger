/**
 * Guards the API contract's path strings against the Flask backend they replace.
 *
 * Why this exists: the frontend generates `src/types/api.gen.ts` from the OpenAPI
 * document, keyed on the exact path string, and CI fails on drift (ADR-0013). A
 * mount-prefix mistake is therefore a breaking change that a typecheck cannot see.
 * It already happened once — `app.route('/api/perspectives', ...)` with a child path
 * of `'/'` emits `/api/perspectives`, while Flask's blueprint emitted
 * `/api/perspectives/` with the trailing slash.
 *
 * The test asserts two directions:
 *   - every path the TS backend emits must exist in Flask's inventory, with the
 *     same methods (no invented or renamed routes)
 *   - progress is reported, so a migrated group cannot quietly regress to unmigrated
 *
 * It deliberately does NOT require full coverage yet; the migration is incremental.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createApp } from '../src/app.js';
import { openApiDoc } from '../src/api/openapi.js';

const flask = JSON.parse(
  readFileSync(join(import.meta.dirname, 'fixtures', 'flask-openapi-paths.json'), 'utf8'),
) as { paths: Record<string, string[]> };

const HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete'];

function tsPaths(): Record<string, string[]> {
  const spec = createApp().getOpenAPI31Document(openApiDoc());
  const out: Record<string, string[]> = {};
  for (const [path, ops] of Object.entries(spec.paths ?? {})) {
    out[path] = Object.keys(ops as object)
      .filter((m) => HTTP_METHODS.includes(m))
      .sort();
  }
  return out;
}

describe('OpenAPI paths match the Flask contract', () => {
  it('emits no path Flask did not have', () => {
    const unknown = Object.keys(tsPaths()).filter((p) => !(p in flask.paths));
    expect(
      unknown,
      'these paths do not exist in the Flask backend — check the mount prefix and ' +
        'the trailing slash, which are part of the contract',
    ).toEqual([]);
  });

  it('emits the same methods per path as Flask', () => {
    const ts = tsPaths();
    const mismatches: string[] = [];
    for (const [path, methods] of Object.entries(ts)) {
      const expected = flask.paths[path];
      if (!expected) continue; // covered by the previous test
      const missing = expected.filter((m) => !methods.includes(m));
      const extra = methods.filter((m) => !expected.includes(m));
      if (missing.length || extra.length) {
        mismatches.push(
          `${path}: flask=[${expected}] ts=[${methods}]` +
            (missing.length ? ` missing=[${missing}]` : '') +
            (extra.length ? ` extra=[${extra}]` : ''),
        );
      }
    }
    // A partially migrated path is a real bug: the frontend would get a 405 for the
    // methods that did not come across.
    expect(mismatches).toEqual([]);
  });

  it('reports migration progress', () => {
    const ts = tsPaths();
    const migrated = Object.keys(ts).filter((p) => p in flask.paths);
    const total = Object.keys(flask.paths).length;
    console.log(
      `OpenAPI paths migrated: ${migrated.length}/${total}\n` +
        `  remaining: ${Object.keys(flask.paths)
          .filter((p) => !(p in ts))
          .join(', ')}`,
    );
    // Ratchet: once a group is migrated it must stay migrated.
    expect(migrated.length).toBeGreaterThanOrEqual(8);
  });
});
