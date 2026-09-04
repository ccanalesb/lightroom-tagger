/**
 * RAW decode via libraw-wasm.
 *
 * libraw-wasm is an Emscripten browser build. Node needs shims for `Worker`, `self`
 * inside workers, and `fetch` for `file://` WASM loads.
 *
 * `half_size: true` matches half-resolution decode: enough for a 1024px vision
 * preview and roughly four times faster. Each decode must call `dispose()` or the
 * process retains ~200 MB per instance.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname } from 'node:path';
import { pathToFileURL } from 'node:url';
import sharp from 'sharp';

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

/**
 * Worker prelude: bridge the browser Worker surface onto `worker_threads`, then
 * import the real worker script.
 *
 * Bridges `self`, `postMessage`, inbound `MessageEvent` wrapping, and `file://`
 * fetch for WASM. Kept as a string constant so there is nothing to resolve at runtime.
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
 * Install browser shims libraw-wasm's Emscripten glue expects.
 *
 * Idempotent and non-destructive: an existing `globalThis.Worker` or `fetch` is
 * left alone.
 */
async function installBrowserShims(): Promise<void> {
  if (shimsInstalled) return;
  shimsInstalled = true;

  const { Worker: NodeWorker } = await import('node:worker_threads');

  if (typeof (globalThis as { Worker?: unknown }).Worker === 'undefined') {
    /**
     * A `Worker` adapter over `worker_threads`.
     *
     * Node passes message values directly; the browser wraps them in `MessageEvent`.
     */
    class WorkerShim {
      private readonly worker: InstanceType<typeof NodeWorker>;
      onmessage: ((event: { data: unknown }) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;

      constructor(scriptUrl: string | URL) {
        const url = typeof scriptUrl === 'string' ? scriptUrl : scriptUrl.href;
        // Both shims must run inside the worker before the real script loads.
        // Emscripten fetches `libraw.wasm` via `file://` from the worker isolate.
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

/**
 * Convert a RAW file to a temporary JPEG. Returns `null` when it cannot.
 *
 * Three attempts cover intermittent NAS read failures. Quality 95.
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
