/**
 * Pins `erf` / `erfc` against `fixtures/erf-reference.json`.
 *
 * Holds relative error at MAX_RELATIVE_ERROR so a regression surfaces here rather
 * than as a lens that quietly stops being crowned.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { erf, erfc } from '../src/utils/erf.js';

interface Reference {
  values: { x: number; erf: number; erfc: number }[];
}

const reference = JSON.parse(
  readFileSync(join(import.meta.dirname, 'fixtures', 'erf-reference.json'), 'utf8'),
) as Reference;

/**
 * The bound the module documents. Deliberately not loosened to "whatever passes":
 * 1e-8 is still 50x below the sixth decimal that `p_value` is published to, so a
 * regression past it would be a real loss of headroom.
 */
const MAX_RELATIVE_ERROR = 1e-8;

function relativeError(got: number, want: number): number {
  if (want === 0) return Math.abs(got);
  return Math.abs(got - want) / Math.abs(want);
}

describe('erf / erfc against reference values', () => {
  it('has a reference table covering every branch', () => {
    expect(reference.values.length).toBeGreaterThan(50);
    // The tail branches and the crossover are where the error lives.
    const xs = reference.values.map((v) => v.x);
    expect(xs.some((x) => x > 0 && x < 0.84375)).toBe(true);
    expect(xs.some((x) => x >= 0.84375 && x < 1.25)).toBe(true);
    expect(xs.some((x) => x >= 1.25 && x < 4.5)).toBe(true);
    expect(xs.some((x) => x >= 4.5 && x < 28)).toBe(true);
    expect(xs.some((x) => x < 0)).toBe(true);
  });

  it('stays within the documented relative error', () => {
    let worstErf = { x: 0, rel: 0 };
    let worstErfc = { x: 0, rel: 0 };

    for (const { x, erf: wantErf, erfc: wantErfc } of reference.values) {
      const relErf = relativeError(erf(x), wantErf);
      const relErfc = relativeError(erfc(x), wantErfc);
      if (relErf > worstErf.rel) worstErf = { x, rel: relErf };
      if (relErfc > worstErfc.rel) worstErfc = { x, rel: relErfc };
    }

    expect(worstErf.rel, `erf worst at x=${worstErf.x}`).toBeLessThan(MAX_RELATIVE_ERROR);
    expect(worstErfc.rel, `erfc worst at x=${worstErfc.x}`).toBeLessThan(MAX_RELATIVE_ERROR);
    console.log(
      `erf/erfc vs reference: worst relative error erf=${worstErf.rel.toExponential(2)} ` +
        `(x=${worstErf.x}), erfc=${worstErfc.rel.toExponential(2)} (x=${worstErfc.x})`,
    );
  });

  it('holds the identities that the tails must satisfy', () => {
    // erfc(x) = 1 - erf(x) is exact in real arithmetic; near zero it must also hold
    // numerically, which is what the split branch below 0.25 exists to protect.
    for (const x of [0, 0.01, 0.1, 0.2, 0.5, -0.5]) {
      expect(erfc(x) + erf(x)).toBeCloseTo(1, 15);
    }
    // Symmetry, which the sign handling must not break.
    for (const x of [0.3, 1, 2, 5]) {
      expect(erf(-x)).toBeCloseTo(-erf(x), 15);
      expect(erfc(-x)).toBeCloseTo(2 - erfc(x), 15);
    }
  });

  it('saturates rather than returning nonsense far out in the tails', () => {
    expect(erfc(30)).toBeGreaterThanOrEqual(0);
    expect(erfc(30)).toBeLessThan(1e-300);
    expect(erfc(-30)).toBeCloseTo(2, 15);
    expect(erf(30)).toBeCloseTo(1, 15);
    expect(erf(-30)).toBeCloseTo(-1, 15);
    expect(Number.isNaN(erfc(Number.NaN))).toBe(true);
    expect(erfc(Number.POSITIVE_INFINITY)).toBe(0);
    expect(erfc(Number.NEGATIVE_INFINITY)).toBe(2);
  });
});
