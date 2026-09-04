/**
 * `erf` and `erfc` to double precision.
 *
 * Node has no `Math.erfc`; the Mirror crowning test needs it for the binomial upper
 * tail via `0.5 * erfc(z / sqrt(2))`.
 *
 * FDLIBM `s_erf.c` rational approximations (Sun Microsystems, 1993). Worst relative
 * error ~5.4e-9 over the crowning range, pinned by `tests/erf.test.ts`.
 */

const TINY = 1e-300;

/**
 * Crossover between the two tail approximations.
 *
 * FDLIBM splits at ~2.857; here at 4.5 where measured error actually crosses.
 */
const TAIL_SPLIT = 4.5;
const ERX = 8.45062911510467529297e-1;

// Coefficients for approximation to erf on [0, 0.84375]
const EFX = 1.28379167095512586316e-1;
const EFX8 = 1.02703333676410069053;
const PP0 = 1.28379167095512558561e-1;
const PP1 = -3.25042107247001499370e-1;
const PP2 = -2.84817495755985104766e-2;
const PP3 = -5.77027029648944159157e-3;
const PP4 = -2.37630166566501626084e-5;
const QQ1 = 3.97917223959155352819e-1;
const QQ2 = 6.50222499887672944485e-2;
const QQ3 = 5.08130628187576562776e-3;
const QQ4 = 1.32494738004321644526e-4;
const QQ5 = -3.96022827877536812320e-6;

// Coefficients for approximation to erf on [0.84375, 1.25]
const PA0 = -2.36211856075265944077e-3;
const PA1 = 4.14856118683748331666e-1;
const PA2 = -3.72207876035701323847e-1;
const PA3 = 3.18346619901161753674e-1;
const PA4 = -1.10894694282396677476e-1;
const PA5 = 3.54783043256182359371e-2;
const PA6 = -2.16637559486879084300e-3;
const QA1 = 1.06420880400844228286e-1;
const QA2 = 5.40397917702171048937e-1;
const QA3 = 7.18286544141962662868e-2;
const QA4 = 1.26171219808761642112e-1;
const QA5 = 1.36370839120290507362e-2;
const QA6 = 1.19844998467991074170e-2;

// Coefficients for the first tail branch (FDLIBM: [1.25, 1/0.35])
const RA0 = -9.86494403484714822705e-3;
const RA1 = -6.93858326784720833426e-1;
const RA2 = -1.05586262253232909814e1;
const RA3 = -6.23753324503260060396e1;
const RA4 = -1.62396669462573470355e2;
const RA5 = -1.84605092906711035994e2;
const RA6 = -8.12874355063065934246e1;
const RA7 = -9.81432934416914548592;
const SA1 = 1.96512716674392571292e1;
const SA2 = 1.37657754143519042600e2;
const SA3 = 4.34565877475229228821e2;
const SA4 = 6.45387271733267880336e2;
const SA5 = 4.29008140027567833386e2;
const SA6 = 1.08635005541779435134e2;
const SA7 = 6.57024977031928170135;
const SA8 = -6.04244152148580987438e-2;

// Coefficients for the second tail branch (FDLIBM: [1/0.35, 28])
const RB0 = -9.86494292470009928597e-3;
const RB1 = -7.99283237680523006574e-1;
const RB2 = -1.77579549177547519889e1;
const RB3 = -1.60636384855821916062e2;
const RB4 = -6.37566443368389627722e2;
const RB5 = -1.02509513161107724954e3;
const RB6 = -4.83519191608651397019e2;
const RB7 = -2.24409524465858183362e1;
const SB1 = 3.03380607434824582924e1;
const SB2 = 3.25792512996573918826e2;
const SB3 = 1.53672958608443695994e3;
const SB4 = 3.19985821950859553908e3;
const SB5 = 2.55305040643316442583e3;
const SB6 = 4.74528541206955367215e2;
const SB7 = -2.24409524465858183362e1;

/**
 * Truncate a double to its high 32 bits of mantissa.
 *
 * `exp(-z*z - 0.5625)` is evaluated at a truncated `z` so the two exponential
 * factors multiply without cancellation.
 */
function truncateLow(x: number): number {
  const buf = new DataView(new ArrayBuffer(8));
  buf.setFloat64(0, x);
  buf.setUint32(4, 0);
  return buf.getFloat64(0);
}

