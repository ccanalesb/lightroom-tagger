/**
 * Burst stack members and mutations.
 *
 * Reuses catalog row shaping so stack members match the same image in the grid.
 */
import { createRoute, z } from '@hono/zod-openapi';
import { ERROR_IMAGE_NOT_FOUND } from '../../constants/errors.js';
import { queryCatalogImagesByKeys } from '../../db/library/catalog-query.js';
import {
  listPendingStackSuggestions,
  rejectCatalogSimilarityPair,
  stackAcceptSuggestionPair,
} from '../../db/library/stack-suggestions.js';
import {
  listStackMemberKeys,
  stackExists,
  stackMergeInto,
  StackMutationError,
  stackSetRepresentative,
  stackSplitMemberOut,
} from '../../db/library/stacks.js';
import { libraryDb, type LibraryEnv } from '../library-db.js';
import { libraryWrite } from '../../db/library/write.js';
import { HttpError } from '../../utils/responses.js';
import { createOpenApiApp } from '../openapi.js';
import { jsonBody, withValidationError } from '../route-helpers.js';
import { ErrorBody } from '../schemas/errors.js';
import {
  StackMembersResponse,
  StackMergeRequest,
  StackMergeResponse,
  StackRepresentativeRequest,
  StackRepresentativeResponse,
  StackSplitMemberRequest,
  StackSplitMemberResponse,
  StackSuggestionAcceptResponse,
  StackSuggestionPairRequest,
  StackSuggestionRejectResponse,
  StackSuggestionsResponse,
} from '../schemas/stacks.js';
import { catalogThumbnailUrl, rowsToCatalogApiImages } from './row-shaping.js';

export const stacksRoutes = createOpenApiApp<LibraryEnv>();

stacksRoutes.use('/images/stacks/*', libraryDb({ writeForMethods: ['POST'] }));

/**
 * Stack pagination: limit capped at 100, default 20 — not the shared catalog helper
 * (500 / 50). Keep separate so a tidy-up does not merge the two.
 */
function clampStackPagination(
  limitRaw: string | undefined,
  offsetRaw: string | undefined,
): { limit: number; offset: number } {
  // Unparseable query values fall back to the default.
  const toInt = (raw: string | undefined, fallback: number): number =>
    raw !== undefined && /^\s*[+-]?\d+\s*$/.test(raw) ? Number.parseInt(raw.trim(), 10) : fallback;
  return {
    limit: Math.max(1, Math.min(toInt(limitRaw, 20), 100)),
    offset: Math.max(0, toInt(offsetRaw, 0)),
  };
}

/** A non-empty string; `""` is rejected even though it is schema-valid. */
function nonEmpty(value: string): string | null {
  return value.length > 0 ? value : null;
}

const stackIdParams = z.object({ stack_id: z.string() });

/**
 * Parse a `stack_id` path segment.
 *
 * A non-numeric id throws the legacy catch-all 400; an integer below 1 returns null
 * for the caller's 404. OpenAPI requires `{stack_id}` as a string, not an int converter.
 */
function parseStackId(raw: string): number | null {
  if (!/^\d+$/.test(raw)) {
    throw new HttpError(400, "invalid image_type; expected one of ('catalog', 'instagram')");
  }
  const n = Number.parseInt(raw, 10);
  return n >= 1 ? n : null;
}

// --- suggestions ------------------------------------------------------------

const suggestionsRoute = createRoute({
  method: 'get',
  path: '/images/stacks/suggestions',
  tags: ['images-stacks'],
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackSuggestionsResponse) },
  }),
});

