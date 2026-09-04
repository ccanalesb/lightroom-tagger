/**
 * Post-next suggestions from coverage-eligible catalog gaps.
 */
import type { Db } from '../db/connection.js';
import { computeImagePeakPercentileScores, type PeakPercentileItem } from './percentiles.js';
import { buildCatalogScoreIndex } from './score-index.js';
import { sortByRanking } from './sort.js';
import { imageMetaMap } from './ranking.js';
import { computeSignatureStats } from './signature.js';

/**
 * Round halves to even, not away from zero.
 *
 * Load-bearing for the p90 index: `round(0.9 * (n - 1))` at exactly 4.5 picks
 * index 4 under half-to-even but 5 under `Math.round`.
 */
export function roundHalfEven(value: number): number {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

interface PerPerspectiveLike {
  perspective_slug?: string;
  display_name?: string;
  percentile?: number;
}

/** The image's strongest lens: highest percentile, then slug for determinism. */
function peakPerspective(perPerspective: readonly PerPerspectiveLike[]): PerPerspectiveLike {
  return [...perPerspective].sort((a, b) => {
    const byPct = (b.percentile ?? 0) - (a.percentile ?? 0);
    if (byPct !== 0) return byPct;
    const sa = String(a.perspective_slug ?? '');
    const sb = String(b.perspective_slug ?? '');
    return sa < sb ? -1 : sa > sb ? 1 : 0;
  })[0]!;
}

export interface PostNextCandidate {
  image_key: string;
  filename: string;
  date_taken: string;
  rating: number;
  peak_percentile: number;
  peak_perspective_slug: string;
  peak_perspective_display_name: string;
  is_signature: boolean;
  perspectives_covered: number;
  per_perspective: PeakPercentileItem['per_perspective'];
  reasons: string[];
  reason_codes: string[];
}

export interface PostNextPayload {
  candidates: PostNextCandidate[];
  total: number;
  meta: Record<string, unknown>;
  empty_state: string | null;
}

/**
 * Unposted, coverage-eligible catalog images with heuristic reasons (D-44–D-46).
 *
 * `sortByDate` only moves the tiebreaker; the corroboration-vetoed ranking
 * percentile stays the primary sort key.
 */
export function suggestWhatToPostNext(
  db: Db,
  opts: { limit: number; offset?: number; sortByDate?: 'newest' | 'oldest' | null },
): PostNextPayload {
  const sortByDate = opts.sortByDate ?? null;
  if (sortByDate !== null && sortByDate !== 'newest' && sortByDate !== 'oldest') {
    throw new RangeError("sort_by_date must be 'newest' or 'oldest'");
  }
  const offset = opts.offset ?? 0;

  // One index, three consumers: the score table is scanned once rather than
  // three times.
  const scan = buildCatalogScoreIndex(db);
  const { items, meta: peakMeta } = computeImagePeakPercentileScores(scan, {
    includeIneligible: false,
  });
  const crowned = new Set(
    computeSignatureStats(scan)
      .stats.filter((s) => s.crowned)
      .map((s) => s.perspective_slug),
  );

  const eligibleKeys = items.filter((i) => i.eligible).map((i) => String(i.image_key));
  const imgMeta = imageMetaMap(db, eligibleKeys);

  interface Candidate extends PeakPercentileItem {
    filename?: string;
    date_taken?: string;
    rating?: number;
    instagram_posted?: boolean;
    peak_perspective_slug: string;
    peak_perspective_display_name: string;
    is_signature: boolean;
  }

  const candidatesFull: Candidate[] = [];
  for (const i of items) {
    if (!i.eligible) continue;
    const k = String(i.image_key);
    const im = imgMeta.get(k);
    // Already posted: not a suggestion for what to post next.
    if (im?.instagram_posted) continue;
    const per = i.per_perspective ?? [];
    const peakLens = per.length > 0 ? peakPerspective(per) : {};
    const slug = String(peakLens.perspective_slug ?? '');
    candidatesFull.push({
      ...i,
      ...(im ?? {}),
      peak_perspective_slug: slug,
      peak_perspective_display_name: String(peakLens.display_name ?? slug),
      is_signature: slug ? crowned.has(slug) : false,
    });
  }

  sortByRanking(candidatesFull, sortByDate);

  // p90 of the *unposted eligible* population, not the whole catalog: the reason
  // code means "strong among what you have left to post".
  const rankings = candidatesFull.map((c) => Number(c.ranking_percentile));
  let p90 = 1;
  if (rankings.length > 0) {
    const sorted = [...rankings].sort((a, b) => a - b);
    const idx = Math.max(0, roundHalfEven(0.9 * (sorted.length - 1)));
    p90 = sorted[idx]!;
  }

  const suggestionsMeta = {
    weighting: peakMeta.weighting,
    ranking_key: peakMeta.ranking_key,
    corroboration_rule: peakMeta.corroboration_rule,
    min_perspectives_used: peakMeta.min_perspectives_used,
    coverage_rule: peakMeta.coverage_rule,
    high_score_rule:
      'reason code high_score_unposted when ranking_percentile >= p90 of eligible ' +
      "unposted images' corroboration-vetoed ranking percentiles.",
  };

  const total = candidatesFull.length;
  const lim = Math.max(0, opts.limit);
  const page = candidatesFull.slice(offset, offset + lim);

  const outCandidates: PostNextCandidate[] = page.map((cand) => {
    const reasons: string[] = [];
    const codes: string[] = [];
    const ranking = Number(cand.ranking_percentile);
    const lensName = String(cand.peak_perspective_display_name || '');

    if (ranking >= p90) {
      reasons.push(
        'Strong ranking percentile among scored, unposted catalog images ' +
          `(ranking_percentile=${ranking.toFixed(4)}).`,
      );
      codes.push('high_score_unposted');
    }

    if (lensName) {
      reasons.push(
        cand.is_signature
          ? `Peak lens is ${lensName}, one of your crowned signature techniques.`
          : `Peak lens is ${lensName}.`,
      );
    }

    // Only when no *code* was added — the lens sentence above is a reason but not a
    // reason code, so an image can carry it and still fall back to eligible_unposted.
    if (codes.length === 0) {
      reasons.push(
        'Unposted catalog image with sufficient perspective coverage; ' +
          'ranked by corroboration-vetoed ranking percentile among eligible candidates.',
      );
      codes.push('eligible_unposted');
    }

    return {
      image_key: cand.image_key,
      filename: cand.filename ?? '',
      date_taken: cand.date_taken ?? '',
      rating: cand.rating ?? 0,
      peak_percentile: cand.peak_percentile,
      peak_perspective_slug: cand.peak_perspective_slug ?? '',
      peak_perspective_display_name: cand.peak_perspective_display_name ?? '',
      is_signature: Boolean(cand.is_signature),
      perspectives_covered: cand.perspectives_covered,
      per_perspective: cand.per_perspective ?? [],
      reasons,
      reason_codes: codes,
    };
  });

  return {
    candidates: outCandidates,
    total,
    meta: suggestionsMeta,
    empty_state:
      outCandidates.length === 0
        ? 'No unposted catalog images meet perspective coverage with current scores.'
        : null,
  };
}
