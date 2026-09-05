/**
 * phash parity against values stored in `vision_cache`.
 *
 * phash is computed from the viewable image path, not the compressed cache file.
 * For RAW originals the viewable temp file is gone, so only JPEG originals with
 * reachable files on disk are comparable here.
 *
 * Skips unless the real library.db and referenced originals are reachable.
 */
import { describe, expect, it } from 'vitest';
import { existsSync } from 'node:fs';
import { extname } from 'node:path';
import { config } from '../src/config.js';
import { openLibraryDb } from '../src/db/connection.js';
import { decodeRgb } from '../src/imaging/clip-embed.js';
import { hammingDistance, phash } from '../src/imaging/phash.js';

const hasLibrary = existsSync(config.LIBRARY_DB);
const describeMaybe = hasLibrary ? describe : describe.skip;

interface Row {
  key: string;
  filepath: string;
  phash: string;
}

function loadJpegSamples(limit: number): Row[] {
  const db = openLibraryDb(config.LIBRARY_DB, { readonly: true });
  try {
    const rows = db
      .prepare(
        `select vc.key as key, i.filepath as filepath, vc.phash as phash
         from vision_cache vc join images i on i.key = vc.key
         where vc.phash is not null and i.filepath is not null`,
      )
      .all() as Row[];

    const out: Row[] = [];
    for (const r of rows) {
      // Only JPEG originals have a stable on-disk input for phash.
      const ext = extname(r.filepath).toLowerCase();
      if (ext !== '.jpg' && ext !== '.jpeg') continue;
      if (!existsSync(r.filepath)) continue;
      out.push(r);
      if (out.length >= limit) break;
    }
    return out;
  } finally {
    db.close();
  }
}

describeMaybe('phash reproduces stored vision_cache values', () => {
  it('matches exactly on JPEG originals', async () => {
    const samples = loadJpegSamples(12);
    if (samples.length === 0) {
      console.warn('no reachable JPEG originals with a stored phash; nothing compared');
      return;
    }

    const distances: number[] = [];
    for (const s of samples) {
      const got = phash(await decodeRgb(s.filepath));
      const d = hammingDistance(got, s.phash);
      distances.push(d);
      expect(got, `${s.key} (${s.filepath})`).toBe(s.phash);
    }

    const exact = distances.filter((d) => d === 0).length;
    console.log(
      `phash parity: ${exact}/${distances.length} exact, ` +
        `max hamming ${Math.max(...distances)} of 64 bits`,
    );
  }, 300_000);
});