stacksRoutes.openapi(suggestionsRoute, (c) => {
  const db = c.get('libraryDb');
  const { limit, offset } = clampStackPagination(c.req.query('limit'), c.req.query('offset'));
  const { rows, total } = listPendingStackSuggestions(db, { limit, offset });

  const items = [];
  for (const row of rows) {
    const keys = [String(row.seed_key), String(row.candidate_key)];
    const images = rowsToCatalogApiImages(queryCatalogImagesByKeys(db, keys));
    const byKey = new Map(images.map((img) => [String(img.key), img]));
    const imageA = byKey.get(String(row.seed_key));
    const imageB = byKey.get(String(row.candidate_key));
    // Either end being collapsed out of the primary grid drops the pair: a
    // suggestion you cannot see both halves of is not reviewable.
    if (!imageA || !imageB) continue;

    imageA.thumbnail_url = catalogThumbnailUrl(String(imageA.key));
    imageB.thumbnail_url = catalogThumbnailUrl(String(imageB.key));
    items.push({
      group_id: Math.trunc(row.group_id),
      image_a: imageA,
      image_b: imageB,
      similarity: Number(row.similarity ?? 0),
      why_matched: String(row.why_matched ?? ''),
      time_gap_seconds:
        row.time_gap_seconds === null || row.time_gap_seconds === undefined
          ? null
          : Math.trunc(row.time_gap_seconds),
    });
  }
  return c.json({ items, total }, 200);
});

const acceptRoute = createRoute({
  method: 'post',
  path: '/images/stacks/suggestions/accept',
  tags: ['images-stacks'],
  request: { body: { content: jsonBody(StackSuggestionPairRequest) } },
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackSuggestionAcceptResponse) },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    404: { description: 'Not Found', content: jsonBody(ErrorBody) },
  }),
});

stacksRoutes.openapi(acceptRoute, (c) => {
  const db = c.get('libraryDb');
  const { image_key_a: rawA, image_key_b: rawB } = c.req.valid('json');
  const keyA = nonEmpty(rawA);
  const keyB = nonEmpty(rawB);
  if (!keyA || !keyB) return c.json({ error: 'image_key_a and image_key_b required' }, 400);

  try {
    const result = libraryWrite(db, () => stackAcceptSuggestionPair(db, keyA.trim(), keyB.trim()));
    // The merge branch also returns `merged_stack_id`, which this response model
    // forbids — narrow rather than spread.
    return c.json({ stack: result.stack }, 200);
  } catch (e) {
    if (e instanceof StackMutationError) {
      // This route reports a missing *image*, unlike the stack-scoped routes.
      if (e.statusCode === 404) return c.json({ error: ERROR_IMAGE_NOT_FOUND }, 404);
      if (e.statusCode < 500) return c.json({ error: e.message }, 400);
    }
    throw e;
  }
});

const rejectRoute = createRoute({
  method: 'post',
  path: '/images/stacks/suggestions/reject',
  tags: ['images-stacks'],
  request: { body: { content: jsonBody(StackSuggestionPairRequest) } },
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackSuggestionRejectResponse) },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
  }),
});

stacksRoutes.openapi(rejectRoute, (c) => {
  const db = c.get('libraryDb');
  const { image_key_a: rawA, image_key_b: rawB } = c.req.valid('json');
  const keyA = nonEmpty(rawA);
  const keyB = nonEmpty(rawB);
  if (!keyA || !keyB) return c.json({ error: 'image_key_a and image_key_b required' }, 400);

  const a = keyA.trim();
  const b = keyB.trim();
  if (a === b) return c.json({ error: 'image_key_a and image_key_b must differ' }, 400);

  libraryWrite(db, () => rejectCatalogSimilarityPair(db, a, b));
  return c.json({ image_key_a: a, image_key_b: b, rejected: true }, 200);
});

// --- members ----------------------------------------------------------------

const membersRoute = createRoute({
  method: 'get',
  path: '/images/stacks/{stack_id}/members',
  tags: ['images-stacks'],
  request: { params: stackIdParams },
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackMembersResponse) },
    404: { description: 'Not Found', content: jsonBody(ErrorBody) },
  }),
});

stacksRoutes.openapi(membersRoute, (c) => {
  const db = c.get('libraryDb');
  const stackId = parseStackId(c.req.param('stack_id'));
  if (stackId === null) return c.json({ error: 'stack not found' }, 404);
  if (!stackExists(db, stackId)) return c.json({ error: 'stack not found' }, 404);

  const keys = listStackMemberKeys(db, stackId);
  if (keys.length === 0) return c.json({ items: [] }, 200);

  // `primaryGridOnly: false` is the point of this query — the reason to open a stack
  // is to see the members the grid collapses away.
  const items = rowsToCatalogApiImages(
    queryCatalogImagesByKeys(db, keys, { scorePerspective: null, primaryGridOnly: false }),
  );
  for (const it of items) it.thumbnail_url = catalogThumbnailUrl(String(it.key));
  return c.json({ items }, 200);
});

