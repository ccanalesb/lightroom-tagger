/**
 * Turn `queryCatalogImages` rows into API image objects.
 * Port of `_rows_to_catalog_api_images` in `api/images/catalog.py`.
 *
 * Shared by the catalog list, visual similarity, similarity groups, stack
 * suggestions and stack members. Every one of those returns `CatalogImage`, so the
 * shaping has to live in exactly one place or the six endpoints drift.
 *
 * A note on wire fidelity: spectree validated responses against the pydantic model
 * but did **not** re-serialize them — on success it forwarded the original
 * `jsonify` bytes. So a column like `pick`, declared `bool | None` in the model but
 * stored as an INTEGER and never coerced, went out over the wire as `0`/`1` while
 * the published contract said boolean. That is preserved here rather than
 * corrected: the frontend reads it truthily, and quietly changing a value's JSON
 * type during a backend swap is exactly the sort of drift that is hard to trace
 * later. (The same validation also meant an unexpected `images` column produced a
 * 500 under `extra='forbid'`; there is no response validation here, so a new column
 * would pass through instead. The strict Zod schema documents the intent, and the
 * contract test compares it against the pydantic model.)
 */
import type { Row } from '../../db/library/catalog.js';
import type { CatalogImage } from '../schemas/catalog.js';

/** The `thumbnail_url` every catalog consumer builds for a key. */
export function catalogThumbnailUrl(key: string): string {
  return `/api/images/catalog/${key}/thumbnail`;
}

/**
 * `id` is a TEXT column holding a Lightroom row id. Only an all-digits value
 * becomes a number; anything else (including a negative number, which
 * `str.isdigit()` rejects in Python) becomes null rather than NaN.
 */
function numericId(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  // Python's `str.isdigit()` also accepts non-ASCII decimal digits, which
  // `Number.parseInt` would then mis-handle; restrict to ASCII, which is all a
  // Lightroom id can be.
  return /^[0-9]+$/.test(s) ? Number.parseInt(s, 10) : null;
}

function intOrNull(value: unknown): number | null {
  return value === null || value === undefined ? null : Math.trunc(Number(value));
}

/**
 * Rows in, `CatalogImage`s out.
 *
 * The return type is asserted rather than inferred, and that is unavoidable: the
 * object is a spread of `SELECT i.*`, so its keys are only known at runtime. The
 * assertion is the single place where "these columns are that schema" is claimed,
 * and `tests/openapi-contract.test.ts` is what checks the claim — it diffs the Zod
 * schema against the pydantic model the Flask backend published, field by field.
 *
 * The cast also papers over one known, deliberate mismatch: `pick` goes out as the
 * raw `0`/`1` from SQLite while the schema declares a boolean (see the module
 * comment). Widening the schema instead would change the published type.
 */
export function rowsToCatalogApiImages(rows: readonly Row[]): CatalogImage[] {
  return rows.map((row) => {
    const out: Row = { ...row };

    const descSummary = out.description_summary ?? null;
    const descBest = out.description_best_perspective ?? null;

    const cps = out.catalog_perspective_score ?? null;
    out.catalog_perspective_score = cps === null ? null : Math.trunc(Number(cps));
    const csp = out.catalog_score_perspective ?? null;
    // Deliberately gated on the *score*, not the slug: a slug without a score is
    // meaningless, so both fields drop together.
    out.catalog_score_perspective = cps !== null && csp !== null ? String(csp) : null;

    // "Analyzed" means a description row exists, which the LEFT JOIN reports as a
    // non-null summary. An empty summary still counts as analyzed, hence the
    // null-check rather than a truthiness test.
    const aiAnalyzed = descSummary !== null;
    out.ai_analyzed = aiAnalyzed;
    out.description_summary = aiAnalyzed ? descSummary || '' : null;
    out.description_best_perspective = aiAnalyzed ? descBest || '' : null;

    out.id = numericId(out.id);
    out.stack_id = intOrNull(out.stack_id);
    out.stack_member_count = intOrNull(out.stack_member_count);
    out.is_stack_representative =
      out.is_stack_representative === null || out.is_stack_representative === undefined
        ? false
        : Boolean(out.is_stack_representative);

    return out as unknown as CatalogImage;
  });
}

/** `Visual match (87%)` — the similarity line shown under a CLIP neighbour. */
export function clipSimilarityWhyMatchedLine(similarity: number): string {
  // Python's `round()` on a float here is half-to-even, but the input is a cosine
  // distance complement, so an exact .5 at percent granularity would require the
  // similarity to be an exact multiple of 0.005 in binary — which 0.005 is not.
  const pct = Math.max(0, Math.min(100, Math.round(Number(similarity) * 100)));
  return `Visual match (${pct}%)`;
}
