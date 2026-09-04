/**
 * Frame substance detector parity. Mirrors `core/test_frame_substance_detector.py`,
 * and pins the five statistics against the numpy values in
 * `fixtures/frame-substance/manifest.json`.
 *
 * Every verdict row in `library.db` was written by the numpy detector, so a rerun
 * of this one has to agree with it or the catalog silently re-judges itself. The
 * two pixel fractions are exact rationals and compared exactly; the other three
 * are compared to a relative tolerance because numpy accumulates them in float32
 * and this port accumulates in float64.
 *
 * The manifest is frozen. The numpy detector that produced it was deleted with the
 * Python package, so there is nothing left to regenerate it from — which is the
 * point: it is the independent second opinion this port is measured against. A
 * deliberate threshold change means recovering the detector from git history, not
 * rewriting these numbers from the TypeScript side.
 */
import { describe, expect, it } from 'vitest';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import {
  classifyVerdict,
  computeStatisticsFromGreyscale,
  computeStatisticsFromPath,
  detectorVersion,
  type FrameStatistics,
  type Verdict,
} from '../src/imaging/frame-substance-detector.js';
import type { Plane } from '../src/imaging/pil-resample.js';

interface ManifestEntry {
  name: string;
  file: string;
  mode: string;
  width: number;
  height: number;
  stats: FrameStatistics;
  verdict: Verdict;
}

const FIXTURES = join(import.meta.dirname, 'fixtures', 'frame-substance');
const manifest = JSON.parse(readFileSync(join(FIXTURES, 'manifest.json'), 'utf8')) as {
  detector_version: string;
  numpy: string;
  images: ManifestEntry[];
};

/** float32 keeps 24 bits of mantissa; anything wider than this is a real drift. */
const MAX_RELATIVE_ERROR = 1e-6;

function greyPlane(width: number, height: number, fill: (x: number, y: number) => number): Plane {
  const data = new Uint8Array(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) data[y * width + x] = fill(x, y);
  }
  return { data, width, height, channels: 1 };
}

describe(`frame substance statistics against numpy ${manifest.numpy}`, () => {
  for (const entry of manifest.images) {
    it(`${entry.name} (${entry.mode} ${entry.width}x${entry.height})`, async () => {
      const stats = await computeStatisticsFromPath(join(FIXTURES, entry.file));
      expect(stats).not.toBeNull();

      expect(stats!.black_frac_25).toBe(entry.stats.black_frac_25);
      expect(stats!.blown_frac_235).toBe(entry.stats.blown_frac_235);
      for (const key of ['entropy', 'lap_var', 'tile_max'] as const) {
        const want = entry.stats[key];
        const got = stats![key];
        const rel = want === 0 ? Math.abs(got) : Math.abs(got - want) / Math.abs(want);
        expect(rel, `${key}: ${got} vs ${want}`).toBeLessThan(MAX_RELATIVE_ERROR);
      }
      expect(classifyVerdict(stats!)).toBe(entry.verdict);
    });
  }
});

describe('verdict rules over the golden statistics', () => {
  // Independent of the pixel arithmetic: feed Python's own numbers to the rules.
  for (const entry of manifest.images) {
    it(`${entry.name} is ${entry.verdict}`, () => {
      expect(classifyVerdict(entry.stats)).toBe(entry.verdict);
    });
  }

  it('lets an untriggered frame through whatever its structure statistics say', () => {
    const stats: FrameStatistics = {
      black_frac_25: 0.5,
      blown_frac_235: 0.4,
      entropy: 0,
      lap_var: 0,
      tile_max: 0,
    };
    expect(classifyVerdict(stats)).toBe('ok');
  });
});

describe('detectorVersion', () => {
  it('reproduces the hash the numpy detector stamps on every verdict row', () => {
    expect(detectorVersion()).toBe(manifest.detector_version);
  });
});

describe('computeStatisticsFromGreyscale edges', () => {
  it('returns zeros for an empty plane', () => {
    const stats = computeStatisticsFromGreyscale({
      data: new Uint8Array(0),
      width: 0,
      height: 0,
      channels: 1,
    });
    expect(stats).toEqual({
      black_frac_25: 0,
      blown_frac_235: 0,
      entropy: 0,
      lap_var: 0,
      tile_max: 0,
    });
  });

  it('refuses a frame too small to hold a 32x32 tile grid, as numpy does', () => {
    expect(() => computeStatisticsFromGreyscale(greyPlane(40, 20, () => 7))).toThrow(
      /too small to tile/,
    );
  });
});

describe('computeStatisticsFromPath', () => {
  it('returns null for a file that is not an image', async () => {
    await expect(computeStatisticsFromPath(join(FIXTURES, 'manifest.json'))).resolves.toBeNull();
  });

  it('returns null for a path that does not exist', async () => {
    await expect(computeStatisticsFromPath(join(FIXTURES, 'nope.png'))).resolves.toBeNull();
  });

  it('returns null for a preview too small to tile, rather than aborting the scan', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'lt-fs-detector-'));
    const path = join(dir, 'tiny.png');
    try {
      await sharp({ create: { width: 20, height: 20, channels: 3, background: '#000' } })
        .png()
        .toFile(path);
      await expect(computeStatisticsFromPath(path)).resolves.toBeNull();
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
