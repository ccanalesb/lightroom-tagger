/**
 * Pins the Pillow-exact imaging path against golden files produced by Pillow itself
 * (see tests/fixtures/imaging/regenerate-fixtures.py).
 *
 * These assertions are deliberately bit-exact, not tolerance-based. The failure mode
 * being guarded against is silent: a resize that is merely *close* leaves CLIP
 * embeddings ~0.93 cosine from the stored corpus, inside the near-duplicate band that
 * stack detection ranks on. "Nearly right" is the bug.
 */
import { describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { decodePlaneFromFile } from '../src/imaging/decode-plane.js';
import { centerCrop, pilGreyscale, pilResize, type Plane } from '../src/imaging/pil-resample.js';
import { clipPixelValues, resizeShortestEdgeSize } from '../src/imaging/clip-preprocess.js';
import { hammingDistance, phash, phashDctBlock } from '../src/imaging/phash.js';

const DIR = join(import.meta.dirname, 'fixtures', 'imaging');

interface ResizeEntry {
  filter: 'bicubic' | 'lanczos';
  width: number;
  height: number;
  file: string;
}
interface ImageEntry {
  name: string;
  width: number;
  height: number;
  resizes: ResizeEntry[];
  grey_resizes: ResizeEntry[];
  grey: string;
  clip_shape: number[];
  clip_sha256: string;
  clip_spot: Record<string, number>;
  phash: string;
  dct8: number[];
  dct_ties: number;
  phash_degenerate: boolean;
}
const manifest = JSON.parse(readFileSync(join(DIR, 'manifest.json'), 'utf8')) as {
  pillow: string;
  images: ImageEntry[];
};

/** Decode a fixture PNG to interleaved samples. PNG is lossless, so this is exact. */
async function loadPng(file: string): Promise<Plane> {
  return decodePlaneFromFile(join(DIR, file));
}

const loadRgb = (name: string) => loadPng(`${name}.png`);

function firstDifference(a: ArrayLike<number>, b: ArrayLike<number>) {
  if (a.length !== b.length) return { index: -1, a: a.length, b: b.length, count: -1 };
  let count = 0;
  let index = -1;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) {
      count++;
      if (index < 0) index = i;
    }
  }
  return { index, a: index < 0 ? 0 : a[index], b: index < 0 ? 0 : b[index], count };
}

