/**
 * The browser globals libraw-wasm's Emscripten glue expects, implemented for Node.
 *
 * libraw-wasm ships a browser build: it constructs `new Worker(url, {type:'module'})`
 * and its runtime fetches `libraw.wasm` over a `file://` URL. Neither exists in
 * Node, so three shims stand in — a `Worker` over `node:worker_threads`, a `self`
 * bridge inside the worker isolate, and a `fetch` that can read `file://`.
 *
 * This is our code to own, and it must be re-verified on every libraw-wasm upgrade.
 * It is kept in its own module so the decode path stays readable and so the shims
 * can be exercised on their own.
 *
 * ## What this does to the process
 *
 * `globalThis.Worker` is only defined when absent. `globalThis.fetch` is **always**
 * replaced, because it has to intercept `file://` — but the replacement closes over
 * the previous implementation and delegates every other scheme to it unchanged.
 * Installation happens once per process and is idempotent.
 */
import { readFile } from 'node:fs/promises';

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

/** The URL of whatever is being fetched, across the three input shapes. */
export function requestUrl(input: unknown): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  return String((input as { url?: string } | null)?.url ?? '');
}

/**
 * A `fetch` that serves `file://` from disk and delegates everything else.
 *
 * Exported so the delegation can be tested without touching the real global.
 */
export function fileUrlFetch(originalFetch: typeof globalThis.fetch): typeof globalThis.fetch {
  const patched = async (input: unknown, init?: unknown): Promise<Response> => {
    const url = requestUrl(input);
    if (url.startsWith('file://')) {
      const { fileURLToPath } = await import('node:url');
      const body = await readFile(fileURLToPath(url));
      return new Response(new Uint8Array(body), { status: 200 });
    }
    return originalFetch(input as Parameters<typeof originalFetch>[0], init as never);
  };
  return patched as typeof globalThis.fetch;
}

/**
 * A `Worker` adapter over `worker_threads`.
 *
 * Node passes message values directly; the browser wraps them in `MessageEvent`.
 */
export function makeWorkerShim(
  NodeWorker: typeof import('node:worker_threads').Worker,
): new (scriptUrl: string | URL) => unknown {
  return class WorkerShim {
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
  };
}

let installed = false;

/** Install the shims once. See the module header for what it mutates. */
export async function installBrowserShims(): Promise<void> {
  if (installed) return;
  installed = true;

  const { Worker: NodeWorker } = await import('node:worker_threads');
  if (typeof (globalThis as { Worker?: unknown }).Worker === 'undefined') {
    (globalThis as { Worker?: unknown }).Worker = makeWorkerShim(NodeWorker);
  }

  globalThis.fetch = fileUrlFetch(globalThis.fetch);
}
