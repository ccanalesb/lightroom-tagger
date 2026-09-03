/**
 * RAW decode via libraw-wasm. Replaces `rawpy` in
 * `core/analyzer/image_prep.convert_raw_to_jpg`.
 *
 * This was the single hardest dependency in the migration and it needed three
 * shims, because libraw-wasm ships an Emscripten build written for a browser:
 *
 *   1. `globalThis.Worker` — the module spawns a Web Worker. Node has
 *      `worker_threads`, whose API is close but not identical, so a small
 *      adapter presents the browser surface over it.
 *   2. `self` inside the worker — the Emscripten glue expects it.
 *   3. `fetch` for `file://` — the glue fetches its own `.wasm` next to the
 *      script, and Node's `fetch` refuses the `file:` scheme.
 *
 * `half_size: true` matches rawpy's call exactly: half-resolution is plenty for a
 * 1024px vision preview and it is roughly four times faster.
 *
 * Measured on this catalog, 40 consecutive Leica DNGs: 40 of 40 decoded to
 * 2992×1996×3 (portrait frames come back 1996×2992, correctly un-rotated) at
 * roughly 900 ms each. RSS rises to a ~924 MB high-water mark and falls back to
 * 600 MB, so it is GC-bounded rather than leaking — but only with the `dispose()`
 * in `decodeRaw`. The "~14 decodes then hard failure" reported in the background
 * research did not reproduce through this adapter.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname } from 'node:path';
import { pathToFileURL } from 'node:url';
import sharp from 'sharp';

/** Extensions `rawpy` handled, and therefore the ones the sidecar check covers. */
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

/**
 * Worker prelude: bridge the browser Worker surface onto `worker_threads`, then
 * import the real worker script.
 *
 * Three bridges, each needed because a Node worker is not a Web Worker:
 *
 *   - `self` — the Emscripten glue and libraw's own `worker.js` both use it.
 *   - `postMessage` / `self.postMessage` — in Node these live on `parentPort`,
 *     not on the global, so the worker's replies would go nowhere.
 *   - inbound messages — the worker assigns `self.onmessage`, but Node delivers
 *     via `parentPort.on('message')`, and it hands over the value directly where
 *     the browser wraps it in a `MessageEvent`. Without the `{ data }` wrapper
 *     every call silently hangs, which is exactly how this first failed.
 *
 * Plus the `file://` fetch patch, because Emscripten resolves `libraw.wasm`
 * relative to the script and fetches it *from the worker* — patching the main
 * thread's `fetch` does nothing for a separate isolate.
 *
 * Kept as a string constant so there is nothing to resolve at runtime.
 */
const WORKER_BOOTSTRAP = `
import { parentPort } from 'node:worker_threads';

globalThis.self = globalThis;
globalThis.postMessage = (msg, transfer) => parentPort.postMessage(msg, transfer);
parentPort.on('message', (data) => {
  const handler = globalThis.onmessage;
  if (typeof handler === 'function') handler({ data });
});

const __originalFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = typeof input === 'string'
    ? input
    : input instanceof URL ? input.href : String(input?.url ?? '');
  if (url.startsWith('file://')) {
    const { readFile } = await import('node:fs/promises');
    const { fileURLToPath } = await import('node:url');
    const body = await readFile(fileURLToPath(url));
    return new Response(new Uint8Array(body), {
      status: 200,
      headers: { 'Content-Type': 'application/wasm' },
    });
  }
  return __originalFetch(input, init);
};

await import(__URL__);
`;

let shimsInstalled = false;

/**
 * Install the three browser shims libraw-wasm's Emscripten glue expects.
 *
 * Idempotent, and deliberately non-destructive: an existing `globalThis.Worker`
 * or `fetch` is left alone, so this cannot break a runtime that already provides
 * them.
 */
