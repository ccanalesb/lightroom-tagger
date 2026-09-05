/**
 * Perceptual hash (hash_size=8, highfreq_factor=4).
 *
 * Greyscale before resize, unnormalized DCT-II, median includes the DC term.
 * Resize and greyscale must use `pil-resample.ts`.
 */
import { pilGreyscale, pilResize, type Plane } from './pil-resample.js';

const HASH_SIZE = 8;
const HIGHFREQ_FACTOR = 4;

/** Unnormalized DCT-II. */
function dct1d(input: Float64Array, out: Float64Array): void {
  const N = input.length;
  for (let k = 0; k < N; k++) {
    let s = 0;
    for (let n = 0; n < N; n++) {
      s += input[n]! * Math.cos((Math.PI * k * (2 * n + 1)) / (2 * N));
    }
    out[k] = 2 * s;
  }
}

/** Median for an even-length sample: mean of the middle two. */
function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  const mid = n >> 1;
  return n % 2 === 0 ? (sorted[mid - 1]! + sorted[mid]!) / 2 : sorted[mid]!;
}

/**
 * The low-frequency 8×8 DCT block phash thresholds, in row-major order.
 *
 * Exported so tests can compare the numeric stage directly. Comparing the block
 * catches real errors that a hash comparison on periodic input would mask.
 */
export function phashDctBlock(rgbOrGrey: Plane): Float64Array {
  const size = HASH_SIZE * HIGHFREQ_FACTOR; // 32
  const grey = pilGreyscale(rgbOrGrey);
  const small = pilResize(grey, size, size, 'lanczos');

  // Column DCT first, then row DCT.
  const matrix: Float64Array[] = [];
  for (let y = 0; y < size; y++) {
    const row = new Float64Array(size);
    for (let x = 0; x < size; x++) row[x] = small.data[y * size + x]!;
    matrix.push(row);
  }

  const col = new Float64Array(size);
  const colOut = new Float64Array(size);
  const colResults: Float64Array[] = [];
  for (let x = 0; x < size; x++) {
    for (let y = 0; y < size; y++) col[y] = matrix[y]![x]!;
    dct1d(col, colOut);
    colResults.push(Float64Array.from(colOut));
  }
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) matrix[y]![x] = colResults[x]![y]!;
  }
  const rowOut = new Float64Array(size);
  for (let y = 0; y < size; y++) {
    dct1d(matrix[y]!, rowOut);
    matrix[y]!.set(rowOut);
  }

  const block = new Float64Array(HASH_SIZE * HASH_SIZE);
  for (let y = 0; y < HASH_SIZE; y++) {
    for (let x = 0; x < HASH_SIZE; x++) block[y * HASH_SIZE + x] = matrix[y]![x]!;
  }
  return block;
}

/**
 * Compute the phash of already-decoded pixels.
 *
 * Returns a 16-character hex string: the flattened bit array packed big-endian,
 * 4 bits per hex digit.
 */
export function phash(rgbOrGrey: Plane): string {
  const block = Array.from(phashDctBlock(rgbOrGrey));
  const med = median(block);

  let hex = '';
  for (let i = 0; i < block.length; i += 4) {
    const nibble =
      (block[i]! > med ? 8 : 0) |
      (block[i + 1]! > med ? 4 : 0) |
      (block[i + 2]! > med ? 2 : 0) |
      (block[i + 3]! > med ? 1 : 0);
    hex += nibble.toString(16);
  }
  return hex;
}

/** Hamming distance between two hex hashes of equal length. */
export function hammingDistance(a: string, b: string): number {
  if (a.length !== b.length) throw new Error(`hash length mismatch: ${a.length} vs ${b.length}`);
  let d = 0;
  for (let i = 0; i < a.length; i++) {
    let x = parseInt(a[i]!, 16) ^ parseInt(b[i]!, 16);
    while (x) {
      d += x & 1;
      x >>= 1;
    }
  }
  return d;
}
