/**
 * Perceptual hash of a file on disk.
 *
 * Split from `phash.ts` so that module stays pure pixel arithmetic. Decoding uses
 * sharp; resize and greyscale use `pil-resample.ts` for fixture-exact output.
 */
import { unlink } from 'node:fs/promises';
import { decodePlaneFromFile } from './decode-plane.js';
import { makeTempJpgPath } from './image-prep.js';
import { phash } from './phash.js';
import { convertRawToJpg, isRawPath } from './raw-decode.js';

/**
 * The phash of an image file, or `null` when it cannot be read.
 *
 * Returns `null` rather than throwing so a corrupt file in a large cache build
 * skips that image instead of aborting the run.
 */
export async function phashFromFile(path: string): Promise<string | null> {
  // A RAW has to be rendered before it can be hashed. Note this hashes the
  // *viewable* image — which is why the phash of a RAW depends on whether a
  // sidecar JPEG exists.
  const raw = isRawPath(path);
  let decodePath: string | null = path;
  if (raw) decodePath = await convertRawToJpg(path, makeTempJpgPath).catch(() => null);

  try {
    if (decodePath === null) return null;
    return phash(await decodePlaneFromFile(decodePath));
  } catch {
    return null;
  } finally {
    // The render is ours; the original never is.
    if (raw && decodePath !== null) await unlink(decodePath).catch(() => {});
  }
}
