/**
 * Standardized response helpers.
 *
 * Routes must shape JSON through these helpers, not hand-rolled bodies.
 */
import type { Context } from 'hono';
import {
  ERROR_DB_NOT_FOUND,
  ERROR_IMAGE_FILE_NOT_FOUND,
  ERROR_IMAGE_NOT_FOUND,
  ERROR_INTERNAL_SERVER,
} from '../constants/errors.js';

/**
 * An error response whose status the route deliberately does not declare in OpenAPI.
 *
 * Throwing keeps the published contract unchanged while `app.onError` renders it.
 */
export class HttpError extends Error {
  readonly status: 400 | 401 | 403 | 404 | 409 | 429 | 503;

  constructor(status: HttpError['status'], message: string) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
  }
}

export type ResourceType = 'image' | 'media' | 'database' | 'file' | (string & {});

const NOT_FOUND_MESSAGES: Record<string, string> = {
  image: ERROR_IMAGE_NOT_FOUND,
  media: ERROR_IMAGE_NOT_FOUND,
  database: ERROR_DB_NOT_FOUND,
  file: ERROR_IMAGE_FILE_NOT_FOUND,
};

export function errorNotFound(c: Context, resourceType: ResourceType = 'resource') {
  const message = NOT_FOUND_MESSAGES[resourceType] ?? `${resourceType} not found`;
  return c.json({ error: message }, 404);
}

export function errorBadRequest(c: Context, message = 'Invalid request') {
  return c.json({ error: message }, 400);
}

export function errorServerError(c: Context, message?: string) {
  return c.json({ error: message ?? ERROR_INTERNAL_SERVER }, 500);
}

export interface Pagination {
  offset: number;
  limit: number;
  current_page: number;
  total_pages: number;
  has_more: boolean;
}

export interface PaginatedBody<T> {
  total: number;
  data: T[];
  pagination: Pagination;
}

/** Build the paginated envelope. Kept pure so it can be unit-tested without a Context. */
export function paginatedBody<T>(
  data: T[],
  total: number,
  offset: number,
  limit: number,
): PaginatedBody<T> {
  return {
    total,
    data,
    pagination: {
      offset,
      limit,
      current_page: Math.floor(offset / limit) + 1,
      total_pages: Math.floor((total + limit - 1) / limit),
      has_more: offset + limit < total,
    },
  };
}

export function successPaginated<T>(
  c: Context,
  data: T[],
  total: number,
  offset: number,
  limit: number,
) {
  return c.json(paginatedBody(data, total, offset, limit), 200);
}

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 500;

/**
 * Clamp `limit`/`offset`: unparseable values fall back to defaults rather than erroring.
 */
export function clampPagination(
  limit: unknown,
  offset: unknown,
  defaultLimit = DEFAULT_LIMIT,
): { limit: number; offset: number } {
  const toInt = (v: unknown, fallback: number): number => {
    if (v === null || v === undefined || v === '') return fallback;
    const n = Number(v);
    return Number.isFinite(n) ? Math.trunc(n) : fallback;
  };
  return {
    limit: Math.max(1, Math.min(MAX_LIMIT, toInt(limit, defaultLimit))),
    offset: Math.max(0, toInt(offset, 0)),
  };
}
