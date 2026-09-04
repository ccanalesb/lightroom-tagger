/**
 * Perceptual hash of a file on disk.
 *
 * Split from `phash.ts` so that module stays pure pixel arithmetic. Decoding uses
 * sharp; resize and greyscale use `pil-resample.ts` for fixture-exact output.
 */
import sharp from 'sharp';
import { phash } from './phash.js';
import { convertRawToJpg, isRawPath } from './raw-decode.js';
import type { Plane } from './pil-resample.js';

/**
 * Decode to an interleaved plane, pinning the colourspace.
 *
 * The pin is load-bearing: sharp promotes a 1-channel image to 3 channels on
 * `.raw()` unless told otherwise, and the phash pipeline greyscales itself, so
 * an unpinned decode changes the input to the hash.
 */
async function decodePlane(path: string): Promise<Plane> {
  const meta = await sharp(path).metadata();
  const { data, info } = await sharp(path)
    .toColourspace(meta.channels === 1 ? 'b-w' : 'srgb')
    .raw()
    .toBuffer({ resolveWithObject: true });
  return {
    data: new Uint8Array(data),
    width: info.width,
    height: info.height,
    channels: info.channels,
  };
}

/**
 * The phash of an image file, or `null` when it cannot be read.
 *
 * Returns `null` rather than throwing so a corrupt file in a large cache build
 * skips that image instead of aborting the run.
 */
export async function phashFromFile(path: string): Promise<string | null> {
  try {
    // A RAW has to be rendered before it can be hashed. Note this hashes the
    // *viewable* image — which is why the phash of a RAW depends on whether a
    // sidecar JPEG exists.
    const decodePath = isRawPath(path)
      ? await convertRawToJpg(path, async () => `${path}.phash.tmp.jpg`)
      : path;
    if (decodePath === null) return null;
    return phash(await decodePlane(decodePath));
  } catch {
    return null;
  }
}
