/** Shared perspective slug validation. Port of `utils/perspective_slug.py`. */

export const PERSPECTIVE_SLUG_RE = /^[a-z][a-z0-9_-]{0,63}$/;

export function isValidPerspectiveSlug(slug: string): boolean {
  return PERSPECTIVE_SLUG_RE.test(slug);
}
