/**
 * Standardized response helpers. Port of `utils/responses.py`.
 *
 * Architectural constraint carried over from the Flask backend: routes must always
 * shape JSON through these helpers, never by hand-rolling a body and status code.
 */
import type { Context } from 'hono';
import {
  ERROR_DB_NOT_FOUND,
  ERROR_IMAGE_FILE_NOT_FOUND,
  ERROR_IMAGE_NOT_FOUND,
  ERROR_INTERNAL_SERVER,
} from '../constants/errors.js';

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
 * Clamp `limit`/`offset` the same way `utils/pagination._clamp_pagination` does:
 * unparseable values fall back to the defaults rather than erroring.
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
