/**
 * Serve a file from disk. Stands in for Flask's `send_file`.
 *
 * Flask's `send_file` defaults to `conditional=True`, so it answers
 * `If-Modified-Since` / `If-None-Match` with a 304 and supports byte ranges. The
 * thumbnail grid loads hundreds of images per page view, so dropping conditional
 * responses would turn every scroll back into a full re-download.
 *
 * Two deliberate differences from Werkzeug:
 *
 *   - the ETag value is `"<mtime-ms>-<size>"` rather than Werkzeug's
 *     `mtime-size-adler32(filename)`. It is still stable per file version, which is
 *     what the header is for; matching Werkzeug's exact bytes would only serve to
 *     keep caches warm *across* the backend switch, and invalidating them once at
 *     cutover is the safer outcome.
 *   - `Range` is not implemented. These are whole JPEGs rendered by `<img>`, which
 *     never asks for a range. A route that serves video would need it.
 */
import type { Context } from 'hono';
import { createReadStream, statSync } from 'node:fs';
import { Readable } from 'node:stream';

export interface SendFileOptions {
  mimetype?: string;
}

/**
 * Stream `path` to the client with caching headers, or a 304 when the client's
 * copy is current.
 *
 * The body is streamed rather than buffered: a full-size original is served as the
 * fallback when no cached thumbnail exists, and those run to tens of megabytes.
 */
export function sendFile(c: Context, path: string, opts: SendFileOptions = {}): Response {
  const stat = statSync(path);
  // HTTP dates have second resolution, so the mtime must be floored to the second
  // before comparing — otherwise a sub-second remainder makes every conditional
  // request look stale.
  const mtimeMs = Math.floor(stat.mtimeMs / 1000) * 1000;
  const etag = `"${stat.mtimeMs}-${stat.size}"`;
  const lastModified = new Date(mtimeMs).toUTCString();

  const headers: Record<string, string> = {
    'Content-Type': opts.mimetype ?? 'application/octet-stream',
    'Last-Modified': lastModified,
    ETag: etag,
  };

  const ifNoneMatch = c.req.header('if-none-match');
  const ifModifiedSince = c.req.header('if-modified-since');
  const notModified =
    // An ETag match wins outright; the date is only consulted when no ETag was sent,
    // matching RFC 9110's precedence.
    ifNoneMatch !== undefined
      ? ifNoneMatch.split(',').some((t) => t.trim() === etag || t.trim() === `W/${etag}`)
      : ifModifiedSince !== undefined && Date.parse(ifModifiedSince) >= mtimeMs;

  if (notModified) {
    return new Response(null, { status: 304, headers });
  }

  headers['Content-Length'] = String(stat.size);
  const body = Readable.toWeb(createReadStream(path)) as ReadableStream;
  return new Response(body, { status: 200, headers });
}
