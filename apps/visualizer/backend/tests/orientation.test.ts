import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import {
  ORIENTATION_CODES,
  applyOrientation,
  isQuarterTurn,
  normalizeOrientation,
  orientationFromLibrawFlip,
  remainingOrientation,
  type OrientationCode,
} from '../src/imaging/orientation.js';

/** 3 wide, 2 tall: `[[0, 1, 2], [3, 4, 5]]`. */
const PROBE = [0, 1, 2, 3, 4, 5];

/** Written out by hand from what each code means on screen, not derived from the module. */
const EXPECTED: Record<OrientationCode, number[][]> = {
  AB: [
    [0, 1, 2],
    [3, 4, 5],
  ],
  BC: [
    [3, 0],
    [4, 1],
    [5, 2],
  ],
  CD: [
    [5, 4, 3],
    [2, 1, 0],
  ],
  DA: [
    [2, 5],
    [1, 4],
    [0, 3],
  ],
  BA: [
    [2, 1, 0],
    [5, 4, 3],
  ],
  DC: [
    [3, 4, 5],
    [0, 1, 2],
  ],
  CB: [
    [0, 3],
    [1, 4],
    [2, 5],
  ],
  AD: [
    [5, 2],
    [4, 1],
    [3, 0],
  ],
};

async function transform(
  pixels: number[],
  width: number,
  height: number,
  code: OrientationCode,
): Promise<{ rows: number[][]; flat: number[]; width: number; height: number }> {
  const input = Buffer.from(pixels.map((v) => v * 40));
  const pipeline = sharp(input, { raw: { width, height, channels: 1 } });
  const { data, info } = await applyOrientation(pipeline, code)
    .extractChannel(0)
    .raw()
    .toBuffer({ resolveWithObject: true });
  const flat = [...data].map((v) => v / 40);
  const rows = Array.from({ length: info.height }, (_, y) =>
    flat.slice(y * info.width, (y + 1) * info.width),
  );
  return { rows, flat, width: info.width, height: info.height };
}

describe('applyOrientation', () => {
  it.each(ORIENTATION_CODES)('%s turns the stored pixels the way Lightroom shows them', async (code) => {
    expect((await transform(PROBE, 3, 2, code)).rows).toEqual(EXPECTED[code]);
  });
});

describe('remainingOrientation', () => {
  it('finishes the job whatever the decoder already applied', async () => {
    for (const target of ORIENTATION_CODES) {
      for (const applied of ORIENTATION_CODES) {
        const half = await transform(PROBE, 3, 2, applied);
        const rest = remainingOrientation(target, applied);
        const done = await transform(half.flat, half.width, half.height, rest);
        expect(done.rows, `${target} after ${applied}`).toEqual(EXPECTED[target]);
      }
    }
  });

  it('is nothing when the decoder already did it all', () => {
    for (const code of ORIENTATION_CODES) expect(remainingOrientation(code, code)).toBe('AB');
  });
});

describe('code helpers', () => {
  it('reads LibRaw flips the way cameras write them', () => {
    expect(orientationFromLibrawFlip(0)).toBe('AB');
    expect(orientationFromLibrawFlip(3)).toBe('CD');
    expect(orientationFromLibrawFlip(5)).toBe('DA');
    expect(orientationFromLibrawFlip(6)).toBe('BC');
    expect(orientationFromLibrawFlip(undefined)).toBe('AB');
  });

  it('treats a missing or unknown stored code as upright', () => {
    expect(normalizeOrientation(null)).toBe('AB');
    expect(normalizeOrientation('XY')).toBe('AB');
    expect(normalizeOrientation('DA')).toBe('DA');
  });

  it('knows which codes swap width and height', () => {
    expect(ORIENTATION_CODES.filter(isQuarterTurn)).toEqual(['BC', 'DA', 'CB', 'AD']);
  });
});
