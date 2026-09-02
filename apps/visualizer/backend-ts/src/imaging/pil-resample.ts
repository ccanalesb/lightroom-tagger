/**
 * Pillow-exact image resampling.
 *
 * WHY THIS EXISTS: every image-derived value in `library.db` — the 43,451 CLIP
 * embeddings and every stored phash — was produced by Pillow. `sharp`/libvips
 * resizing is *not* Pillow resizing, and the difference is not cosmetic:
 *
 *   - CLIP embeddings drift to cosine 0.93–0.97 against the stored corpus, which is
 *     inside the near-duplicate band that stack detection and catalog similarity
 *     rank on. Feeding Pillow's own tensor through the same ONNX graph gives
 *     cosine 1.000000, so the model is exact and the resize is the entire error.
 *   - phash lands ~2 bits of 64 off, exact on only 7 of 12 sample images.
 *
 * So the resize is ported rather than delegated. This is a direct transcription of
 * `src/libImaging/Resample.c` from Pillow (tested against Pillow 12.2.0), keeping
 * its fixed-point arithmetic and rounding rules — those, not the filter maths, are
 * what make the output bit-identical.
 *
 * Only the 8-bit-per-channel path is implemented, which is all this project needs.
 */

/** `32 - 8 - 2` in Resample.c. Coefficients are fixed-point with this many bits. */
const PRECISION_BITS = 22;
const HALF = 1 << (PRECISION_BITS - 1);
const SCALE = 1 << PRECISION_BITS;

export type FilterName = 'bilinear' | 'bicubic' | 'lanczos';

interface Filter {
  support: number;
  fn: (x: number) => number;
}

function bilinearFilter(x: number): number {
  if (x < 0) x = -x;
  return x < 1.0 ? 1.0 - x : 0.0;
}

/** Catmull-Rom-style cubic with a = -0.5, matching Pillow's `bicubic_filter`. */
function bicubicFilter(x: number): number {
  const a = -0.5;
  if (x < 0) x = -x;
  if (x < 1.0) return ((a + 2.0) * x - (a + 3.0)) * x * x + 1.0;
  if (x < 2.0) return (((x - 5.0) * x + 8.0) * x - 4.0) * a;
  return 0.0;
}

function sinc(x: number): number {
  if (x === 0.0) return 1.0;
  const px = x * Math.PI;
  return Math.sin(px) / px;
}

/** Sinc truncated at 3 lobes, matching Pillow's `lanczos_filter`. */
function lanczosFilter(x: number): number {
  if (x >= -3.0 && x < 3.0) return sinc(x) * sinc(x / 3.0);
  return 0.0;
}

const FILTERS: Record<FilterName, Filter> = {
  bilinear: { support: 1.0, fn: bilinearFilter },
  bicubic: { support: 2.0, fn: bicubicFilter },
  lanczos: { support: 3.0, fn: lanczosFilter },
};

interface Coeffs {
  ksize: number;
  /** `[xmin, xmax]` pairs, one per output pixel. */
  bounds: Int32Array;
  /** Fixed-point coefficients, `ksize` per output pixel. */
  kk: Int32Array;
}

/**
 * Port of `precompute_coeffs` + `normalize_coeffs_8bpc`.
 *
 * C's `(int)` truncates toward zero, so `Math.trunc` is used deliberately in place
 * of `Math.floor` — they differ for the negative intermediates that arise near the
 * left/top edge, and the truncating form is what Pillow does.
 */
function precomputeCoeffs(
  inSize: number,
  in0: number,
  in1: number,
  outSize: number,
  filter: Filter,
): Coeffs {
  const scale = (in1 - in0) / outSize;
  const filterscale = scale < 1.0 ? 1.0 : scale;
  const support = filter.support * filterscale;
  const ksize = Math.ceil(support) * 2 + 1;

  const bounds = new Int32Array(outSize * 2);
  const kk = new Int32Array(outSize * ksize);
  const k = new Float64Array(ksize);

  for (let xx = 0; xx < outSize; xx++) {
    const center = in0 + (xx + 0.5) * scale;
    const ss = 1.0 / filterscale;

    let xmin = Math.trunc(center - support + 0.5);
    if (xmin < 0) xmin = 0;
    let xmax = Math.trunc(center + support + 0.5);
    if (xmax > inSize) xmax = inSize;
    xmax -= xmin;

    let ww = 0.0;
    for (let x = 0; x < xmax; x++) {
      const w = filter.fn((x + xmin - center + 0.5) * ss);
      k[x] = w;
      ww += w;
    }
    if (ww !== 0.0) {
      for (let x = 0; x < xmax; x++) k[x]! /= ww;
    }

    // normalize_coeffs_8bpc: round half away from zero, then truncate.
    const base = xx * ksize;
    for (let x = 0; x < xmax; x++) {
      const v = k[x]!;
      kk[base + x] = Math.trunc(v < 0 ? -0.5 + v * SCALE : 0.5 + v * SCALE);
    }
    for (let x = xmax; x < ksize; x++) kk[base + x] = 0;

    bounds[xx * 2] = xmin;
    bounds[xx * 2 + 1] = xmax;
  }

  return { ksize, bounds, kk };
}

/** `clip8` — arithmetic shift down out of fixed point, then clamp to a byte. */
function clip8(v: number): number {
  const s = v >> PRECISION_BITS;
  return s < 0 ? 0 : s > 255 ? 255 : s;
}

/**
 * An 8-bit image as interleaved channel data, the layout both `sharp().raw()` and
 * `numpy.asarray(pil_image)` produce.
 */
