/**
 * Mirror scan value object plus the crowning statistics primitive.
 *
 * "Crowning" asks whether a lens wins the argmax more often than chance. Chance is
 * not 1/(number of lenses): each photo was scored on a different number of lenses,
 * so the per-photo win probability varies and the null is a Poisson-binomial.
 */
import { erfc } from '../utils/erf.js';
import type { CatalogScoreIndex } from './score-index.js';

export const LOW_COVERAGE_THRESHOLD = 0.5;
export const MIN_VOTING_LENSES = 2;
export const CROWN_ALPHA = 0.05;


export interface SignatureStat {
  perspective_slug: string;
  display_name: string;
  votes: number;
  photos_on: number;
  win_rate: number;
  expected_wins: number;
  chance_rate: number;
  z_score: number;
  p_value: number;
  crowned: boolean;
  coverage: number;
  low_coverage: boolean;
}

export interface SignatureStats {
  stats: SignatureStat[];
  /**
   * The population the stats were computed over — images scored on at least
   * `MIN_VOTING_LENSES` lenses. Returned so callers do not re-derive the threshold.
   */
  votingPopulation: number;
}

const round1 = (v: number): number => Math.round(v * 10) / 10;
const round2 = (v: number): number => Math.round(v * 100) / 100;
const round4 = (v: number): number => Math.round(v * 1e4) / 1e4;
const round6 = (v: number): number => Math.round(v * 1e6) / 1e6;

/** Exact `n choose k` for the small `n` the exact binomial path uses. */
function comb(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  const kk = Math.min(k, n - k);
  let result = 1;
  for (let i = 0; i < kk; i += 1) {
    result = (result * (n - i)) / (i + 1);
  }
  // Exact for n < 30, where every intermediate stays inside the 2^53 integer range.
  return Math.round(result);
}

/**
 * `P(X >= k)` for `X ~ Binomial(n, p)`.
 *
 * Exact for `n < 30`; beyond that — the real-catalog regime, where `n` is in the
 * thousands — the continuity-corrected normal approximation, which is accurate deep
 * in the upper tail where crowning decisions actually sit. A lens sitting right at
 * `p ~ 0.05` could differ marginally from the exact test; distinctive lenses (large
 * z) are unaffected.
 */
export function binomSf(k: number, n: number, p: number): number {
  if (k <= 0) return 1;
  if (k > n) return 0;
  if (p <= 0) return k > 0 ? 0 : 1;
  if (p >= 1) return k <= n ? 1 : 0;

  const mu = n * p;
  if (n >= 30) {
    const sigmaSq = n * p * (1 - p);
    if (sigmaSq <= 0) return k > mu ? 0 : 1;
    const z = (k - 0.5 - mu) / Math.sqrt(sigmaSq);
    return 0.5 * erfc(z / Math.sqrt(2));
  }

  let total = 0;
  const q = 1 - p;
  for (let i = k; i <= n; i += 1) {
    total += comb(n, i) * p ** i * q ** (n - i);
  }
  return Math.min(1, total);
}

/**
 * Standardized vote surplus.
 *
 * Each photo's win probability is `1/k` for the `k` lenses it was scored on, so the
 * vote count is Poisson-binomial. This approximates it with a homogeneous
 * `Binomial(photos_on, chance)` using the mean per-photo chance. Because the true
 * variance `sum p_i(1-p_i)` is at most `n * chance * (1 - chance)` by Jensen, this
 * denominator is an upper bound — so z is understated and crowning never over-fires.
 */
export function signatureZ(
  votes: number,
  expectedWins: number,
  photosOn: number,
  chance: number,
): number {
  const denom = photosOn * chance * (1 - chance);
  if (denom <= 0) return 0;
  return (votes - expectedWins) / Math.sqrt(denom);
}

/** Per-lens vote counts, z-scores, p-values and crowning flags. */
export function computeSignatureStats(scan: CatalogScoreIndex): SignatureStats {
  const votes = new Map<string, number>();
  const photosOn = new Map<string, number>();
  const expectedWins = new Map<string, number>(scan.activeSlugs.map((s) => [s, 0]));
  let votingPopulation = 0;

  for (const perspectives of scan.byImage.values()) {
    // A photo scored on one lens cannot express a preference between lenses.
    if (perspectives.length < MIN_VOTING_LENSES) continue;
    votingPopulation += 1;
    const invK = 1 / perspectives.length;
    const topPct = Math.max(...perspectives.map((p) => p.percentile));
    const tied = perspectives.filter((p) => p.percentile === topPct);

    // Strict argmax: a tie is not a vote for anybody, but the photo still counts
    // toward every participating lens's exposure and expected wins.
    if (tied.length !== 1) {
      for (const p of perspectives) {
        photosOn.set(p.perspective_slug, (photosOn.get(p.perspective_slug) ?? 0) + 1);
        expectedWins.set(
          p.perspective_slug,
          (expectedWins.get(p.perspective_slug) ?? 0) + invK,
        );
      }
      continue;
    }

    const winnerSlug = tied[0]!.perspective_slug;
    votes.set(winnerSlug, (votes.get(winnerSlug) ?? 0) + 1);
    for (const p of perspectives) {
      photosOn.set(p.perspective_slug, (photosOn.get(p.perspective_slug) ?? 0) + 1);
      expectedWins.set(p.perspective_slug, (expectedWins.get(p.perspective_slug) ?? 0) + invK);
    }
  }

  const stats: SignatureStat[] = [];
  for (const slug of scan.activeSlugs) {
    const n = photosOn.get(slug) ?? 0;
    if (n === 0) continue;
    const v = votes.get(slug) ?? 0;
    const expected = expectedWins.get(slug) ?? 0;
    const chance = n ? expected / n : 0;
    const winRate = n ? v / n : 0;
    const z = signatureZ(v, expected, n, chance);
    const pValue = chance > 0 && chance < 1 ? binomSf(v, n, chance) : 1;
    const coverage = scan.totalCatalog ? n / scan.totalCatalog : 0;
    stats.push({
      perspective_slug: slug,
      display_name: scan.displayBySlug.get(slug) ?? slug,
      votes: v,
      photos_on: n,
      win_rate: round6(winRate),
      expected_wins: round4(expected),
      chance_rate: round6(chance),
      z_score: round2(z),
      p_value: round6(pValue),
      // Compared on the unrounded p-value.
      crowned: pValue < CROWN_ALPHA && z > 0,
      coverage: round4(coverage),
      low_coverage: coverage < LOW_COVERAGE_THRESHOLD,
    });
  }
  return { stats, votingPopulation };
}

export { round1, round2, round4, round6 };
