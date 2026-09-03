/**
 * Image description read routes. Port of the GET routes in `api/descriptions.py`.
 *
 * NOT YET PORTED: `POST /api/descriptions/{image_key}/generate`. It calls
 * `describe_matched_image`, which needs the vision provider pipeline from the
 * library core — a later slice. Omitting the whole path (rather than serving it
 * with a stub) keeps the contract honest: the OpenAPI document simply does not
 * advertise it yet, and `tests/openapi-paths.test.ts` lists it as remaining.
 */
import { createRoute, z } from '@hono/zod-openapi';
import {
  getAllImagesWithDescriptions,
  getImageDescription,
} from '../db/library/descriptions.js';
import { libraryDb, type LibraryEnv } from '../db/library/with-db.js';
import { HttpError } from '../utils/responses.js';
import { createOpenApiApp } from './openapi.js';
import { jsonBody, redirectToTrailingSlash, withValidationError } from './route-helpers.js';
import { ErrorBody } from './schemas/errors.js';
import {
  DescriptionGetResponse,
  DescriptionsListResponse,
} from './schemas/descriptions.js';

export const descriptionsRoutes = createOpenApiApp<LibraryEnv>();

descriptionsRoutes.use('/descriptions/*', libraryDb());
redirectToTrailingSlash(descriptionsRoutes, '/descriptions');

/**
 * `limit`/`offset` use Flask's `type=int` semantics: an unparseable value falls
 * back to the default rather than erroring. Note this is NOT the clamped
 * `_clamp_pagination` helper — `api/descriptions.py` deliberately does not clamp,
 * so no bounds are imposed here either.
 */
function intArg(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw === '') return fallback;
  const n = Number(raw);
  return Number.isInteger(n) ? n : fallback;
}

const listRoute = createRoute({
  method: 'get',
  path: '/descriptions/',
  tags: ['descriptions'],
  responses: withValidationError({
    200: { description: 'Images with descriptions', content: jsonBody(DescriptionsListResponse) },
  }),
});

descriptionsRoutes.openapi(listRoute, (c) => {
  const imageType = c.req.query('image_type');
  // Catalog-only since #218; anything else is a client error, not empty results.
  //
  // Thrown rather than returned: spectree documented only 200 and 422 for this
  // route, so declaring the 400 would change the published contract even though
  // Flask really does answer 400 here. See `HttpError`.
  if (imageType !== undefined && imageType !== '' && imageType !== 'catalog') {
    throw new HttpError(400, `Invalid image_type: ${imageType}`);
  }

  const describedOnly = c.req.query('described_only') === 'true';
  const limit = intArg(c.req.query('limit'), 50);
  const offset = intArg(c.req.query('offset'), 0);

  const { items, total } = getAllImagesWithDescriptions(c.get('libraryDb'), {
    describedOnly,
    limit,
    offset,
  });

  return c.json(
    {
      total,
      items,
      pagination: {
        offset,
        limit,
        current_page: Math.floor(offset / limit) + 1,
        // Python emits 0 pages for an empty result, not 1 — the `if total` guard.
        total_pages: total ? Math.floor((total + limit - 1) / limit) : 0,
        has_more: offset + limit < total,
      },
    },
    200,
  );
});

const detailRoute = createRoute({
  method: 'get',
  path: '/descriptions/{image_key}',
  tags: ['descriptions'],
  request: { params: z.object({ image_key: z.string() }) },
  responses: withValidationError({
    200: { description: 'One description, or null', content: jsonBody(DescriptionGetResponse) },
  }),
});

descriptionsRoutes.openapi(detailRoute, (c) => {
  // A missing description is `{"description": null}` with a 200, not a 404 —
  // the UI renders an empty panel rather than treating it as an error.
  const desc = getImageDescription(c.get('libraryDb'), c.req.param('image_key'));
  return c.json({ description: desc as z.infer<typeof DescriptionGetResponse>['description'] }, 200);
});