export interface Plane {
  data: Uint8Array;
  width: number;
  height: number;
  channels: number;
}

function resampleHorizontal(
  src: Plane,
  outWidth: number,
  offset: number,
  outHeight: number,
  c: Coeffs,
): Plane {
  const { channels } = src;
  const out = new Uint8Array(outWidth * outHeight * channels);
  const { ksize, bounds, kk } = c;

  for (let yy = 0; yy < outHeight; yy++) {
    const srcRow = (yy + offset) * src.width * channels;
    const outRow = yy * outWidth * channels;
    for (let xx = 0; xx < outWidth; xx++) {
      const xmin = bounds[xx * 2]!;
      const xmax = bounds[xx * 2 + 1]!;
      const kbase = xx * ksize;
      for (let ch = 0; ch < channels; ch++) {
        let ss = HALF;
        for (let x = 0; x < xmax; x++) {
          ss += src.data[srcRow + (x + xmin) * channels + ch]! * kk[kbase + x]!;
        }
        out[outRow + xx * channels + ch] = clip8(ss);
      }
    }
  }
  return { data: out, width: outWidth, height: outHeight, channels };
}

function resampleVertical(src: Plane, outHeight: number, c: Coeffs): Plane {
  const { channels, width } = src;
  const out = new Uint8Array(width * outHeight * channels);
  const { ksize, bounds, kk } = c;

  for (let yy = 0; yy < outHeight; yy++) {
    const ymin = bounds[yy * 2]!;
    const ymax = bounds[yy * 2 + 1]!;
    const kbase = yy * ksize;
    const outRow = yy * width * channels;
    for (let xx = 0; xx < width; xx++) {
      for (let ch = 0; ch < channels; ch++) {
        let ss = HALF;
        for (let y = 0; y < ymax; y++) {
          ss += src.data[(y + ymin) * width * channels + xx * channels + ch]! * kk[kbase + y]!;
        }
        out[outRow + xx * channels + ch] = clip8(ss);
      }
    }
  }
  return { data: out, width, height: outHeight, channels };
}

/**
 * Resize `src` to `outWidth`×`outHeight`, bit-identically to
 * `PIL.Image.resize((outWidth, outHeight), resample=<filter>)`.
 *
 * Two-pass like Pillow: horizontal into a temp restricted to the rows the vertical
 * pass will actually read, then vertical. Passes are skipped when the corresponding
 * dimension is unchanged, which is also what Pillow does — and it matters, because
 * a skipped pass is not the same as a no-op pass through fixed-point rounding.
 */
export function pilResize(
  src: Plane,
  outWidth: number,
  outHeight: number,
  filterName: FilterName,
): Plane {
  const filter = FILTERS[filterName];
  if (outWidth === src.width && outHeight === src.height) {
    return { ...src, data: Uint8Array.prototype.slice.call(src.data) };
  }

  const needHorizontal = outWidth !== src.width;
  const needVertical = outHeight !== src.height;

  const horiz = precomputeCoeffs(src.width, 0, src.width, outWidth, filter);
  const vert = precomputeCoeffs(src.height, 0, src.height, outHeight, filter);

  // Rows of the source the vertical pass touches, so the temp image is no taller.
  const yboxFirst = vert.bounds[0]!;
  const yboxLast = vert.bounds[outHeight * 2 - 2]! + vert.bounds[outHeight * 2 - 1]!;

  let img = src;
  if (needHorizontal) {
    // Rebase the vertical bounds onto the temp image, which starts at yboxFirst.
    for (let i = 0; i < outHeight; i++) vert.bounds[i * 2] = vert.bounds[i * 2]! - yboxFirst;
    img = resampleHorizontal(src, outWidth, yboxFirst, yboxLast - yboxFirst, horiz);
  }
  if (needVertical) {
    img = resampleVertical(img, outHeight, vert);
  }
  return img;
}

/**
 * PIL `Image.convert("L")` — ITU-R 601-2 luma in Pillow's fixed point.
 *
 * `sharp().greyscale()` is NOT equivalent: measured against Pillow on a real cache
 * JPEG it differs on 23.7% of pixels (max 11 levels). Use this.
 */
export function pilGreyscale(src: Plane): Plane {
  if (src.channels === 1) return { ...src, data: Uint8Array.prototype.slice.call(src.data) };
  const n = src.width * src.height;
  const out = new Uint8Array(n);
  const d = src.data;
  const ch = src.channels;
  for (let i = 0; i < n; i++) {
    const o = i * ch;
    out[i] = (d[o]! * 19595 + d[o + 1]! * 38470 + d[o + 2]! * 7471 + 0x8000) >> 16;
  }
  return { data: out, width: src.width, height: src.height, channels: 1 };
}

/**
 * Crop a centred region, matching `transformers.image_transforms.center_crop`
 * (floor division for the offsets). Assumes the crop fits; callers resize first.
 */
export function centerCrop(src: Plane, cropWidth: number, cropHeight: number): Plane {
  const left = Math.floor((src.width - cropWidth) / 2);
  const top = Math.floor((src.height - cropHeight) / 2);
  const { channels } = src;
  const out = new Uint8Array(cropWidth * cropHeight * channels);
  for (let y = 0; y < cropHeight; y++) {
    const srcStart = ((y + top) * src.width + left) * channels;
    out.set(src.data.subarray(srcStart, srcStart + cropWidth * channels), y * cropWidth * channels);
  }
  return { data: out, width: cropWidth, height: cropHeight, channels };
}
