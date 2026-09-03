/**
 * Identity API: best-photos ranking, mirror signature, post-next suggestions.
 * Port of `api/identity.py`.
 *
 * Thumbnails are not inlined: responses carry `image_key` and `filename` so the
 * frontend reuses the catalog thumbnail route.
 *
 * These are the only routes in the Flask backend where spectree was given a `query=`
 * model, so they are the only ones whose query parameters appear in the contract —
 * and the models are NOT `extra='forbid'`, so unknown parameters are ignored.
 *
 * The integer parameters use `z.coerce` because that is what pydantic's lax mode
 * did: a query value arrives as a string, and `int | None` accepted `"4"` while
 * rejecting `"abc"` and `"4.5"`. The one input where the two differ is `?limit=`
 * (empty): pydantic rejected it, Zod coerces it to 0, which the pagination clamp
 * then lifts to 1. Flask's rejection surfaced as `500 {"error": "??? Unknown Error:
 * None"}` anyway, because `with_db` swallowed spectree's abort — so nothing was
 * relying on it.
 */
import { createRoute, z } from '@hono/zod-openapi';
import { libraryDb, type LibraryEnv } from '../db/library/with-db.js';
import { buildLensExemplars, buildMirror } from '../identity/mirror.js';
import { rankBestPhotos } from '../identity/ranking.js';
import { suggestWhatToPostNext } from '../identity/suggest-post.js';
import { clampPagination } from '../utils/responses.js';
import { createOpenApiApp } from './openapi.js';
import { jsonBody, withValidationError } from './route-helpers.js';
import { ErrorBody } from './schemas/errors.js';
import {
  IdentityBestPhotosResponse,
  MirrorLensExemplarsResponse,
  MirrorResponse,
  PostNextSuggestionsResponse,
} from './schemas/identity.js';

export const identityRoutes = createOpenApiApp<LibraryEnv>();

/** An optional integer query parameter, emitted as `integer | null`. */
const intParam = z.coerce.number().int().nullish();

identityRoutes.use('/identity/*', libraryDb());

type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

/**
 * `min_perspectives`: an integer of at least 1, silently capped at 50.
 *
 * The cap is a clamp rather than a rejection — asking for 200 perspectives is not a
 * client error, there just are not that many.
 */
function parseMinPerspectives(raw: string | undefined): Parsed<number | null> {
  if (raw === undefined || raw.trim() === '') return { ok: true, value: null };
  if (!/^\s*[+-]?\d+\s*$/.test(raw)) {
    return { ok: false, error: 'min_perspectives must be an integer' };
  }
  const v = Number.parseInt(raw.trim(), 10);
  if (v < 1) return { ok: false, error: 'min_perspectives must be at least 1' };
  return { ok: true, value: Math.min(v, 50) };
}

function parseSortByDate(raw: string | undefined): Parsed<'newest' | 'oldest' | null> {
  const value = (raw ?? '').trim().toLowerCase();
  if (!value) return { ok: true, value: null };
  if (value !== 'newest' && value !== 'oldest') {
    return { ok: false, error: 'sort_by_date must be newest or oldest' };
  }
  return { ok: true, value };
}

/**
 * `posted`: a tri-state.
 *
 * Unlike the catalog list — which silently ignores an unrecognized value — this one
 * rejects it, and accepts `1`/`yes`/`0`/`no` as well as the booleans.
 */
function parsePosted(raw: string | undefined): Parsed<boolean | null> {
  if (raw === undefined || raw.trim() === '') return { ok: true, value: null };
  const key = raw.trim().toLowerCase();
  if (['true', '1', 'yes'].includes(key)) return { ok: true, value: true };
  if (['false', '0', 'no'].includes(key)) return { ok: true, value: false };
  return { ok: false, error: 'posted must be true or false' };
}

// --- best photos ------------------------------------------------------------

