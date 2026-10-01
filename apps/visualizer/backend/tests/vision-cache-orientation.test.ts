/**
 * The vision cache turns each JPEG to the photo's Lightroom orientation, and a
 * JPEG turned any other way is not handed to a vision op.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { stringify as stringifyYaml } from 'yaml';
import { LibraryFixture } from './helpers/library-fixture.js';
import { openLibraryDb, type Db } from '../src/db/connection.js';
import { tryVisionCache } from '../src/jobs/handlers/path-diagnostics.js';
import {
  getOrCreateCachedImage,
  isVisionCacheValid,
  resolveVisionImage,
} from '../src/vision/vision-cache.js';

let fx: LibraryFixture;
let dir: string;
let original: string;
let db: Db;

/** 300×200: white top half, black bottom half. */
async function writeOriginal(path: string): Promise<void> {
  const white = await sharp({
    create: { width: 300, height: 100, channels: 3, background: '#ffffff' },
  })
    .png()
    .toBuffer();
  await sharp({ create: { width: 300, height: 200, channels: 3, background: '#000000' } })
    .composite([{ input: white, top: 0, left: 0 }])
    .jpeg({ quality: 95 })
    .toFile(path);
}

async function luminanceAt(path: string, x: number, y: number): Promise<number> {
  const { data, info } = await sharp(path).greyscale().raw().toBuffer({ resolveWithObject: true });
  return data[y * info.width + x]!;
}

beforeEach(async () => {
  fx = new LibraryFixture().activate();
  dir = mkdtempSync(join(tmpdir(), 'lt-vc-orient-'));
  const cfgPath = join(dir, 'config.yaml');
  writeFileSync(cfgPath, stringifyYaml({ vision_cache_dir: join(dir, 'cache') }));
  process.env.LT_CONFIG_YAML = cfgPath;
  original = join(dir, 'photo.jpg');
  await writeOriginal(original);
  fx.addImage({ key: 'k', filepath: original, width: 300, height: 200 });
  db = openLibraryDb(fx.dbPath);
});

afterEach(() => {
  db.close();
  fx.cleanup();
  delete process.env.LT_CONFIG_YAML;
  rmSync(dir, { recursive: true, force: true });
});

describe('vision cache orientation', () => {
  it('turns the JPEG the way Lightroom shows the photo, and records it', async () => {
    db.prepare("UPDATE images SET orientation = 'BC'").run();

    const cached = (await getOrCreateCachedImage(db, 'k', original))!;

    const meta = await sharp(cached).metadata();
    expect([meta.width, meta.height]).toEqual([200, 300]);
    // Turned clockwise, the black bottom half ends up on the left.
    expect(await luminanceAt(cached, 20, 150)).toBeLessThan(50);
    expect(await luminanceAt(cached, 180, 150)).toBeGreaterThan(200);
    expect(db.prepare('SELECT orientation FROM vision_cache').get()).toEqual({ orientation: 'BC' });
    expect(await isVisionCacheValid(db, 'k', original)).toBe(true);
  });

  it('treats a JPEG turned another way as unusable until rebuilt', async () => {
    const cached = (await getOrCreateCachedImage(db, 'k', original))!;
    expect(tryVisionCache(db, 'k')).toBe(cached);

    db.prepare("UPDATE images SET orientation = 'DA'").run();

    expect(await isVisionCacheValid(db, 'k', original)).toBe(false);
    expect(tryVisionCache(db, 'k')).toBeNull();
    // With the original unreachable it is not handed out sideways.
    rmSync(original);
    expect(await resolveVisionImage(db, 'k', original)).toEqual({
      path: null,
      silentCompression: false,
    });
  });
});