// --- mutations --------------------------------------------------------------

/**
 * Stack mutation error mapping is repeated inline: a helper returning `Response`
 * erases the typed-response information `@hono/zod-openapi` checks against.
 */

const splitMemberRoute = createRoute({
  method: 'post',
  path: '/images/stacks/{stack_id}/split-member',
  tags: ['images-stacks'],
  request: { params: stackIdParams, body: { content: jsonBody(StackSplitMemberRequest) } },
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackSplitMemberResponse) },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    404: { description: 'Not Found', content: jsonBody(ErrorBody) },
  }),
});

stacksRoutes.openapi(splitMemberRoute, (c) => {
  const db = c.get('libraryDb');
  const stackId = parseStackId(c.req.param('stack_id'));
  if (stackId === null) return c.json({ error: 'stack not found' }, 404);

  const imageKey = nonEmpty(c.req.valid('json').image_key);
  if (!imageKey) return c.json({ error: 'image_key required' }, 400);

  try {
    return c.json(libraryWrite(db, () => stackSplitMemberOut(db, stackId, imageKey.trim())), 200);
  } catch (e) {
    if (e instanceof StackMutationError) {
      if (e.statusCode === 404) return c.json({ error: 'stack not found' }, 404);
      if (e.statusCode < 500) return c.json({ error: e.message }, 400);
    }
    throw e;
  }
});

const mergeRoute = createRoute({
  method: 'post',
  path: '/images/stacks/{target_stack_id}/merge',
  tags: ['images-stacks'],
  request: {
    params: z.object({ target_stack_id: z.string() }),
    body: { content: jsonBody(StackMergeRequest) },
  },
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackMergeResponse) },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    404: { description: 'Not Found', content: jsonBody(ErrorBody) },
  }),
});

stacksRoutes.openapi(mergeRoute, (c) => {
  const db = c.get('libraryDb');
  const targetStackId = parseStackId(c.req.param('target_stack_id'));
  if (targetStackId === null) return c.json({ error: 'stack not found' }, 404);

  const sourceStackId = c.req.valid('json').source_stack_id;
  try {
    return c.json(libraryWrite(db, () => stackMergeInto(db, targetStackId, sourceStackId)), 200);
  } catch (e) {
    if (e instanceof StackMutationError) {
      if (e.statusCode === 404) return c.json({ error: 'stack not found' }, 404);
      if (e.statusCode < 500) return c.json({ error: e.message }, 400);
    }
    throw e;
  }
});

const representativeRoute = createRoute({
  method: 'post',
  path: '/images/stacks/{stack_id}/representative',
  tags: ['images-stacks'],
  request: { params: stackIdParams, body: { content: jsonBody(StackRepresentativeRequest) } },
  responses: withValidationError({
    200: { description: 'OK', content: jsonBody(StackRepresentativeResponse) },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    404: { description: 'Not Found', content: jsonBody(ErrorBody) },
  }),
});

stacksRoutes.openapi(representativeRoute, (c) => {
  const db = c.get('libraryDb');
  const stackId = parseStackId(c.req.param('stack_id'));
  if (stackId === null) return c.json({ error: 'stack not found' }, 404);

  const imageKey = nonEmpty(c.req.valid('json').image_key);
  if (!imageKey) return c.json({ error: 'image_key required' }, 400);

  try {
    return c.json(libraryWrite(db, () => stackSetRepresentative(db, stackId, imageKey.trim())), 200);
  } catch (e) {
    if (e instanceof StackMutationError) {
      if (e.statusCode === 404) return c.json({ error: 'stack not found' }, 404);
      if (e.statusCode < 500) return c.json({ error: e.message }, 400);
    }
    throw e;
  }
});
