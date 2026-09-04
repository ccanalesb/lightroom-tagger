/**
 * The one pass over the score table that every identity view starts from.
 *
 * `SCORES_BASE_SQL` returns 146,983 rows on this catalog, and the Mirror, the
 * best-photos ranking and the post-next suggestions all need the same three
 * things out of it: which perspectives are live, the within-perspective
 * percentile of every cell, and the cells grouped by image. Building that twice
 * was two full reads and two near-identical loops that had to agree on slug
 * filtering, display-name fallback and lookup keys or the percentiles came back
 * `undefined`.
 */
import type { Db } from '../db/connection.js';
import { activePerspectiveSlugs, SCORES_BASE_SQL, type ScoreRow } from './aggregates.js';
import { cellKey, computeWithinPerspectivePercentileLookup } from './percentiles.js';

/**
 * One `(image, perspective)` score, with everything any consumer needs.
 *
 * `percentile` is raw and unrounded: the Mirror ranks on full precision, and the
 * best-photos view rounds to six decimals on the way out. Rounding here would
 * quietly change which of the two is authoritative.
 */
export interface CatalogScoreCell {
  perspective_slug: string;
  display_name: string;
  score: number;
  percentile: number;
  rationale: string;
  model_used: string;
  prompt_version: string;
  scored_at: string;
}

export interface CatalogScoreIndex {
  activeSlugs: string[];
  slugSet: Set<string>;
  displayBySlug: Map<string, string>;
  /** Active-perspective cells only, keyed by image. Insertion order is the
   *  pre-sort order of every list built from it, so it is the final tiebreaker. */
  byImage: Map<string, CatalogScoreCell[]>;
  rationalesBySlug: Map<string, string[]>;
  corpusRationales: string[];
  percentileLookup: Map<string, number>;
  totalCatalog: number;
}

export function buildCatalogScoreIndex(db: Db): CatalogScoreIndex {
  const activeSlugs = activePerspectiveSlugs(db);
  const slugSet = new Set(activeSlugs);
  const rows = db.prepare(SCORES_BASE_SQL).all() as ScoreRow[];

  const displayBySlug = new Map<string, string>();
  for (const r of rows) {
    const slug = String(r.perspective_slug);
    if (!slugSet.has(slug)) continue;
    if (!displayBySlug.has(slug)) {
      displayBySlug.set(slug, String(r.perspective_display_name || slug));
    }
  }

  // `rows` is handed over so the score table is read once, not twice.
  const percentileLookup = computeWithinPerspectivePercentileLookup(db, rows);
  const totalCatalog = Math.trunc(
    (db.prepare('SELECT COUNT(*) AS c FROM images').get() as { c: number }).c,
  );

  const byImage = new Map<string, CatalogScoreCell[]>();
  const rationalesBySlug = new Map<string, string[]>(activeSlugs.map((s) => [s, []]));
  const corpusRationales: string[] = [];

  for (const r of rows) {
    const slug = String(r.perspective_slug);
    if (!slugSet.has(slug)) continue;
    const imageKey = String(r.image_key);
    const rationale = r.rationale ?? '';
    if (rationale.trim()) {
      rationalesBySlug.get(slug)?.push(rationale);
      corpusRationales.push(rationale);
    }
    const cell: CatalogScoreCell = {
      perspective_slug: slug,
      display_name: displayBySlug.get(slug) ?? slug,
      score: Math.trunc(r.score),
      percentile: percentileLookup.get(cellKey(imageKey, slug))!,
      rationale,
      model_used: r.model_used ?? '',
      prompt_version: r.prompt_version ?? '',
      scored_at: r.scored_at ?? '',
    };
    const list = byImage.get(imageKey);
    if (list) list.push(cell);
    else byImage.set(imageKey, [cell]);
  }

  return {
    activeSlugs,
    slugSet,
    displayBySlug,
    byImage,
    rationalesBySlug,
    corpusRationales,
    percentileLookup,
    totalCatalog,
  };
}
