/**
 * Diffs the TypeScript backend's OpenAPI document against the Flask document it
 * replaces, for every path that has been migrated so far.
 *
 * Why this is the load-bearing test of the migration: the frontend generates
 * `src/types/api.gen.ts` from this document and CI fails on drift (ADR-0013). A
 * wrong response field, a missing status code, or a path that gained a query
 * parameter it never had are all breaking changes that `tsc` cannot see, because
 * nothing in the TypeScript backend references the old contract.
 *
 * It checks four things per migrated operation:
 *   - the same set of HTTP methods
 *   - the same request parameters (name, location, required)
 *   - the same response status codes
 *   - the same response *shape*, with schema names resolved away
 *
 * It does NOT compare schema names, response descriptions, summaries or tags —
 * see `helpers/openapi-shape.ts` for why those cannot match and why it does not
 * matter. Nor does it require full coverage; the migration is incremental, and the
 * ratchet at the bottom is what stops a migrated group from regressing.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createApp } from '../src/app.js';
import { openApiDoc } from '../src/api/openapi.js';
import {
  canonical,
  paramsOf,
  requestBodyShape,
  responseShapes,
  type OpenApiDoc,
  type Shape,
} from './helpers/openapi-shape.js';

const HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete'] as const;

/**
 * Response fields the TypeScript backend adds on purpose, with the reason.
 *
 * The bar for an entry here is high: the Flask contract is the invariant, and the
 * only justification so far is a contract that cannot be served at all. Each entry
 * is *asserted* to be present, so if Flask is ever fixed to match, the stale entry
 * fails rather than silently hiding a new difference — and every other field of the
 * same response is still compared exactly.
 */
const INTENTIONAL_ADDED_FIELDS: Record<
  string,
  { paths: string[]; reason: string }
> = {
  'get /api/identity/best-photos 200': {
    paths: [
      'items[].ranking_percentile',
      'items[].corroboration_revoked',
      'items[].corroboration_revoked_by',
    ],
    reason:
      'The corroboration veto (#292, f8b6662) started returning these three fields ' +
      "from rank_best_photos, but IdentityBestPhotoItem sets extra='forbid' and was " +
      'never updated — so spectree rejects the payload and the Flask endpoint answers ' +
      '500 on the real catalog. Declaring them is the only way to serve the page.',
  },
};

/** Remove a `parent[].child` path from a normalized shape, in place. */
function stripPath(shape: Shape | undefined, path: string): boolean {
  const [head, ...rest] = path.split('.');
  if (head === undefined) return false;
  const isArray = head.endsWith('[]');
  const name = isArray ? head.slice(0, -2) : head;

  if (shape?.t !== 'object') return false;
  let child = shape.props[name];
  if (child === undefined) return false;
  if (isArray) {
    if (child.t !== 'array') return false;
    child = child.items;
  }
  if (rest.length === 0) {
    // Leaf: the parent holds it directly.
    return false;
  }
  if (rest.length === 1 && child.t === 'object') {
    const leaf = rest[0]!;
    if (!(leaf in child.props)) return false;
    delete child.props[leaf];
    child.required = child.required.filter((r) => r !== leaf);
    return true;
  }
  return stripPath(child, rest.join('.'));
}

const flask = JSON.parse(
  readFileSync(join(import.meta.dirname, 'fixtures', 'flask-openapi.json'), 'utf8'),
) as OpenApiDoc;

const ts = createApp().getOpenAPI31Document(openApiDoc()) as unknown as OpenApiDoc;

function methodsOf(pathItem: Record<string, unknown>): string[] {
  return HTTP_METHODS.filter((m) => m in pathItem).sort();
}

/** Paths present in both documents — i.e. the migrated surface. */
const sharedPaths = Object.keys(ts.paths ?? {})
  .filter((p) => p in (flask.paths ?? {}))
  .sort();

describe('OpenAPI contract vs the Flask backend', () => {
  it('emits no path Flask did not have', () => {
    const unknown = Object.keys(ts.paths ?? {}).filter((p) => !(p in (flask.paths ?? {})));
    expect(
      unknown,
      'these paths do not exist in the Flask backend — check the mount prefix and ' +
        'the trailing slash, which are part of the contract',
    ).toEqual([]);
  });

  it('has migrated at least one path', () => {
    // Guards against the diff below silently passing because it compared nothing.
    expect(sharedPaths.length).toBeGreaterThan(0);
  });

  it.each(sharedPaths)('%s matches', (path) => {
    const tsItem = ts.paths![path]!;
    const flaskItem = flask.paths![path]!;

    // A partially migrated path is a real bug: the frontend gets a 405 for the
    // methods that did not come across.
    expect(methodsOf(tsItem), `${path}: methods`).toEqual(methodsOf(flaskItem));

    for (const method of methodsOf(tsItem)) {
      const tsOp = tsItem[method] as Record<string, unknown>;
      const flaskOp = flaskItem[method] as Record<string, unknown>;

      expect(paramsOf(tsOp), `${path} ${method}: parameters`).toEqual(paramsOf(flaskOp));

      const tsResponses = responseShapes(tsOp, ts);
      const flaskResponses = responseShapes(flaskOp, flask);
      expect(Object.keys(tsResponses).sort(), `${path} ${method}: response codes`).toEqual(
        Object.keys(flaskResponses).sort(),
      );

      for (const status of Object.keys(flaskResponses)) {
        if (!(status in tsResponses)) continue; // reported above
        const tsShape = tsResponses[status]!;

        const intentional = INTENTIONAL_ADDED_FIELDS[`${method} ${path} ${status}`];
        if (intentional) {
          for (const fieldPath of intentional.paths) {
            expect(
              stripPath(tsShape, fieldPath),
              `${path} ${method} → ${status}: expected to add ${fieldPath} ` +
                `(${intentional.reason}) but it is not there — is the entry stale?`,
            ).toBe(true);
          }
        }

        expect(
          canonical(tsShape),
          `${path} ${method} → ${status}: response body shape`,
        ).toBe(canonical(flaskResponses[status]!));
      }

      const tsBody = requestBodyShape(tsOp, ts);
      const flaskBody = requestBodyShape(flaskOp, flask);
      expect(
        tsBody === null ? null : canonical(tsBody),
        `${path} ${method}: request body shape`,
      ).toBe(flaskBody === null ? null : canonical(flaskBody));
    }
  });

  it('reports migration progress', () => {
    const total = Object.keys(flask.paths ?? {}).length;
    console.log(
      `OpenAPI paths migrated: ${sharedPaths.length}/${total}\n` +
        `  remaining: ${Object.keys(flask.paths ?? {})
          .filter((p) => !(p in (ts.paths ?? {})))
          .sort()
          .join(', ')}`,
    );
    // Ratchet: once a group is migrated it must stay migrated. 52 is every path
    // Flask serves, so this is now also an equality check in practice.
    expect(sharedPaths.length).toBeGreaterThanOrEqual(52);
  });
});
