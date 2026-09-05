/**
 * RAW decode through libraw-wasm.
 *
 * `halfSize: true` is enough for a 1024px vision preview and roughly four times
 * faster. The browser globals the Emscripten build needs are installed by
 * `browser-shims.ts`.
 */
import { readFile } from 'node:fs/promises';
import { installBrowserShims } from './browser-shims.js';

export interface DecodedRaw {
  data: Buffer;
  width: number;
  height: number;
  channels: number;
}

/** The slice of libraw-wasm's surface this module uses. */
interface LibRawHandle {
  open(bytes: Uint8Array, opts?: Record<string, unknown>): Promise<unknown>;
  imageData(): Promise<
    | {
        width: number;
        height: number;
        colors: number;
        bits: number;
        data: Uint8Array | Uint16Array;
      }
    | undefined
  >;
  dispose(): void;
}

/**
 * Decode a RAW file to RGB pixels.
 *
 * A fresh instance per call, and `dispose()` in a `finally`. Both halves matter:
 * each `LibRaw` spawns its own worker thread holding a WASM heap, so without the
 * dispose the process grows by roughly 200 MB per decode — measured at
 * 439 → 675 → 874 MB over three images, which on a 43,000-image run ends with
 * the OOM reaper rather than a finished batch.
 */
export async function decodeRaw(rawPath: string): Promise<DecodedRaw> {
  await installBrowserShims();
  const { default: LibRaw } = await import('libraw-wasm');

  const buf = await readFile(rawPath);
  const libraw = new LibRaw() as unknown as LibRawHandle;
  try {
    return await decodeWith(libraw, rawPath, buf);
  } finally {
    // Terminates the worker. Skipping it is the leak described above. A throw
    // from here would replace whatever the decode was failing with, and the
    // decode error is the one worth reading.
    try {
      libraw.dispose();
    } catch {
      // Nothing useful to do: the instance is being abandoned either way.
    }
  }
}

async function decodeWith(
  libraw: LibRawHandle,
  rawPath: string,
  buf: Buffer,
): Promise<DecodedRaw> {
  // `new Uint8Array(buf)` copies on purpose: libraw-wasm transfers the argument's
  // `.buffer` in `postMessage`, and a Node `Buffer` under 8 KB may share a pool.
  //
  // `useCameraWb` is load-bearing: without the camera's recorded white balance a
  // daylight frame renders strongly blue. `outputBps: 8` is explicit because
  // `imageData()` reports `bits` and 16-bit samples need different handling.
  await libraw.open(new Uint8Array(buf), {
    halfSize: true,
    useCameraWb: true,
    outputBps: 8,
  });
  const image = await libraw.imageData();
  if (!image) throw new Error(`libraw returned no image data for ${rawPath}`);

  const { width, height, colors, bits, data } = image;
  if (!width || !height) throw new Error(`libraw returned no dimensions for ${rawPath}`);
  if (bits !== 8) {
    throw new Error(`libraw returned ${bits}-bit samples for ${rawPath}; expected 8`);
  }
  if (colors !== 3 && colors !== 4) {
    throw new Error(`libraw returned ${colors} channels for ${rawPath}; expected 3 or 4`);
  }

  return {
    data: Buffer.from(data.buffer, data.byteOffset, data.byteLength),
    width,
    height,
    channels: colors,
  };
}