const bestPhotosRoute = createRoute({
  method: 'get',
  path: '/identity/best-photos',
  tags: ['identity'],
  request: {
    query: z.object({
      limit: intParam,
      offset: intParam,
      min_perspectives: intParam,
      sort_by_date: z.string().nullish(),
      posted: z.string().nullish(),
    }),
  },
  responses: withValidationError({
    200: {
      description: 'Ranked eligible catalog images',
      content: jsonBody(IdentityBestPhotosResponse),
    },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

identityRoutes.openapi(bestPhotosRoute, (c) => {
  const { limit, offset } = clampPagination(c.req.query('limit'), c.req.query('offset'));
  const minP = parseMinPerspectives(c.req.query('min_perspectives'));
  if (!minP.ok) return c.json({ error: minP.error }, 400);
  const sortByDate = parseSortByDate(c.req.query('sort_by_date'));
  if (!sortByDate.ok) return c.json({ error: sortByDate.error }, 400);
  const posted = parsePosted(c.req.query('posted'));
  if (!posted.ok) return c.json({ error: posted.error }, 400);

  const { items, total, meta } = rankBestPhotos(c.get('libraryDb'), {
    limit,
    offset,
    minPerspectives: minP.value,
    sortByDate: sortByDate.value,
    posted: posted.value,
  });
  return c.json({ items, total, meta } as z.infer<typeof IdentityBestPhotosResponse>, 200);
});

// --- mirror -----------------------------------------------------------------

const mirrorRoute = createRoute({
  method: 'get',
  path: '/identity/mirror',
  tags: ['identity'],
  responses: withValidationError({
    200: { description: 'Crowned signature techniques', content: jsonBody(MirrorResponse) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

identityRoutes.openapi(mirrorRoute, (c) =>
  c.json(buildMirror(c.get('libraryDb')) as z.infer<typeof MirrorResponse>, 200),
);

const lensExemplarsRoute = createRoute({
  method: 'get',
  path: '/identity/mirror/lens/{slug}/exemplars',
  tags: ['identity'],
  request: {
    params: z.object({ slug: z.string() }),
    query: z.object({ limit: intParam, offset: intParam }),
  },
  responses: withValidationError({
    200: { description: 'Exemplar rail', content: jsonBody(MirrorLensExemplarsResponse) },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

identityRoutes.openapi(lensExemplarsRoute, (c) => {
  // Default 24, not the shared helper's 50 — it is the initial exemplar rail size.
  const { limit, offset } = clampPagination(c.req.query('limit'), c.req.query('offset'), 24);
  try {
    return c.json(
      buildLensExemplars(c.get('libraryDb'), c.req.param('slug'), { offset, limit }),
      200,
    );
  } catch (e) {
    // An unknown or deactivated slug is a 400, matching the ValueError branch.
    if (e instanceof RangeError) return c.json({ error: e.message }, 400);
    throw e;
  }
});

// --- suggestions ------------------------------------------------------------

const suggestionsRoute = createRoute({
  method: 'get',
  path: '/identity/suggestions',
  tags: ['identity'],
  request: {
    query: z.object({
      limit: intParam,
      offset: intParam,
      sort_by_date: z.string().nullish(),
    }),
  },
  responses: withValidationError({
    200: {
      description: 'What to post next',
      content: jsonBody(PostNextSuggestionsResponse),
    },
    400: { description: 'Bad Request', content: jsonBody(ErrorBody) },
    500: { description: 'Server error', content: jsonBody(ErrorBody) },
  }),
});

identityRoutes.openapi(suggestionsRoute, (c) => {
  // Default 20 here.
  const { limit, offset } = clampPagination(c.req.query('limit'), c.req.query('offset'), 20);
  const sortByDate = parseSortByDate(c.req.query('sort_by_date'));
  if (!sortByDate.ok) return c.json({ error: sortByDate.error }, 400);

  const payload = suggestWhatToPostNext(c.get('libraryDb'), {
    limit,
    offset,
    sortByDate: sortByDate.value,
  });
  return c.json(
    {
      candidates: payload.candidates,
      total: payload.total,
      meta: payload.meta,
      empty_state: payload.empty_state,
    } as z.infer<typeof PostNextSuggestionsResponse>,
    200,
  );
});