describe(`Pillow parity (golden files from Pillow ${manifest.pillow})`, () => {
  it('decodes fixture PNGs at the expected dimensions', async () => {
    for (const img of manifest.images) {
      const rgb = await loadRgb(img.name);
      expect([rgb.width, rgb.height, rgb.channels]).toEqual([img.width, img.height, 3]);
    }
  });

  describe('pilGreyscale matches PIL convert("L")', () => {
    for (const img of manifest.images) {
      it(img.name, async () => {
        const rgb = await loadRgb(img.name);
        const grey = pilGreyscale(rgb);
        const expected = (await loadPng(img.grey)).data;
        expect(grey.data.length).toBe(expected.length);
        expect(firstDifference(grey.data, expected).count).toBe(0);
      });
    }
  });

  describe('pilResize matches PIL Image.resize bit-for-bit', () => {
    for (const img of manifest.images) {
      for (const r of img.resizes) {
        it(`${img.name} -> ${r.width}x${r.height} ${r.filter}`, async () => {
          const rgb = await loadRgb(img.name);
          const out = pilResize(rgb, r.width, r.height, r.filter);
          const expected = (await loadPng(r.file)).data;

          expect(out.width).toBe(r.width);
          expect(out.height).toBe(r.height);
          expect(out.data.length).toBe(expected.length);

          const diff = firstDifference(out.data, expected);
          // Report the offending byte rather than just "arrays differ".
          expect(diff, `first mismatch at byte ${diff.index}`).toMatchObject({ count: 0 });
        });
      }
    }
  });

  describe('pilResize on a 1-channel plane matches PIL', () => {
    // The phash path greyscales before resizing, so the resampler runs on a
    // single-channel plane. The RGB goldens above never exercise that.
    for (const img of manifest.images) {
      for (const r of img.grey_resizes) {
        it(`${img.name} grey -> ${r.width}x${r.height} ${r.filter}`, async () => {
          const grey = pilGreyscale(await loadRgb(img.name));
          const out = pilResize(grey, r.width, r.height, r.filter);
          const expected = (await loadPng(r.file)).data;
          expect(out.channels).toBe(1);
          expect(out.data.length).toBe(expected.length);
          const diff = firstDifference(out.data, expected);
          expect(diff, `first mismatch at byte ${diff.index}`).toMatchObject({ count: 0 });
        });
      }
    }
  });

  describe('phash DCT block matches scipy', () => {
    // Checked for every image, including the degenerate one: this is the numeric
    // stage, and it is comparable even where the thresholded hash is not.
    for (const img of manifest.images) {
      it(img.name, async () => {
        const got = phashDctBlock(await loadRgb(img.name));
        const expected = Float64Array.from(img.dct8);
        expect(got.length).toBe(expected.length);

        // Relative tolerance: the DC term is ~5e5 while AC terms are ~1e1.
        let worst = 0;
        for (let i = 0; i < got.length; i++) {
          const scale = Math.max(1, Math.abs(expected[i]!));
          worst = Math.max(worst, Math.abs(got[i]! - expected[i]!) / scale);
        }
        expect(worst).toBeLessThan(1e-9);
      });
    }
  });

  describe('CLIP pixel_values match CLIPImageProcessor', () => {
    for (const img of manifest.images) {
      it(img.name, async () => {
        const rgb = await loadRgb(img.name);
        const got = clipPixelValues(rgb);

        // Pillow-side shape is CHW with no batch dim; ours is the flat tensor for
        // a batch of 1. Compare element counts rather than assuming a rank.
        expect(img.clip_shape).toEqual([3, 224, 224]);
        expect(got.length).toBe(img.clip_shape.reduce((a, b) => a * b, 1));

        // Digest over the raw float32 bytes: catches a single flipped bit anywhere
        // in the tensor without committing 602KB of floats per image.
        const digest = createHash('sha256')
          .update(Buffer.from(got.buffer, got.byteOffset, got.byteLength))
          .digest('hex');
        expect(digest).toBe(img.clip_sha256);

        // Spot values, so a failure says *what* drifted, not just "digest differs".
        for (const [index, value] of Object.entries(img.clip_spot)) {
          expect(got[Number(index)], `pixel_values[${index}]`).toBeCloseTo(value, 6);
        }
      });
    }
  });

  describe('phash matches imagehash.phash exactly', () => {
    for (const img of manifest.images.filter((i) => !i.phash_degenerate)) {
      it(`${img.name} -> ${img.phash}`, async () => {
        const rgb = await loadRgb(img.name);
        const got = phash(rgb);
        expect(got).toBe(img.phash);
        expect(hammingDistance(got, img.phash)).toBe(0);
      });
    }
  });

  describe('phash on numerically degenerate input', () => {
    // A 1px checkerboard resizes to a near-uniform plane, so 47 of its 64 DCT
    // coefficients cancel to exactly zero in scipy and the median is also zero.
    // `0.0 > 0.0` is false there, but a different summation order leaves those
    // terms at ~1e-13 and they flip true. The hash is therefore decided by
    // floating-point luck in BOTH implementations, so asserting equality would
    // pin our arithmetic to scipy's accumulation order rather than to correct
    // behaviour. The DCT block above is the meaningful check; real photographs
    // produce no exact ties (measured: 0 of 64 on all non-synthetic samples).
    for (const img of manifest.images.filter((i) => i.phash_degenerate)) {
      it(`${img.name} is documented as degenerate (${img.dct_ties}/64 ties), not asserted`, async () => {
        const got = phash(await loadRgb(img.name));
        expect(got).toMatch(/^[0-9a-f]{16}$/);
        expect(img.dct_ties).toBeGreaterThan(1);
      });
    }
  });
});

describe('helpers', () => {
  it('resizeShortestEdgeSize truncates toward zero like int()', () => {
    // 1024x683 landscape: short edge is the height.
    expect(resizeShortestEdgeSize(1024, 683)).toEqual({
      width: Math.trunc((224 * 1024) / 683),
      height: 224,
    });
    // Portrait puts 224 on the width instead.
    expect(resizeShortestEdgeSize(683, 1024)).toEqual({
      width: 224,
      height: Math.trunc((224 * 1024) / 683),
    });
    // Square stays square.
    expect(resizeShortestEdgeSize(500, 500)).toEqual({ width: 224, height: 224 });
  });

  it('pilResize returns a copy, not the input buffer, when size is unchanged', async () => {
    const rgb = await loadRgb('tiny_7x5');
    const out = pilResize(rgb, rgb.width, rgb.height, 'bicubic');
    expect(out.data).not.toBe(rgb.data);
    expect(firstDifference(out.data, rgb.data).count).toBe(0);
  });

  it('centerCrop offsets with floor division', () => {
    // 5-wide source, 2-wide crop: left = floor(3/2) = 1.
    const src: Plane = {
      data: new Uint8Array([0, 1, 2, 3, 4]),
      width: 5,
      height: 1,
      channels: 1,
    };
    expect([...centerCrop(src, 2, 1).data]).toEqual([1, 2]);
  });

  it('hammingDistance counts differing bits', () => {
    expect(hammingDistance('0000', '0000')).toBe(0);
    expect(hammingDistance('0000', 'ffff')).toBe(16);
    expect(hammingDistance('0000', '0001')).toBe(1);
  });
});
