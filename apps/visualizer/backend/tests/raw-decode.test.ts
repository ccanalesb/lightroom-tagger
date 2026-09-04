/**
 * The libraw adapter's two testable halves: the `file://` fetch shim, and the
 * retry policy `convertRawToJpg` wraps a decode in.
 *
 * The decode itself needs a real RAW and the WASM build, so it is not exercised
 * here — which is exactly why the code around it is worth pinning. A regression
 * in either half looks like "RAW previews stopped working" with no other signal.
 */
import { describe, expect, it, vi } from 'vitest';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import sharp from 'sharp';
import { fileUrlFetch, requestUrl } from '../src/imaging/libraw/browser-shims.js';
import {
  convertRawToJpg,
  isRawPath,
  isVideoPath,
  type RawDecoder,
} from '../src/imaging/raw-decode.js';

async function tempDir(): Promise<string> {
  return mkdtemp(join(tmpdir(), 'lt-rawtest-'));
}

/** A decoder returning a 2x2 RGB image, which sharp can encode. */
const okDecoder: RawDecoder = async () => ({
  data: Buffer.from([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255]),
  width: 2,
  height: 2,
  channels: 3,
});

describe('requestUrl', () => {
  it('reads the three shapes fetch accepts', () => {
    expect(requestUrl('file:///a.wasm')).toBe('file:///a.wasm');
    expect(requestUrl(new URL('file:///b.wasm'))).toBe('file:///b.wasm');
    expect(requestUrl({ url: 'https://example.test/c' })).toBe('https://example.test/c');
    expect(requestUrl(null)).toBe('');
  });
});

describe('fileUrlFetch', () => {
  it('serves file:// from disk, which Node fetch refuses to do', async () => {
    const dir = await tempDir();
    const path = join(dir, 'libraw.wasm');
    await writeFile(path, Buffer.from([0, 97, 115, 109]));

    const original = vi.fn();
    const patched = fileUrlFetch(original as unknown as typeof globalThis.fetch);
    const res = await patched(pathToFileURL(path).href);

    expect(res.status).toBe(200);
    expect(Buffer.from(await res.arrayBuffer())).toEqual(Buffer.from([0, 97, 115, 109]));
    expect(original).not.toHaveBeenCalled();
  });

  it('delegates every other scheme to the fetch it replaced', async () => {
    const sentinel = new Response('ok');
    const original = vi.fn(async () => sentinel);
    const patched = fileUrlFetch(original as unknown as typeof globalThis.fetch);

    const res = await patched('https://example.test/models');

    expect(res).toBe(sentinel);
    expect(original).toHaveBeenCalledOnce();
  });
});

describe('convertRawToJpg', () => {
  it('encodes the decoded pixels to the path the factory hands it', async () => {
    const dir = await tempDir();
    const out = join(dir, 'out.jpg');
    const src = join(dir, 'in.arw');
    await writeFile(src, 'not really a raw');

    expect(await convertRawToJpg(src, async () => out, okDecoder)).toBe(out);
    expect((await sharp(await readFile(out)).metadata()).width).toBe(2);
  });

  it('returns null without decoding when the source is not there', async () => {
    const decode = vi.fn(okDecoder);
    const result = await convertRawToJpg('/nonexistent/x.arw', async () => '/tmp/o.jpg', decode);

    expect(result).toBeNull();
    expect(decode).not.toHaveBeenCalled();
  });

  it('retries a transient failure and succeeds', async () => {
    const dir = await tempDir();
    const src = join(dir, 'in.arw');
    await writeFile(src, 'x');

    let calls = 0;
    const flaky: RawDecoder = async (p) => {
      calls += 1;
      if (calls === 1) throw new Error('input/output error');
      return okDecoder(p);
    };

    const out = await convertRawToJpg(src, async () => join(dir, 'o.jpg'), flaky);
    expect(out).not.toBeNull();
    expect(calls).toBe(2);
  });

  it('gives up immediately on "too big", which is not transient', async () => {
    const dir = await tempDir();
    const src = join(dir, 'in.arw');
    await writeFile(src, 'x');

    let calls = 0;
    const tooBig: RawDecoder = async () => {
      calls += 1;
      throw new Error('Too big');
    };

    const out = await convertRawToJpg(src, async () => join(dir, 'o.jpg'), tooBig);
    expect(out).toBeNull();
    expect(calls).toBe(1);
  });

  it('returns null after exhausting retries', async () => {
    const dir = await tempDir();
    const src = join(dir, 'in.arw');
    await writeFile(src, 'x');

    let calls = 0;
    const broken: RawDecoder = async () => {
      calls += 1;
      throw new Error('read failed');
    };

    const out = await convertRawToJpg(src, async () => join(dir, 'o.jpg'), broken);
    expect(out).toBeNull();
    expect(calls).toBe(3);
  });
});

describe('extension predicates', () => {
  it('classifies by extension, case-insensitively', () => {
    expect(isRawPath('/a/b.ARW')).toBe(true);
    expect(isRawPath('/a/b.jpg')).toBe(false);
    expect(isVideoPath('/a/b.MOV')).toBe(true);
    expect(isVideoPath('/a/b.dng')).toBe(false);
  });
});