async function installBrowserShims(): Promise<void> {
  if (shimsInstalled) return;
  shimsInstalled = true;

  const { Worker: NodeWorker } = await import('node:worker_threads');

  if (typeof (globalThis as { Worker?: unknown }).Worker === 'undefined') {
    /**
     * A `Worker` adapter over `worker_threads`.
     *
     * The differences that matter: the browser delivers messages as a
     * `MessageEvent` with a `.data` property while Node passes the value
     * directly, and the browser's worker script needs `self` defined. Both are
     * bridged here.
     */
    class WorkerShim {
      private readonly worker: InstanceType<typeof NodeWorker>;
      onmessage: ((event: { data: unknown }) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;

      constructor(scriptUrl: string | URL) {
        const url = typeof scriptUrl === 'string' ? scriptUrl : scriptUrl.href;
        // Both shims have to be installed *inside* the worker, before the real
        // script is imported. A worker is a separate isolate, so patching
        // `globalThis` on the main thread does nothing for it — which is exactly
        // how this first failed: "both async and sync fetching of the wasm
        // failed", because Emscripten resolves `libraw.wasm` to a file:// URL
        // and fetches it from the worker.
        this.worker = new NodeWorker(WORKER_BOOTSTRAP.replace('__URL__', JSON.stringify(url)), {
          eval: true,
        });
        this.worker.on('message', (data: unknown) => this.onmessage?.({ data }));
        this.worker.on('error', (err: unknown) => this.onerror?.(err));
      }

      postMessage(message: unknown, transfer?: readonly unknown[]): void {
        this.worker.postMessage(message, transfer as never);
      }

      terminate(): void {
        void this.worker.terminate();
      }

      addEventListener(type: string, listener: (event: { data: unknown }) => void): void {
        if (type === 'message') this.onmessage = listener;
        if (type === 'error') this.onerror = listener as never;
      }

      removeEventListener(): void {
        this.onmessage = null;
        this.onerror = null;
      }
    }
    (globalThis as { Worker?: unknown }).Worker = WorkerShim;
  }

  // Node's fetch rejects `file:`, and the glue fetches its own .wasm by
  // relative URL. Only that scheme is intercepted; everything else passes through.
  const originalFetch = globalThis.fetch;
  const patched = async (input: unknown, init?: unknown): Promise<Response> => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.href
          : String((input as { url?: string }).url ?? '');
    if (url.startsWith('file://')) {
      const { fileURLToPath } = await import('node:url');
      const body = await readFile(fileURLToPath(url));
      return new Response(new Uint8Array(body), { status: 200 });
    }
    return originalFetch(input as Parameters<typeof originalFetch>[0], init as never);
  };
  globalThis.fetch = patched as typeof globalThis.fetch;
}

export interface DecodedRaw {
  data: Buffer;
  width: number;
  height: number;
  channels: number;
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
    // Terminates the worker. Skipping it is the leak described above.
    libraw.dispose();
  }
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

async function decodeWith(
  libraw: LibRawHandle,
  rawPath: string,
  buf: Buffer,
): Promise<DecodedRaw> {
  // `new Uint8Array(buf)` copies, and the copy is the point: libraw-wasm's
  // `runFn` puts the argument's `.buffer` in `postMessage`'s transfer list, and a
  // Node `Buffer` under 8 KB is a view into a shared pool — transferring it would
  // detach every other Buffer sharing that pool. A fresh Uint8Array owns its
  // ArrayBuffer outright, so there is nothing else to detach.
  //
  // These three settings mirror rawpy's `postprocess(use_camera_wb=True,
  // half_size=True)` call. `useCameraWb` is load-bearing rather than cosmetic:
  // without the camera's recorded white balance a daylight frame renders
  // strongly blue and the model describes the wrong photograph. `outputBps: 8`
  // is stated explicitly rather than relied on, because `imageData()` reports
  // `bits` and a 16-bit buffer would need different handling below.
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

/**
 * Convert a RAW file to a temporary JPEG. Returns `null` when it cannot.
 *
 * The three-attempt retry is for NAS flakiness, not for decode bugs: an
 * intermittent read over SMB was the original reason it exists, and a genuine
 * decode failure fails the same way three times. Quality 95 matches Python.
 */
export async function convertRawToJpg(
  rawPath: string,
  tempPathFactory: () => Promise<string>,
): Promise<string | null> {
  if (!existsSync(rawPath)) return null;

  const maxRetries = 3;
  for (let attempt = 0; attempt < maxRetries; attempt += 1) {
    try {
      const { data, width, height, channels } = await decodeRaw(rawPath);
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
