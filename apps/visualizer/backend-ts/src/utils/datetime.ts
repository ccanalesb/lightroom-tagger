/**
 * Timestamp formatting that matches what Python wrote into `library.db`.
 *
 * Three distinct formats are already persisted, and they are not interchangeable:
 *
 *   - `datetime.now(timezone.utc).isoformat()` → `2026-04-12T21:40:51.334442+00:00`
 *     used for `perspectives.created_at/updated_at` and the frame-substance tables
 *   - the same truncated to whole seconds → `2026-04-12T21:40:51+00:00`
 *     used for `image_scores.scored_at`, which is the only column Python writes
 *     through `.replace(microsecond=0)`
 *   - `datetime.now().isoformat()` → `2026-09-02T13:50:07.083774` (naive, local)
 *     used for `catalog_similarity_rejections.rejected_at` and
 *     `catalog_similarity_groups.created_at`
 *
 * `Date.prototype.toISOString()` produces neither: it renders UTC with a `Z`
 * suffix and millisecond precision. That matters because these columns are sorted
 * as text (`idx_catalog_similarity_rejections_rejected_at` is a plain string index)
 * and rendered directly in the UI, so a row written by this backend must be
 * indistinguishable in shape from one written by the Python backend.
 *
 * JavaScript clocks only resolve to milliseconds, so the microsecond field is
 * zero-padded rather than invented. Fixed six-digit width keeps text ordering
 * correct against the existing rows.
 */

function pad(n: number, width: number): string {
  return String(n).padStart(width, '0');
}

/** `YYYY-MM-DDTHH:MM:SS.ffffff`, built from whichever clock parts are passed. */
function format(
  y: number,
  mo: number,
  d: number,
  h: number,
  mi: number,
  s: number,
  ms: number,
): string {
  return (
    `${pad(y, 4)}-${pad(mo, 2)}-${pad(d, 2)}` +
    `T${pad(h, 2)}:${pad(mi, 2)}:${pad(s, 2)}.${pad(ms, 3)}000`
  );
}

/** UTC instant with an explicit `+00:00` offset, as `datetime.now(timezone.utc)` writes. */
export function nowIsoUtc(date: Date = new Date()): string {
  return (
    format(
      date.getUTCFullYear(),
      date.getUTCMonth() + 1,
      date.getUTCDate(),
      date.getUTCHours(),
      date.getUTCMinutes(),
      date.getUTCSeconds(),
      date.getUTCMilliseconds(),
    ) + '+00:00'
  );
}

/** UTC instant truncated to whole seconds, as `image_scores.scored_at` holds it. */
export function nowIsoUtcSeconds(date: Date = new Date()): string {
  return nowIsoUtc(date).replace(/\.\d+(?=\+)/, '');
}

/**
 * Local wall-clock instant with no offset, as bare `datetime.now()` writes.
 *
 * Naive local time is a poor choice for a stored timestamp — it is ambiguous across
 * a DST transition — but it is what these columns already hold, and mixing offsets
 * into a text-sorted column would order rows wrongly.
 */
export function nowIsoLocal(date: Date = new Date()): string {
  return format(
    date.getFullYear(),
    date.getMonth() + 1,
    date.getDate(),
    date.getHours(),
    date.getMinutes(),
    date.getSeconds(),
    date.getMilliseconds(),
  );
}
