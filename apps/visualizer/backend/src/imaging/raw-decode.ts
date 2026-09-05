/**
 * File formats, and rendering a RAW to a JPEG a downstream step can read.
 *
 * The libraw-wasm adapter itself lives in `libraw/` — this module owns only the
 * extension sets and the retry policy around a decode.
 */
import { writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname } from 'node:path';
import { pathToFileURL } from 'node:url';
import sharp from 'sharp';
import { decodeRaw, type DecodedRaw } from './libraw/decode.js';

export { decodeRaw };
export type { DecodedRaw };

/** RAW extensions the sidecar check covers. */
export const RAW_EXTENSIONS = new Set([
  '.dng',
  '.raw',
  '.cr2',
  '.cr3',
  '.nef',
  '.arw',
  '.rw2',
  '.orf',
  '.raf',
  '.sr2',
  '.srw',
  '.x3f',
]);

export const VIDEO_EXTENSIONS = new Set([
  '.mov',
  '.mp4',
  '.avi',
  '.mkv',
  '.wmv',
  '.m4v',
  '.3gp',
  '.webm',
  '.mts',
  '.m2ts',
]);

/** Signature of `decodeRaw`, so a test can drive the retry policy without a RAW. */
export type RawDecoder = (rawPath: string) => Promise<DecodedRaw>;

/**
 * Convert a RAW file to a temporary JPEG. Returns `null` when it cannot.
 *
 * Three attempts cover intermittent NAS read failures. Quality 95.
 */
export async function convertRawToJpg(
  rawPath: string,
  tempPathFactory: () => Promise<string>,
  decode: RawDecoder = decodeRaw,
): Promise<string | null> {
  if (!existsSync(rawPath)) return null;

  const maxRetries = 3;
  for (let attempt = 0; attempt < maxRetries; attempt += 1) {
    try {
      const { data, width, height, channels } = await decode(rawPath);
      const jpgPath = await tempPathFactory();
      await sharp(data, { raw: { width, height, channels: channels as 3 | 4 } })
        .jpeg({ quality: 95 })
        .toFile(jpgPath);
      return jpgPath;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      // "Too big" is not transient — the file exceeds LibRaw's limits.
      if (/too ?big/i.test(message)) return null;
      if (attempt < maxRetries - 1) {
        await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
        continue;
      }
      return null;
    }
  }
  return null;
}

export function isRawPath(path: string): boolean {
  return RAW_EXTENSIONS.has(extname(path).toLowerCase());
}

export function isVideoPath(path: string): boolean {
  return VIDEO_EXTENSIONS.has(extname(path).toLowerCase());
}

/** Write a buffer to a path, for callers that already have encoded bytes. */
export async function writeTemp(path: string, data: Buffer): Promise<string> {
  await writeFile(path, data);
  return path;
}

/** `pathToFileURL` re-exported so the shim's users need not import `node:url`. */
export { pathToFileURL };