export function erf(x: number): number {
  if (Number.isNaN(x)) return Number.NaN;
  if (!Number.isFinite(x)) return x > 0 ? 1 : -1;

  const sign = x < 0 ? -1 : 1;
  const ax = Math.abs(x);

  if (ax < 0.84375) {
    if (ax < 3.7252902984e-9) {
      // Avoid underflow in the polynomial; the linear term is already exact here.
      if (ax < 2.848094538889218e-306) return 0.125 * (8 * x + EFX8 * x);
      return x + EFX * x;
    }
    const z = x * x;
    const r = PP0 + z * (PP1 + z * (PP2 + z * (PP3 + z * PP4)));
    const s = 1 + z * (QQ1 + z * (QQ2 + z * (QQ3 + z * (QQ4 + z * QQ5))));
    return x + x * (r / s);
  }

  if (ax < 1.25) {
    const s = ax - 1;
    const P = PA0 + s * (PA1 + s * (PA2 + s * (PA3 + s * (PA4 + s * (PA5 + s * PA6)))));
    const Q = 1 + s * (QA1 + s * (QA2 + s * (QA3 + s * (QA4 + s * (QA5 + s * QA6)))));
    return sign * (ERX + P / Q);
  }

  if (ax >= 6) return sign * (1 - TINY);

  const s = 1 / (ax * ax);
  let R: number;
  let S: number;
  if (ax < TAIL_SPLIT) {
    R = RA0 + s * (RA1 + s * (RA2 + s * (RA3 + s * (RA4 + s * (RA5 + s * (RA6 + s * RA7))))));
    S =
      1 +
      s * (SA1 + s * (SA2 + s * (SA3 + s * (SA4 + s * (SA5 + s * (SA6 + s * (SA7 + s * SA8)))))));
  } else {
    R = RB0 + s * (RB1 + s * (RB2 + s * (RB3 + s * (RB4 + s * (RB5 + s * (RB6 + s * RB7))))));
    S = 1 + s * (SB1 + s * (SB2 + s * (SB3 + s * (SB4 + s * (SB5 + s * (SB6 + s * SB7))))));
  }
  const z = truncateLow(ax);
  const r = Math.exp(-z * z - 0.5625) * Math.exp((z - ax) * (z + ax) + R / S);
  return sign * (1 - r / ax);
}

export function erfc(x: number): number {
  if (Number.isNaN(x)) return Number.NaN;
  if (!Number.isFinite(x)) return x > 0 ? 0 : 2;

  const sign = x < 0 ? -1 : 1;
  const ax = Math.abs(x);

  if (ax < 0.84375) {
    if (ax < 1.3877787807814457e-17) return 1 - x;
    const z = x * x;
    const r = PP0 + z * (PP1 + z * (PP2 + z * (PP3 + z * PP4)));
    const s = 1 + z * (QQ1 + z * (QQ2 + z * (QQ3 + z * (QQ4 + z * QQ5))));
    const y = r / s;
    if (ax < 0.25) return 1 - (x + x * y);
    // Split so the subtraction stays accurate as erf(x) approaches 0.5.
    let r2 = x * y;
    r2 += x - 0.5;
    return 0.5 - r2;
  }

  if (ax < 1.25) {
    const s = ax - 1;
    const P = PA0 + s * (PA1 + s * (PA2 + s * (PA3 + s * (PA4 + s * (PA5 + s * PA6)))));
    const Q = 1 + s * (QA1 + s * (QA2 + s * (QA3 + s * (QA4 + s * (QA5 + s * QA6)))));
    return sign > 0 ? 1 - ERX - P / Q : 1 + (ERX + P / Q);
  }

  if (ax < 28) {
    const s = 1 / (ax * ax);
    let R: number;
    let S: number;
    if (ax < TAIL_SPLIT) {
      R = RA0 + s * (RA1 + s * (RA2 + s * (RA3 + s * (RA4 + s * (RA5 + s * (RA6 + s * RA7))))));
      S =
        1 +
        s *
          (SA1 + s * (SA2 + s * (SA3 + s * (SA4 + s * (SA5 + s * (SA6 + s * (SA7 + s * SA8)))))));
    } else {
      // The negative tail saturates at 2 well before the positive one underflows.
      if (sign < 0 && ax > 6) return 2 - TINY;
      R = RB0 + s * (RB1 + s * (RB2 + s * (RB3 + s * (RB4 + s * (RB5 + s * (RB6 + s * RB7))))));
      S = 1 + s * (SB1 + s * (SB2 + s * (SB3 + s * (SB4 + s * (SB5 + s * (SB6 + s * SB7))))));
    }
    const z = truncateLow(ax);
    const r = Math.exp(-z * z - 0.5625) * Math.exp((z - ax) * (z + ax) + R / S);
    return sign > 0 ? r / ax : 2 - r / ax;
  }

  return sign > 0 ? TINY * TINY : 2 - TINY;
}
